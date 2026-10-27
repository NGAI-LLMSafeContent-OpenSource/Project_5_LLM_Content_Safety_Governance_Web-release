"""Read-only CBRNE anomaly seedbank governance capabilities (#120 / Spec #116 T4).

Benchmark registry + query/detail services remain the single fact source.
This module only projects registered facts into governance payloads: no second
dataset copy, no Activation Probe / evaluator calls, no executable eval actions.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.schemas.governance import AssetSourceRef
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_cbrne_dataset_query_service import (
    BenchmarkCbrneDatasetQueryError,
    BenchmarkCbrneDatasetQueryNotFoundError,
    BenchmarkCbrneDatasetQueryService,
)
from app.services.benchmark_cbrne_dataset_snapshot_service import (
    BENCHMARK_TYPE,
    SOURCE_MODE,
)

CBRNE_REF_TYPE = "cbrne_anomaly_seedbank"
CBRNE_SEARCH_DEFAULT_LIMIT = 10
CBRNE_SEARCH_MAX_LIMIT = 50


class GovernanceCbrneDatasetError(RuntimeError):
    """Raised for invalid CBRNE governance filter/asset requests."""


class GovernanceCbrneDatasetNotFoundError(GovernanceCbrneDatasetError):
    """Raised when no matching CBRNE dataset_snapshot asset exists."""


def benchmark_asset_href(asset_id: str) -> str:
    return f"/benchmark/assets/{quote(asset_id, safe='')}"


def benchmark_sample_href(asset_id: str, sample_id: str) -> str:
    return f"{benchmark_asset_href(asset_id)}/samples/{quote(sample_id, safe='')}"


def _loads_manifest(asset: BenchmarkAsset) -> dict[str, Any]:
    try:
        payload = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_cbrne_asset(asset: BenchmarkAsset, manifest: dict[str, Any]) -> bool:
    return (
        asset.source_mode == SOURCE_MODE
        and manifest.get("benchmark_type") == BENCHMARK_TYPE
    )


def _record_version(asset: BenchmarkAsset, manifest: dict[str, Any]) -> str:
    return str(
        manifest.get("dataset_content_sha256")
        or manifest.get("version")
        or asset.artifact_sha256
        or ""
    )


def _source_ref(asset: BenchmarkAsset, manifest: dict[str, Any]) -> AssetSourceRef:
    return AssetSourceRef(
        ref_type=CBRNE_REF_TYPE,
        ref_id=asset.asset_id,
        name=str(manifest.get("name") or asset.name or asset.asset_id),
        source_repo=str(manifest.get("source_repo") or asset.source_repo or ""),
        source_commit=str(manifest.get("source_commit") or asset.source_commit or ""),
    )


def _int_distribution(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        try:
            result[str(key)] = int(raw)
        except (TypeError, ValueError):
            continue
    return dict(sorted(result.items()))


async def _cbrne_assets(db: AsyncSession) -> list[tuple[BenchmarkAsset, dict[str, Any]]]:
    assets = await BenchmarkAssetRegistryService().list_assets(
        db, source_mode=SOURCE_MODE
    )
    matched: list[tuple[BenchmarkAsset, dict[str, Any]]] = []
    for asset in assets:
        manifest = _loads_manifest(asset)
        if _is_cbrne_asset(asset, manifest):
            matched.append((asset, manifest))
    matched.sort(
        key=lambda item: (
            0 if bool(item[1].get("is_current")) else 1,
            str(item[1].get("version") or ""),
            item[0].asset_id,
        )
    )
    return matched


async def resolve_cbrne_asset(
    db: AsyncSession, asset_id: str | None = None
) -> tuple[BenchmarkAsset, dict[str, Any]]:
    matched = await _cbrne_assets(db)
    if asset_id:
        for asset, manifest in matched:
            if asset.asset_id == asset_id:
                return asset, manifest
        raise GovernanceCbrneDatasetNotFoundError("asset not found")
    for asset, manifest in matched:
        if bool(manifest.get("is_current")):
            return asset, manifest
    if matched:
        return matched[0]
    raise GovernanceCbrneDatasetNotFoundError("no CBRNE dataset_snapshot asset registered")


async def list_cbrne_dataset_assets(db: AsyncSession) -> dict[str, Any]:
    matched = await _cbrne_assets(db)
    records = []
    source_refs: list[AssetSourceRef] = []
    for asset, manifest in matched:
        ref = _source_ref(asset, manifest)
        source_refs.append(ref)
        records.append(
            {
                "asset_id": asset.asset_id,
                "asset_name": ref.name,
                "asset_version": str(manifest.get("version") or ""),
                "record_version": _record_version(asset, manifest),
                "is_current": bool(manifest.get("is_current")),
                "sample_count": int(manifest.get("sample_count") or 0),
                "source_repo": ref.source_repo,
                "source_commit": ref.source_commit,
                "benchmark_href": benchmark_asset_href(asset.asset_id),
                "resource_ref": {
                    "kind": "benchmark.cbrne_asset",
                    "asset_id": asset.asset_id,
                },
            }
        )
    return {
        "available": bool(records),
        "total": len(records),
        "records": records,
        "source_refs": [ref.model_dump() for ref in source_refs],
    }


async def build_cbrne_dataset_overview(
    db: AsyncSession, *, asset_id: str | None = None
) -> dict[str, Any]:
    try:
        asset, manifest = await resolve_cbrne_asset(db, asset_id)
    except GovernanceCbrneDatasetNotFoundError:
        return {
            "available": False,
            "asset_id": asset_id,
            "asset_name": None,
            "asset_version": "",
            "record_version": "",
            "is_current": False,
            "sample_count": 0,
            "label_counts": {},
            "cbrne_category_counts": {},
            "source_counts": {},
            "exposure_tier_counts": {},
            "evaluator_relative_difficulty_counts": {},
            "difficulty_definition": "",
            "source_limitations": [],
            "licence_notes": "",
            "benchmark_href": None,
            "resource_ref": None,
            "source_refs": [],
        }

    stats = manifest.get("platform_stats")
    if not isinstance(stats, dict):
        stats = manifest.get("delivery_profile")
    if not isinstance(stats, dict):
        stats = {}

    ref = _source_ref(asset, manifest)
    return {
        "available": True,
        "asset_id": asset.asset_id,
        "asset_name": ref.name,
        "asset_version": str(manifest.get("version") or ""),
        "record_version": _record_version(asset, manifest),
        "is_current": bool(manifest.get("is_current")),
        "sample_count": int(stats.get("sample_count") or manifest.get("sample_count") or 0),
        "label_counts": _int_distribution(stats.get("label_counts")),
        "cbrne_category_counts": _int_distribution(stats.get("cbrne_category_counts")),
        "source_counts": _int_distribution(stats.get("source_counts")),
        "exposure_tier_counts": _int_distribution(stats.get("exposure_tier_counts")),
        "evaluator_relative_difficulty_counts": _int_distribution(
            stats.get("evaluator_relative_difficulty_counts")
        ),
        "difficulty_definition": str(manifest.get("difficulty_definition") or ""),
        "source_limitations": [
            str(item)
            for item in (manifest.get("source_limitations") or [])
            if str(item).strip()
        ],
        "licence_notes": str(manifest.get("licence_notes") or ""),
        "benchmark_href": benchmark_asset_href(asset.asset_id),
        "resource_ref": {
            "kind": "benchmark.cbrne_asset",
            "asset_id": asset.asset_id,
        },
        "source_refs": [ref.model_dump()],
    }


async def search_cbrne_dataset_samples(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
    label: str | None = None,
    cbrne_category: str | None = None,
    source: str | None = None,
    exposure_tier: str | None = None,
    difficulty_min: int | None = None,
    difficulty_max: int | None = None,
    limit: int = CBRNE_SEARCH_DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        asset, manifest = await resolve_cbrne_asset(db, asset_id)
    except GovernanceCbrneDatasetNotFoundError as exc:
        raise GovernanceCbrneDatasetNotFoundError(str(exc)) from exc

    try:
        listed = await BenchmarkCbrneDatasetQueryService().query_samples(
            db,
            asset_id=asset.asset_id,
            label=label,
            cbrne_category=cbrne_category,
            source=source,
            exposure_tier=exposure_tier,
            difficulty_min=difficulty_min,
            difficulty_max=difficulty_max,
            limit=limit,
            offset=offset,
        )
    except BenchmarkCbrneDatasetQueryNotFoundError as exc:
        raise GovernanceCbrneDatasetNotFoundError(str(exc)) from exc
    except BenchmarkCbrneDatasetQueryError as exc:
        raise GovernanceCbrneDatasetError(str(exc)) from exc

    samples = []
    for item in listed.get("samples") or []:
        sample_id = str(item.get("sample_id") or "")
        samples.append(
            {
                "sample_id": sample_id,
                "label": str(item.get("label") or ""),
                "cbrne_category": str(item.get("cbrne_category") or ""),
                "source": str(item.get("source") or ""),
                "exposure_tier": str(item.get("exposure_tier") or ""),
                "evaluator_relative_difficulty": int(
                    item.get("evaluator_relative_difficulty") or 0
                ),
                "text_excerpt": str(item.get("text_excerpt") or ""),
                "resource_ref": item.get("resource_ref")
                or {
                    "kind": "benchmark.cbrne_sample",
                    "asset_id": asset.asset_id,
                    "sample_id": sample_id,
                },
                "benchmark_href": benchmark_sample_href(asset.asset_id, sample_id),
            }
        )

    ref = _source_ref(asset, manifest)
    query = listed.get("query") if isinstance(listed.get("query"), dict) else {}
    return {
        "available": True,
        "asset_id": asset.asset_id,
        "asset_name": ref.name,
        "asset_version": str(listed.get("asset_version") or manifest.get("version") or ""),
        "record_version": str(
            listed.get("record_version") or _record_version(asset, manifest)
        ),
        "query": query,
        "filters": {
            key: value
            for key, value in query.items()
            if value is not None and value != ""
        },
        "total": int(listed.get("total") or 0),
        "limit": int(listed.get("limit") or limit),
        "offset": int(listed.get("offset") or offset),
        "distributions": listed.get("distributions") or {},
        "samples": samples,
        "benchmark_href": benchmark_asset_href(asset.asset_id),
        "resource_ref": {
            "kind": "benchmark.cbrne_asset",
            "asset_id": asset.asset_id,
        },
        "source_refs": [ref.model_dump()],
        "execute_actions": [],
    }


async def refuse_cbrne_full_text(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
    sample_id: str,
) -> dict[str, Any]:
    """Explain disclosure policy and return a Benchmark detail link; never text."""
    cleaned_sample = str(sample_id or "").strip()
    try:
        asset, manifest = await resolve_cbrne_asset(db, asset_id)
    except GovernanceCbrneDatasetNotFoundError:
        return {
            "available": False,
            "disclosure": "full_text_benchmark_detail_only",
            "asset_id": asset_id,
            "sample_id": cleaned_sample,
            "asset_version": "",
            "record_version": "",
            "benchmark_href": None,
            "resource_ref": None,
            "source_refs": [],
            "full_text": None,
        }

    ref = _source_ref(asset, manifest)
    href = (
        benchmark_sample_href(asset.asset_id, cleaned_sample)
        if cleaned_sample
        else benchmark_asset_href(asset.asset_id)
    )
    return {
        "available": True,
        "disclosure": "full_text_benchmark_detail_only",
        "asset_id": asset.asset_id,
        "sample_id": cleaned_sample,
        "asset_version": str(manifest.get("version") or ""),
        "record_version": _record_version(asset, manifest),
        "benchmark_href": href,
        "resource_ref": {
            "kind": "benchmark.cbrne_sample",
            "asset_id": asset.asset_id,
            "sample_id": cleaned_sample,
        }
        if cleaned_sample
        else {
            "kind": "benchmark.cbrne_asset",
            "asset_id": asset.asset_id,
        },
        "source_refs": [ref.model_dump()],
        "full_text": None,
    }
