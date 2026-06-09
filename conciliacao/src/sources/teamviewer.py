"""
Adaptador TeamViewer — lista de dispositivos por grupo (endpoint /devices).

Documentação oficial: https://webapi.teamviewer.com/api/v1/docs/index

TODO: validar todos os nomes de campo marcados com "# TODO" contra a API real.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

# ─── Configuração da API TeamViewer ──────────────────────────────────────────
_BASE_URL = "https://webapi.teamviewer.com/api/v1"
_TOKEN = os.getenv("TEAMVIEWER_TOKEN", "")

# Mapeamento campo API → campo interno
_FIELD_MAP = {
    "device_id": "teamviewer_id",          # TODO: confirmar (pode ser "id" ou "remotecontrol_id")
    "alias": "hostname",                   # TODO: confirmar (pode ser "description" ou "name")
    "last_seen": "last_seen_tv",           # TODO: confirmar formato ISO 8601
    "device_type": "device_type_tv",      # TODO: confirmar enum de valores
    "groupid": "group_id",                # TODO: confirmar
}
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_NOW = datetime.now(timezone.utc)


def _mock_devices(grupo: str) -> list[dict]:
    """Dados de exemplo realistas para modo mock."""
    base = [
        {
            "teamviewer_id": "TV-100001",
            "hostname": "PC-RECEPCAO-01",
            "last_seen_tv": (_MOCK_NOW - timedelta(hours=4)).isoformat(),
            "device_type_tv": "workstation",
            "group_id": grupo,
        },
        {
            "teamviewer_id": "TV-100002",
            "hostname": "PC-FINANCEIRO-02",
            "last_seen_tv": (_MOCK_NOW - timedelta(days=40)).isoformat(),  # Sem contato
            "device_type_tv": "workstation",
            "group_id": grupo,
        },
        {
            "teamviewer_id": "TV-100003",
            "hostname": "SRV-FILES-01",
            "last_seen_tv": (_MOCK_NOW - timedelta(days=1)).isoformat(),
            "device_type_tv": "server",
            "group_id": grupo,
        },
        {
            "teamviewer_id": "TV-100004",
            "hostname": "PC-DIRETORIA-04",
            "last_seen_tv": (_MOCK_NOW - timedelta(days=3)).isoformat(),
            "device_type_tv": "laptop",
            "group_id": grupo,
        },
        {
            # Dispositivo presente no TV mas sem agente Milvus — "Sem agente"
            "teamviewer_id": "TV-100099",
            "hostname": "PC-VISITANTE-99",
            "last_seen_tv": (_MOCK_NOW - timedelta(days=2)).isoformat(),
            "device_type_tv": "workstation",
            "group_id": grupo,
        },
    ]
    if grupo.startswith("Acme"):
        return base  # 5 dispositivos (inclui o sem agente)
    return base[:4]


def _normalize(raw: dict) -> dict:
    """Converte campos da API para o esquema interno."""
    raw_ts = raw.get("last_seen_tv")
    if isinstance(raw_ts, str):
        try:
            dt = datetime.fromisoformat(raw_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            raw["last_seen_tv"] = dt
        except ValueError:
            logger.warning("TeamViewer: timestamp inválido '%s'", raw_ts)
            raw["last_seen_tv"] = None
    return raw


def _get_group_id(group_name: str, headers: dict) -> str | None:
    """Busca o ID numérico do grupo pelo nome."""
    try:
        resp = requests.get(f"{_BASE_URL}/groups", headers=headers, timeout=30)
        resp.raise_for_status()
        for grp in resp.json().get("groups", []):
            # TODO: confirmar campos "name" e "id" no retorno de /groups
            if grp.get("name") == group_name:
                return grp.get("id")
    except requests.RequestException as exc:
        logger.error("TeamViewer: erro ao listar grupos — %s", exc)
    return None


def get_devices(grupo: str) -> list[dict]:
    """
    Retorna lista de dispositivos do grupo TeamViewer informado.

    Em modo mock retorna dados de exemplo; em modo real chama a API TeamViewer.
    """
    _mode = (os.getenv("CONCILIACAO_MODE") or os.getenv("MODE", "mock")).lower()
    if _mode == "mock":
        logger.debug("TeamViewer [mock] grupo=%s", grupo)
        return [_normalize(d) for d in _mock_devices(grupo)]

    # ─── Modo real ────────────────────────────────────────────────────────────
    headers = {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }

    group_id = _get_group_id(grupo, headers)
    if group_id is None:
        logger.warning("TeamViewer: grupo '%s' não encontrado", grupo)
        return []

    # TODO: confirmar se o endpoint é /devices?groupid=X ou /groups/{id}/devices
    params = {"groupid": group_id}
    try:
        resp = requests.get(
            f"{_BASE_URL}/devices",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # TODO: confirmar chave da lista no retorno (pode ser "devices" ou "data")
        items = data.get("devices") or data.get("data") or data
        logger.info("TeamViewer: %d dispositivos obtidos para grupo '%s'", len(items), grupo)

        normalized = []
        for item in items:
            # Remapear para esquema interno
            mapped = {
                "teamviewer_id": item.get("device_id") or item.get("id"),        # TODO
                "hostname": item.get("alias") or item.get("description"),        # TODO
                "last_seen_tv": item.get("last_seen"),                            # TODO
                "device_type_tv": item.get("device_type", ""),                   # TODO
                "group_id": item.get("groupid", group_id),                       # TODO
            }
            normalized.append(_normalize(mapped))
        return normalized
    except requests.RequestException as exc:
        logger.error("TeamViewer: erro ao buscar dispositivos de '%s' — %s", grupo, exc)
        return []
