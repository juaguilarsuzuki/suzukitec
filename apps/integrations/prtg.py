"""
PRTG integration — fetches server monitoring data for a client group/device map.

PRTG API: https://<PRTG_BASE_URL>/api/
Authentication: username + passhash (preferred) or username + password.

Collected data shape:
{
    "total_sensors": int,
    "sensors_ok": int,
    "sensors_warning": int,
    "sensors_error": int,
    "sensors_paused": int,
    "uptime_percent": float,
    "devices": [
        {
            "id": str,
            "name": str,
            "host": str,
            "status": str,
            "sensors_ok": int,
            "sensors_warning": int,
            "sensors_error": int,
        },
        ...
    ],
    "top_alerts": [
        {"sensor": str, "device": str, "message": str, "since": str},
        ...
    ],
}
"""
import logging
from datetime import date

from django.conf import settings

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class PRTGClient(BaseAPIClient):
    def __init__(self):
        self.base_url = settings.PRTG_BASE_URL
        self.username = settings.PRTG_USERNAME
        self.passhash = settings.PRTG_PASSHASH
        self.password = settings.PRTG_PASSWORD

    @property
    def _auth_params(self) -> dict:
        if self.passhash:
            return {"username": self.username, "passhash": self.passhash}
        return {"username": self.username, "password": self.password}

    def _get_devices(self, group_id: str) -> list[dict]:
        params = {
            **self._auth_params,
            "content": "devices",
            "columns": "objid,name,host,status,upsens,downsens,warnsens,pausedsens",
            "filter_group": group_id,
            "output": "json",
            "count": 500,
        }
        data = self._get("/api/table.json", params=params)
        return data.get("devices", [])

    def _get_sensors(self, group_id: str) -> list[dict]:
        params = {
            **self._auth_params,
            "content": "sensors",
            "columns": "objid,name,device,status,message,lastup,lastdown",
            "filter_group": group_id,
            "output": "json",
            "count": 1000,
        }
        data = self._get("/api/table.json", params=params)
        return data.get("sensors", [])

    def collect(self, external_id: str, start: date, end: date, extra: dict = None) -> dict:
        extra = extra or {}
        group_id = extra.get("group_id", external_id)

        devices = self._get_devices(group_id)
        sensors = self._get_sensors(group_id)

        return self._process(devices, sensors)

    def _process(self, devices: list, sensors: list) -> dict:
        status_map = {
            "up": "ok",
            "down": "error",
            "warning": "warning",
            "paused": "paused",
            "unknown": "unknown",
        }

        sensors_ok = sensors_warning = sensors_error = sensors_paused = 0
        for s in sensors:
            raw = (s.get("status") or "").lower()
            mapped = next((v for k, v in status_map.items() if k in raw), "unknown")
            if mapped == "ok":
                sensors_ok += 1
            elif mapped == "warning":
                sensors_warning += 1
            elif mapped == "error":
                sensors_error += 1
            elif mapped == "paused":
                sensors_paused += 1

        total_active = sensors_ok + sensors_warning + sensors_error
        uptime = round((sensors_ok / total_active) * 100, 2) if total_active else 0.0

        processed_devices = []
        for d in devices:
            processed_devices.append({
                "id": str(d.get("objid", "")),
                "name": d.get("name", "—"),
                "host": d.get("host", "—"),
                "status": (d.get("status") or "—").lower(),
                "sensors_ok": int(d.get("upsens") or 0),
                "sensors_warning": int(d.get("warnsens") or 0),
                "sensors_error": int(d.get("downsens") or 0),
            })
        processed_devices.sort(key=lambda x: (-x["sensors_error"], x["name"]))

        # Top alerts: sensors that are down or warning
        top_alerts = []
        for s in sensors:
            raw = (s.get("status") or "").lower()
            if "down" in raw or "warning" in raw:
                top_alerts.append({
                    "sensor": s.get("name", "—"),
                    "device": s.get("device", "—"),
                    "message": s.get("message", "—"),
                    "since": (s.get("lastdown") or s.get("lastup") or "")[:16],
                })
        top_alerts = top_alerts[:20]

        return {
            "total_sensors": len(sensors),
            "sensors_ok": sensors_ok,
            "sensors_warning": sensors_warning,
            "sensors_error": sensors_error,
            "sensors_paused": sensors_paused,
            "uptime_percent": uptime,
            "devices": processed_devices,
            "top_alerts": top_alerts,
        }
