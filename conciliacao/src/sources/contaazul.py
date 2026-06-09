"""
Adaptador Conta Azul — serviços/itens faturados por cliente.

A reconciliação Conta Azul é por cliente (quantidade total faturada),
não por dispositivo individual.

TODO: validar todos os campos marcados com "# TODO" contra a API real.
      Documentação: https://developers.contaazul.com/
"""
import logging
import os
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

# ─── Configuração da API Conta Azul ──────────────────────────────────────────
_CLIENT_ID = os.getenv("CONTAAZUL_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("CONTAAZUL_CLIENT_SECRET", "")
_TOKEN_URL = os.getenv("CONTAAZUL_TOKEN_URL", "https://api.contaazul.com/oauth2/token")
_BASE_URL = "https://api.contaazul.com/v1"  # TODO: confirmar versão da API

# Mapeamento de campos
_SALE_ITEM_FIELD_MAP = {
    "description": "servico",      # TODO: confirmar nome do campo (pode ser "name" ou "product_name")
    "quantity": "quantidade",      # TODO: confirmar nome do campo
    "value": "valor_unitario",     # TODO: confirmar nome do campo (pode ser "unit_price" ou "price")
}
# ─────────────────────────────────────────────────────────────────────────────

_token_cache: dict = {"access_token": None, "expires_at": 0}

_MOCK_NOW = datetime.now(timezone.utc)


def _mock_faturamento(cliente_id: str) -> dict:
    """Dados de faturamento mock para cada cliente."""
    dados = {
        "CLI-001": {
            "cliente_id": "CA-10021",
            "servicos": [
                {
                    "servico": "Gestão de TI - Estação de Trabalho",
                    "quantidade": 3,  # Faturado 3, mas cliente tem 4 → "Não faturado"
                    "valor_unitario": 120.00,
                },
                {
                    "servico": "Gestão de TI - Servidor",
                    "quantidade": 1,
                    "valor_unitario": 250.00,
                },
            ],
        },
        "CLI-002": {
            "cliente_id": "CA-10034",
            "servicos": [
                {
                    "servico": "Gestão de TI - Estação de Trabalho",
                    "quantidade": 3,
                    "valor_unitario": 120.00,
                },
            ],
        },
        "CLI-003": {
            "cliente_id": "CA-10058",
            "servicos": [
                {
                    "servico": "Gestão de TI - Estação de Trabalho",
                    "quantidade": 2,
                    "valor_unitario": 120.00,
                },
                {
                    "servico": "Gestão de TI - Servidor",
                    "quantidade": 1,
                    "valor_unitario": 250.00,
                },
            ],
        },
    }
    return dados.get(cliente_id, {"cliente_id": cliente_id, "servicos": []})


def _get_access_token() -> str:
    """Obtém (ou reutiliza) um access token OAuth2 do Conta Azul."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        _token_cache["access_token"] = payload["access_token"]
        _token_cache["expires_at"] = now + payload.get("expires_in", 3600)
        return _token_cache["access_token"]
    except requests.RequestException as exc:
        logger.error("ContaAzul: falha ao obter token — %s", exc)
        raise


def get_faturamento(cliente_id: str, periodo_inicio: str, periodo_fim: str) -> dict:
    """
    Retorna o faturamento (serviços e quantidades) de um cliente no período.

    Parâmetros:
        cliente_id       ID do cliente no Milvus (usado como chave de lookup)
        periodo_inicio   Data início ISO 8601 (YYYY-MM-DD)
        periodo_fim      Data fim ISO 8601 (YYYY-MM-DD)

    Retorno:
        {
            "cliente_id": str,
            "servicos": [
                {"servico": str, "quantidade": int, "valor_unitario": float},
                ...
            ]
        }
    """
    if os.getenv("MODE", "mock").lower() == "mock":
        logger.debug("ContaAzul [mock] cliente_id=%s", cliente_id)
        return _mock_faturamento(cliente_id)

    # ─── Modo real ────────────────────────────────────────────────────────────
    token = _get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # TODO: confirmar endpoint de vendas/notas por cliente
    # Pode ser /sales, /invoices ou /service-invoices
    params = {
        "customer_id": cliente_id,            # TODO: confirmar nome do param
        "emission_start": periodo_inicio,     # TODO: confirmar nome do param
        "emission_end": periodo_fim,          # TODO: confirmar nome do param
        "page_size": 100,                     # TODO: confirmar paginação
    }

    try:
        resp = requests.get(
            f"{_BASE_URL}/sales",              # TODO: confirmar endpoint
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # TODO: confirmar estrutura do retorno
        sales = data.get("data") or data.get("items") or data

        # Agrega itens de todos os pedidos de venda do período
        servicos: list[dict] = []
        for sale in sales:
            for item in sale.get("items", []):   # TODO: confirmar chave "items"
                servicos.append({
                    "servico": item.get("description") or item.get("name", ""),   # TODO
                    "quantidade": item.get("quantity", 0),                         # TODO
                    "valor_unitario": item.get("value") or item.get("unit_price", 0.0),  # TODO
                })

        logger.info("ContaAzul: %d itens obtidos para cliente %s", len(servicos), cliente_id)
        return {"cliente_id": cliente_id, "servicos": servicos}
    except requests.RequestException as exc:
        logger.error("ContaAzul: erro ao buscar faturamento de %s — %s", cliente_id, exc)
        return {"cliente_id": cliente_id, "servicos": []}
