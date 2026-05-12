import logging
import requests
from datetime import date

logger = logging.getLogger(__name__)


class BaseAPIClient:
    base_url: str = ""
    timeout: int = 30

    def _get(self, path: str, params: dict = None, headers: dict = None) -> dict | list:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error("GET %s failed: %s", url, exc)
            raise

    def _post(self, path: str, payload: dict, headers: dict = None) -> dict | list:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error("POST %s failed: %s", url, exc)
            raise

    def collect(self, external_id: str, start: date, end: date, extra: dict = None) -> dict:
        raise NotImplementedError
