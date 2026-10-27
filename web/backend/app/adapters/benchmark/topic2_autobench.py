from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings


class Topic2AutoBenchUpstreamError(RuntimeError):
    """Raised when the upstream AutoBench HTTP API returns an error response."""


class Topic2AutoBenchProtocolError(RuntimeError):
    """Raised when the upstream AutoBench response does not match the SSE contract."""


@dataclass(slots=True)
class AgentEvent:
    event_type: str
    data: dict[str, Any]


class Topic2AutoBenchAdapter:
    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        timeout: float = 300.0,
        health_timeout: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.health_timeout = health_timeout
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )

    @classmethod
    def from_settings(cls) -> Topic2AutoBenchAdapter:
        settings = get_settings()
        token = settings.topic2_autobench_api_token.strip()
        return cls(
            base_url=settings.topic2_autobench_base_url,
            api_token=token or None,
            health_timeout=settings.topic2_autobench_health_timeout_seconds,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self, *, accept_sse: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if accept_sse:
            headers["Accept"] = "text/event-stream"
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get(
                "/api/health",
                headers=self._headers(),
                timeout=httpx.Timeout(self.health_timeout),
            )
        except httpx.TimeoutException as exc:
            raise Topic2AutoBenchUpstreamError(
                f"health check timed out after {self.health_timeout:g}s"
            ) from exc
        except httpx.RequestError as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise Topic2AutoBenchUpstreamError(
                f"health check request failed: {message}"
            ) from exc
        if response.status_code >= 400:
            raise Topic2AutoBenchUpstreamError(
                f"health check failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise Topic2AutoBenchProtocolError("health response must be a JSON object")
        return payload

    async def runtime(self) -> dict[str, Any]:
        try:
            response = await self._client.get(
                "/api/runtime",
                headers=self._headers(),
                timeout=httpx.Timeout(self.health_timeout),
            )
        except httpx.TimeoutException as exc:
            raise Topic2AutoBenchUpstreamError(
                f"runtime check timed out after {self.health_timeout:g}s"
            ) from exc
        except httpx.RequestError as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise Topic2AutoBenchUpstreamError(
                f"runtime check request failed: {message}"
            ) from exc
        if response.status_code >= 400:
            raise Topic2AutoBenchUpstreamError(
                f"runtime check failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise Topic2AutoBenchProtocolError("runtime response must be a JSON object")
        return payload

    async def options(self) -> dict[str, Any]:
        response = await self._client.get("/api/options", headers=self._headers())
        if response.status_code >= 400:
            raise Topic2AutoBenchUpstreamError(
                f"options request failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise Topic2AutoBenchProtocolError("options response must be a JSON object")
        return payload

    async def seedbank_stats(self) -> dict[str, Any]:
        response = await self._client.get(
            "/api/seedbank/stats",
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise Topic2AutoBenchUpstreamError(
                f"seedbank stats request failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise Topic2AutoBenchProtocolError(
                "seedbank stats response must be a JSON object"
            )
        return payload

    async def stream_run(self, payload: dict[str, Any]) -> AsyncIterator[AgentEvent]:
        async with self._client.stream(
            "POST",
            "/api/run-agent",
            json=payload,
            headers=self._headers(accept_sse=True),
        ) as response:
            if response.status_code >= 400:
                raise Topic2AutoBenchUpstreamError(
                    f"run-agent failed with status {response.status_code}"
                )
            async for event in _parse_sse_stream(response):
                yield event

    async def download_latest_artifact(self) -> bytes:
        return await self.download_artifact(None)

    async def download_artifact(self, artifact_url: str | None = None) -> bytes:
        path = artifact_url or "/api/artifacts/latest/download"
        parsed = urlparse(path)
        if (
            parsed.scheme
            or parsed.netloc
            or not parsed.path.startswith("/")
            or ".." in parsed.path.split("/")
        ):
            raise Topic2AutoBenchProtocolError("artifact_url must be a same-origin absolute path")
        response = await self._client.get(
            path,
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise Topic2AutoBenchUpstreamError(
                f"artifact download failed with status {response.status_code}"
            )
        return response.content


async def _parse_sse_stream(
    response: httpx.Response,
) -> AsyncIterator[AgentEvent]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type.lower():
        raise Topic2AutoBenchProtocolError("expected text/event-stream response")

    event_type: str | None = None
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line == "":
            if event_type is not None:
                yield _build_agent_event(event_type, data_lines)
            event_type = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())

    if event_type is not None:
        yield _build_agent_event(event_type, data_lines)


def _build_agent_event(event_type: str, data_lines: list[str]) -> AgentEvent:
    data_str = "\n".join(data_lines)
    if not data_str:
        data: dict[str, Any] = {}
    else:
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError as exc:
            raise Topic2AutoBenchProtocolError("invalid SSE data JSON") from exc
        if not isinstance(parsed, dict):
            raise Topic2AutoBenchProtocolError("SSE data must be a JSON object")
        data = parsed
    return AgentEvent(event_type=event_type, data=data)
