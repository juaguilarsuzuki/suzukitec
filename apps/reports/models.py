from django.db import models
from apps.clients.models import Client


class MonthlyReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        GENERATING = "generating", "Gerando"
        DONE = "done", "Concluído"
        SENT = "sent", "Enviado"
        ERROR = "error", "Erro"

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="reports",
        verbose_name="Cliente"
    )
    reference_month = models.DateField(
        "Mês de referência",
        help_text="Sempre o primeiro dia do mês referente ao relatório."
    )
    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    pdf_file = models.FileField(
        "Arquivo PDF", upload_to="reports/%Y/%m/", blank=True, null=True
    )
    sent_at = models.DateTimeField("Enviado em", null=True, blank=True)
    error_message = models.TextField("Mensagem de erro", blank=True)

    # Snapshot of collected data (stored so we can re-render without re-fetching)
    data_snapshot = models.JSONField("Dados coletados", default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Relatório Mensal"
        verbose_name_plural = "Relatórios Mensais"
        ordering = ["-reference_month", "client__name"]
        unique_together = [("client", "reference_month")]

    def __str__(self):
        return f"{self.client} — {self.reference_month.strftime('%B/%Y')}"

    @property
    def month_label(self):
        months = [
            "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        ]
        return f"{months[self.reference_month.month]}/{self.reference_month.year}"
