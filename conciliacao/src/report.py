"""
Geração de relatório PDF por cliente usando ReportLab.

Cores da marca:  Azul  #33A3DC  |  Preto #323132
"""
import logging
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

logger = logging.getLogger(__name__)

# ─── Paleta de cores ──────────────────────────────────────────────────────────
AZUL = colors.HexColor("#33A3DC")
PRETO = colors.HexColor("#323132")
CINZA_CLARO = colors.HexColor("#F2F2F2")
CINZA_MEDIO = colors.HexColor("#CCCCCC")
VERDE = colors.HexColor("#27AE60")
VERMELHO = colors.HexColor("#E74C3C")
AMARELO = colors.HexColor("#F39C12")

STATUS_COLORS = {
    "OK": VERDE,
    "Sem agente": AMARELO,
    "Sem contato": VERMELHO,
    "Não faturado": VERMELHO,
}

# ─── Estilos ──────────────────────────────────────────────────────────────────
_styles = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "Title",
    parent=_styles["Normal"],
    fontSize=18,
    textColor=PRETO,
    spaceAfter=4,
    fontName="Helvetica-Bold",
)
STYLE_SUBTITLE = ParagraphStyle(
    "Subtitle",
    parent=_styles["Normal"],
    fontSize=11,
    textColor=AZUL,
    spaceAfter=2,
    fontName="Helvetica",
)
STYLE_SECTION = ParagraphStyle(
    "Section",
    parent=_styles["Normal"],
    fontSize=12,
    textColor=PRETO,
    spaceBefore=12,
    spaceAfter=4,
    fontName="Helvetica-Bold",
)
STYLE_BODY = ParagraphStyle(
    "Body",
    parent=_styles["Normal"],
    fontSize=9,
    textColor=PRETO,
    fontName="Helvetica",
)
STYLE_SMALL = ParagraphStyle(
    "Small",
    parent=_styles["Normal"],
    fontSize=8,
    textColor=colors.grey,
    fontName="Helvetica",
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M")
    return str(dt)


def _status_paragraph(status: str) -> Paragraph:
    """Retorna um Paragraph colorido para o status."""
    color = STATUS_COLORS.get(status, PRETO)
    hex_color = color.hexval() if hasattr(color, "hexval") else "#323132"
    text = f'<font color="{hex_color}"><b>{status}</b></font>'
    return Paragraph(text, STYLE_BODY)


def _build_header(nome_cliente: str, periodo: str, gerado_em: str) -> list:
    elements = []
    elements.append(Paragraph(f"Relatório de Conciliação — {nome_cliente}", STYLE_TITLE))
    elements.append(Paragraph(f"Período: {periodo}  |  Gerado em: {gerado_em}", STYLE_SUBTITLE))
    elements.append(HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=8))
    return elements


def _build_device_table(devices: list[dict]) -> list:
    elements = [Paragraph("Dispositivos", STYLE_SECTION)]

    headers = [
        Paragraph("<b>ID TeamViewer</b>", STYLE_BODY),
        Paragraph("<b>Nome</b>", STYLE_BODY),
        Paragraph("<b>Usuário</b>", STYLE_BODY),
        Paragraph("<b>Tipo</b>", STYLE_BODY),
        Paragraph("<b>Últ. Atualiz. Milvus</b>", STYLE_BODY),
        Paragraph("<b>Últ. Atualiz. TV</b>", STYLE_BODY),
        Paragraph("<b>Status</b>", STYLE_BODY),
    ]

    rows = [headers]
    for dev in devices:
        rows.append([
            Paragraph(dev.get("teamviewer_id") or "—", STYLE_BODY),
            Paragraph(dev.get("hostname") or "—", STYLE_BODY),
            Paragraph(dev.get("logged_user") or "—", STYLE_BODY),
            Paragraph(dev.get("device_type") or "—", STYLE_BODY),
            Paragraph(_fmt_dt(dev.get("last_seen_milvus")), STYLE_BODY),
            Paragraph(_fmt_dt(dev.get("last_seen_tv")), STYLE_BODY),
            _status_paragraph(dev.get("status", "—")),
        ])

    # Larguras relativas em A4 (17 cm úteis)
    col_widths = [3.0*cm, 3.5*cm, 2.8*cm, 2.5*cm, 2.7*cm, 2.7*cm, 2.5*cm]

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Cabeçalho
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Corpo
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.5, CINZA_MEDIO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]))

    elements.append(table)
    return elements


