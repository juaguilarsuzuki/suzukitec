from django.contrib import admin
from django.utils.html import format_html
from .models import MonthlyReport


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ("client", "month_label", "status_badge", "sent_at", "pdf_link", "created_at")
    list_filter = ("status", "reference_month", "client")
    search_fields = ("client__name",)
    readonly_fields = ("created_at", "updated_at", "sent_at", "data_snapshot", "pdf_file")
    actions = ["regenerate_report", "resend_report"]

    fieldsets = (
        (None, {
            "fields": ("client", "reference_month", "status", "error_message")
        }),
        ("Arquivo", {
            "fields": ("pdf_file", "sent_at")
        }),
        ("Dados coletados", {
            "fields": ("data_snapshot",),
            "classes": ("collapse",),
        }),
        ("Auditoria", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "pending": "#6b7280",
            "generating": "#1d4ed8",
            "done": "#16a34a",
            "sent": "#059669",
            "error": "#dc2626",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.display(description="PDF")
    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">📄 Download</a>', obj.pdf_file.url)
        return "—"

    @admin.action(description="Regenerar relatório selecionado")
    def regenerate_report(self, request, queryset):
        from apps.reports.tasks import generate_client_report, send_client_report
        count = 0
        for report in queryset:
            generate_client_report.apply_async(
                args=[report.client.pk, report.reference_month.year, report.reference_month.month],
                link=send_client_report.s(),
            )
            count += 1
        self.message_user(request, f"{count} relatório(s) enfileirado(s) para regeneração.")

    @admin.action(description="Reenviar relatório por e-mail")
    def resend_report(self, request, queryset):
        from apps.reports.tasks import send_client_report
        count = 0
        for report in queryset.filter(status__in=["done", "sent"]):
            send_client_report.apply_async(args=[report.pk])
            count += 1
        self.message_user(request, f"{count} e-mail(s) enfileirado(s) para reenvio.")
