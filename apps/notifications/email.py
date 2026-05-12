"""Sends the monthly report PDF to the client by email."""
import logging
from email.mime.application import MIMEApplication
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def send_report_email(report) -> None:
    """Sends the PDF report to the client's email (and CC list)."""
    pdf_path = Path(report.pdf_file.path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    subject = (
        f"[{settings.COMPANY_NAME}] Relatório Mensal — "
        f"{report.client.name} — {report.month_label}"
    )

    body = _build_body(report)

    recipients = [report.client.email]
    cc = report.client.cc_emails

    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        cc=cc,
    )
    msg.content_subtype = "html"

    with open(pdf_path, "rb") as f:
        filename = f"Relatorio_{report.client.name.replace(' ', '_')}_{report.month_label.replace('/', '_')}.pdf"
        msg.attach(filename, f.read(), "application/pdf")

    msg.send()
    logger.info("Report email sent to %s for %s", recipients, report)


def _build_body(report) -> str:
    from django.conf import settings

    company = settings.COMPANY_NAME
    month = report.month_label
    client = report.client.name

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1f2937;line-height:1.6;">
    <div style="max-width:600px;margin:0 auto;">
      <div style="background:#1d4ed8;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:18pt;">{company}</h1>
        <p style="color:#bfdbfe;margin:4px 0 0;">Relatório Gerencial Mensal</p>
      </div>
      <div style="background:#f8fafc;padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <p>Olá, <strong>{client}</strong>!</p>
        <p>
          Segue em anexo o seu <strong>Relatório Gerencial Mensal referente a {month}</strong>,
          consolidando as informações de atendimentos, inventário de equipamentos e monitoramento
          de servidores do período.
        </p>
        <div style="background:#eff6ff;border-left:4px solid #1d4ed8;padding:12px 16px;
                    border-radius:0 6px 6px 0;margin:16px 0;">
          <p style="margin:0;font-size:9pt;color:#1e40af;">
            📎 O relatório completo está disponível em PDF em anexo a este e-mail.<br>
            Você também pode acessá-lo pelo nosso portal de clientes.
          </p>
        </div>
        <p>
          Em caso de dúvidas ou para solicitar esclarecimentos sobre qualquer informação
          contida no relatório, não hesite em entrar em contato conosco.
        </p>
        <p style="margin-top:20px;">
          Atenciosamente,<br>
          <strong>Equipe {company}</strong>
        </p>
      </div>
      <p style="font-size:8pt;color:#9ca3af;text-align:center;margin-top:12px;">
        Este é um e-mail automático. Por favor, não responda diretamente a este endereço.
      </p>
    </div>
    </body></html>
    """
