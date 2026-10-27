import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Topic2ActivationProbeUnavailable(RuntimeError):
    pass


class Topic2ActivationProbeClient:
    """Remote Activation Probe + predicted same_l1 moderator (Topic 2 neuron showcase)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.topic2_activation_probe_base_url.rstrip("/")
        self.proxy_url = (
            settings.topic2_activation_probe_proxy_url or ""
        ).strip() or None
        self.timeout = float(settings.topic2_activation_probe_timeout_seconds)
        self.max_batch = max(1, int(settings.topic2_activation_probe_max_batch))
        self.max_text_chars = max(
            1, int(settings.topic2_activation_probe_max_text_chars)
        )
        self.method = "activation_probe"

    async def health(self) -> dict[str, Any]:
        return await self._get("/healthz")

    async def info(self) -> dict[str, Any]:
        return await self._get("/v1/info")

    async def moderate(self, texts: list[str]) -> dict[str, Any]:
        if not texts:
            return {
                "status": "success",
                "method": "activation_probe__same_l1",
                "results": [],
                "batch_size": 0,
            }

        # The new Activation Probe caps a single text at 32768 chars and rejects
        # the whole request when any text exceeds it. Fail the whole batch here
        # with an explicit, actionable reason instead of surfacing the upstream
        # 400 as a transport error (agreed policy: no partial/silent detection).
        too_long = [
            (index, len(text))
            for index, text in enumerate(texts)
            if len(text) > self.max_text_chars
        ]
        if too_long:
            index, length = too_long[0]
            raise Topic2ActivationProbeUnavailable(
                "单条文本超过 Activation Probe 上限 "
                f"{self.max_text_chars} 字符（第 {index + 1} 条为 {length} 字符）；"
                "已整批拒绝，未调用在线检测。"
            )

        merged_results: list[dict[str, Any]] = []
        last_payload: dict[str, Any] = {}
        for start in range(0, len(texts), self.max_batch):
            chunk = texts[start : start + self.max_batch]
            payload = await self._post("/v1/moderate", {"texts": chunk})
            last_payload = payload
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise Topic2ActivationProbeUnavailable("Activation Probe results is not a list")
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                local_index = int(normalized.get("index") or 0)
                normalized["index"] = start + local_index
                merged_results.append(normalized)

        return {
            **last_payload,
            "status": str(last_payload.get("status") or "success"),
            "method": str(last_payload.get("method") or "activation_probe__same_l1"),
            "batch_size": len(texts),
            "results": merged_results,
        }

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(**self._client_options()) as client:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic2 Activation Probe GET failed: %s", path, exc_info=True)
            raise Topic2ActivationProbeUnavailable(
                self._describe_failure("GET", path, exc)
            ) from exc

        if not isinstance(payload, dict):
            raise Topic2ActivationProbeUnavailable("Activation Probe response is not an object")
        self._raise_if_error_payload(payload)
        return payload

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(**self._client_options()) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic2 Activation Probe POST failed: %s", path, exc_info=True)
            raise Topic2ActivationProbeUnavailable(
                self._describe_failure("POST", path, exc)
            ) from exc

        if not isinstance(data, dict):
            raise Topic2ActivationProbeUnavailable("Activation Probe response is not an object")
        self._raise_if_error_payload(data)
        return data

    @staticmethod
    def _error_message(data: dict[str, Any]) -> str:
        """Normalize both service error shapes into one readable message.

        Old: ``{"status":"error","error":{"code":..,"message":..}}``.
        New: low-level parse errors return ``{"error":"bad_request"}`` with no
        ``status``; validation errors return ``status="failed"`` with an
        ``error`` object carrying ``code``/``message``/``retryable``."""
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
        elif isinstance(error, str):
            message = error
        else:
            message = None
        return str(message or data.get("message") or "Activation Probe returned error status")

    def _raise_if_error_payload(self, data: dict[str, Any]) -> None:
        """Fail on any ``error`` field, even when ``status`` is absent.

        The new Activation Probe can answer ``{"error":"bad_request"}`` without a
        ``status``; the old guard keyed only on ``status`` and would have treated
        it as success with zero results."""
        status = str(data.get("status") or "").strip().lower()
        if data.get("error") or status == "failed" or status not in {"", "success", "ready", "ok"}:
            raise Topic2ActivationProbeUnavailable(self._error_message(data))

    def _client_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "timeout": self.timeout,
            "trust_env": False,
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        return options

    def _describe_failure(self, method: str, path: str, exc: Exception) -> str:
        target = f"{method} {path}"
        if isinstance(exc, httpx.TimeoutException):
            return f"{target} timed out after {self.timeout:g}s"
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            return f"{target} returned HTTP {status_code}"
        if isinstance(exc, ValueError):
            return f"{target} returned invalid JSON"
        detail = str(exc).strip()
        if detail:
            return f"{target} failed: {detail}"
        return f"{target} failed with {type(exc).__name__}"


def build_topic2_activation_probe_client() -> Topic2ActivationProbeClient:
    return Topic2ActivationProbeClient()
