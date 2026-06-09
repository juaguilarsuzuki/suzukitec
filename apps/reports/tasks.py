"""Celery tasks for report generation and email delivery."""
import logging
from datetime import date
from pathlib import Path

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_client_report(self, client_id: int, year: int, month: int) -> dict:
    """
    Collects data from all configured tools and generates the PDF report
    for one client. Returns a summary dict.
    """
    from apps.clients.models import Client
    from apps.reports.models import MonthlyReport
    from apps.integrations.collector import collect_client_data
    from apps.reports.generator import generate_pdf

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        logger.error("Client %s not found", client_id)
        return {"status": "error", "reason": "client_not_found"}

    reference_month = date(year, month, 1)
    report, _ = MonthlyReport.objects.get_or_create(
        client=client, reference_month=reference_month
    )

    report.status = MonthlyReport.Status.GENERATING
    report.error_message = ""
    report.save(update_fields=["status", "error_message"])

    try:
        # Date range: full month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

        data = collect_client_data(client, start, end)
        report.data_snapshot = data
        report.save(update_fields=["data_snapshot"])

        pdf_path = generate_pdf(report)

        # Store relative path in FileField
        from django.conf import settings
        relative = Path(pdf_path).relative_to(settings.MEDIA_ROOT)
        report.pdf_file.name = str(relative)
        report.status = MonthlyReport.Status.DONE
        report.save(update_fields=["pdf_file", "status"])

        logger.info("Report generated for %s %s/%s", client, month, year)
        return {"status": "done", "report_id": report.pk}

    except Exception as exc:
        logger.exception("Error generating report for client %s: %s", client, exc)
        report.status = MonthlyReport.Status.ERROR
        report.error_message = str(exc)
        report.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_client_report(self, report_id: int) -> dict:
    """Sends the generated PDF report by email to the client."""
    from apps.reports.models import MonthlyReport
    from apps.notifications.email import send_report_email

    try:
        report = MonthlyReport.objects.select_related("client").get(pk=report_id)
    except MonthlyReport.DoesNotExist:
        return {"status": "error", "reason": "report_not_found"}

    if report.status != MonthlyReport.Status.DONE:
        return {"status": "skipped", "reason": f"report status is {report.status}"}

    if not report.client.send_report:
        return {"status": "skipped", "reason": "client opted out of reports"}

    try:
        send_report_email(report)
        report.status = MonthlyReport.Status.SENT
        report.sent_at = timezone.now()
        report.save(update_fields=["status", "sent_at"])
        return {"status": "sent", "report_id": report_id}
    except Exception as exc:
        logger.exception("Error sending report %s: %s", report_id, exc)
        report.error_message = str(exc)
        report.save(update_fields=["error_message"])
        raise self.retry(exc=exc)


@shared_task
def generate_all_monthly_reports() -> dict:
    """
    Triggered by Celery Beat on the 1st of every month.
    Generates PDFs for the PREVIOUS month. Sending is manual only.
    """
    from apps.clients.models import Client
    from dateutil.relativedelta import relativedelta

    today = date.today()
    prev = today - relativedelta(months=1)
    year, month = prev.year, prev.month

    clients = Client.objects.filter(is_active=True)
    dispatched = []

    for client in clients:
        task = generate_client_report.apply_async(args=[client.pk, year, month])
        dispatched.append({"client_id": client.pk, "task_id": str(task.id)})
        logger.info("Dispatched report generation for %s (%s/%s)", client, month, year)

    return {"dispatched": len(dispatched), "details": dispatched}
