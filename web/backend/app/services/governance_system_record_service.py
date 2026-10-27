"""Governance system prerun records (output domain).

System prerun records stay in the Benchmark asset registry; the governance layer
only reads them and returns a reference plus a presentation snapshot. Two hard
rules from #56:

* a system record never becomes a user governance completion record, and never
  creates a user session in the left-hand history;
* when the referenced asset is gone or its version changed, the result states
  that explicitly instead of letting the assistant fabricate a result.

Risk safety is the first record type (#56); cultural diversity (#57) is the
second on the same frame. Every record carries ``record_type`` so the assistant
and the frontend can distinguish and route the two types without one reusing
the other's fields.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.schemas.governance import (
    SYSTEM_RECORD_TYPE_CULTURAL,
    SYSTEM_RECORD_TYPE_CULTURAL_LABEL,
    SYSTEM_RECORD_TYPE_LABEL,
    SYSTEM_RECORD_TYPE_RISK,
    AssetSourceRef,
    CulturalSystemRecordDataset,
    CulturalSystemRecordSample,
    SystemRecordDataset,
    SystemRecordItem,
    SystemRecordModelResult,
    parse_iso_datetime,
)
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic3_cultural_asset_service import (
    BENCHMARK_TYPE as CULTURAL_BENCHMARK_TYPE,
)
from app.services.benchmark_topic3_risk_series_service import (
    BenchmarkTopic3RiskSeriesError,
    ResolvedTopic3RiskAsset,
    build_resolved_evaluation_summary,
    describe_asset,
    normalize_asset_version,
)
from app.services.benchmark_topic3_risk_sample_service import (
    BenchmarkTopic3RiskSampleError,
    BenchmarkTopic3RiskSampleService,
)
from app.services.benchmark_topic3_risk_v6_service import (
    BENCHMARK_TYPE as RISK_BENCHMARK_TYPE,
    RELEASE_KIND as RISK_V6_RELEASE_KIND,
    BenchmarkTopic3RiskV6Service,
)

PRERUN_SOURCE_MODE = "prerun_snapshot"

CULTURAL_SAMPLE_PREVIEW_LIMIT = 5

STATUS_LABELS: dict[str, str] = {
    "evaluation_imported": "评测结果已导入",
    "evaluation_pending": "评测结果待导入",
    "evaluation_unavailable": "评测结果不可用",
}

STATUS_IMPORTED = "evaluation_imported"
STATUS_PENDING = "evaluation_pending"

# The assistant maps a user's wording onto stored values; the parameter has no
# DB access at prompt-build time, so a few common synonyms are accepted here.
STATUS_ALIASES: dict[str, str] = {
    "completed": STATUS_IMPORTED,
    "complete": STATUS_IMPORTED,
    "imported": STATUS_IMPORTED,
    "done": STATUS_IMPORTED,
    "已完成": STATUS_IMPORTED,
    "完成": STATUS_IMPORTED,
    "已导入": STATUS_IMPORTED,
    "pending": STATUS_PENDING,
    "not_started": STATUS_PENDING,
    "pending_import": STATUS_PENDING,
    "未完成": STATUS_PENDING,
    "待导入": STATUS_PENDING,
}


def normalize_status(value: Any) -> str:
    normalized = _normalize(value)
    if not normalized:
        return ""
    return STATUS_ALIASES.get(normalized, normalized)


def _loads_manifest(asset: BenchmarkAsset) -> dict[str, Any]:
    try:
        data = json.loads(asset.manifest_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_bound(value: str | None, *, end_of_day: bool) -> datetime | None:
    """Parse a filter bound. A date-only bound is inclusive of that whole day,
    so ``completed_before=2026-09-22`` still matches records completed at
    2026-09-22T10:00Z."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    parsed = parse_iso_datetime(text)
    if parsed is None:
        return None
    date_only = len(text) == 10 and "T" not in text
    if date_only:
        if end_of_day:
            return datetime.combine(parsed.date(), time.max, tzinfo=timezone.utc)
        return datetime.combine(parsed.date(), time.min, tzinfo=timezone.utc)
    return parsed


