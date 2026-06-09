"""
Orquestrador — coleta dados das 3 fontes, executa a conciliação e gera PDFs.

Uso:
    python -m src.main                  # usa variáveis de ambiente / .env
    MODE=mock python -m src.main        # modo mock sem credenciais reais
"""
import logging
import os
import sys
from datetime import datetime, timezone

import yaml
from dotenv import load_dotenv

from .reconcile import reconcile
from .report import generate_pdf
from .sources import contaazul, milvus, teamviewer

# ─── Configuração de logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ─── Carregar .env ────────────────────────────────────────────────────────────
load_dotenv()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "clientes.yaml")
# Aceita tanto CONCILIACAO_OUTPUT_DIR (integrado ao Django) quanto OUTPUT_DIR (standalone)
OUTPUT_DIR = os.getenv("CONCILIACAO_OUTPUT_DIR") or os.getenv("OUTPUT_DIR", "saida")
PERIODO = (
    os.getenv("CONCILIACAO_PERIODO")
    or os.getenv("PERIODO")
    or datetime.now(timezone.utc).strftime("%B/%Y")
)

# Período para consulta Conta Azul (mês corrente)
_hoje = datetime.now(timezone.utc)
PERIODO_INICIO = _hoje.replace(day=1).strftime("%Y-%m-%d")
PERIODO_FIM = _hoje.strftime("%Y-%m-%d")


def _carregar_clientes() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    clientes = cfg.get("clientes", [])

    validos = []
    for c in clientes:
        if not c.get("ativo", True):
            logger.info("Cliente '%s' inativo — ignorado.", c.get("nome"))
            continue
        if not (c.get("milvus_cliente_id") and c.get("teamviewer_grupo") and c.get("contaazul_cliente_id")):
            logger.warning("Cliente '%s' sem vinculação completa — ignorado.", c.get("nome"))
            continue
        validos.append(c)

    logger.info("%d cliente(s) válido(s) carregado(s).", len(validos))
    return validos


def processar_cliente(cliente: dict) -> str | None:
    nome = cliente["nome"]
    logger.info("─── Processando: %s ───", nome)

    # 1. Coleta
    devs_milvus = milvus.get_devices(cliente["milvus_cliente_id"])
    devs_tv = teamviewer.get_devices(cliente["teamviewer_grupo"])
    fat = contaazul.get_faturamento(
        cliente["milvus_cliente_id"], PERIODO_INICIO, PERIODO_FIM
    )

    logger.info(
        "%s — Milvus=%d | TeamViewer=%d | Conta Azul=%d serviço(s)",
        nome,
        len(devs_milvus),
        len(devs_tv),
        len(fat.get("servicos", [])),
    )

    # 2. Conciliação
    devices = reconcile(devs_milvus, devs_tv, fat)

    # 3. Relatório
    pdf_path = generate_pdf(nome, PERIODO, devices, fat, OUTPUT_DIR)
    return pdf_path


def main() -> None:
    mode = os.getenv("MODE", "mock").lower()
    logger.info("Motor de conciliação iniciado. MODE=%s | PERIODO=%s", mode.upper(), PERIODO)

    clientes = _carregar_clientes()
    if not clientes:
        logger.error("Nenhum cliente válido encontrado em %s", CONFIG_PATH)
        sys.exit(1)

    pdfs = []
    erros = []
    for cliente in clientes:
        try:
            path = processar_cliente(cliente)
            if path:
                pdfs.append(path)
        except Exception as exc:
            logger.error("Erro ao processar '%s': %s", cliente.get("nome"), exc, exc_info=True)
            erros.append(cliente.get("nome"))

    logger.info("─────────────────────────────────────────────")
    logger.info("PDFs gerados (%d):", len(pdfs))
    for p in pdfs:
        logger.info("  %s", p)
    if erros:
        logger.warning("Clientes com erro (%d): %s", len(erros), ", ".join(erros))


if __name__ == "__main__":
    main()
