"""
Celery task wrapper para o motor de conciliação.

Registrado explicitamente em config/celery.py (não está em INSTALLED_APPS,
portanto autodiscover_tasks não o encontra automaticamente).
"""
import logging
import os
import sys

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="conciliacao.run_all", max_retries=2, default_retry_delay=300)
def run_conciliacao(self) -> dict:
    """
    Executa a coleta, conciliação e geração de PDFs para todos os clientes ativos.
    Acionado pelo Celery Beat (ver config/celery.py).
    """
    from conciliacao.src.main import _carregar_clientes, processar_cliente

    clientes = _carregar_clientes()
    resultados = {"ok": [], "erro": []}

    for cliente in clientes:
        try:
            pdf_path = processar_cliente(cliente)
            resultados["ok"].append({"cliente": cliente["nome"], "pdf": pdf_path})
            logger.info("Conciliação OK: %s → %s", cliente["nome"], pdf_path)
        except Exception as exc:
            logger.error("Conciliação FALHA: %s — %s", cliente["nome"], exc, exc_info=True)
            resultados["erro"].append({"cliente": cliente["nome"], "erro": str(exc)})
            # Não propaga o erro para não bloquear os demais clientes

    if resultados["erro"] and not resultados["ok"]:
        # Todos falharam — tenta reprocessar depois
        raise self.retry(exc=RuntimeError("Todos os clientes falharam"))

    return resultados
