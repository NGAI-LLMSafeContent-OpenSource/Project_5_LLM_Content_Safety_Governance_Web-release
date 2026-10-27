"""Controlled CBRNE sample detail + access audit (#119 / Spec #116 T3).

Additive to dataset_snapshot import. Does not broaden prerun_snapshot or own
filtered list UI (T2). Sample-refs expose stable IDs/previews only.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset, BenchmarkSampleAccessEvent, utc_now
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_cbrne_dataset_snapshot_service import (
    BENCHMARK_TYPE,
    SCHEMA_ID,
    SOURCE_MODE,
)

ACTION_TYPE_FULL_TEXT_DETAIL = "benchmark_sample_full_text_detail"
ACTION_TYPE_FULL_TEXT_DISCLOSURE = "benchmark_sample_full_text_disclosure"
TEXT_FIELD_CANDIDATES = ("prompt", "text", "content", "instruction", "query")
PREVIEW_MAX_CHARS = 40


class BenchmarkCbrneSampleDetailError(RuntimeError):
    """Raised when a CBRNE detail/refs request cannot be satisfied."""


class BenchmarkCbrneSampleDetailNotFoundError(BenchmarkCbrneSampleDetailError):
    """Raised when the requested asset version or sample does not exist."""


class BenchmarkCbrneSampleDisclosureConflictError(BenchmarkCbrneSampleDetailError):
    """Raised when a disclosure request identity is reused for another target."""


class BenchmarkCbrneSampleDetailService:
    async def disclose_sample(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        sample_id: str,
        disclosure_request_id: str,
    ) -> dict[str, Any]:
        asset, manifest, index = await self._load_cbrne_asset(db, asset_id)
        requested, row = _require_sample(index, sample_id)
        asset_version = str(manifest.get("version") or index["asset_version"] or "")
        access_event = await _find_disclosure_event(db, disclosure_request_id)
        if access_event is not None:
            _require_matching_disclosure_target(
                access_event,
                asset_id=asset.asset_id,
                asset_version=asset_version,
                sample_id=requested,
            )
            return _detail_payload(asset.asset_id, asset_version, requested, row, access_event)

        candidate = BenchmarkSampleAccessEvent(
            event_id=str(uuid4()),
            asset_id=asset.asset_id,
            asset_version=asset_version,
            sample_id=requested,
            action_type=ACTION_TYPE_FULL_TEXT_DISCLOSURE,
            disclosure_request_id=disclosure_request_id,
        )
        try:
            async with db.begin_nested():
                db.add(candidate)
                await db.flush()
            access_event = candidate
        except IntegrityError:
            access_event = await _find_disclosure_event(db, disclosure_request_id)
            if access_event is None:
                raise
            _require_matching_disclosure_target(
                access_event,
                asset_id=asset.asset_id,
                asset_version=asset_version,
                sample_id=requested,
            )
        await db.commit()
        return _detail_payload(asset.asset_id, asset_version, requested, row, access_event)

    async def list_sample_refs(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset, _manifest, index = await self._load_cbrne_asset(db, asset_id)
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        ordered_ids = index["ordered_ids"]
        page_ids = ordered_ids[safe_offset : safe_offset + safe_limit]
        items = [_to_ref_item(index["by_sample_id"][sample_id]) for sample_id in page_ids]
        return {
            "asset_id": asset.asset_id,
            "asset_version": str(index["asset_version"]),
            "total": len(ordered_ids),
            "limit": safe_limit,
            "offset": safe_offset,
            "items": items,
        }

    async def get_sample_ref(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        """Exact masked identity for a stable sample deep link (#175).

        Reads only the sample reference projection: never the full text, and
        never a full-text access event.
        """

        asset, manifest, index = await self._load_cbrne_asset(db, asset_id)
        requested, row = _require_sample(index, sample_id)
        asset_version = str(manifest.get("version") or index["asset_version"] or "")
        return {
            "asset_id": asset.asset_id,
            "asset_version": asset_version,
            **_to_ref_item(row),
        }

    async def get_sample_detail(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        asset, manifest, index = await self._load_cbrne_asset(db, asset_id)
        requested, row = _require_sample(index, sample_id)

        asset_version = str(manifest.get("version") or index["asset_version"] or "")
        access_event = await _record_access_event(
            db,
            asset_id=asset.asset_id,
            asset_version=asset_version,
            sample_id=requested,
            action_type=ACTION_TYPE_FULL_TEXT_DETAIL,
        )
        await db.commit()

        return _detail_payload(asset.asset_id, asset_version, requested, row, access_event)

    async def _load_cbrne_asset(
        self,
        db: AsyncSession,
        asset_id: str,
    ) -> tuple[BenchmarkAsset, dict[str, Any], dict[str, Any]]:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkCbrneSampleDetailNotFoundError("asset not found")
        manifest = _loads_json_object(asset.manifest_json)
        if (
            asset.source_mode != SOURCE_MODE
            or manifest.get("benchmark_type") != BENCHMARK_TYPE
            or not str(manifest.get("schema_id") or "").startswith(SCHEMA_ID.rsplit(".", 1)[0])
        ):
            raise BenchmarkCbrneSampleDetailError(
                "asset is not a CBRNE dataset_snapshot asset"
            )
        artifact_dir = Path(asset.artifact_dir)
        if not artifact_dir.is_dir():
            raise BenchmarkCbrneSampleDetailError("asset artifact directory not found")
        index = _load_asset_index(
            asset.asset_id,
            asset.artifact_sha256,
            asset.artifact_dir,
            str(manifest.get("version") or ""),
        )
        return asset, manifest, index


async def _record_access_event(
    db: AsyncSession,
    *,
    asset_id: str,
    asset_version: str,
    sample_id: str,
    action_type: str,
    disclosure_request_id: str | None = None,
) -> BenchmarkSampleAccessEvent:
    event = BenchmarkSampleAccessEvent(
        event_id=str(uuid4()),
        asset_id=asset_id,
        asset_version=asset_version,
        sample_id=sample_id,
        action_type=action_type,
        disclosure_request_id=disclosure_request_id,
        accessed_at=utc_now(),
    )
    db.add(event)
    await db.flush()
    return event


def _require_sample(index: dict[str, Any], sample_id: str) -> tuple[str, dict[str, Any]]:
    requested = str(sample_id or "").strip()
    if not requested:
        raise BenchmarkCbrneSampleDetailNotFoundError("sample not found")
    row = index["by_sample_id"].get(requested)
    if row is None:
        raise BenchmarkCbrneSampleDetailNotFoundError("sample not found")
    return requested, row


def _detail_payload(
    asset_id: str,
    asset_version: str,
    sample_id: str,
    row: dict[str, Any],
    access_event: BenchmarkSampleAccessEvent,
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "asset_version": asset_version,
        "sample_id": sample_id,
        "full_text": row["full_text"],
        "raw": copy.deepcopy(row["raw"]),
        "platform_normalized": dict(row["platform_normalized"]),
        "access_event": {
            "event_id": access_event.event_id,
            "asset_id": access_event.asset_id,
            "asset_version": access_event.asset_version,
            "sample_id": access_event.sample_id,
            "action_type": access_event.action_type,
            "accessed_at": access_event.accessed_at.isoformat(),
            "disclosure_request_id": access_event.disclosure_request_id,
        },
    }


async def _find_disclosure_event(
    db: AsyncSession, disclosure_request_id: str
) -> BenchmarkSampleAccessEvent | None:
    return await db.scalar(
        select(BenchmarkSampleAccessEvent).where(
            BenchmarkSampleAccessEvent.disclosure_request_id == disclosure_request_id
        )
    )


def _require_matching_disclosure_target(
    event: BenchmarkSampleAccessEvent,
    *,
    asset_id: str,
    asset_version: str,
    sample_id: str,
) -> None:
    if (
        event.asset_id != asset_id
        or event.asset_version != asset_version
        or event.sample_id != sample_id
        or event.action_type != ACTION_TYPE_FULL_TEXT_DISCLOSURE
    ):
        raise BenchmarkCbrneSampleDisclosureConflictError(
            "disclosure request identity is already bound to another target"
        )


def _load_asset_index(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
    asset_version: str,
) -> dict[str, Any]:
    return _load_asset_index_cached(
        asset_id, artifact_sha256, artifact_dir_value, asset_version
    )


@lru_cache(maxsize=32)
def _load_asset_index_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
    asset_version: str,
) -> dict[str, Any]:
    del artifact_sha256  # cache key only
    dataset_path = Path(artifact_dir_value) / "dataset.jsonl"
    if not dataset_path.is_file():
        raise BenchmarkCbrneSampleDetailError("dataset.jsonl not found for asset")
    by_sample_id: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    for line_number, line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkCbrneSampleDetailError(
                f"invalid JSON in dataset.jsonl:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkCbrneSampleDetailError(
                f"dataset.jsonl:{line_number} must contain a JSON object"
            )
        sample_id = str(row.get("id") or "").strip()
        if not sample_id:
            raise BenchmarkCbrneSampleDetailError(
                f"dataset.jsonl:{line_number}.id must be a non-empty string"
            )
        if sample_id in by_sample_id:
            raise BenchmarkCbrneSampleDetailError(f"duplicate sample id: {sample_id}")
        text_field, full_text = _extract_full_text(row)
        by_sample_id[sample_id] = {
            "sample_id": sample_id,
            "raw": row,
            "full_text": full_text,
            "platform_normalized": {
                "sample_id": sample_id,
                "label": str(row.get("label") or "").strip(),
                "cbrne_category": str(row.get("cbrne_category") or "").strip(),
                "source": str(row.get("source") or "").strip(),
                "exposure_tier": str(row.get("exposure_tier") or "").strip(),
                "evaluator_relative_difficulty": int(
                    row.get("evaluator_relative_difficulty") or 0
                ),
                "text_field": text_field,
            },
        }
        ordered_ids.append(sample_id)
    return {
        "asset_id": asset_id,
        "asset_version": asset_version,
        "by_sample_id": by_sample_id,
        "ordered_ids": ordered_ids,
    }


def _extract_full_text(row: dict[str, Any]) -> tuple[str, str]:
    for field in TEXT_FIELD_CANDIDATES:
        value = row.get(field)
        if isinstance(value, str):
            return field, value
    return "prompt", ""


def _to_ref_item(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = entry["platform_normalized"]
    preview = _mask_preview(entry["full_text"])
    return {
        "sample_id": entry["sample_id"],
        "label": normalized["label"],
        "cbrne_category": normalized["cbrne_category"],
        "source": normalized["source"],
        "exposure_tier": normalized["exposure_tier"],
        "evaluator_relative_difficulty": normalized["evaluator_relative_difficulty"],
        "text_preview": preview,
    }


def _mask_preview(text: str) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return ""
    # Always truncate with ellipsis so list/refs never equal source full text.
    visible = min(PREVIEW_MAX_CHARS, max(8, len(compact) // 2))
    return compact[:visible] + "…"


def _loads_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
