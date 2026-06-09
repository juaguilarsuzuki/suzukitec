"""
Motor de conciliação — normalização, cruzamento e classificação de status.

Regras de status (por dispositivo):
  OK           — presente no Milvus e no TeamViewer, last_seen <= 30 dias em ambos.
  Sem agente   — presente no TeamViewer, ausente no Milvus.
  Sem contato  — last_seen > 30 dias em qualquer uma das fontes.
  Não faturado — total de dispositivos ativos do cliente > quantidade faturada no CA.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

logger = logging.getLogger(__name__)

STALE_DAYS = 30
_NOW = datetime.now(timezone.utc)


class Device(TypedDict, total=False):
    teamviewer_id: str | None
    hostname: str | None
    logged_user: str | None
    device_type: str | None
    last_seen_milvus: datetime | None
    last_seen_tv: datetime | None
    mac: str | None
    serial: str | None
    milvus_id: str | None
    status: str


def _is_stale(dt: datetime | None) -> bool:
    if dt is None:
        return True
    return (_NOW - dt) > timedelta(days=STALE_DAYS)


def _key(device: dict) -> str | None:
    """
    Chave de junção primária: teamviewer_id.
    Fallback: hostname normalizado.
    """
    tv_id = (device.get("teamviewer_id") or "").strip()
    if tv_id:
        return f"tvid:{tv_id}"
    hostname = (device.get("hostname") or "").strip().upper()
    if hostname:
        return f"host:{hostname}"
    mac = (device.get("mac") or "").strip().upper().replace("-", ":")
    if mac:
        return f"mac:{mac}"
    return None


def reconcile(
    milvus_devices: list[dict],
    tv_devices: list[dict],
    faturamento: dict,
) -> list[Device]:
    """
    Cruza os três conjuntos de dados e atribui status a cada dispositivo.

    Retorna lista de Device com a coluna 'status' preenchida.
    """
    # Indexar Milvus por chave de junção
    milvus_index: dict[str, dict] = {}
    for dev in milvus_devices:
        k = _key(dev)
        if k:
            milvus_index[k] = dev

    # Total faturado no Conta Azul (soma das quantidades de todos os serviços)
    total_faturado = sum(
        int(s.get("quantidade", 0)) for s in faturamento.get("servicos", [])
    )

    results: list[Device] = []

    # Processar todos os dispositivos TeamViewer (fontes de verdade da lista)
    for tv_dev in tv_devices:
        k = _key(tv_dev)
        mil_dev = milvus_index.get(k) if k else None

        device: Device = {
            "teamviewer_id": tv_dev.get("teamviewer_id"),
            "hostname": tv_dev.get("hostname"),
            "logged_user": mil_dev.get("logged_user") if mil_dev else None,
            "device_type": (
                mil_dev.get("device_type") if mil_dev else tv_dev.get("device_type_tv")
            ),
            "last_seen_milvus": mil_dev.get("last_seen_milvus") if mil_dev else None,
            "last_seen_tv": tv_dev.get("last_seen_tv"),
            "mac": mil_dev.get("mac") if mil_dev else None,
            "serial": mil_dev.get("serial") if mil_dev else None,
            "milvus_id": mil_dev.get("milvus_id") if mil_dev else None,
        }

        if mil_dev is None:
            device["status"] = "Sem agente"
        elif _is_stale(device["last_seen_milvus"]) or _is_stale(device["last_seen_tv"]):
            device["status"] = "Sem contato"
        else:
            device["status"] = "OK"

        results.append(device)

    # Atualizar status "Não faturado" onde aplicável
    active_count = len(results)
    if active_count > total_faturado:
        logger.info(
            "Divergência: %d dispositivos ativos vs. %d faturados", active_count, total_faturado
        )
        # Marca os excedentes (os últimos da lista) como "Não faturado"
        excedente = active_count - total_faturado
        # Aplica "Não faturado" apenas em dispositivos que já eram OK (evitar duplo status)
        ok_devices = [i for i, d in enumerate(results) if d.get("status") == "OK"]
        for idx in ok_devices[-excedente:]:
            results[idx]["status"] = "Não faturado"

    logger.info(
        "Conciliação: %d dispositivos | faturados=%d | status=%s",
        active_count,
        total_faturado,
        {s: sum(1 for d in results if d.get("status") == s) for s in {"OK", "Sem agente", "Sem contato", "Não faturado"}},
    )
    return results
