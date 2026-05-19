from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0002_alter_systemsettings_email_host_password"),
    ]

    operations = [
        # MilvusContact
        migrations.CreateModel(
            name="MilvusContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("milvus_id", models.CharField(max_length=200, unique=True, verbose_name="ID no Milvus")),
                ("name", models.CharField(max_length=200, verbose_name="Nome no Milvus")),
                ("digisac_pessoa_id", models.CharField(blank=True, max_length=200, verbose_name="ID da PESSOA no Digisac")),
                ("synced_at", models.DateTimeField(auto_now=True, verbose_name="Última sincronização")),
            ],
            options={"verbose_name": "Contato Milvus", "verbose_name_plural": "Contatos Milvus", "ordering": ["name"]},
        ),
        # Client.milvus_contact FK
        migrations.AddField(
            model_name="client",
            name="milvus_contact",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                to="clients.milvuscontact", verbose_name="Cliente no Milvus",
            ),
        ),
        # ClientDigisacConfig
        migrations.CreateModel(
            name="ClientDigisacConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("department_id", models.CharField(max_length=200, verbose_name="ID do Departamento")),
                ("pessoa_id", models.CharField(blank=True, max_length=200, verbose_name="ID da PESSOA")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                ("client", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="digisac_config", to="clients.client", verbose_name="Cliente",
                )),
            ],
            options={"verbose_name": "Configuração Digisac", "verbose_name_plural": "Configurações Digisac"},
        ),
        # ClientMilvusConfig
        migrations.CreateModel(
            name="ClientMilvusConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("milvus_client_id", models.CharField(max_length=200, verbose_name="ID do Cliente no Milvus")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                ("client", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="milvus_config", to="clients.client", verbose_name="Cliente",
                )),
            ],
            options={"verbose_name": "Configuração Milvus", "verbose_name_plural": "Configurações Milvus"},
        ),
        # ClientPRTGConfig
        migrations.CreateModel(
            name="ClientPRTGConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("label", models.CharField(max_length=100, verbose_name="Identificação")),
                ("prtg_url", models.CharField(max_length=300, verbose_name="Endereço PRTG")),
                ("username", models.CharField(max_length=200, verbose_name="Usuário")),
                ("passhash", models.CharField(max_length=500, verbose_name="Passhash")),
                ("group_id", models.CharField(max_length=200, verbose_name="ID do Grupo")),
                ("columns", models.CharField(
                    default="objid,device,sensor,status,lastvalue,message",
                    max_length=500, verbose_name="Colunas",
                )),
                ("count", models.PositiveIntegerField(default=1000, verbose_name="Quantidade máxima de sensores")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                ("client", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="prtg_configs", to="clients.client", verbose_name="Cliente",
                )),
            ],
            options={
                "verbose_name": "Configuração PRTG",
                "verbose_name_plural": "Configurações PRTG",
                "ordering": ["client", "label"],
            },
        ),
    ]
