from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from .models import (
    Client, ClientDigisacConfig, ClientMilvusConfig,
    ClientPRTGConfig, MilvusContact, SystemSettings,
)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    change_form_template = "admin/clients/systemsettings/change_form.html"
    fieldsets = (
        ("Empresa", {"fields": ("company_name", "company_logo_url")}),
        ("E-mail (SMTP)", {
            "fields": ("email_host", "email_port", "email_use_tls",
                       "email_host_user", "email_host_password", "default_from_email"),
            "description": (
                "Para Gmail, gere uma <strong>Senha de App</strong> em "
                "Conta Google → Segurança → Senhas de app."
            ),
        }),
        ("Digisac", {
            "fields": ("digisac_base_url", "digisac_token"),
            "description": "Token de autenticação da API Digisac.",
        }),
        ("Milvus", {
            "fields": ("milvus_base_url", "milvus_token"),
            "description": "Token de autenticação da API Milvus.",
        }),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return redirect(f"/admin/clients/systemsettings/{obj.pk}/change/")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("test-digisac/", self.admin_site.admin_view(self._test_digisac), name="test_digisac"),
            path("test-milvus/", self.admin_site.admin_view(self._test_milvus), name="test_milvus"),
        ]
        return custom + urls

    def _test_digisac(self, request):
        try:
            from apps.integrations.digisac import DigisacClient
            api = DigisacClient()
            resp = api._get("/departments", headers=api._headers)
            return JsonResponse({"ok": True, "message": f"Conexão OK — {len(resp) if isinstance(resp, list) else 'dados recebidos'}"})
        except Exception as exc:
            return JsonResponse({"ok": False, "message": str(exc)})

    def _test_milvus(self, request):
        try:
            from apps.integrations.milvus import MilvusClient
            api = MilvusClient()
            contacts = api.list_contacts()
            return JsonResponse({"ok": True, "message": f"Conexão OK — {len(contacts)} cliente(s) encontrado(s)"})
        except Exception as exc:
            return JsonResponse({"ok": False, "message": str(exc)})


@admin.register(MilvusContact)
class MilvusContactAdmin(admin.ModelAdmin):
    list_display = ("name", "milvus_id", "digisac_pessoa_id", "synced_at")
    search_fields = ("name", "milvus_id", "digisac_pessoa_id")
    readonly_fields = ("milvus_id", "name", "synced_at")
    fields = ("name", "milvus_id", "digisac_pessoa_id", "synced_at")
    actions = ["sync_from_milvus"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="🔄 Sincronizar clientes da API Milvus")
    def sync_from_milvus(self, request, queryset):
        from apps.integrations.milvus import MilvusClient
        try:
            api = MilvusClient()
            contacts = api.list_contacts()
            created = updated = 0
            for c in contacts:
                obj, is_new = MilvusContact.objects.update_or_create(
                    milvus_id=str(c["id"]),
                    defaults={"name": c["name"]},
                )
                if is_new:
                    created += 1
                else:
                    updated += 1
            self.message_user(request, f"Sincronização concluída: {created} criados, {updated} atualizados.")
        except Exception as exc:
            self.message_user(request, f"Erro na sincronização: {exc}", level="error")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("sync/", self.admin_site.admin_view(self._sync_view), name="milvuscontact_sync"),
        ]
        return custom + urls

    def _sync_view(self, request):
        from apps.integrations.milvus import MilvusClient
        try:
            api = MilvusClient()
            contacts = api.list_contacts()
            created = updated = 0
            for c in contacts:
                obj, is_new = MilvusContact.objects.update_or_create(
                    milvus_id=str(c["id"]),
                    defaults={"name": c["name"]},
                )
                if is_new:
                    created += 1
                else:
                    updated += 1
            self.message_user(request, f"Sincronização concluída: {created} criados, {updated} atualizados.")
        except Exception as exc:
            self.message_user(request, f"Erro na sincronização: {exc}", level="error")
        return redirect("../")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["sync_url"] = "sync/"
        return super().changelist_view(request, extra_context)


class DigisacConfigInline(admin.StackedInline):
    model = ClientDigisacConfig
    extra = 0
    max_num = 1
    fields = ("department_id", "pessoa_id", "is_active")
    verbose_name_plural = "Digisac"


class MilvusConfigInline(admin.StackedInline):
    model = ClientMilvusConfig
    extra = 0
    max_num = 1
    fields = ("milvus_client_id", "is_active")
    verbose_name_plural = "Milvus"


class PRTGConfigInline(admin.TabularInline):
    model = ClientPRTGConfig
    extra = 1
    fields = ("label", "prtg_url", "username", "passhash", "group_id", "columns", "count", "is_active")
    verbose_name = "Grupo PRTG"
    verbose_name_plural = "PRTG — Grupos de Monitoramento"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company_name", "email", "milvus_contact", "is_active", "send_report", "report_count")
    list_filter = ("is_active", "send_report")
    search_fields = ("name", "company_name", "cnpj", "email")
    inlines = [DigisacConfigInline, MilvusConfigInline, PRTGConfigInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identificação", {"fields": ("name", "company_name", "cnpj")}),
        ("Contato", {"fields": ("email", "email_cc", "phone")}),
        ("Vínculo com Milvus / Digisac", {
            "fields": ("milvus_contact",),
            "description": (
                "Selecione o cliente importado do Milvus. "
                "O ID da PESSOA no Digisac será preenchido automaticamente "
                "conforme o cadastro em <strong>Contatos Milvus</strong>."
            ),
        }),
        ("Configurações", {"fields": ("is_active", "send_report", "notes")}),
        ("Auditoria", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
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
