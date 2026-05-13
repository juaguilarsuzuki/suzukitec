from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SystemSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(default="Suzuki Tec", max_length=200, verbose_name="Nome da empresa")),
                ("company_logo_url", models.URLField(blank=True, verbose_name="URL do logotipo")),
                ("email_host", models.CharField(default="smtp.gmail.com", max_length=200, verbose_name="Servidor SMTP")),
                ("email_port", models.PositiveIntegerField(default=587, verbose_name="Porta SMTP")),
                ("email_use_tls", models.BooleanField(default=True, verbose_name="Usar TLS")),
                ("email_host_user", models.CharField(blank=True, max_length=200, verbose_name="Usuário SMTP")),
                ("email_host_password", models.CharField(blank=True, max_length=200, verbose_name="Senha SMTP")),
                ("default_from_email", models.EmailField(default="relatorios@suzukitec.com.br", verbose_name="E-mail de origem")),
                ("digisac_base_url", models.CharField(default="https://api.digisac.com.br/v1", max_length=300, verbose_name="URL base Digisac")),
                ("digisac_token", models.CharField(blank=True, max_length=500, verbose_name="Token Digisac")),
                ("milvus_base_url", models.CharField(default="https://api.milvus.com.br/v1", max_length=300, verbose_name="URL base Milvus")),
                ("milvus_token", models.CharField(blank=True, max_length=500, verbose_name="Token Milvus")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Configurações do Sistema", "verbose_name_plural": "Configurações do Sistema"},
        ),
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Nome")),
                ("company_name", models.CharField(blank=True, max_length=200, verbose_name="Razão Social")),
                ("cnpj", models.CharField(blank=True, max_length=18, verbose_name="CNPJ")),
                ("email", models.EmailField(verbose_name="E-mail principal")),
                ("email_cc", models.TextField(blank=True, help_text="Adicione um e-mail por linha para cópias do relatório.", verbose_name="E-mails em cópia (um por linha)")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="Telefone")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                ("send_report", models.BooleanField(default=True, verbose_name="Enviar relatório mensal")),
                ("notes", models.TextField(blank=True, verbose_name="Observações")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Cliente", "verbose_name_plural": "Clientes", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ClientToolConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tool", models.CharField(choices=[("digisac", "Digisac"), ("milvus", "Milvus"), ("prtg", "PRTG")], max_length=20, verbose_name="Ferramenta")),
                ("label", models.CharField(blank=True, help_text="Ex: Sede, Filial SP, Servidor de Arquivos. Obrigatório quando há mais de um PRTG.", max_length=100, verbose_name="Identificação")),
                ("external_id", models.CharField(help_text="Digisac: ID do departamento | Milvus: ID do cliente | PRTG: ID do grupo", max_length=200, verbose_name="ID externo")),
                ("extra_config", models.JSONField(blank=True, default=dict, help_text='PRTG: {"prtg_url":"https://...","prtg_username":"...","prtg_passhash":"..."}', verbose_name="Configurações extras")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tool_configs", to="clients.client", verbose_name="Cliente")),
            ],
            options={"verbose_name": "Configuração de Ferramenta", "verbose_name_plural": "Configurações de Ferramentas", "ordering": ["tool", "label"]},
        ),
    ]
