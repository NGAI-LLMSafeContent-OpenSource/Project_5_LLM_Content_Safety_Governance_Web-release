"""Cultural Gen backend HTTP client — proxies requests to Project_3_Cultural_Generation_Tool."""

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
CULTURE_ANALYZE_BASE = settings.cultural_gen_base_url.rstrip("/")
CULTURE_DATA_BASE = settings.cultural_gen_data_base_url.rstrip("/")

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), verify=False)
    return _http_client


async def _get_json(base_url: str, path: str) -> Any | None:
    try:
        client = await _get_client()
        resp = await client.get(f"{base_url}{path}")
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning("Cultural Gen GET %s%s failed: %s", base_url, path, exc)
        return None


async def _post_json(base_url: str, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
    try:
        client = await _get_client()
        resp = await client.post(f"{base_url}{path}", json=body)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning("Cultural Gen POST %s%s failed: %s", base_url, path, exc)
        return None


async def get_culture_samples_payload() -> dict[str, Any] | None:
    """Read samples from Cultural Gen data API, with legacy backend fallback."""
    data = await _get_json(CULTURE_DATA_BASE, "/samples")
    if isinstance(data, dict):
        data = data.get("samples")
    if isinstance(data, list):
        return {"samples": data, "integration_mode": "upstream_data_api"}

    fallback = await _get_json(CULTURE_ANALYZE_BASE, "/api/samples")
    if isinstance(fallback, dict):
        fallback = fallback.get("samples")
    if isinstance(fallback, list):
        return {"samples": fallback, "integration_mode": "legacy_backend_samples_api"}
    return None


async def get_culture_samples() -> list[dict[str, Any]] | None:
    payload = await get_culture_samples_payload()
    if not payload:
        return None
    samples = payload.get("samples")
    return samples if isinstance(samples, list) else None


async def analyze_culture(text: str) -> dict[str, Any] | None:
    """POST /api/analyze to Cultural Gen backend."""
    result = await _post_json(CULTURE_ANALYZE_BASE, "/api/analyze", {"text": text})
    if result and result.get("success"):
        return result["data"]
    return None
