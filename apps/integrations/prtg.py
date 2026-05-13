"""
PRTG integration — fetches server monitoring data per client.

Each client can have MULTIPLE PRTG configs (one per server group/location).
Per-client PRTG credentials are stored in ClientToolConfig.extra_config:
  {
    "prtg_url": "https://prtg.empresa.com.br",
    "prtg_username": "usuario",
    "prtg_passhash": "hash",   // preferred
    "prtg_password": "senha"   // fallback if no passhash
  }
Global PRTG credentials in .env are used when extra_config is empty.
"""
import logging
from datetime import date

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class PRTGClient(BaseAPIClient):
    def __init__(self, base_url: str = None, username: str = None,
                 passhash: str = None, password: str = None):
        if base_url:
            self.base_url = base_url
            self.username = username or ""
            self.passhash = passhash or ""
            self.password = password or ""
        else:
            from django.conf import settings
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
        status_map = {"up": "ok", "down": "error", "warning": "warning", "paused": "paused"}

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

        processed_devices = sorted([
            {
                "id": str(d.get("objid", "")),
                "name": d.get("name", "—"),
                "host": d.get("host", "—"),
                "status": (d.get("status") or "—").lower(),
                "sensors_ok": int(d.get("upsens") or 0),
                "sensors_warning": int(d.get("warnsens") or 0),
                "sensors_error": int(d.get("downsens") or 0),
            }
            for d in devices
        ], key=lambda x: (-x["sensors_error"], x["name"]))

        top_alerts = [
            {
                "sensor": s.get("name", "—"),
                "device": s.get("device", "—"),
                "message": s.get("message", "—"),
                "since": (s.get("lastdown") or s.get("lastup") or "")[:16],
            }
            for s in sensors
            if "down" in (s.get("status") or "").lower() or "warning" in (s.get("status") or "").lower()
        ][:20]

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


def collect_prtg_for_client(configs: list, start: date, end: date) -> dict:
    """
    Collects and merges PRTG data from all active PRTG configs of a client.
    Returns a dict with aggregated totals and a 'groups' list (one per config).
    """
    if not configs:
        return None

    groups = []
    totals = {
        "total_sensors": 0, "sensors_ok": 0, "sensors_warning": 0,
        "sensors_error": 0, "sensors_paused": 0,
        "devices": [], "top_alerts": [],
    }

    for config in configs:
        extra = config.extra_config or {}
        label = config.label or config.external_id

        client = PRTGClient(
            base_url=extra.get("prtg_url") or None,
            username=extra.get("prtg_username") or None,
            passhash=extra.get("prtg_passhash") or None,
            password=extra.get("prtg_password") or None,
        )

        try:
            data = client.collect(config.external_id, start, end, extra)
            data["label"] = label
            groups.append(data)

            for key in ("total_sensors", "sensors_ok", "sensors_warning", "sensors_error", "sensors_paused"):
                totals[key] += data.get(key, 0)
            totals["devices"].extend(data.get("devices", []))
            totals["top_alerts"].extend(data.get("top_alerts", []))

        except Exception as exc:
            logger.error("PRTG collect failed for config %s: %s", config, exc)
            groups.append({"label": label, "error": str(exc)})

    total_active = totals["sensors_ok"] + totals["sensors_warning"] + totals["sensors_error"]
    totals["uptime_percent"] = (
        round((totals["sensors_ok"] / total_active) * 100, 2) if total_active else 0.0
    )
    totals["groups"] = groups
    totals["top_alerts"] = sorted(
        totals["top_alerts"], key=lambda x: x.get("since", ""), reverse=True
    )[:20]

    return totals
