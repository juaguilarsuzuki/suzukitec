"""Orchestrates data collection from all tools for a given client + period."""
import logging
from datetime import date

from apps.clients.models import Client
from .digisac import DigisacClient
from .milvus import MilvusClient
from .prtg import collect_prtg_for_client

logger = logging.getLogger(__name__)


def collect_client_data(client: Client, start: date, end: date) -> dict:
    result = {"digisac": None, "milvus": None, "prtg": None}

    # ── Digisac ───────────────────────────────────────────────────────────────
    try:
        cfg = client.digisac_config
        if cfg and cfg.is_active:
            result["digisac"] = DigisacClient().collect(
                department_id=cfg.department_id,
                pessoa_id=cfg.pessoa_id or client.digisac_pessoa_id,
                start=start,
                end=end,
            )
            logger.info("Collected Digisac for %s", client)
    except Client.digisac_config.RelatedObjectDoesNotExist:
        pass
    except Exception as exc:
        logger.error("Digisac failed for %s: %s", client, exc)
        result["digisac"] = {"error": str(exc)}

    # ── Milvus ────────────────────────────────────────────────────────────────
    try:
        mcfg = client.milvus_config
        if mcfg and mcfg.is_active:
            result["milvus"] = MilvusClient().collect(
                external_id=mcfg.client_id,
                start=start,
                end=end,
            )
            logger.info("Collected Milvus for %s", client)
    except Client.milvus_config.RelatedObjectDoesNotExist:
        pass
    except Exception as exc:
        logger.error("Milvus failed for %s: %s", client, exc)
        result["milvus"] = {"error": str(exc)}

    # ── PRTG (múltiplos grupos) ───────────────────────────────────────────────
    prtg_configs = list(client.prtg_configs.filter(is_active=True))
    if prtg_configs:
        try:
            result["prtg"] = collect_prtg_for_client(prtg_configs, start, end)
            logger.info("Collected PRTG for %s (%d group(s))", client, len(prtg_configs))
        except Exception as exc:
            logger.error("PRTG failed for %s: %s", client, exc)
            result["prtg"] = {"error": str(exc)}

    return result
