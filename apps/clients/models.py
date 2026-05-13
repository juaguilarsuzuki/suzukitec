from django.db import models


class SystemSettings(models.Model):
    """
    Singleton model — only one record should exist.
    Stores global integrations and SMTP config, editable via admin panel.
    """

    # ── Company ───────────────────────────────────────────────────────────────
    company_name = models.CharField("Nome da empresa", max_length=200, default="Suzuki Tec")
    company_logo_url = models.URLField("URL do logotipo", blank=True)

    # ── E-mail SMTP ───────────────────────────────────────────────────────────
    email_host = models.CharField("Servidor SMTP", max_length=200, default="smtp.gmail.com")
    email_port = models.PositiveIntegerField("Porta SMTP", default=587)
    email_use_tls = models.BooleanField("Usar TLS", default=True)
    email_host_user = models.CharField("Usuário SMTP", max_length=200, blank=True)
    email_host_password = models.CharField(
        "Senha SMTP", max_length=200, blank=True,
        help_text="Para Gmail, use uma Senha de App (não a senha da conta)."
    )
    default_from_email = models.EmailField(
        "E-mail de origem", default="relatorios@suzukitec.com.br"
    )

    # ── Digisac ───────────────────────────────────────────────────────────────
    digisac_base_url = models.CharField(
        "URL base Digisac", max_length=300, default="https://api.digisac.com.br/v1"
    )
    digisac_token = models.CharField("Token Digisac", max_length=500, blank=True)

    # ── Milvus ────────────────────────────────────────────────────────────────
    milvus_base_url = models.CharField(
        "URL base Milvus", max_length=300, default="https://api.milvus.com.br/v1"
    )
    milvus_token = models.CharField("Token Milvus", max_length=500, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configurações do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return "Configurações do Sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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
    """Identifies this client in each external tool. Multiple entries allowed per tool."""

    class Tool(models.TextChoices):
        DIGISAC = "digisac", "Digisac"
        MILVUS = "milvus", "Milvus"
        PRTG = "prtg", "PRTG"

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="tool_configs",
        verbose_name="Cliente"
    )
    tool = models.CharField("Ferramenta", max_length=20, choices=Tool.choices)
    label = models.CharField(
        "Identificação", max_length=100, blank=True,
        help_text="Ex: Sede, Filial SP, Servidor de Arquivos. Obrigatório quando há mais de um PRTG."
    )
    external_id = models.CharField(
        "ID externo", max_length=200,
        help_text="Digisac: ID do departamento | Milvus: ID do cliente | PRTG: ID do grupo"
    )
    extra_config = models.JSONField(
        "Configurações extras", default=dict, blank=True,
        help_text='PRTG: {"prtg_url":"https://...","prtg_username":"...","prtg_passhash":"..."}'
    )
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Configuração de Ferramenta"
        verbose_name_plural = "Configurações de Ferramentas"
        ordering = ["tool", "label"]

    def __str__(self):
        label = f" — {self.label}" if self.label else ""
        return f"{self.client} — {self.get_tool_display()}{label} ({self.external_id})"
