"""
PRTG integration — fetches server monitoring data.
Each ClientPRTGConfig has its own URL, credentials and group_id.
Multiple configs per client are merged into one aggregated result.
"""
import logging
from datetime import date

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class PRTGClient(BaseAPIClient):
    def __init__(self, prtg_url: str, username: str, passhash: str):
        self.base_url = prtg_url.rstrip("/")
        self.username = username
        self.passhash = passhash

    @property
    def _auth(self) -> dict:
        return {"username": self.username, "passhash": self.passhash}

    def _get_sensors(self, group_id: str, columns: str, count: int) -> list[dict]:
        params = {
            **self._auth,
            "content": "sensors",
            "columns": columns,
            "filter_group": group_id,
            "output": "json",
            "count": count,
        }
        data = self._get("/api/table.json", params=params)
        return data.get("sensors", [])

    def _get_devices(self, group_id: str) -> list[dict]:
        params = {
            **self._auth,
            "content": "devices",
            "columns": "objid,name,host,status,upsens,downsens,warnsens,pausedsens",
            "filter_group": group_id,
            "output": "json",
            "count": 500,
        }
        data = self._get("/api/table.json", params=params)
        return data.get("devices", [])

    def collect_group(self, group_id: str, columns: str, count: int) -> dict:
        sensors = self._get_sensors(group_id, columns, count)
        devices = self._get_devices(group_id)
        return self._process(sensors, devices)

    def _process(self, sensors: list, devices: list) -> dict:
        status_map = {"up": "ok", "down": "error", "warning": "warning", "paused": "paused"}

        sensors_ok = sensors_warning = sensors_error = sensors_paused = 0
        sensor_rows = []
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
            sensor_rows.append({
                "objid": s.get("objid", ""),
                "device": s.get("device", "—"),
                "sensor": s.get("sensor") or s.get("name", "—"),
                "status": mapped,
                "lastvalue": s.get("lastvalue", "—"),
                "message": s.get("message", "—"),
            })

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
                "sensor": s.get("sensor") or s.get("name", "—"),
                "device": s.get("device", "—"),
                "message": s.get("message", "—"),
                "lastvalue": s.get("lastvalue", "—"),
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
            "sensor_rows": sensor_rows,
            "top_alerts": top_alerts,
        }


def collect_prtg_for_client(configs, start: date, end: date) -> dict:
    """Collects and merges PRTG data from all active configs of a client."""
    groups = []
    totals = {
        "total_sensors": 0, "sensors_ok": 0, "sensors_warning": 0,
        "sensors_error": 0, "sensors_paused": 0,
        "devices": [], "top_alerts": [],
    }

    for config in configs:
        try:
            api = PRTGClient(
                prtg_url=config.prtg_url,
                username=config.username,
                passhash=config.passhash,
            )
            data = api.collect_group(
                group_id=config.group_id,
                columns=config.columns,
                count=config.count,
            )
            data["label"] = config.label
            groups.append(data)
            for key in ("total_sensors", "sensors_ok", "sensors_warning", "sensors_error", "sensors_paused"):
                totals[key] += data.get(key, 0)
            totals["devices"].extend(data.get("devices", []))
            totals["top_alerts"].extend(data.get("top_alerts", []))
        except Exception as exc:
            logger.error("PRTG failed for config %s: %s", config, exc)
            groups.append({"label": config.label, "error": str(exc)})

    total_active = totals["sensors_ok"] + totals["sensors_warning"] + totals["sensors_error"]
    totals["uptime_percent"] = round((totals["sensors_ok"] / total_active) * 100, 2) if total_active else 0.0
    totals["groups"] = groups
    totals["top_alerts"] = totals["top_alerts"][:20]
    return totals
