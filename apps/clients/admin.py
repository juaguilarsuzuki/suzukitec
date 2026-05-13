from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientToolConfig, SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Empresa", {
            "fields": ("company_name", "company_logo_url"),
        }),
        ("E-mail (SMTP)", {
            "fields": (
                "email_host", "email_port", "email_use_tls",
                "email_host_user", "email_host_password", "default_from_email",
            ),
            "description": (
                "Configure o servidor de e-mail para envio dos relatórios. "
                "Para Gmail, gere uma <strong>Senha de App</strong> em "
                "Conta Google → Segurança → Senhas de app."
            ),
        }),
        ("Digisac", {
            "fields": ("digisac_base_url", "digisac_token"),
        }),
        ("Milvus", {
            "fields": ("milvus_base_url", "milvus_token"),
        }),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redireciona direto para a tela de edição do registro único
        from django.shortcuts import redirect
        obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return redirect(f"/admin/clients/systemsettings/{obj.pk}/change/")


class ClientToolConfigInline(admin.TabularInline):
    model = ClientToolConfig
    extra = 1
    fields = ("tool", "label", "external_id", "extra_config", "is_active")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company_name", "email", "is_active", "send_report", "report_count")
    list_filter = ("is_active", "send_report")
    search_fields = ("name", "company_name", "cnpj", "email")
    inlines = [ClientToolConfigInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identificação", {
            "fields": ("name", "company_name", "cnpj")
        }),
        ("Contato", {
            "fields": ("email", "email_cc", "phone")
        }),
        ("Configurações", {
            "fields": ("is_active", "send_report", "notes")
        }),
        ("Auditoria", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    actions = ["trigger_report_generation"]

    @admin.display(description="Relatórios")
    def report_count(self, obj):
        count = obj.reports.count()
        return format_html(
            '<a href="/admin/reports/monthlyreport/?client__id__exact={}">{} relatório(s)</a>',
            obj.pk, count
        )

    @admin.action(description="Gerar relatório do mês anterior")
    def trigger_report_generation(self, request, queryset):
        from datetime import date
        from dateutil.relativedelta import relativedelta
        from apps.reports.tasks import generate_client_report, send_client_report

        prev = date.today() - relativedelta(months=1)
        count = 0
        for client in queryset.filter(is_active=True):
            generate_client_report.apply_async(
                args=[client.pk, prev.year, prev.month],
                link=send_client_report.s(),
            )
            count += 1
        self.message_user(request, f"{count} relatório(s) enfileirado(s) para geração.")


@admin.register(ClientToolConfig)
class ClientToolConfigAdmin(admin.ModelAdmin):
    list_display = ("client", "tool", "label", "external_id", "is_active")
    list_filter = ("tool", "is_active")
    search_fields = ("client__name", "external_id", "label")
