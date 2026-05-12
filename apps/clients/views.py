from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import Client
from apps.reports.models import MonthlyReport


@login_required
def dashboard(request):
    clients = Client.objects.filter(is_active=True).prefetch_related("reports")
    recent_reports = (
        MonthlyReport.objects.select_related("client")
        .order_by("-reference_month", "client__name")[:20]
    )
    stats = {
        "total_clients": clients.count(),
        "reports_sent": MonthlyReport.objects.filter(status=MonthlyReport.Status.SENT).count(),
        "reports_error": MonthlyReport.objects.filter(status=MonthlyReport.Status.ERROR).count(),
        "reports_pending": MonthlyReport.objects.filter(
            status__in=[MonthlyReport.Status.PENDING, MonthlyReport.Status.GENERATING]
        ).count(),
    }
    return render(request, "dashboard/index.html", {
        "clients": clients,
        "recent_reports": recent_reports,
        "stats": stats,
    })


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    reports = client.reports.order_by("-reference_month")
    return render(request, "dashboard/client_detail.html", {
        "client": client,
        "reports": reports,
    })
