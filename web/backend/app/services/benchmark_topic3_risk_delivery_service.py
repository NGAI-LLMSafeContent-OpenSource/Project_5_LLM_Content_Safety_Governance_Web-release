"""Benchmark management import: receive, stage and validate delivery packages (#151).

Every upload streams into its own ``<staging_root>/.attempts/<attempt_id>``
directory. The delivery record is claimed first (the primary key arbitrates
concurrent uploads) and every later state change is conditional on the
claiming ``attempt_id``. Only the claiming attempt moves its validated staging
into ``<staging_root>/<delivery_id>``, while it holds the record's write lock.

A delivery is never registered as a Benchmark asset here, so ordinary
Benchmark queries and the current version are unaffected. Publishing a
publishable delivery is a separate, explicit step (#152) that claims
``publishing`` with the same ``attempt_id`` conditional update.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import uuid
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkDelivery, utc_now
from app.services.benchmark_topic3_risk_delivery_validation import (
    DeliveryLimits,
    empty_report,
    validate_delivery_package,
)
from app.services.benchmark_topic3_risk_identity import sha256_file


logger = logging.getLogger(__name__)


class _StringEnum(str, Enum):
    """Python 3.10-compatible string enum with ``StrEnum`` semantics."""

    def __str__(self) -> str:
        return self.value


class DeliveryStatus(_StringEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    PUBLISHABLE = "publishable"
    PUBLISHING = "publishing"
    PUBLISHED = "published"


_SETTLED_STATUSES = frozenset(
    {
        DeliveryStatus.VALIDATION_FAILED,
        DeliveryStatus.PUBLISHABLE,
        DeliveryStatus.PUBLISHED,
    }
)


class PublishClaim(_StringEnum):
    CLAIMED = "claimed"
    IDEMPOTENT = "idempotent"
    IN_PROGRESS = "in_progress"
    NOT_PUBLISHABLE = "not_publishable"
    NOT_FOUND = "not_found"


class ReceiveOutcome(_StringEnum):
    # This request staged and validated the package.
    VALIDATED = "validated"
    # The same package was already settled; the record is returned unchanged.
    EXISTING = "existing"
    # Another live attempt is still importing the same package.
    IN_PROGRESS = "in_progress"


PACKAGE_FILE = "package.zip"
CONTENT_DIR = "content"
_ATTEMPTS_DIR = ".attempts"
_CHUNK_SIZE = 1024 * 1024


class UploadedPackage(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class BenchmarkDeliveryError(RuntimeError):
    """Raised when an uploaded delivery package cannot be accepted."""


class BenchmarkDeliveryTooLargeError(BenchmarkDeliveryError):
    pass


class BenchmarkDeliveryConflictError(BenchmarkDeliveryError):
    pass


def staging_root() -> Path:
    return Path(get_settings().benchmark_delivery_staging_root)


def delivery_limits() -> DeliveryLimits:
    settings = get_settings()
    return DeliveryLimits(
        max_entries=settings.benchmark_delivery_max_entries,
        max_entry_bytes=settings.benchmark_delivery_max_entry_bytes,
        max_total_bytes=settings.benchmark_delivery_max_total_bytes,
        max_compression_ratio=settings.benchmark_delivery_max_compression_ratio,
    )


async def receive_delivery(
    db: AsyncSession,
    *,
    delivery_id: str,
    upload: UploadedPackage,
    uploaded_by: str,
) -> tuple[BenchmarkDelivery, ReceiveOutcome]:
    """Stage and validate an uploaded package.

    Idempotent on ``(delivery_id, package sha256)``: a settled delivery with the
    same package is returned unchanged, one still being imported by a live
    attempt is reported in progress, and a stale unsettled one is taken over
    and re-validated. A different package for an existing delivery id is
    rejected without storing anything.
    """
    root = staging_root()
    attempt_id = uuid.uuid4().hex
    attempt_dir = root / _ATTEMPTS_DIR / attempt_id
    attempt_dir.mkdir(parents=True)
    try:
        package_sha256, package_size = await _receive(
            upload,
            attempt_dir / PACKAGE_FILE,
            get_settings().benchmark_delivery_max_package_bytes,
        )
        row, claimed = await _claim(
            db,
            delivery_id=delivery_id,
            attempt_id=attempt_id,
            package_sha256=package_sha256,
            package_size=package_size,
            uploaded_by=uploaded_by,
        )
        if not claimed:
            return row, _outcome_of(row)
        return await _validate_claimed(db, delivery_id, attempt_id, attempt_dir, package_sha256)
    finally:
        shutil.rmtree(attempt_dir, ignore_errors=True)


async def get_delivery(db: AsyncSession, delivery_id: str) -> BenchmarkDelivery | None:
    return await db.get(BenchmarkDelivery, delivery_id)


async def begin_publish(db: AsyncSession, delivery_id: str) -> tuple[BenchmarkDelivery | None, PublishClaim]:
    """Claim ``publishing`` for one publish attempt.

    A published delivery is returned unchanged. Two overlapping publish
    requests cannot both claim the same ``attempt_id``. A stale ``publishing``
    record can be taken over here; an upload cannot.
    """
    row = await get_delivery(db, delivery_id)
    if row is None:
        return None, PublishClaim.NOT_FOUND
    if row.status == DeliveryStatus.PUBLISHED:
        return row, PublishClaim.IDEMPOTENT
    now = utc_now()
    stale_after = timedelta(seconds=get_settings().benchmark_delivery_stale_seconds)
    if row.status == DeliveryStatus.PUBLISHING and now - row.updated_at < stale_after:
        return row, PublishClaim.IN_PROGRESS
    if row.status not in {DeliveryStatus.PUBLISHABLE, DeliveryStatus.PUBLISHING}:
        return row, PublishClaim.NOT_PUBLISHABLE

    attempt_id = uuid.uuid4().hex
    owner = BenchmarkDelivery.attempt_id
    result = await db.execute(
        update(BenchmarkDelivery)
        .where(
            BenchmarkDelivery.delivery_id == delivery_id,
            owner.is_(None) if row.attempt_id is None else owner == row.attempt_id,
            BenchmarkDelivery.status == row.status,
        )
        .values(status=DeliveryStatus.PUBLISHING, attempt_id=attempt_id, updated_at=now)
    )
    await db.commit()
    if result.rowcount != 1:
        current = await get_delivery(db, delivery_id)
        if current is not None and current.status == DeliveryStatus.PUBLISHED:
            return current, PublishClaim.IDEMPOTENT
        if current is not None and current.status == DeliveryStatus.PUBLISHING:
            return current, PublishClaim.IN_PROGRESS
        return current, PublishClaim.NOT_PUBLISHABLE
    return await _reload(db, delivery_id), PublishClaim.CLAIMED


async def mark_delivery_published(db: AsyncSession, delivery_id: str, attempt_id: str) -> bool:
    """Move a claimed delivery to ``published`` without committing."""
    return await _update_owned(
        db,
        delivery_id,
        attempt_id,
        status=DeliveryStatus.PUBLISHED,
        updated_at=utc_now(),
    )


async def release_publish_claim(db: AsyncSession, delivery_id: str, attempt_id: str) -> None:
    """Return a claimed publish to ``publishable`` after a failed attempt."""
    await db.rollback()
    owned = await _update_owned(
        db,
        delivery_id,
        attempt_id,
        status=DeliveryStatus.PUBLISHABLE,
        updated_at=utc_now(),
    )
    if owned:
        await db.commit()
    else:
        await db.rollback()


async def _claim(
    db: AsyncSession,
    *,
    delivery_id: str,
    attempt_id: str,
    package_sha256: str,
    package_size: int,
    uploaded_by: str,
) -> tuple[BenchmarkDelivery, bool]:
    now = utc_now()
    db.add(
        BenchmarkDelivery(
            delivery_id=delivery_id,
            package_sha256=package_sha256,
            package_size=package_size,
            status=DeliveryStatus.UPLOADED,
            uploaded_by=uploaded_by,
            attempt_id=attempt_id,
            report_json="{}",
            received_at=now,
            updated_at=now,
        )
    )
    try:
        await db.commit()
        return await _reload(db, delivery_id), True
    except IntegrityError:
        await db.rollback()

    row = await _reload(db, delivery_id)
    if row.package_sha256 != package_sha256:
        raise BenchmarkDeliveryConflictError(
            f"delivery {delivery_id} already exists with a different package sha256"
        )
    # A publish claim is released only by the publish step, including when it
    # has gone stale. An upload must not restart a delivery that is publishing.
    if row.status == DeliveryStatus.PUBLISHING:
        return row, False
    stale_after = timedelta(seconds=get_settings().benchmark_delivery_stale_seconds)
    if row.status in _SETTLED_STATUSES or now - row.updated_at < stale_after:
        return row, False
    owner = BenchmarkDelivery.attempt_id
    result = await db.execute(
        update(BenchmarkDelivery)
        .where(
            BenchmarkDelivery.delivery_id == delivery_id,
            owner.is_(None) if row.attempt_id is None else owner == row.attempt_id,
            BenchmarkDelivery.updated_at == row.updated_at,
        )
        .values(
            attempt_id=attempt_id,
            status=DeliveryStatus.UPLOADED,
            package_size=package_size,
            staging_dir=None,
            report_json="{}",
            validated_at=None,
            updated_at=now,
        )
    )
    await db.commit()
    if result.rowcount == 1:
        logger.warning("Taking over stale Benchmark delivery import: %s", delivery_id)
    return await _reload(db, delivery_id), result.rowcount == 1


async def _validate_claimed(
    db: AsyncSession,
    delivery_id: str,
    attempt_id: str,
    attempt_dir: Path,
    package_sha256: str,
) -> tuple[BenchmarkDelivery, ReceiveOutcome]:
    if not await _update_owned(db, delivery_id, attempt_id, status=DeliveryStatus.VALIDATING):
        return await _lost_claim(db, delivery_id)
    await db.commit()

    report = await _validate(attempt_dir, delivery_id)
    if not report["errors"]:
        staged_sha256 = await asyncio.to_thread(sha256_file, attempt_dir / PACKAGE_FILE)
        if staged_sha256 != package_sha256:
            report["errors"].append(
                {
                    "code": "package_hash_mismatch",
                    "message": "staged package changed during validation; upload it again",
                }
            )
    if report["errors"]:
        return await _settle(db, delivery_id, attempt_id, report, final_dir=None)

    final_dir = staging_root() / delivery_id
    try:
        return await _settle(
            db, delivery_id, attempt_id, report, final_dir=final_dir, staged=attempt_dir
        )
    except OSError:
        logger.exception("Benchmark delivery staging failed: %s", delivery_id)
        await db.rollback()
        report["errors"].append(
            {"code": "staging_internal_error", "message": "staging stopped unexpectedly"}
        )
        return await _settle(db, delivery_id, attempt_id, report, final_dir=None)


async def _settle(
    db: AsyncSession,
    delivery_id: str,
    attempt_id: str,
    report: dict[str, Any],
    *,
    final_dir: Path | None,
    staged: Path | None = None,
) -> tuple[BenchmarkDelivery, ReceiveOutcome]:
    identity = report["manifest"] or {}
    now = utc_now()
    owned = await _update_owned(
        db,
        delivery_id,
        attempt_id,
        status=DeliveryStatus.VALIDATION_FAILED if final_dir is None else DeliveryStatus.PUBLISHABLE,
        staging_dir=None if final_dir is None else str(final_dir),
        provider=identity.get("provider", ""),
        series_id=identity.get("series_id", ""),
        asset_id=identity.get("asset_id", ""),
        asset_version=identity.get("asset_version", ""),
        report_json=json.dumps(report, ensure_ascii=False),
        validated_at=now,
        updated_at=now,
    )
    if not owned:
        return await _lost_claim(db, delivery_id)
    if final_dir is not None and staged is not None:
        # The uncommitted update holds the record's write lock, so no other
        # attempt can claim it while the staging directory is moved into place.
        _discard_leftover(final_dir)
        os.replace(staged, final_dir)
    await db.commit()
    return await _reload(db, delivery_id), ReceiveOutcome.VALIDATED


async def _update_owned(
    db: AsyncSession, delivery_id: str, attempt_id: str, **values: Any
) -> bool:
    values.setdefault("updated_at", utc_now())
    result = await db.execute(
        update(BenchmarkDelivery)
        .where(
            BenchmarkDelivery.delivery_id == delivery_id,
            BenchmarkDelivery.attempt_id == attempt_id,
        )
        .values(**values)
    )
    return result.rowcount == 1


async def _lost_claim(
    db: AsyncSession, delivery_id: str
) -> tuple[BenchmarkDelivery, ReceiveOutcome]:
    await db.rollback()
    logger.warning("Benchmark delivery import lost its claim: %s", delivery_id)
    row = await _reload(db, delivery_id)
    return row, _outcome_of(row)


async def _reload(db: AsyncSession, delivery_id: str) -> BenchmarkDelivery:
    row = await db.get(BenchmarkDelivery, delivery_id, populate_existing=True)
    if row is None:
        raise BenchmarkDeliveryConflictError(
            f"delivery {delivery_id} changed during the upload; retry"
        )
    return row


def _outcome_of(row: BenchmarkDelivery) -> ReceiveOutcome:
    if row.status in _SETTLED_STATUSES:
        return ReceiveOutcome.EXISTING
    return ReceiveOutcome.IN_PROGRESS


def _discard_leftover(final_dir: Path) -> None:
    """Removes a delivery directory left by an attempt that crashed before committing."""
    if not final_dir.exists():
        return
    graveyard = final_dir.parent / _ATTEMPTS_DIR / f"{uuid.uuid4().hex}.leftover"
    os.replace(final_dir, graveyard)
    shutil.rmtree(graveyard, ignore_errors=True)


async def _receive(upload: UploadedPackage, target: Path, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with target.open("xb") as sink:
        while chunk := await upload.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise BenchmarkDeliveryTooLargeError(
                    f"delivery package exceeds the {max_bytes}-byte limit"
                )
            digest.update(chunk)
            sink.write(chunk)
    return digest.hexdigest(), size


async def _validate(attempt_dir: Path, delivery_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            validate_delivery_package,
            attempt_dir / PACKAGE_FILE,
            attempt_dir / CONTENT_DIR,
            delivery_id=delivery_id,
            limits=delivery_limits(),
        )
    except Exception:
        logger.exception("Benchmark delivery validation crashed: %s", delivery_id)
        report = empty_report()
        report["errors"].append(
            {"code": "validation_internal_error", "message": "validation stopped unexpectedly"}
        )
        return report
