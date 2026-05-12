from django.db import models


class Client(models.Model):
    name = models.CharField("Nome", max_length=200)
    company_name = models.CharField("Razão Social", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    email = models.EmailField("E-mail principal")
    email_cc = models.TextField(
        "E-mails em cópia (um por linha)", blank=True,
        help_text="Adicione um e-mail por linha para cópias do relatório."
    )
    phone = models.CharField("Telefone", max_length=20, blank=True)
    is_active = models.BooleanField("Ativo", default=True)
    send_report = models.BooleanField("Enviar relatório mensal", default=True)
    notes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def cc_emails(self):
        return [e.strip() for e in self.email_cc.splitlines() if e.strip()]


class ClientToolConfig(models.Model):
    """Stores the IDs/slugs that identify this client in each external tool."""

    class Tool(models.TextChoices):
        DIGISAC = "digisac", "Digisac"
        MILVUS = "milvus", "Milvus"
        PRTG = "prtg", "PRTG"

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="tool_configs",
        verbose_name="Cliente"
    )
    tool = models.CharField("Ferramenta", max_length=20, choices=Tool.choices)
    # Digisac: department/service ID; Milvus: client ID; PRTG: group/device ID
    external_id = models.CharField("ID externo", max_length=200)
    extra_config = models.JSONField(
        "Configurações extras", default=dict, blank=True,
        help_text="JSON com parâmetros adicionais (ex: filtros, tags)."
    )
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Configuração de Ferramenta"
        verbose_name_plural = "Configurações de Ferramentas"
        unique_together = [("client", "tool")]

    def __str__(self):
        return f"{self.client} — {self.get_tool_display()} ({self.external_id})"
