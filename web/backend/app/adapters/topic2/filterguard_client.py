import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Topic2FilterGuardUnavailable(RuntimeError):
    pass


class Topic2FilterGuardClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.topic2_filterguard_base_url.rstrip("/")
        self.timeout = float(settings.topic2_filterguard_timeout_seconds)
        self.method = settings.topic2_filterguard_method.strip() or "keyword"

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def predict(self, texts: list[str]) -> dict[str, Any]:
        return await self._post(f"/predict/{self.method}", {"texts": texts, "method": self.method})

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic2 FilterGuard GET failed: %s", path, exc_info=True)
            raise Topic2FilterGuardUnavailable(str(exc)) from exc

        if not isinstance(payload, dict):
            raise Topic2FilterGuardUnavailable("Topic2 FilterGuard response is not an object")
        return payload

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic2 FilterGuard POST failed: %s", path, exc_info=True)
            raise Topic2FilterGuardUnavailable(str(exc)) from exc

        if not isinstance(data, dict):
            raise Topic2FilterGuardUnavailable("Topic2 FilterGuard response is not an object")
        return data


def build_topic2_filterguard_client() -> Topic2FilterGuardClient:
    return Topic2FilterGuardClient()
