"""Orchestrates data collection from all tools for a given client + period."""
import logging
from datetime import date

from apps.clients.models import Client, ClientToolConfig

from .digisac import DigisacClient
from .milvus import MilvusClient
from .prtg import PRTGClient

logger = logging.getLogger(__name__)

_CLIENTS = {
    ClientToolConfig.Tool.DIGISAC: DigisacClient,
    ClientToolConfig.Tool.MILVUS: MilvusClient,
    ClientToolConfig.Tool.PRTG: PRTGClient,
}


def collect_client_data(client: Client, start: date, end: date) -> dict:
    """Returns a dict with keys 'digisac', 'milvus', 'prtg' (None if not configured)."""
    result = {"digisac": None, "milvus": None, "prtg": None}

    configs = client.tool_configs.filter(is_active=True)
    for config in configs:
        tool_key = config.tool
        api_class = _CLIENTS.get(tool_key)
        if not api_class:
            continue
        try:
            api = api_class()
            result[tool_key] = api.collect(
                external_id=config.external_id,
                start=start,
                end=end,
                extra=config.extra_config,
            )
            logger.info("Collected %s data for client %s", tool_key, client)
        except Exception as exc:
            logger.error("Failed to collect %s for client %s: %s", tool_key, client, exc)
            result[tool_key] = {"error": str(exc)}

    return result
