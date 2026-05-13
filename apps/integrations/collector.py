"""Orchestrates data collection from all tools for a given client + period."""
import logging
from datetime import date

from apps.clients.models import Client, ClientToolConfig

from .digisac import DigisacClient
from .milvus import MilvusClient
from .prtg import collect_prtg_for_client

logger = logging.getLogger(__name__)


def collect_client_data(client: Client, start: date, end: date) -> dict:
    """Returns a dict with keys 'digisac', 'milvus', 'prtg' (None if not configured)."""
    result = {"digisac": None, "milvus": None, "prtg": None}

    configs = client.tool_configs.filter(is_active=True)

    # Digisac — single config
    digisac_configs = configs.filter(tool=ClientToolConfig.Tool.DIGISAC)
    if digisac_configs.exists():
        config = digisac_configs.first()
        try:
            result["digisac"] = DigisacClient().collect(
                external_id=config.external_id,
                start=start, end=end,
                extra=config.extra_config,
            )
            logger.info("Collected Digisac data for client %s", client)
        except Exception as exc:
            logger.error("Digisac failed for %s: %s", client, exc)
            result["digisac"] = {"error": str(exc)}

    # Milvus — single config
    milvus_configs = configs.filter(tool=ClientToolConfig.Tool.MILVUS)
    if milvus_configs.exists():
        config = milvus_configs.first()
        try:
            result["milvus"] = MilvusClient().collect(
                external_id=config.external_id,
                start=start, end=end,
                extra=config.extra_config,
            )
            logger.info("Collected Milvus data for client %s", client)
        except Exception as exc:
            logger.error("Milvus failed for %s: %s", client, exc)
            result["milvus"] = {"error": str(exc)}

    # PRTG — multiple configs supported
    prtg_configs = list(configs.filter(tool=ClientToolConfig.Tool.PRTG))
    if prtg_configs:
        try:
            result["prtg"] = collect_prtg_for_client(prtg_configs, start, end)
            logger.info("Collected PRTG data for client %s (%d config(s))", client, len(prtg_configs))
        except Exception as exc:
            logger.error("PRTG failed for %s: %s", client, exc)
            result["prtg"] = {"error": str(exc)}

    return result
