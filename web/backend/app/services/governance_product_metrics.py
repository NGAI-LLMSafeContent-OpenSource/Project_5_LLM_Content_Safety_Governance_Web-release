"""Anonymized governance product-funnel metrics (#67 / #83).

Online events store only hashed identifiers and whitelist attributes. Sample
text, credentials, prompts, and raw upstream payloads are rejected/stripped.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import GovernanceProductEvent, utc_now

logger = logging.getLogger(__name__)

PRODUCT_EVENT_NAMES = frozenset(
    {
        "goal_recognized",
        "plan_first_pass_ok",
        "task_completed",
        "task_completed_partial",
        "time_to_first_event_ms",
        "confirm_abandoned",
        "retry_recovered",
        "suggestion_continued",
        "review_find_success",
        "unsupported_rejected",
    }
)

# Structured funnel attributes only — never corpus or auth material.
ALLOWED_ATTRIBUTE_KEYS = frozenset(
    {
        "skill_key",
        "skill_version",
        "domain",
        "provider",
        "status",
        "latency_ms",
        "capability",
        "parse_status",
        "error_code",
        "suggestion_id",
        "handling",
        "attempt",
        "scope_selection",
        "has_taxonomy",
        "has_evidence",
        "has_provenance",
        "first_pass",
        "recovered",
        "partial",
    }
)

_FORBIDDEN_KEY_EXACT = frozenset(
    {
        "text",
        "content",
        "prompt",
        "sample_text",
        "samples",
        "api_key",
        "authorization",
        "password",
        "token",
        "share_token",
        "raw",
        "raw_body",
        "upstream",
        "upstream_raw",
        "message",
        "body",
        "credential",
        "credentials",
        "session_id",
        "task_id",
        "client_id",
    }
)

_FORBIDDEN_KEY_PATTERN = re.compile(
    r"(sample.?text|api.?key|authorization|password|raw.?body|upstream|credential|prompt|content)",
    re.IGNORECASE,
)

_ALLOWED_ATTR_TYPES = (bool, int, float, str, type(None))


def hash_governance_id(value: str | None) -> str | None:
    """SHA-256 hex digest of a session/task id; ``None`` stays ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_forbidden_key(key: str) -> bool:
    lowered = key.strip().lower()
    if lowered in _FORBIDDEN_KEY_EXACT:
        return True
    if lowered in ALLOWED_ATTRIBUTE_KEYS:
        return False
    return _FORBIDDEN_KEY_PATTERN.search(lowered) is not None


def sanitize_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep whitelist keys with scalar values; strip/reject forbidden fields."""

    if not attributes:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        name = str(key)
        if name not in ALLOWED_ATTRIBUTE_KEYS:
            continue
        if _is_forbidden_key(name):
            continue
        if not isinstance(value, _ALLOWED_ATTR_TYPES):
            continue
        if isinstance(value, str) and len(value) > 128:
            # Avoid accidentally persisting long free-text under a whitelist key.
            continue
        cleaned[name] = value
    return cleaned


def review_find_markers(task_detail: Mapping[str, Any] | None) -> dict[str, bool]:
    """Derive taxonomy/evidence/provenance presence flags without reading sample text."""

    detail = task_detail or {}
    result = detail.get("result")
    result_map = result if isinstance(result, Mapping) else {}

    has_taxonomy = bool(
        result_map.get("taxonomy_schema")
        or result_map.get("taxonomy")
        or (
            isinstance(result_map.get("filters"), Mapping)
            and result_map["filters"].get("taxonomy")
        )
    )
    has_evidence = bool(
        result_map.get("evidence")
        or result_map.get("source_refs")
        or detail.get("runs")
    )
    provenance = result_map.get("runs") or result_map.get("run_provenance")
    has_provenance = bool(provenance) or bool(detail.get("runs"))
    return {
        "has_taxonomy": has_taxonomy,
        "has_evidence": has_evidence,
        "has_provenance": has_provenance,
    }


async def emit_product_event(
    db: AsyncSession,
    event_name: str,
    *,
    session_id: str | None = None,
    task_id: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> GovernanceProductEvent | None:
    """Persist one anonymized product event when metrics are enabled.

    Unknown event names and empty/disabled sinks are no-ops (return ``None``).
    Forbidden attribute keys are stripped before persistence.
    """

    settings = get_settings()
    if not getattr(settings, "governance_product_metrics_enabled", True):
        return None
    if event_name not in PRODUCT_EVENT_NAMES:
        logger.warning("ignoring unknown governance product event: %s", event_name)
        return None

    safe_attrs = sanitize_attributes(attributes)
    event = GovernanceProductEvent(
        event_id=str(uuid4()),
        event_name=event_name,
        occurred_at=occurred_at or utc_now(),
        session_id_hash=hash_governance_id(session_id),
        task_id_hash=hash_governance_id(task_id),
        attributes_json=json.dumps(safe_attrs, ensure_ascii=False, sort_keys=True),
    )
    db.add(event)
    await db.flush()
    return event


def match_suggestion_id(
    prompt: str, suggestions: list[Mapping[str, Any]] | None
) -> str | None:
    """Return suggestion ``id`` when ``prompt`` exactly matches a candidate prompt."""

    text = (prompt or "").strip()
    if not text or not suggestions:
        return None
    for item in suggestions:
        if str(item.get("prompt") or "").strip() == text:
            suggestion_id = str(item.get("id") or "").strip()
            return suggestion_id or None
    return None


def attributes_contain_sensitive(payload: Mapping[str, Any] | str | None) -> bool:
    """Test helper: True when a stored payload still carries forbidden keys/values."""

    if payload is None:
        return False
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            lowered = payload.lower()
            return any(
                marker in lowered
                for marker in (
                    "api_key",
                    "authorization",
                    "sample_text",
                    "sensitive",
                )
            )
    else:
        data = payload
    if not isinstance(data, Mapping):
        return False
    for key in data:
        if _is_forbidden_key(str(key)):
            return True
        if str(key) not in ALLOWED_ATTRIBUTE_KEYS:
            return True
    return False