def _build_faturamento(faturamento: dict) -> list:
    elements = [Paragraph("Faturamento Conta Azul", STYLE_SECTION)]

    servicos = faturamento.get("servicos", [])
    if not servicos:
        elements.append(Paragraph("Nenhum item de faturamento encontrado.", STYLE_BODY))
        return elements

    headers = [
        Paragraph("<b>Serviço</b>", STYLE_BODY),
        Paragraph("<b>Qtd.</b>", STYLE_BODY),
        Paragraph("<b>Vlr. Unit. (R$)</b>", STYLE_BODY),
        Paragraph("<b>Total (R$)</b>", STYLE_BODY),
    ]

    rows = [headers]
    grand_total = 0.0
    for srv in servicos:
        qty = int(srv.get("quantidade", 0))
        unit = float(srv.get("valor_unitario", 0.0))
        total = qty * unit
        grand_total += total
        rows.append([
            Paragraph(srv.get("servico", "—"), STYLE_BODY),
            Paragraph(str(qty), STYLE_BODY),
            Paragraph(f"{unit:,.2f}", STYLE_BODY),
            Paragraph(f"{total:,.2f}", STYLE_BODY),
        ])

    # Linha de total
    rows.append([
        Paragraph("<b>TOTAL</b>", STYLE_BODY),
        Paragraph("", STYLE_BODY),
        Paragraph("", STYLE_BODY),
        Paragraph(f"<b>R$ {grand_total:,.2f}</b>", STYLE_BODY),
    ])

    col_widths = [9.0*cm, 2.0*cm, 3.0*cm, 3.5*cm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.5, CINZA_MEDIO),
        ("BACKGROUND", (0, -1), (-1, -1), CINZA_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elements.append(table)
    return elements


def _build_conferencia(devices: list[dict], faturamento: dict) -> list:
    elements = [Paragraph("Conferência", STYLE_SECTION)]

    total_gerenciados = len(devices)
    total_faturado = sum(int(s.get("quantidade", 0)) for s in faturamento.get("servicos", []))
    diferenca = total_gerenciados - total_faturado

    dif_str = f"+{diferenca}" if diferenca > 0 else str(diferenca)
    dif_color = VERMELHO if diferenca != 0 else VERDE
    hex_dif = dif_color.hexval() if hasattr(dif_color, "hexval") else "#323132"

    status_counts = {}
    for dev in devices:
        s = dev.get("status", "—")
        status_counts[s] = status_counts.get(s, 0) + 1

    summary_data = [
        ["Dispositivos sob gestão (Milvus + TeamViewer)", str(total_gerenciados)],
        ["Dispositivos cobrados (Conta Azul)", str(total_faturado)],
        ["Diferença", Paragraph(f'<font color="{hex_dif}"><b>{dif_str}</b></font>', STYLE_BODY)],
    ]
    for status, count in sorted(status_counts.items()):
        summary_data.append([f"  — {status}", str(count)])

    table = Table(summary_data, colWidths=[12*cm, 5*cm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, CINZA_MEDIO),
        ("BACKGROUND", (0, 0), (-1, 1), CINZA_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 1.5*cm))

    # Linha de assinatura
    elements.append(HRFlowable(width="50%", thickness=1, color=PRETO, spaceAfter=4))
    elements.append(Paragraph("Conferido por: ___________________________________", STYLE_BODY))
    elements.append(Paragraph("Data: ____/____/________", STYLE_BODY))

    return elements


def generate_pdf(
    nome_cliente: str,
    periodo: str,
    devices: list[dict],
    faturamento: dict,
    output_dir: str = "saida",
) -> str:
    """
    Gera o PDF de conciliação para um cliente.

    Retorna o caminho do arquivo gerado.
    """
    os.makedirs(output_dir, exist_ok=True)

    safe_nome = nome_cliente.replace(" ", "_").replace("/", "-")
    safe_periodo = periodo.replace("/", "-").replace(" ", "_")
    filename = f"{safe_nome}_{safe_periodo}.pdf"
    filepath = os.path.join(output_dir, filename)

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title=f"Conciliação — {nome_cliente}",
        author="Motor de Conciliação",
    )

    story = []
    story += _build_header(nome_cliente, periodo, gerado_em)
    story += _build_device_table(devices)
    story.append(Spacer(1, 0.5*cm))
    story += _build_faturamento(faturamento)
    story.append(Spacer(1, 0.5*cm))
    story += _build_conferencia(devices, faturamento)

    doc.build(story)
    logger.info("PDF gerado: %s", filepath)
    return filepath
