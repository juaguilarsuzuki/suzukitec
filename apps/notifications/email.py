"""Sends the monthly report PDF to the client by email."""
import logging
from pathlib import Path

from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def _load_email_settings():
    """Returns (connection_params_dict, from_email, company_name) from DB or django settings."""
    try:
        from apps.clients.models import SystemSettings
        cfg = SystemSettings.load()
        if cfg.email_host_user:
            return {
                "host": cfg.email_host,
                "port": cfg.email_port,
                "use_tls": cfg.email_use_tls,
                "username": cfg.email_host_user,
                "password": cfg.email_host_password,
            }, cfg.default_from_email, cfg.company_name
    except Exception:
        pass
    from django.conf import settings
    return None, settings.DEFAULT_FROM_EMAIL, settings.COMPANY_NAME


def send_report_email(report) -> None:
    """Sends the PDF report to the client's email (and CC list)."""
    pdf_path = Path(report.pdf_file.path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    conn_params, from_email, company_name = _load_email_settings()

    subject = f"[{company_name}] Relatório Mensal — {report.client.name} — {report.month_label}"
    body = _build_body(report, company_name)

    recipients = [report.client.email]
    cc = report.client.cc_emails

    kwargs = {"subject": subject, "body": body, "from_email": from_email, "to": recipients, "cc": cc}
    if conn_params:
        from django.core.mail import get_connection
        kwargs["connection"] = get_connection(**conn_params)

    msg = EmailMessage(**kwargs)
    msg.content_subtype = "html"

    with open(pdf_path, "rb") as f:
        filename = f"Relatorio_{report.client.name.replace(' ', '_')}_{report.month_label.replace('/', '_')}.pdf"
        msg.attach(filename, f.read(), "application/pdf")

    msg.send()
    logger.info("Report email sent to %s for %s", recipients, report)


def _build_body(report, company_name: str = None) -> str:
    if not company_name:
        from django.conf import settings
        company_name = settings.COMPANY_NAME

    company = settings.COMPANY_NAME
    month = report.month_label
    client = report.client.name

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1f2937;line-height:1.6;">
    <div style="max-width:600px;margin:0 auto;">
      <div style="background:#1d4ed8;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:18pt;">{company_name}</h1>
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
          <strong>Equipe {company_name}</strong>
        </p>
      </div>
      <p style="font-size:8pt;color:#9ca3af;text-align:center;margin-top:12px;">
        Este é um e-mail automático. Por favor, não responda diretamente a este endereço.
      </p>
    </div>
    </body></html>
    """
