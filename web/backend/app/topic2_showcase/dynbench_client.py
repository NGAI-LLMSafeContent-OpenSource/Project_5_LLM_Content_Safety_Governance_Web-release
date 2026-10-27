from __future__ import annotations

from typing import Any

import httpx
from pydantic import AnyHttpUrl, BaseModel

from app.topic2_showcase.config import ShowcaseSettings
from app.topic2_showcase.contracts import Readiness


EXPECTED_DYNBENCH_SERVICE = "autobench-agent"
HEALTH_PATH = "/api/health"
WEBUI_PATH = "/agent"


class DynBenchHealth(BaseModel):
    readiness: Readiness
    webui_url: str | None = None


class DynBenchClient:
    def __init__(
        self,
        base_url: str | AnyHttpUrl = "http://127.0.0.1:8766",
        public_base_url: str | AnyHttpUrl | None = None,
        timeout_seconds: float = 1.5,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.public_base_url = str(public_base_url or base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    @classmethod
    def from_settings(cls, settings: ShowcaseSettings) -> DynBenchClient:
        return cls(
            base_url=settings.dynbench_base_url,
            public_base_url=(
                settings.dynbench_public_base_url or settings.dynbench_base_url
            ),
            timeout_seconds=settings.dynbench_timeout_seconds,
        )

    def readiness(self) -> Readiness:
        return self.check_health().readiness

    def check_health(self) -> DynBenchHealth:
        try:
            with self._http_client() as client:
                response = client.get(HEALTH_PATH)
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError:
                    return DynBenchHealth(readiness="invalid")
        except (httpx.HTTPError, ImportError):
            return DynBenchHealth(readiness="offline")

        if not self._is_valid_health_payload(payload):
            return DynBenchHealth(readiness="invalid")

        return DynBenchHealth(
            readiness="ready",
            webui_url=f"{self.public_base_url}{WEBUI_PATH}",
        )

    def _http_client(self) -> httpx.Client:
        if self._client is not None:
            return _BorrowedClient(self._client)
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            trust_env=False,
        )

    @staticmethod
    def _is_valid_health_payload(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        return (
            payload.get("status") == "ok"
            and payload.get("service") == EXPECTED_DYNBENCH_SERVICE
        )


class _BorrowedClient:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, *_args: object) -> None:
        return None
