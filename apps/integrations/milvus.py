"""
Milvus integration — fetches asset (computer) information for a client.

Milvus REST API: https://api.milvus.com.br/
Authentication: token via MILVUS_TOKEN env var.

Collected data shape:
{
    "total_assets": int,
    "assets_by_type": [{"type": str, "count": int}],
    "assets_online": int,
    "assets_offline": int,
    "assets_with_alerts": int,
    "assets": [
        {
            "id": str,
            "name": str,
            "type": str,
            "os": str,
            "last_seen": str,
            "status": str,
            "alerts": int,
        },
        ...
    ]
}
"""
import logging
from datetime import date

from django.conf import settings

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class MilvusClient(BaseAPIClient):
    def __init__(self):
        self.base_url = settings.MILVUS_BASE_URL
        self.token = settings.MILVUS_TOKEN

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get_assets(self, client_id: str) -> list[dict]:
        params = {"clientId": client_id, "limit": 500}
        data = self._get("/assets", params=params, headers=self._headers)
        return data.get("data", data) if isinstance(data, dict) else data

    def collect(self, external_id: str, start: date, end: date, extra: dict = None) -> dict:
        assets = self._get_assets(external_id)
        return self._process(assets)

    def _process(self, assets: list) -> dict:
        from collections import defaultdict

        by_type = defaultdict(int)
        online = offline = with_alerts = 0

        processed = []
        for a in assets:
            status = (a.get("status") or a.get("connectionStatus") or "unknown").lower()
            asset_type = a.get("type") or a.get("deviceType") or "Computador"
            alerts = a.get("alertCount") or a.get("alerts") or 0

            by_type[asset_type] += 1
            if status in ("online", "ativo", "connected"):
                online += 1
            else:
                offline += 1
            if alerts:
                with_alerts += 1

            processed.append({
                "id": str(a.get("id") or a.get("assetId", "")),
                "name": a.get("name") or a.get("hostname") or "—",
                "type": asset_type,
                "os": a.get("operatingSystem") or a.get("os") or "—",
                "last_seen": (a.get("lastSeen") or a.get("last_seen") or "")[:16],
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
