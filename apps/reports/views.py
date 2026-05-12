import json
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import MonthlyReport


@login_required
def report_detail(request, report_id):
    report = get_object_or_404(MonthlyReport.objects.select_related("client"), pk=report_id)
    data = report.data_snapshot
    digisac = data.get("digisac") or {}
    milvus = data.get("milvus") or {}
    prtg = data.get("prtg") or {}

    return render(request, "dashboard/report_detail.html", {
        "report": report,
        "digisac": digisac,
        "milvus": milvus,
        "prtg": prtg,
        "digisac_json": json.dumps(digisac),
        "milvus_json": json.dumps(milvus),
        "prtg_json": json.dumps(prtg),
    })


@login_required
def download_pdf(request, report_id):
    report = get_object_or_404(MonthlyReport, pk=report_id)
    if not report.pdf_file:
        raise Http404("PDF não disponível.")
    return FileResponse(report.pdf_file.open("rb"), content_type="application/pdf",
                        as_attachment=True, filename=f"Relatorio_{report.client.name}_{report.month_label}.pdf")


@login_required
@require_POST
def trigger_report(request, report_id):
    """Manually trigger report (re)generation via AJAX."""
    from apps.reports.tasks import generate_client_report, send_client_report
    report = get_object_or_404(MonthlyReport, pk=report_id)
    generate_client_report.apply_async(
        args=[report.client.pk, report.reference_month.year, report.reference_month.month],
        link=send_client_report.s(),
    )
    return JsonResponse({"status": "enqueued"})
