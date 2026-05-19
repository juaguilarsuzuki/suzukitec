from django.db import models


class SystemSettings(models.Model):
    """Singleton — configurações globais editáveis pelo painel admin."""

    company_name = models.CharField("Nome da empresa", max_length=200, default="Suzuki Tec")
    company_logo_url = models.URLField("URL do logotipo", blank=True)

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

    digisac_base_url = models.CharField(
        "URL base Digisac", max_length=300, default="https://api.digisac.com.br/v1"
    )
    digisac_token = models.CharField("Token Digisac", max_length=500, blank=True)

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


class MilvusContact(models.Model):
    """
    Clientes sincronizados da API Milvus.
    O vínculo com o PESSOAS do Digisac é feito manualmente aqui.
    """
    milvus_id = models.CharField("ID no Milvus", max_length=200, unique=True)
    name = models.CharField("Nome no Milvus", max_length=200)
    digisac_pessoa_id = models.CharField(
        "ID da PESSOA no Digisac", max_length=200, blank=True,
        help_text="Informe o ID do contato correspondente na plataforma Digisac."
    )
    synced_at = models.DateTimeField("Última sincronização", auto_now=True)

    class Meta:
        verbose_name = "Contato Milvus"
        verbose_name_plural = "Contatos Milvus"
        ordering = ["name"]

    def __str__(self):
        return self.name


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

    # Vínculos com ferramentas
    milvus_contact = models.ForeignKey(
        MilvusContact, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Cliente no Milvus",
        help_text="Selecione o cliente correspondente na base do Milvus."
    )

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

    @property
    def digisac_pessoa_id(self):
        return self.milvus_contact.digisac_pessoa_id if self.milvus_contact else ""


class ClientDigisacConfig(models.Model):
    """Configuração Digisac por cliente — departamento e PESSOAS."""
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE, related_name="digisac_config",
        verbose_name="Cliente"
    )
    department_id = models.CharField(
        "ID do Departamento", max_length=200,
        help_text="ID do departamento no Digisac para filtrar os atendimentos."
    )
    pessoa_id = models.CharField(
        "ID da PESSOA", max_length=200, blank=True,
        help_text="ID do contato PESSOAS no Digisac (preenchido automaticamente se vinculado ao Milvus)."
    )
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Configuração Digisac"
        verbose_name_plural = "Configurações Digisac"

    def __str__(self):
        return f"{self.client} — Digisac"

    def save(self, *args, **kwargs):
        # Auto-preenche pessoa_id do vínculo Milvus se não informado manualmente
        if not self.pessoa_id and self.client.milvus_contact:
            self.pessoa_id = self.client.milvus_contact.digisac_pessoa_id
        super().save(*args, **kwargs)


class ClientMilvusConfig(models.Model):
    """Configuração Milvus por cliente."""
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE, related_name="milvus_config",
        verbose_name="Cliente"
    )
    client_id = models.CharField(
        "ID do Cliente no Milvus", max_length=200,
        help_text="ID do cliente na plataforma Milvus."
    )
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Configuração Milvus"
        verbose_name_plural = "Configurações Milvus"

    def __str__(self):
        return f"{self.client} — Milvus"


class ClientPRTGConfig(models.Model):
    """
    Configuração PRTG por grupo de monitoramento.
    Um cliente pode ter múltiplos grupos (sede, filiais, servidores etc.).
    """
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="prtg_configs",
        verbose_name="Cliente"
    )
    label = models.CharField(
        "Identificação", max_length=100,
        help_text="Ex: Sede, Filial SP, Servidor de Arquivos."
    )
    prtg_url = models.CharField(
        "Endereço PRTG", max_length=300,
        help_text="Ex: https://prtg.suaempresa.com.br"
    )
    username = models.CharField("Usuário", max_length=200)
    passhash = models.CharField(
        "Passhash", max_length=500,
        help_text="Passhash gerado pelo PRTG (preferível à senha)."
    )
    group_id = models.CharField(
        "ID do Grupo", max_length=200,
        help_text="objid do grupo ou dispositivo no PRTG."
    )
    columns = models.CharField(
        "Colunas", max_length=500,
        default="objid,device,sensor,status,lastvalue,message"
    )
    count = models.PositiveIntegerField("Quantidade máxima de sensores", default=1000)
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Configuração PRTG"
        verbose_name_plural = "Configurações PRTG"
        ordering = ["client", "label"]

    def __str__(self):
        return f"{self.client} — PRTG — {self.label}"