def _evaluation_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    value = manifest.get("evaluation_results")
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _record_status(manifest: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    status = manifest.get("evaluation_status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    return STATUS_IMPORTED if entries else STATUS_PENDING


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status or "状态未知")


def _evaluated_at(entries: list[dict[str, Any]]) -> str | None:
    parsed = [
        value
        for value in (
            (entry.get("evaluated_at"), parse_iso_datetime(entry.get("evaluated_at")))
            for entry in entries
        )
        if value[1] is not None
    ]
    if parsed:
        parsed.sort(key=lambda item: item[1])
        return str(parsed[-1][0])
    raw = [str(entry.get("evaluated_at")) for entry in entries if entry.get("evaluated_at")]
    return sorted(raw)[-1] if raw else None


def _model_display_name(entry: dict[str, Any]) -> str:
    return str(
        entry.get("model_name")
        or entry.get("display_name")
        or entry.get("model_id")
        or "unknown"
    )


def _record_version(asset: BenchmarkAsset, manifest: dict[str, Any]) -> str:
    for candidate in (
        manifest.get("source_commit"),
        asset.source_commit,
        manifest.get("asset_sha256"),
        asset.artifact_sha256,
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _completed_at(asset: BenchmarkAsset, entries: list[dict[str, Any]]) -> str:
    latest = _evaluated_at(entries)
    parsed = parse_iso_datetime(latest)
    if parsed is not None:
        return _iso(parsed)
    created = asset.created_at
    if created is None:
        return ""
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return _iso(created)


def _is_risk_record(asset: BenchmarkAsset, manifest: dict[str, Any]) -> bool:
    if asset.source_mode != PRERUN_SOURCE_MODE:
        return False
    return manifest.get("benchmark_type") == RISK_BENCHMARK_TYPE


def _record_item(
    asset: BenchmarkAsset,
    manifest: dict[str, Any],
    *,
    asset_version: str | None,
    asset_status: str,
    asset_sha256: str,
) -> SystemRecordItem:
    entries = _evaluation_entries(manifest)
    model_names: list[str] = []
    for entry in entries:
        name = _model_display_name(entry)
        if name and name not in model_names:
            model_names.append(name)
    status = _record_status(manifest, entries)
    return SystemRecordItem(
        record_id=asset.asset_id,
        record_type=SYSTEM_RECORD_TYPE_RISK,
        record_type_label=SYSTEM_RECORD_TYPE_LABEL,
        name=asset.name or asset.asset_id,
        status=status,
        status_label=_status_label(status),
        source_repo=asset.source_repo or str(manifest.get("source_repo") or ""),
        source_commit=asset.source_commit or str(manifest.get("source_commit") or ""),
        record_version=_record_version(asset, manifest),
        asset_version=asset_version,
        asset_status=asset_status,
        asset_sha256=asset_sha256,
        sample_count=int(manifest.get("sample_count") or 0),
        model_names=model_names,
        has_evaluation=bool(entries),
        evaluated_at=_evaluated_at(entries),
        completed_at=_completed_at(asset, entries),
        created_at=_iso(asset.created_at) if asset.created_at else "",
    )


def _source_refs(asset: BenchmarkAsset, manifest: dict[str, Any]) -> list[AssetSourceRef]:
    return [
        AssetSourceRef(
            ref_type="benchmark_asset",
            ref_id=asset.asset_id,
            name=asset.name or asset.asset_id,
            source_repo=asset.source_repo or str(manifest.get("source_repo") or ""),
            source_commit=asset.source_commit or str(manifest.get("source_commit") or ""),
        )
    ]


async def _resolve_series_asset(
    db: AsyncSession, asset: BenchmarkAsset
) -> ResolvedTopic3RiskAsset | None:
    """Series identity for one asset, without letting one stale row hide the list.

    Registered assets use the server-owned resolver: the registry content hash,
    not the mutable manifest value, is the fact source. An asset outside the
    series (or one whose manifest no longer matches its registration) stays
    readable as ``unregistered`` instead of failing the whole page.
    """
    try:
        return await describe_asset(db, asset)
    except BenchmarkTopic3RiskSeriesError:
        return None


def _series_identity(
    resolved: ResolvedTopic3RiskAsset | None, asset: BenchmarkAsset
) -> tuple[str | None, str, str]:
    if resolved is None:
        manifest = _loads_manifest(asset)
        return (
            None,
            "unregistered",
            str(manifest.get("asset_sha256") or asset.artifact_sha256 or ""),
        )
    return resolved.asset_version, resolved.asset_status, resolved.asset_sha256


async def _risk_asset_entries(
    db: AsyncSession,
) -> list[tuple[BenchmarkAsset, str | None, str, str]]:
    registry = BenchmarkAssetRegistryService()
    assets = await registry.list_assets(db, source_mode=PRERUN_SOURCE_MODE)
    entries = []
    for asset in assets:
        if not _is_risk_record(asset, _loads_manifest(asset)):
            continue
        resolved = await _resolve_series_asset(db, asset)
        entries.append((asset, *_series_identity(resolved, asset)))
    return entries


def _select_record_entries(
    entries: list[tuple[BenchmarkAsset, str | None, str, str]],
    asset_version: str | None,
) -> list[tuple[BenchmarkAsset, str | None, str, str]]:
    """Default to the current series version; keep unregistered assets readable.

    An explicit version selects exactly that registered version. Historical
    versions are therefore never returned by an unspecified query, while
    assets outside the series keep their pre-#156 behaviour.
    """
    requested = normalize_asset_version(asset_version)
    if requested:
        return [entry for entry in entries if entry[1] == requested]
    has_current = any(entry[2] == "current" for entry in entries)
    if not has_current:
        return entries
    return [entry for entry in entries if entry[2] in {"current", "unregistered"}]


def _sort_key(item: SystemRecordItem) -> tuple[str, str]:
    return (item.completed_at or "", item.record_id)


async def list_risk_system_records(
    db: AsyncSession,
    *,
    source: str | None = None,
    status: str | None = None,
    asset_version: str | None = None,
    completed_after: str | None = None,
    completed_before: str | None = None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    entries = _select_record_entries(await _risk_asset_entries(db), asset_version)
    items = [
        (
            asset,
            _record_item(
                asset,
                _loads_manifest(asset),
                asset_version=version,
                asset_status=asset_status,
                asset_sha256=asset_sha256,
            ),
        )
        for asset, version, asset_status, asset_sha256 in entries
    ]

    source_filter = _normalize(source) or None
    status_filter = normalize_status(status) or None
    after = _parse_bound(completed_after, end_of_day=False)
    before = _parse_bound(completed_before, end_of_day=True)

    matched: list[tuple[BenchmarkAsset, SystemRecordItem]] = []
    for asset, item in items:
        if source_filter and _normalize(item.source_repo) != source_filter:
            continue
        if status_filter and _normalize(item.status) != status_filter:
            continue
        completed = parse_iso_datetime(item.completed_at)
        if after is not None and (completed is None or completed < after):
            continue
        if before is not None and (completed is None or completed > before):
            continue
        matched.append((asset, item))

    matched.sort(key=lambda pair: _sort_key(pair[1]), reverse=True)
    total = len(matched)
    page = matched[offset : offset + limit]
    return {
        "available": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": [item.model_dump() for _, item in page],
        "source_refs": [
            ref.model_dump()
            for asset, _ in page
            for ref in _source_refs(asset, _loads_manifest(asset))
        ],
    }


async def get_risk_system_record_asset(
    db: AsyncSession, record_id: str
) -> BenchmarkAsset | None:
    asset = await BenchmarkAssetRegistryService().get_asset(db, record_id)
    if asset is None:
        return None
    if not _is_risk_record(asset, _loads_manifest(asset)):
        return None
    return asset


def _dataset_from_manifest(manifest: dict[str, Any]) -> SystemRecordDataset:
    sample_count = manifest.get("sample_count")
    safe_total = manifest.get("safe_total") or manifest.get("safe_count") or 0
    risk_total = manifest.get("risk_total") or manifest.get("low_count") or 0
    risk_levels = manifest.get("risk_levels")
    risk_level_distribution = manifest.get("risk_level_distribution")
    if not isinstance(risk_level_distribution, dict) and isinstance(risk_levels, list):
        counts = {"safe": safe_total, "low": risk_total}
        risk_level_distribution = {
            str(level): int(counts.get(str(level), 0)) for level in risk_levels
        }
    return SystemRecordDataset(
        sample_count=int(sample_count) if isinstance(sample_count, int) else 0,
        safe_total=int(safe_total) if isinstance(safe_total, int) else 0,
        risk_total=int(risk_total) if isinstance(risk_total, int) else 0,
        taxonomy_schema=str(manifest.get("taxonomy_schema") or ""),
        category_distribution=_int_distribution(manifest.get("category_distribution")),
        language_distribution=_int_distribution(manifest.get("language_distribution")),
        culture_distribution=_int_distribution(manifest.get("culture_distribution")),
        risk_level_distribution=_int_distribution(risk_level_distribution),
    )


def _dataset_from_resolved_asset(
    manifest: dict[str, Any], resolved: ResolvedTopic3RiskAsset | None
) -> SystemRecordDataset:
    dataset = _dataset_from_manifest(manifest)
    if resolved is None or resolved.asset_version is None:
        return dataset
    try:
        summary = BenchmarkTopic3RiskSampleService().summarize_resolved_asset(resolved)
    except (BenchmarkTopic3RiskSampleError, OSError, UnicodeError, ValueError):
        return dataset
    return SystemRecordDataset(
        sample_count=int(summary.get("sample_count") or dataset.sample_count),
        safe_total=int(summary.get("safe_count") or 0),
        risk_total=int(summary.get("risk_count") or 0),
        taxonomy_schema=dataset.taxonomy_schema,
        category_distribution=_int_distribution(summary.get("category_distribution")),
        language_distribution=_int_distribution(summary.get("language_distribution")),
        culture_distribution=_int_distribution(summary.get("culture_distribution")),
        risk_level_distribution=_int_distribution(summary.get("risk_level_distribution")),
    )


def _int_distribution(value: Any) -> dict[str, int]:
    """Normalize a manifest distribution. Some manifests nest counts per level
    (``{"low": {"C01": 3}}``); flatten those by summing per key instead of
    coercing a dict into an int."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            result[str(key)] = raw
        elif isinstance(raw, dict):
            for nested_key, nested_raw in raw.items():
                if isinstance(nested_raw, int) and not isinstance(nested_raw, bool):
                    result[str(nested_key)] = result.get(str(nested_key), 0) + nested_raw
    return result


def _dataset_sample_summary(dataset: SystemRecordDataset) -> str:
    parts = [f"样本 {dataset.sample_count} 条（安全 {dataset.safe_total} / 风险 {dataset.risk_total}）"]
    if dataset.category_distribution:
        parts.append(f"覆盖 {len(dataset.category_distribution)} 类风险分类")
    if dataset.language_distribution:
        parts.append("语言 " + "、".join(sorted(dataset.language_distribution)))
    if dataset.culture_distribution:
        parts.append("文化 " + "、".join(sorted(dataset.culture_distribution)))
    return "；".join(parts)


def _models_from_summary(
    summary: dict[str, Any],
) -> tuple[list[SystemRecordModelResult], list[dict[str, str]], bool, str]:
    models = [
        SystemRecordModelResult(
            model_id=str(entry.get("model_id") or ""),
            model_name=str(entry.get("model_name") or ""),
            display_name=str(entry.get("display_name") or ""),
            model_version=str(entry.get("model_version") or ""),
            role=str(entry.get("role") or ""),
            run_id=str(entry.get("run_id") or ""),
            evaluated_at=str(entry.get("evaluated_at") or ""),
            predictions_count=int(entry.get("predictions_count") or 0),
            primary_metrics=entry.get("primary_metrics") or {},
            supporting_metrics=entry.get("supporting_metrics") or {},
            per_category_metrics=entry.get("per_category_metrics") or {},
        )
        for entry in summary.get("results", [])
    ]
    catalog = [
        {"key": str(metric.get("key") or ""), "display_name": str(metric.get("display_name") or "")}
        for metric in summary.get("primary_metrics", [])
    ]
    live_eval = summary.get("live_eval") or {}
    return models, catalog, bool(live_eval.get("enabled")), str(summary.get("status") or "")


def _models_from_v6(
    asset: BenchmarkAsset,
) -> tuple[list[SystemRecordModelResult], list[dict[str, str]], bool, str]:
    return _models_from_summary(BenchmarkTopic3RiskV6Service().build_evaluation_summary(asset))


async def build_risk_system_record_detail(
    db: AsyncSession, asset: BenchmarkAsset
) -> dict[str, Any]:
    from app.services.governance_risk_review_service import risk_review_support_fields

    manifest = _loads_manifest(asset)
    entries = _evaluation_entries(manifest)
    resolved = await _resolve_series_asset(db, asset)
    dataset = _dataset_from_resolved_asset(manifest, resolved)
    asset_version, asset_status, asset_sha256 = _series_identity(resolved, asset)
    is_v6 = manifest.get("release_kind") == RISK_V6_RELEASE_KIND
    if resolved is not None and resolved.asset_version is not None:
        # Registered series assets (v6, v7, ...) share one same-version summary.
        models, catalog, live_eval_enabled, status_override = _models_from_summary(
            build_resolved_evaluation_summary(resolved)
        )
    elif is_v6:
        models, catalog, live_eval_enabled, status_override = _models_from_v6(asset)
    else:
        # Unregistered non-v6 assets: dataset summary only. Do not splice
        # unrelated evaluation summaries into a single unverified metric set.
        models, catalog, live_eval_enabled, status_override = [], [], False, ""

    status = status_override or _record_status(manifest, entries)
    return {
        "available": True,
        "source_status": "ok",
        "record_id": asset.asset_id,
        "record_type": SYSTEM_RECORD_TYPE_RISK,
        "record_type_label": SYSTEM_RECORD_TYPE_LABEL,
        "name": asset.name or asset.asset_id,
        "status": status,
        "status_label": _status_label(status),
        "record_version": _record_version(asset, manifest),
        "asset_version": asset_version,
        "asset_status": asset_status,
        "source_repo": asset.source_repo or str(manifest.get("source_repo") or ""),
        "source_commit": asset.source_commit or str(manifest.get("source_commit") or ""),
        "asset_sha256": asset_sha256,
        "dataset": dataset.model_dump(),
        "models": [model.model_dump() for model in models],
        "primary_metrics": catalog,
        "sample_summary": _dataset_sample_summary(dataset),
        "live_eval_enabled": live_eval_enabled,
        "source_refs": [ref.model_dump() for ref in _source_refs(asset, manifest)],
        **risk_review_support_fields(asset),
    }


# ---------------------------------------------------------------------------
# Cultural diversity (#57)
# ---------------------------------------------------------------------------


def _safe_int(value: Any) -> int:
    try:
        if isinstance(value, bool):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        if isinstance(value, bool):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_cultural_record(asset: BenchmarkAsset, manifest: dict[str, Any]) -> bool:
    if asset.source_mode != PRERUN_SOURCE_MODE:
        return False
    return manifest.get("benchmark_type") == CULTURAL_BENCHMARK_TYPE


def _cultural_status(manifest: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    """Cultural assets expose ``model_eval_status`` (``pending_import`` by
    default) instead of the risk-safety ``evaluation_status``. Imported
    evaluation entries always win so status cannot contradict the data."""
    if entries:
        return STATUS_IMPORTED
    raw = normalize_status(manifest.get("model_eval_status"))
    if raw in (STATUS_IMPORTED, STATUS_PENDING):
        return raw
    return STATUS_PENDING


def _cultural_dataset(manifest: dict[str, Any]) -> CulturalSystemRecordDataset:
    return CulturalSystemRecordDataset(
        sample_count=_safe_int(manifest.get("sample_count")),
        review_passed_count=_safe_int(manifest.get("review_passed_count")),
        review_passed_rate=_safe_float(manifest.get("review_passed_rate")),
        quality_gate_overall=str(manifest.get("quality_gate_overall") or ""),
        difficulty_distribution=_int_distribution(manifest.get("difficulty_distribution")),
        ethnic_distribution=_int_distribution(manifest.get("ethnic_distribution")),
        background_type_distribution=_int_distribution(
            manifest.get("background_type_distribution")
        ),
        persona_distribution=_int_distribution(manifest.get("persona_distribution")),
        query_type_distribution=_int_distribution(manifest.get("query_type_distribution")),
        discard_counts=_int_distribution(manifest.get("discard_counts")),
    )


def _cultural_record_item(
    asset: BenchmarkAsset, manifest: dict[str, Any]
) -> dict[str, Any]:
    entries = _evaluation_entries(manifest)
    dataset = _cultural_dataset(manifest)
    status = _cultural_status(manifest, entries)
    return {
        "record_id": asset.asset_id,
        "record_type": SYSTEM_RECORD_TYPE_CULTURAL,
        "record_type_label": SYSTEM_RECORD_TYPE_CULTURAL_LABEL,
        "name": asset.name or asset.asset_id,
        "status": status,
        "status_label": _status_label(status),
        "source_repo": asset.source_repo or str(manifest.get("source_repo") or ""),
        "source_commit": asset.source_commit or str(manifest.get("source_commit") or ""),
        "record_version": _record_version(asset, manifest),
        "sample_count": dataset.sample_count,
        "difficulty_levels": sorted(dataset.difficulty_distribution),
        "ethnic_groups": sorted(dataset.ethnic_distribution),
        "background_types": sorted(dataset.background_type_distribution),
        "query_types": sorted(dataset.query_type_distribution),
        "review_passed_count": dataset.review_passed_count,
        "review_passed_rate": dataset.review_passed_rate,
        "quality_gate_overall": dataset.quality_gate_overall,
        "has_evaluation": bool(entries),
        "completed_at": _completed_at(asset, entries),
        "created_at": _iso(asset.created_at) if asset.created_at else "",
    }


async def _cultural_assets(db: AsyncSession) -> list[BenchmarkAsset]:
    registry = BenchmarkAssetRegistryService()
    assets = await registry.list_assets(db, source_mode=PRERUN_SOURCE_MODE)
    return [asset for asset in assets if _is_cultural_record(asset, _loads_manifest(asset))]


def _matches_dimension(values: list[str], requested: str | None) -> bool:
    if not requested:
        return True
    wanted = _normalize(requested)
    return any(_normalize(value) == wanted for value in values)


async def list_cultural_system_records(
    db: AsyncSession,
    *,
    source: str | None = None,
    status: str | None = None,
    completed_after: str | None = None,
    completed_before: str | None = None,
    difficulty_level: str | None = None,
    ethnic_group: str | None = None,
    background_type: str | None = None,
    query_type: str | None = None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    assets = await _cultural_assets(db)
    items: list[tuple[BenchmarkAsset, dict[str, Any], dict[str, Any]]] = []
    for asset in assets:
        manifest = _loads_manifest(asset)
        items.append((asset, manifest, _cultural_record_item(asset, manifest)))

    source_filter = _normalize(source) or None
    status_filter = normalize_status(status) or None
    after = _parse_bound(completed_after, end_of_day=False)
    before = _parse_bound(completed_before, end_of_day=True)

    matched: list[tuple[BenchmarkAsset, dict[str, Any], dict[str, Any]]] = []
    for asset, manifest, item in items:
        if source_filter and _normalize(item["source_repo"]) != source_filter:
            continue
        if status_filter and _normalize(item["status"]) != status_filter:
            continue
        completed = parse_iso_datetime(item["completed_at"])
        if after is not None and (completed is None or completed < after):
            continue
        if before is not None and (completed is None or completed > before):
            continue
        if not _matches_dimension(item["difficulty_levels"], difficulty_level):
            continue
        if not _matches_dimension(item["ethnic_groups"], ethnic_group):
            continue
        if not _matches_dimension(item["background_types"], background_type):
            continue
        if not _matches_dimension(item["query_types"], query_type):
            continue
        matched.append((asset, manifest, item))

    matched.sort(
        key=lambda pair: (pair[2]["completed_at"] or "", pair[2]["record_id"]),
        reverse=True,
    )
    total = len(matched)
    page = matched[offset : offset + limit]
    return {
        "available": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": [item for _, _, item in page],
        "source_refs": [
            ref.model_dump()
            for asset, manifest, _ in page
            for ref in _source_refs(asset, manifest)
        ],
    }


async def get_cultural_system_record_asset(
    db: AsyncSession, record_id: str
) -> BenchmarkAsset | None:
    asset = await BenchmarkAssetRegistryService().get_asset(db, record_id)
    if asset is None:
        return None
    if not _is_cultural_record(asset, _loads_manifest(asset)):
        return None
    return asset


def _preview(value: str, *, limit: int = 120) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _cultural_samples(
    asset: BenchmarkAsset, *, limit: int = CULTURAL_SAMPLE_PREVIEW_LIMIT
) -> list[CulturalSystemRecordSample]:
    """Read a bounded sample preview from the frozen asset's normalized
    samples.jsonl. A missing file yields no samples rather than fabricating
    rows; the distribution summary from the manifest still stands on its own."""
    samples_path = Path(asset.artifact_dir or "") / "samples.jsonl"
    if not samples_path.is_file():
        return []
    try:
        lines = samples_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    samples: list[CulturalSystemRecordSample] = []
    for line in lines:
        if len(samples) >= limit:
            break
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt") or raw.get("user_query") or "")
        samples.append(
            CulturalSystemRecordSample(
                sample_id=str(raw.get("sample_id") or raw.get("id") or ""),
                ethnic_group=str(
                    raw.get("ethnic_group") or raw.get("implied_ethnic_group") or ""
                ),
                difficulty_level=str(raw.get("difficulty_level") or ""),
                background_type=str(raw.get("background_type") or ""),
                persona=str(raw.get("persona") or ""),
                query_type=str(raw.get("query_type") or ""),
                prompt_preview=_preview(prompt),
            )
        )
    return samples


def _cultural_sample_summary(dataset: CulturalSystemRecordDataset) -> str:
    parts = [
        f"样本 {dataset.sample_count} 条，审校通过 {dataset.review_passed_count} 条"
        f"（{dataset.review_passed_rate:.0%}）"
    ]
    if dataset.difficulty_distribution:
        parts.append(
            "语境难度 "
            + "、".join(f"{key}×{value}" for key, value in sorted(dataset.difficulty_distribution.items()))
        )
    if dataset.ethnic_distribution:
        parts.append(f"覆盖 {len(dataset.ethnic_distribution)} 个民族")
    if dataset.quality_gate_overall:
        parts.append(f"质量门禁 {dataset.quality_gate_overall}")
    return "；".join(parts)


def build_cultural_system_record_detail(asset: BenchmarkAsset) -> dict[str, Any]:
    from app.services.governance_cultural_review_service import cultural_review_support_fields

    manifest = _loads_manifest(asset)
    entries = _evaluation_entries(manifest)
    dataset = _cultural_dataset(manifest)
    status = _cultural_status(manifest, entries)
    return {
        "available": True,
        "source_status": "ok",
        "record_id": asset.asset_id,
        "record_type": SYSTEM_RECORD_TYPE_CULTURAL,
        "record_type_label": SYSTEM_RECORD_TYPE_CULTURAL_LABEL,
        "name": asset.name or asset.asset_id,
        "status": status,
        "status_label": _status_label(status),
        "record_version": _record_version(asset, manifest),
        "source_repo": asset.source_repo or str(manifest.get("source_repo") or ""),
        "source_commit": asset.source_commit or str(manifest.get("source_commit") or ""),
        "asset_sha256": str(manifest.get("asset_sha256") or asset.artifact_sha256 or ""),
        "dataset": dataset.model_dump(),
        "samples": [sample.model_dump() for sample in _cultural_samples(asset)],
        "sample_summary": _cultural_sample_summary(dataset),
        "source_refs": [ref.model_dump() for ref in _source_refs(asset, manifest)],
        **cultural_review_support_fields(asset),
    }
