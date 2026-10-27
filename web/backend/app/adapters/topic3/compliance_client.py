"""HTTP client for Project_3_Compliance_Editing_Tool."""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ComplianceEditError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _unwrap_payload(body: object) -> dict:
    if not isinstance(body, dict):
        raise ComplianceEditError("合规服务返回格式无效")
    data = body.get("data")
    if isinstance(data, dict):
        return data
    return body


async def edit_compliance_text(
    text: str,
    request_id: str,
    language: str = "zh",
    pre_safety_label: str = "unsafe",
) -> dict:
    settings = get_settings()
    url = f"{settings.compliance_edit_base_url.rstrip('/')}/api/v1/compliance/edit"
    timeout = httpx.Timeout(settings.compliance_edit_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(
                url,
                json={
                    "text": text,
                    "request_id": request_id,
                    "pre_safety_label": pre_safety_label,
                    "language": language,
                },
            )
            resp.raise_for_status()
            return _unwrap_payload(resp.json())
    except httpx.TimeoutException as exc:
        logger.warning("compliance edit timeout: %s", url)
        raise httpx.TimeoutException(str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("compliance edit HTTP %s", exc.response.status_code)
        raise ComplianceEditError(f"合规服务返回 HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.warning("compliance edit unreachable: %s", url)
        raise httpx.RequestError(str(exc), request=exc.request) from exc
