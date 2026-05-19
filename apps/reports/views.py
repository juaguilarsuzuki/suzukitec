import json
from datetime import date
from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import MonthlyReport
from apps.clients.models import Client


@login_required
def report_generator(request):
    """Tela principal: seleciona cliente + período e gera/visualiza o relatório."""
    clients = Client.objects.filter(is_active=True).order_by("name")

    # Mês/ano padrão = mês anterior
    today = date.today()
    default_year = today.year if today.month > 1 else today.year - 1
    default_month = today.month - 1 if today.month > 1 else 12

    years = list(range(today.year - 2, today.year + 1))
    months = [
        (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
        (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
        (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
    ]

    recent_reports = (
        MonthlyReport.objects.select_related("client")
        .order_by("-reference_month", "-created_at")[:15]
    )

    return render(request, "dashboard/report_generator.html", {
        "clients": clients,
        "years": years,
        "months": months,
        "default_year": default_year,
        "default_month": default_month,
        "recent_reports": recent_reports,
    })


@login_required
@require_POST
def generate_report(request):
    """Gera o relatório para o cliente + mês selecionado e redireciona para preview."""
    client_id = request.POST.get("client_id")
    year = int(request.POST.get("year", 0))
    month = int(request.POST.get("month", 0))

    if not client_id or not year or not month:
        messages.error(request, "Selecione o cliente, o ano e o mês.")
        return redirect("report_generator")

    client = get_object_or_404(Client, pk=client_id)
    reference_month = date(year, month, 1)

    report, _ = MonthlyReport.objects.get_or_create(
        client=client, reference_month=reference_month
    )

    # Coleta dados e gera PDF de forma síncrona para permitir preview imediato
    from apps.integrations.collector import collect_client_data
    from apps.reports.generator import generate_pdf
    from pathlib import Path
    from django.conf import settings as django_settings

    report.status = MonthlyReport.Status.GENERATING
    report.error_message = ""
    report.save(update_fields=["status", "error_message"])

    try:
        last_day = monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

        data = collect_client_data(client, start, end)
        report.data_snapshot = data
        report.save(update_fields=["data_snapshot"])

        pdf_path = generate_pdf(report)
        relative = Path(pdf_path).relative_to(django_settings.MEDIA_ROOT)
        report.pdf_file.name = str(relative)
        report.status = MonthlyReport.Status.DONE
        report.save(update_fields=["pdf_file", "status"])

        messages.success(request, f"Relatório gerado com sucesso para {report.month_label}.")
    except Exception as exc:
        report.status = MonthlyReport.Status.ERROR
        report.error_message = str(exc)
        report.save(update_fields=["status", "error_message"])
        messages.error(request, f"Erro ao gerar relatório: {exc}")

    return redirect("report_detail", report_id=report.pk)


@login_required
def report_detail(request, report_id):
    report = get_object_or_404(MonthlyReport.objects.select_related("client"), pk=report_id)
    data = report.data_snapshot
    digisac = data.get("digisac") or {}
    milvus = data.get("milvus") or {}
    prtg = data.get("prtg") or {}

    from apps.reports.generator import _score_label, _star_range
    avg_score = (digisac.get("ratings") or {}).get("average_score", 0)
    satisfaction_label, satisfaction_color = _score_label(avg_score)

    return render(request, "dashboard/report_detail.html", {
        "report": report,
        "digisac": digisac,
        "milvus": milvus,
        "prtg": prtg,
        "avg_score": avg_score,
        "satisfaction_label": satisfaction_label,
        "satisfaction_color": satisfaction_color,
        "stars": _star_range(avg_score),
        "digisac_json": json.dumps(digisac),
        "milvus_json": json.dumps(milvus),
        "prtg_json": json.dumps(prtg),
    })


@login_required
def download_pdf(request, report_id):
    report = get_object_or_404(MonthlyReport, pk=report_id)
    if not report.pdf_file:
        raise Http404("PDF não disponível.")
    return FileResponse(
        report.pdf_file.open("rb"), content_type="application/pdf",
        as_attachment=True,
        filename=f"Relatorio_{report.client.name.replace(' ','_')}_{report.month_label.replace('/','_')}.pdf"
    )


@login_required
@require_POST
def send_report_email(request, report_id):
    """Envia o relatório por e-mail para o cliente."""
    from apps.reports.tasks import send_client_report
    report = get_object_or_404(MonthlyReport, pk=report_id)
    if report.status not in (MonthlyReport.Status.DONE, MonthlyReport.Status.SENT):
        messages.error(request, "O relatório precisa estar gerado antes de ser enviado.")
        return redirect("report_detail", report_id=report_id)
    send_client_report.apply_async(args=[report.pk])
    messages.success(request, f"E-mail enfileirado para envio a {report.client.email}.")
    return redirect("report_detail", report_id=report_id)


@login_required
@require_POST
def trigger_report(request, report_id):
    """Regenera um relatório existente."""
    report = get_object_or_404(MonthlyReport, pk=report_id)
    from apps.reports.tasks import generate_client_report, send_client_report
    generate_client_report.apply_async(
        args=[report.client.pk, report.reference_month.year, report.reference_month.month],
        link=send_client_report.s(),
    )
    return JsonResponse({"status": "enqueued"})
