"""Generates the monthly PDF report using WeasyPrint."""
import logging
from datetime import date
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def generate_pdf(report) -> Path:
    """
    Renders the HTML template and converts to PDF.
    Returns the Path of the saved PDF file.
    """
    from weasyprint import HTML, CSS

    context = _build_context(report)
    html_content = render_to_string("reports/monthly_pdf.html", context)

    output_dir = Path(settings.REPORTS_DIR) / str(report.reference_month.year) / f"{report.reference_month.month:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"relatorio_{report.client.id}_{report.reference_month.strftime('%Y_%m')}.pdf"
    output_path = output_dir / filename

    HTML(string=html_content, base_url=str(settings.BASE_DIR)).write_pdf(
        str(output_path),
        stylesheets=[CSS(string=_pdf_extra_css())],
    )

    logger.info("PDF generated: %s", output_path)
    return output_path


def _build_context(report) -> dict:
    data = report.data_snapshot
    digisac = data.get("digisac") or {}
    milvus = data.get("milvus") or {}
    prtg = data.get("prtg") or {}

    # Satisfaction label
    avg_score = (digisac.get("ratings") or {}).get("average_score", 0)
    satisfaction_label, satisfaction_color = _score_label(avg_score)

    return {
        "report": report,
        "client": report.client,
        "company_name": settings.COMPANY_NAME,
        "company_logo_url": settings.COMPANY_LOGO_URL,
        "digisac": digisac,
        "milvus": milvus,
        "prtg": prtg,
        "avg_score": avg_score,
        "satisfaction_label": satisfaction_label,
        "satisfaction_color": satisfaction_color,
        "stars": _star_range(avg_score),
    }


def _score_label(score: float):
    if score >= 4.5:
        return "Excelente", "#22c55e"
    if score >= 3.5:
        return "Bom", "#84cc16"
    if score >= 2.5:
        return "Regular", "#f59e0b"
    if score >= 1.5:
        return "Ruim", "#f97316"
    return "Muito Ruim", "#ef4444"


def _star_range(score: float) -> list[str]:
    """Returns list of 5 strings: 'full', 'half', or 'empty'."""
    stars = []
    for i in range(1, 6):
        if score >= i:
            stars.append("full")
        elif score >= i - 0.5:
            stars.append("half")
        else:
            stars.append("empty")
    return stars


def _pdf_extra_css() -> str:
    return """
    @page {
        size: A4;
        margin: 15mm 15mm 20mm 15mm;
        @bottom-center {
            content: "Página " counter(page) " de " counter(pages);
            font-size: 9pt;
            color: #6b7280;
        }
    }
    body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1f2937; }
    """
