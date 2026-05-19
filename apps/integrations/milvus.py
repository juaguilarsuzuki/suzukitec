"""
Milvus integration — fetches asset information and client list.
Credentials are read from SystemSettings (admin panel), falling back to .env.
"""
import logging
from collections import defaultdict
from datetime import date

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


def _get_settings():
    try:
        from apps.clients.models import SystemSettings
        return SystemSettings.load()
    except Exception:
        return None


class MilvusClient(BaseAPIClient):
    def __init__(self):
        cfg = _get_settings()
        if cfg and cfg.milvus_token:
            self.base_url = cfg.milvus_base_url
            self.token = cfg.milvus_token
        else:
            from django.conf import settings
            self.base_url = settings.MILVUS_BASE_URL
            self.token = settings.MILVUS_TOKEN

    @property
    def _headers(self):
        return {"Authorization": self.token, "Content-Type": "application/json"}

    def list_contacts(self) -> list[dict]:
        """Returns all clients from Milvus for sync/linking."""
        data = self._get("/cliente/busca", headers=self._headers)
        items = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return [
            {
                "id": str(
                    i.get("id") or i.get("idCliente") or i.get("clientId") or ""
                ),
                "name": (
                    i.get("nomeFantasia") or i.get("razaoSocial")
                    or i.get("nome") or i.get("name")
                    or i.get("companyName") or "—"
                ),
            }
            for i in items
            if i.get("id") or i.get("idCliente") or i.get("clientId")
        ]

    def _get_assets(self, client_id: str) -> list[dict]:
        data = self._get(
            "/ativo/busca",
            params={"idCliente": client_id},
            headers=self._headers,
        )
        items = data.get("data", data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    def collect(self, external_id: str, start: date = None, end: date = None, **kwargs) -> dict:
        assets = self._get_assets(external_id)
        return self._process(assets)

    def _process(self, assets: list) -> dict:
        by_type = defaultdict(int)
        online = offline = with_alerts = 0
        processed = []

        for a in assets:
            status = (
                a.get("status") or a.get("statusConexao") or a.get("connectionStatus") or "unknown"
            ).lower()
            asset_type = (
                a.get("tipo") or a.get("type") or a.get("deviceType") or "Computador"
            )
            alerts = a.get("alertCount") or a.get("alertas") or a.get("alerts") or 0

            by_type[asset_type] += 1
            if status in ("online", "ativo", "connected", "1", "true"):
                online += 1
            else:
                offline += 1
            if alerts:
                with_alerts += 1

            processed.append({
                "id": str(a.get("id") or a.get("idAtivo") or a.get("assetId") or ""),
                "name": (
                    a.get("nome") or a.get("name") or a.get("hostname") or "—"
                ),
                "type": asset_type,
                "os": (
                    a.get("sistemaOperacional") or a.get("operatingSystem")
                    or a.get("os") or "—"
                ),
                "last_seen": (
                    a.get("ultimaConexao") or a.get("lastSeen") or a.get("last_seen") or ""
                )[:16],
                "status": status,
                "alerts": int(alerts),
            })

        processed.sort(key=lambda x: (-x["alerts"], x["name"]))

        return {
            "total_assets": len(assets),
            "assets_by_type": [{"type": t, "count": c} for t, c in sorted(by_type.items())],
            "assets_online": online,
            "assets_offline": offline,
            "assets_with_alerts": with_alerts,
            "assets": processed,
        }
