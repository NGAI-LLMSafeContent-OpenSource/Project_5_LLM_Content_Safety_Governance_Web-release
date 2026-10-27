"""Tokenized, time-limited governance task review shares (#66 / #76)."""

from __future__ import annotations

import copy
import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GovernanceShareAccessEvent,
    GovernanceTask,
    GovernanceTaskShare,
    utc_now,
)
from app.services.governance_product_metrics import (
    emit_product_event,
    review_find_markers,
)

ACCESS_RESULT_OK = "ok"
ACCESS_RESULT_EXPIRED = "expired"
ACCESS_RESULT_REVOKED = "revoked"
ACCESS_RESULT_NOT_FOUND = "not_found"
ACCESS_RESULTS = frozenset(
    {
        ACCESS_RESULT_OK,
        ACCESS_RESULT_EXPIRED,
        ACCESS_RESULT_REVOKED,
        ACCESS_RESULT_NOT_FOUND,
    }
)


def hash_share_token(token: str) -> str:
    """Return SHA-256 hex digest of a plaintext share token (never store plaintext)."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _generate_share_token() -> str:
    return secrets.token_urlsafe(32)


async def _load_owned_task(
    db: AsyncSession, client_id: str, task_id: str
) -> GovernanceTask | None:
    result = await db.execute(
        select(GovernanceTask).where(
            GovernanceTask.task_id == task_id,
            GovernanceTask.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_share_by_token_hash(
    db: AsyncSession, token_hash: str
) -> GovernanceTaskShare | None:
    result = await db.execute(
        select(GovernanceTaskShare).where(GovernanceTaskShare.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


def _share_is_active(share: GovernanceTaskShare, *, now=None) -> bool:
    current = now if now is not None else utc_now()
    if share.revoked_at is not None:
        return False
    if share.expires_at <= current:
        return False
    return True


async def create_share(
    db: AsyncSession,
    client_id: str,
    task_id: str,
    *,
    ttl_days: int = 7,
    show_sample_text: bool = False,
) -> tuple[str, GovernanceTaskShare] | None:
    """Create a review share for a task owned by ``client_id``.

    Returns ``(plaintext_token, share_row)`` once. The plaintext token is never
    persisted; only its SHA-256 hex digest is stored. Returns ``None`` when the
    task is missing or not owned by ``client_id``.
    """
    if ttl_days < 1:
        raise ValueError("ttl_days must be >= 1")

    task = await _load_owned_task(db, client_id, task_id)
    if task is None:
        return None

    plaintext = _generate_share_token()
    now = utc_now()
    share = GovernanceTaskShare(
        share_id=str(uuid4()),
        task_id=task_id,
        client_id=client_id,
        token_hash=hash_share_token(plaintext),
        token_prefix=plaintext[:8],
        expires_at=now + timedelta(days=ttl_days),
        revoked_at=None,
        show_sample_text=bool(show_sample_text),
        created_at=now,
    )
    db.add(share)
    await db.flush()
    return plaintext, share


async def revoke_share(
    db: AsyncSession,
    client_id: str,
    task_id: str,
    share_id: str,
) -> GovernanceTaskShare | None:
    """Soft-revoke a share owned by ``client_id`` for ``task_id``.

    Returns the updated share row, or ``None`` when missing / not owned.
    """
    result = await db.execute(
        select(GovernanceTaskShare).where(
            GovernanceTaskShare.share_id == share_id,
            GovernanceTaskShare.task_id == task_id,
            GovernanceTaskShare.client_id == client_id,
        )
    )
    share = result.scalar_one_or_none()
    if share is None:
        return None
    if share.revoked_at is None:
        share.revoked_at = utc_now()
        await db.flush()
    return share


async def resolve_share_by_token(
    db: AsyncSession, token: str
) -> GovernanceTaskShare | None:
    """Resolve an active share by plaintext token via hash-only lookup.

    Returns ``None`` when the token is unknown, expired, or revoked.
    """
    share = await _load_share_by_token_hash(db, hash_share_token(token))
    if share is None:
        return None
    if not _share_is_active(share):
        return None
    return share


async def classify_share_token(db: AsyncSession, token: str) -> tuple[str, GovernanceTaskShare | None]:
    """Return ``(result, share_or_none)`` for audit without exposing active shares incorrectly.

    ``result`` is one of ok|expired|revoked|not_found. Active shares yield
    ``(ok, share)``; inactive rows still return the share for ``share_id`` audit.
    """
    share = await _load_share_by_token_hash(db, hash_share_token(token))
    if share is None:
        return ACCESS_RESULT_NOT_FOUND, None
    if share.revoked_at is not None:
        return ACCESS_RESULT_REVOKED, share
    if share.expires_at <= utc_now():
        return ACCESS_RESULT_EXPIRED, share
    return ACCESS_RESULT_OK, share


async def record_access_event(
    db: AsyncSession,
    *,
    result: str,
    share_id: str | None = None,
    viewer_meta: str | None = None,
) -> GovernanceShareAccessEvent:
    """Persist an append-only access audit event for a review-share attempt."""
    if result not in ACCESS_RESULTS:
        raise ValueError(f"unsupported access result: {result}")

    event = GovernanceShareAccessEvent(
        event_id=str(uuid4()),
        share_id=share_id,
        accessed_at=utc_now(),
        result=result,
        viewer_meta=viewer_meta,
    )
    db.add(event)
    await db.flush()
    return event


async def emit_review_find_success(
    db: AsyncSession,
    *,
    task_id: str,
    task_detail: dict,
    session_id: str | None = None,
) -> None:
    """Emit ``review_find_success`` when a resolved review payload has markers.

    Markers are boolean flags only (taxonomy / evidence / provenance). Sample
    text is never inspected or stored.
    """
    markers = review_find_markers(task_detail)
    if not any(markers.values()):
        return
    await emit_product_event(
        db,
        "review_find_success",
        session_id=session_id,
        task_id=task_id,
        attributes={
            "status": str(task_detail.get("status") or ""),
            "capability": str(task_detail.get("capability") or ""),
            **markers,
        },
    )


_SAMPLE_TEXT_KEYS = frozenset({"text", "content"})


def _redact_sample_texts_in_tree(node: object) -> None:
    """Recursively empty sensitive sample originals (``text`` / ``content`` strings)."""
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key in _SAMPLE_TEXT_KEYS and isinstance(value, str):
                node[key] = ""
            else:
                _redact_sample_texts_in_tree(value)
    elif isinstance(node, list):
        for item in node:
            _redact_sample_texts_in_tree(item)


def apply_share_disclosure(task_detail: dict, *, show_sample_text: bool) -> dict:
    """Return a deep-copied task detail with sample originals redacted when needed.

    When ``show_sample_text`` is False, strip/empty sample ``text`` / ``content``
    across the task payload (result samples, nested groups, run scopes). Keep
    conclusion, metrics, summary, provenance, digests, and labels.
    """
    detail = copy.deepcopy(task_detail)
    if show_sample_text:
        return detail
    _redact_sample_texts_in_tree(detail)
    return detail


# Top-level get_task fields that cue confirm / cancel / retry in the executable UI.
_REVIEW_ACTION_KEYS = frozenset(
    {
        "revised_plan",
        "available_actions",
        "allowed_actions",
        "next_actions",
        "confirm_url",
        "cancel_url",
        "retry_url",
    }
)


def scrub_review_actions(task_detail: dict) -> dict:
    """Null out executable action affordances for anonymous review payloads.

    Review shares must not invite confirm / cancel / retry. Call after
    ``apply_share_disclosure`` on the review route. Mutates a copied dict in
    place when already deep-copied; otherwise returns a deep copy.
    """
    detail = task_detail
    for key in _REVIEW_ACTION_KEYS:
        if key in detail:
            detail[key] = None
    return detail
