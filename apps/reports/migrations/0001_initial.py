from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonthlyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_month", models.DateField(help_text="Sempre o primeiro dia do mês referente ao relatório.", verbose_name="Mês de referência")),
                ("status", models.CharField(choices=[("pending", "Pendente"), ("generating", "Gerando"), ("done", "Concluído"), ("sent", "Enviado"), ("error", "Erro")], default="pending", max_length=20, verbose_name="Status")),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to="reports/%Y/%m/", verbose_name="Arquivo PDF")),
                ("sent_at", models.DateTimeField(blank=True, null=True, verbose_name="Enviado em")),
                ("error_message", models.TextField(blank=True, verbose_name="Mensagem de erro")),
                ("data_snapshot", models.JSONField(blank=True, default=dict, verbose_name="Dados coletados")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="clients.client", verbose_name="Cliente")),
            ],
            options={"verbose_name": "Relatório Mensal", "verbose_name_plural": "Relatórios Mensais", "ordering": ["-reference_month", "client__name"], "unique_together": {("client", "reference_month")}},
        ),
    ]
