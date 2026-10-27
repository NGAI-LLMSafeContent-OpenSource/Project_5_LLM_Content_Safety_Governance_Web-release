from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.adapters.benchmark.topic2_autobench import AgentEvent
from app.core.config import get_settings

LOCAL_RUNTIME_HINT = (
    "topic3 difficulty live_run requires server-side router/workers; "
    "local start-platform does not manage them"
)


class Topic3DifficultyUpstreamError(RuntimeError):
    """Raised when the upstream dynamic difficulty API returns an error."""


class Topic3DifficultyProtocolError(RuntimeError):
    """Raised when the upstream dynamic difficulty API response is malformed."""


class Topic3DifficultyAdapter:
    def __init__(
        self,
        base_url: str,
        timeout: float = 300.0,
        health_timeout: float = 2.0,
        poll_interval: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.health_timeout = health_timeout
        self.poll_interval = poll_interval
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )
        self._last_job_id: str | None = None

    @classmethod
    def from_settings(cls) -> Topic3DifficultyAdapter:
        settings = get_settings()
        return cls(
            base_url=settings.topic3_difficulty_base_url,
            timeout=settings.topic3_difficulty_timeout_seconds,
            health_timeout=settings.topic3_difficulty_health_timeout_seconds,
            poll_interval=settings.topic3_difficulty_poll_interval_seconds,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get(
                "/api/health",
                timeout=httpx.Timeout(self.health_timeout),
            )
        except httpx.TimeoutException as exc:
            raise Topic3DifficultyUpstreamError(
                f"health check timed out after {self.health_timeout:g}s"
            ) from exc
        except httpx.RequestError as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise Topic3DifficultyUpstreamError(
                f"health check request failed: {message}"
            ) from exc
        if response.status_code >= 400:
            raise Topic3DifficultyUpstreamError(
                f"health check failed with status {response.status_code}"
            )
        return _json_object(response, "health")

    async def options(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/api/generation/options")
        except httpx.RequestError as exc:
            raise _request_error("options request", exc) from exc
        if response.status_code >= 400:
            raise Topic3DifficultyUpstreamError(
                _http_error_message("options request", response)
            )
        return _json_object(response, "options")

    async def stream_run(self, payload: dict[str, Any]) -> AsyncIterator[AgentEvent]:
        job = await self.start_job(payload)
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            raise Topic3DifficultyProtocolError("start job response missing job_id")
        self._last_job_id = job_id
        yield _status_event(job, message="topic3 difficulty job accepted")
        last_progress_signature: tuple[Any, ...] | None = None

        while True:
            await asyncio.sleep(self.poll_interval)
            status = await self.read_job(job_id)
            yield _status_event(status)

            progress_event = _worker_progress_event(status)
            if progress_event is not None:
                signature = _worker_progress_signature(progress_event.data)
                if signature != last_progress_signature:
                    last_progress_signature = signature
                    yield progress_event

            if status.get("difficulty_level_counts"):
                yield AgentEvent(
                    "quality",
                    {
                        "job_id": job_id,
                        "difficulty_level_counts": status.get(
                            "difficulty_level_counts"
                        ),
                        "generated": status.get("generated"),
                        "total": status.get("total"),
                    },
                )

            state = str(status.get("status") or "").lower()
            if state == "completed":
                yield AgentEvent("done", {"reason": "completed", "job_id": job_id})
                return
            if state in {"failed", "error"}:
                yield AgentEvent(
                    "error",
                    {
                        "message": status.get("message")
                        or status.get("error")
                        or "topic3 difficulty job failed",
                        "job_id": job_id,
                    },
                )
                return
            if state == "stopped":
                yield AgentEvent(
                    "error",
                    {
                        "message": "topic3 difficulty job stopped before completion",
                        "job_id": job_id,
                    },
                )
                return

    async def start_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post("/api/generation/jobs", json=payload)
        except httpx.RequestError as exc:
            raise _request_error("start job", exc) from exc
        if response.status_code >= 400:
            raise Topic3DifficultyUpstreamError(
                _http_error_message("start job", response)
            )
        return _json_object(response, "start job")

    async def read_job(self, job_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/api/generation/jobs/{job_id}")
        except httpx.RequestError as exc:
            raise _request_error("read job", exc) from exc
        if response.status_code >= 400:
            raise Topic3DifficultyUpstreamError(
                _http_error_message("read job", response)
            )
        return _json_object(response, "read job")

    async def download_latest_artifact(self) -> bytes:
        if not self._last_job_id:
            raise Topic3DifficultyProtocolError("cannot download artifact before job_id")
        try:
            response = await self._client.get(
                f"/api/generation/jobs/{self._last_job_id}/artifacts/download"
            )
        except httpx.RequestError as exc:
            raise _request_error("artifact download", exc) from exc
        if response.status_code >= 400:
            raise Topic3DifficultyUpstreamError(
                _http_error_message("artifact download", response)
            )
        return response.content


def _request_error(
    operation: str, exc: httpx.RequestError
) -> Topic3DifficultyUpstreamError:
    message = str(exc).strip() or exc.__class__.__name__
    return Topic3DifficultyUpstreamError(
        f"{operation} request failed: {message}; {LOCAL_RUNTIME_HINT}"
    )


def _http_error_message(operation: str, response: httpx.Response) -> str:
    message = (
        f"{operation} failed with status {response.status_code}: "
        f"{_response_detail(response)}"
    )
    if response.status_code >= 500:
        message = f"{message}; {LOCAL_RUNTIME_HINT}"
    return message


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        detail = response.text.strip()
        return detail or response.reason_phrase
    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(payload)
    return str(payload)


def _json_object(response: httpx.Response, label: str) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise Topic3DifficultyProtocolError(f"{label} response must be a JSON object")
    return payload


def _status_event(payload: dict[str, Any], *, message: str | None = None) -> AgentEvent:
    job_id = payload.get("job_id")
    generated = payload.get("generated")
    total = payload.get("total")
    progress = payload.get("progress")
    status = str(payload.get("status") or "running")
    parts = []
    if generated is not None and total is not None:
        parts.append(f"{generated}/{total}")
    if progress is not None:
        parts.append(f"{progress}%")
    return AgentEvent(
        "status",
        {
            "state": status,
            "message": message or " ".join(parts) or status,
            "job_id": job_id,
            "generated": generated,
            "total": total,
            "progress": progress,
        },
    )


def _worker_progress_event(payload: dict[str, Any]) -> AgentEvent | None:
    worker_state = payload.get("worker_state")
    if not isinstance(worker_state, dict):
        return None
    active_sample = worker_state.get("active_sample")
    if not isinstance(active_sample, dict):
        return None

    checks = active_sample.get("checks")
    latest_check = checks[-1] if isinstance(checks, list) and checks else None
    if not isinstance(latest_check, dict):
        latest_check = None

    return AgentEvent(
        "lifecycle",
        {
            "stage": worker_state.get("phase") or "active_sample",
            "sample_id": active_sample.get("sample_id"),
            "job_id": payload.get("job_id"),
            "generated": payload.get("generated"),
            "total": payload.get("total"),
            "progress": payload.get("progress"),
            "attempt": worker_state.get("attempt"),
            "retry": active_sample.get("retry"),
            "difficulty_level": active_sample.get("difficulty_level"),
            "difficulty_strategy": active_sample.get("difficulty_strategy"),
            "domain": active_sample.get("domain"),
            "latest_check": latest_check,
            "message": worker_state.get("message"),
            "discard_counts": worker_state.get("discard_counts"),
        },
    )


def _worker_progress_signature(data: dict[str, Any]) -> tuple[Any, ...]:
    latest_check = data.get("latest_check")
    if not isinstance(latest_check, dict):
        latest_check = {}
    return (
        data.get("job_id"),
        data.get("sample_id"),
        data.get("attempt"),
        data.get("retry"),
        data.get("generated"),
        data.get("stage"),
        latest_check.get("name"),
        latest_check.get("status"),
    )
