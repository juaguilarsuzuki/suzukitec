"""
Adaptador Milvus — dispositivos sob gestão (agente instalado + scan de rede).

TODO: validar todos os nomes de campo marcados com "# TODO" contra a API real
      antes de usar em modo 'real'. Use MODE=mock para rodar sem credenciais.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

# ─── Mapeamento de campos da API Milvus ──────────────────────────────────────
# TODO: confirmar URL base e versão da API com o suporte Milvus
_BASE_URL = os.getenv("MILVUS_BASE_URL", "https://suainstancia.milvus.com.br/api/v1")
_TOKEN = os.getenv("MILVUS_TOKEN", "")

# TODO: confirmar se o endpoint de dispositivos por cliente é este
_ENDPOINT_DEVICES = "/dispositivos"          # TODO: confirmar nome do endpoint

# Mapeamento campo API → campo interno
_FIELD_MAP = {
    "id": "milvus_id",                        # TODO: confirmar nome do campo
    "nome": "hostname",                        # TODO: confirmar nome do campo
    "usuario_logado": "logged_user",           # TODO: confirmar nome do campo
    "tipo_dispositivo": "device_type",         # TODO: confirmar nome do campo
    "teamviewer_id": "teamviewer_id",          # TODO: confirmar nome do campo
    "mac_address": "mac",                      # TODO: confirmar nome do campo
    "numero_serie": "serial",                  # TODO: confirmar nome do campo
    "ultima_atualizacao": "last_seen_milvus",  # TODO: confirmar nome do campo (ISO 8601)
    "cliente_id": "cliente_id",               # TODO: confirmar nome do campo
}
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_NOW = datetime.now(timezone.utc)


def _mock_devices(cliente_id: str) -> list[dict]:
    """
    Dados de exemplo realistas para modo mock.
    Usa nomes de campos da API (mesmos que _FIELD_MAP) para que _normalize funcione.
    """
    base = [
        {
            "id": f"{cliente_id}-M001",
            "nome": "PC-RECEPCAO-01",
            "usuario_logado": "maria.silva",
            "tipo_dispositivo": "Estação de Trabalho",
            "teamviewer_id": "TV-100001",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "numero_serie": "SN-XYZ-001",
            "ultima_atualizacao": (_MOCK_NOW - timedelta(days=1)).isoformat(),
            "cliente_id": cliente_id,
        },
        {
            # Sem contato — última atualização > 30 dias
            "id": f"{cliente_id}-M002",
            "nome": "PC-FINANCEIRO-02",
            "usuario_logado": "joao.costa",
            "tipo_dispositivo": "Estação de Trabalho",
            "teamviewer_id": "TV-100002",
            "mac_address": "AA:BB:CC:DD:EE:02",
            "numero_serie": "SN-XYZ-002",
            "ultima_atualizacao": (_MOCK_NOW - timedelta(days=35)).isoformat(),
            "cliente_id": cliente_id,
        },
        {
            "id": f"{cliente_id}-M003",
            "nome": "SRV-FILES-01",
            "usuario_logado": "",
            "tipo_dispositivo": "Servidor",
            "teamviewer_id": "TV-100003",
            "mac_address": "AA:BB:CC:DD:EE:03",
            "numero_serie": "SN-XYZ-003",
            "ultima_atualizacao": (_MOCK_NOW - timedelta(days=2)).isoformat(),
            "cliente_id": cliente_id,
        },
        {
            # Dispositivo extra para provocar "Não faturado" no cliente CLI-001
            "id": f"{cliente_id}-M004",
            "nome": "PC-DIRETORIA-04",
            "usuario_logado": "ana.lima",
            "tipo_dispositivo": "Notebook",
            "teamviewer_id": "TV-100004",
            "mac_address": "AA:BB:CC:DD:EE:04",
            "numero_serie": "SN-XYZ-004",
            "ultima_atualizacao": (_MOCK_NOW - timedelta(days=5)).isoformat(),
            "cliente_id": cliente_id,
        },
    ]
    # Apenas CLI-001 tem 4 dispositivos (para exibir caso "Não faturado")
    if cliente_id == "CLI-001":
        return base
    return base[:3]


def _normalize(raw: dict) -> dict:
    """Converte campos da API para o esquema interno."""
    out = {}
    for api_key, internal_key in _FIELD_MAP.items():
        out[internal_key] = raw.get(api_key)

    # Garantir que last_seen_milvus seja datetime aware
    raw_ts = out.get("last_seen_milvus")
    if isinstance(raw_ts, str):
        try:
            dt = datetime.fromisoformat(raw_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out["last_seen_milvus"] = dt
        except ValueError:
            logger.warning("Milvus: timestamp inválido '%s' para dispositivo %s", raw_ts, out.get("milvus_id"))
            out["last_seen_milvus"] = None
    return out


def get_devices(cliente_id: str) -> list[dict]:
    """
    Retorna lista de dispositivos gerenciados para um cliente.

    Em modo mock retorna dados de exemplo; em modo real chama a API Milvus.
    """
    _mode = (os.getenv("CONCILIACAO_MODE") or os.getenv("MODE", "mock")).lower()
    if _mode == "mock":
        logger.debug("Milvus [mock] cliente=%s", cliente_id)
        return [_normalize(d) for d in _mock_devices(cliente_id)]

    # ─── Modo real ────────────────────────────────────────────────────────────
    headers = {
        "Authorization": f"Bearer {_TOKEN}",  # TODO: confirmar scheme de auth (Bearer / Basic / API-Key)
        "Content-Type": "application/json",
    }
    # TODO: confirmar se filtro de cliente é query param ou path param
    params = {"cliente_id": cliente_id, "page_size": 500}  # TODO: confirmar paginação

    try:
        resp = requests.get(
            f"{_BASE_URL}{_ENDPOINT_DEVICES}",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # TODO: confirmar se a lista está em data["data"], data["items"] ou direto
        items = data.get("data") or data.get("items") or data
        logger.info("Milvus: %d dispositivos obtidos para cliente %s", len(items), cliente_id)
        return [_normalize(d) for d in items]
    except requests.RequestException as exc:
        logger.error("Milvus: erro ao buscar dispositivos de %s — %s", cliente_id, exc)
        return []
