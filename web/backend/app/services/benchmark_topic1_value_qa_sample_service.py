from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.data_input_value_qa_common import VALUE_LEVEL_DISPLAY, VALUE_LEVEL_SCORE


BENCHMARK_TYPE = "value_qa"
QUALITY_LEVELS = ("high", "medium", "low")
QC_STATUSES = {"not_sampled", "qc_sampled"}


class BenchmarkTopic1ValueQaSampleError(RuntimeError):
    """Raised when topic1 value_qa groups cannot be read."""


class BenchmarkTopic1ValueQaSampleNotFoundError(BenchmarkTopic1ValueQaSampleError):
    """Raised when the requested asset or group does not exist."""


class BenchmarkTopic1ValueQaSampleService:
    async def get_recheck_summary(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
    ) -> dict[str, Any]:
        asset = await self._get_topic1_value_qa_asset(db, asset_id)
        index = _load_asset_index(asset)
        rows = index["rows"]
        manifest = _loads_json_object(asset.manifest_json)
        quality_report = _load_quality_report(asset)
        return _to_recheck_summary(rows, manifest, quality_report)

    async def list_groups(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        topic: str | None = None,
        primary_dimension: str | None = None,
        secondary_dimension: str | None = None,
        qc_status: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = await self._get_topic1_value_qa_asset(db, asset_id)
        groups = _load_asset_index(asset)["groups"]
        filtered = _filter_groups(
            list(groups.values()),
            topic=topic,
            primary_dimension=primary_dimension,
            secondary_dimension=secondary_dimension,
            qc_status=qc_status,
            keyword=keyword,
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        page = filtered[safe_offset : safe_offset + safe_limit]
        return {
            "asset_id": asset.asset_id,
            "total": len(filtered),
            "limit": safe_limit,
            "offset": safe_offset,
            "groups": [_to_group_item(asset.asset_id, item) for item in page],
        }

    async def get_group(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        group_id: str,
    ) -> dict[str, Any]:
        asset = await self._get_topic1_value_qa_asset(db, asset_id)
        item = _load_asset_index(asset)["groups"].get(group_id)
        if item is not None:
            return _to_group_detail(asset.asset_id, item)
        raise BenchmarkTopic1ValueQaSampleNotFoundError("group not found")

    async def list_group_details(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        keyword: str | None = None,
        topic: str | None = None,
        primary_dimension: str | None = None,
        secondary_dimension: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = await self._get_topic1_value_qa_asset(db, asset_id)
        groups = _load_asset_index(asset)["groups"]
        filtered = _filter_groups(
            list(groups.values()),
            topic=topic,
            primary_dimension=primary_dimension,
            secondary_dimension=secondary_dimension,
            qc_status=None,
            keyword=keyword,
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        page = filtered[safe_offset : safe_offset + safe_limit]
        return {
            "asset_id": asset.asset_id,
            "total": len(filtered),
            "limit": safe_limit,
            "offset": safe_offset,
            "group_ids": [str(item["group_id"]) for item in filtered],
            "groups": [_to_group_detail(asset.asset_id, item) for item in page],
        }

    async def _get_topic1_value_qa_asset(
        self,
        db: AsyncSession,
        asset_id: str,
    ) -> BenchmarkAsset:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkTopic1ValueQaSampleNotFoundError("asset not found")
        manifest = _loads_json_object(asset.manifest_json)
        if manifest.get("benchmark_type") != BENCHMARK_TYPE:
            raise BenchmarkTopic1ValueQaSampleError(
                "asset is not a topic1 value_qa benchmark asset"
            )
        artifact_dir = Path(asset.artifact_dir)
        if not artifact_dir.is_dir():
            raise BenchmarkTopic1ValueQaSampleError("asset artifact directory not found")
        return asset


def _load_asset_index(asset: BenchmarkAsset) -> dict[str, Any]:
    return _load_asset_index_cached(
        asset.asset_id,
        asset.artifact_sha256,
        asset.artifact_dir,
    )


@lru_cache(maxsize=32)
def _load_asset_index_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir_value)
    samples_path = artifact_dir / "samples.jsonl"
    if not samples_path.is_file():
        raise BenchmarkTopic1ValueQaSampleError("asset is missing samples.jsonl")
    group_preview_path = artifact_dir / "group_preview.jsonl"
    if not group_preview_path.is_file():
        raise BenchmarkTopic1ValueQaSampleError("asset is missing group_preview.jsonl")

    rows = _load_jsonl(samples_path, "samples.jsonl")
    _load_jsonl(group_preview_path, "group_preview.jsonl")
    groups = _build_groups(rows)
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "rows": rows,
        "groups": groups,
    }


def _load_jsonl(path: Path, display_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic1ValueQaSampleError(
                f"{display_name}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic1ValueQaSampleError(
                f"{display_name}:{line_number} must contain a JSON object"
            )
        rows.append(row)
    if not rows:
        raise BenchmarkTopic1ValueQaSampleError(f"{display_name} must not be empty")
    return rows


def _build_groups(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        group_id = _required_text(row.get("group_id"), "sample.group_id")
        quality_level = _required_text(row.get("quality_level"), f"{group_id}.quality_level")
        if quality_level not in QUALITY_LEVELS:
            raise BenchmarkTopic1ValueQaSampleError(
                f"{group_id}.quality_level must be high, medium or low"
            )
        group = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "topic": str(row.get("topic", "")),
                "primary_dimension": str(row.get("primary_dimension", "")),
                "secondary_dimension": str(row.get("secondary_dimension", "")),
                "levels": {},
            },
        )
        if quality_level in group["levels"]:
            raise BenchmarkTopic1ValueQaSampleError(
                f"group {group_id} contains duplicate {quality_level} sample"
            )
        group["levels"][quality_level] = row

    for group_id, group in grouped.items():
        if set(group["levels"]) != set(QUALITY_LEVELS):
            raise BenchmarkTopic1ValueQaSampleError(
                f"group {group_id} must contain high, medium and low samples"
            )
        group["qc_status"] = _group_qc_status(group)
    return dict(sorted(grouped.items()))


def _required_text(value: Any, label: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise BenchmarkTopic1ValueQaSampleError(f"{label} must not be empty")
    return text


def _group_qc_status(group: dict[str, Any]) -> str:
    for row in group["levels"].values():
        if row.get("qc_status") == "qc_sampled":
            return "qc_sampled"
    return "not_sampled"


def _filter_groups(
    groups: list[dict[str, Any]],
    *,
    topic: str | None,
    primary_dimension: str | None,
    secondary_dimension: str | None,
    qc_status: str | None,
    keyword: str | None,
) -> list[dict[str, Any]]:
    normalized_topic = _normalize_filter_text(topic)
    normalized_primary = _normalize_filter_text(primary_dimension)
    normalized_secondary = _normalize_filter_text(secondary_dimension)
    normalized_qc_status = _normalize_qc_status(qc_status)
    normalized_keyword = keyword.strip().lower() if keyword and keyword.strip() else None

    filtered: list[dict[str, Any]] = []
    for group in groups:
        if normalized_topic and group.get("topic") != normalized_topic:
            continue
        if normalized_primary and group.get("primary_dimension") != normalized_primary:
            continue
        if normalized_secondary and group.get("secondary_dimension") != normalized_secondary:
            continue
        if normalized_qc_status and group.get("qc_status") != normalized_qc_status:
            continue
        if normalized_keyword and not _group_contains_keyword(group, normalized_keyword):
            continue
        filtered.append(group)
    return filtered


def _normalize_filter_text(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _normalize_qc_status(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if normalized not in QC_STATUSES:
        raise BenchmarkTopic1ValueQaSampleError(
            "qc_status must be not_sampled or qc_sampled"
        )
    return normalized


def _group_contains_keyword(group: dict[str, Any], keyword: str) -> bool:
    values = [
        group.get("group_id", ""),
        group.get("topic", ""),
        group.get("primary_dimension", ""),
        group.get("secondary_dimension", ""),
    ]
    for row in group["levels"].values():
        values.extend([row.get("question", ""), row.get("answer", "")])
    haystack = "\n".join(str(value) for value in values).lower()
    return keyword in haystack


def _to_group_item(asset_id: str, group: dict[str, Any]) -> dict[str, Any]:
    return {
        "group_id": group["group_id"],
        "asset_id": asset_id,
        "topic": group["topic"],
        "primary_dimension": group["primary_dimension"],
        "secondary_dimension": group["secondary_dimension"],
        "qc_status": group["qc_status"],
        "levels": {
            level: {
                "sample_id": str(row.get("sample_id", "")),
                "question_preview": _preview(row.get("question")),
                "answer_preview": _preview(row.get("answer")),
                "qc_status": str(row.get("qc_status", "not_sampled")),
            }
            for level, row in _ordered_levels(group).items()
        },
    }


def _to_group_detail(asset_id: str, group: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "group_id": group["group_id"],
        "topic": group["topic"],
        "primary_dimension": group["primary_dimension"],
        "secondary_dimension": group["secondary_dimension"],
        "qc_status": group["qc_status"],
        "levels": {
            level: _to_level_detail(level, row)
            for level, row in _ordered_levels(group).items()
        },
    }


def _ordered_levels(group: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {level: group["levels"][level] for level in QUALITY_LEVELS}


def _to_level_detail(level: str, row: dict[str, Any]) -> dict[str, Any]:
    issue_count = row.get("trace_issue_count")
    raw = row.get("raw")
    raw = raw if isinstance(raw, dict) else {}
    return {
        "sample_id": str(row.get("sample_id", "")),
        "question": str(row.get("question", "")),
        "answer": str(row.get("answer", "")),
        "quality_level": level,
        "level_display": VALUE_LEVEL_DISPLAY.get(level, ""),
        "level_score": VALUE_LEVEL_SCORE.get(level, ""),
        "source_reference": row.get("source_reference")
        if isinstance(row.get("source_reference"), dict)
        else {},
        "source_documents": raw.get("source_refs")
        if isinstance(raw.get("source_refs"), list)
        else [],
        "evidence": raw.get("evidence") if isinstance(raw.get("evidence"), list) else [],
        "value_annotations": raw.get("value_annotations")
        if isinstance(raw.get("value_annotations"), list)
        else [],
        "missing_annotation_count": _safe_int(row.get("missing_annotation_count")),
        "prompt_snapshot": str(row.get("prompt_snapshot", "")),
        "manual_marked_at": row.get("manual_marked_at"),
        "qc_status": str(row.get("qc_status", "not_sampled")),
        "trace_predicted_level": row.get("trace_predicted_level"),
        "trace_true_label": row.get("trace_true_label"),
        "trace_is_consistent": row.get("trace_is_consistent"),
        "trace_match_status": row.get("trace_match_status"),
        "trace_issue_count": _safe_int(issue_count) if issue_count is not None else None,
        "trace_low_issue_spans": row.get("trace_low_issue_spans")
        if isinstance(row.get("trace_low_issue_spans"), list)
        else [],
    }


def _to_recheck_summary(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace_report = {}
    if isinstance(quality_report, dict):
        trace = quality_report.get("trace")
        trace_report = trace if isinstance(trace, dict) else {}
    sample_count = len(rows)
    prediction_rows = [
        row for row in rows if _normalize_label(row.get("trace_predicted_level"))
    ]
    prediction_count = len(prediction_rows)
    true_labels = [
        _trace_true_label(row)
        for row in prediction_rows
        if _trace_true_label(row) in QUALITY_LEVELS
    ]
    predicted_labels = [
        _normalize_label(row.get("trace_predicted_level"))
        for row in prediction_rows
        if _normalize_label(row.get("trace_predicted_level")) in QUALITY_LEVELS
    ]
    correct_count = sum(
        1
        for row in prediction_rows
        if _trace_true_label(row) in QUALITY_LEVELS
        and _normalize_label(row.get("trace_predicted_level")) == _trace_true_label(row)
    )

    low_issue_sample_count = 0
    issue_count = 0
    issue_type_distribution: Counter[str] = Counter()
    for row in rows:
        row_issue_count = _trace_issue_total(row)
        if row_issue_count > 0:
            low_issue_sample_count += 1
            issue_count += row_issue_count
            issue_type_distribution.update(_trace_issue_types(row))

    trace_status = str(manifest.get("trace_status") or "").strip()
    has_recheck = prediction_count > 0 or low_issue_sample_count > 0
    status = "imported" if has_recheck or trace_status == "imported" else "not_imported"
    scope = "partial_quality_recheck" if has_recheck else "none"
    if trace_report.get("scope") == "full_sample_join":
        scope = "full_sample_join"
    return {
        "status": status,
        "scope": scope,
        "sample_count": sample_count,
        "prediction_count": prediction_count,
        "coverage_ratio": prediction_count / sample_count if sample_count else 0.0,
        "correct_count": correct_count,
        "accuracy": correct_count / prediction_count if prediction_count else 0.0,
        "mismatch_count": prediction_count - correct_count,
        "true_label_distribution": dict(Counter(true_labels)),
        "predicted_label_distribution": dict(Counter(predicted_labels)),
        "low_issue_sample_count": low_issue_sample_count,
        "issue_count": issue_count,
        "issue_type_distribution": dict(issue_type_distribution),
        "run_metadata": trace_report.get("run_metadata") or {},
        "source_schema": trace_report.get("source_schema") or "",
        "source_file": trace_report.get("source_file") or manifest.get("trace_source_file"),
        "gold_distribution": trace_report.get("gold_distribution") or {},
        "is_formal_model_eval": False,
    }


def _load_quality_report(asset: BenchmarkAsset) -> dict[str, Any] | None:
    path = Path(asset.artifact_dir) / "quality_report.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _trace_true_label(row: dict[str, Any]) -> str:
    return _normalize_label(row.get("trace_true_label") or row.get("quality_level"))


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _trace_issue_total(row: dict[str, Any]) -> int:
    spans = row.get("trace_low_issue_spans")
    if isinstance(spans, list) and spans:
        total = 0
        for item in spans:
            total += _issue_entry_count(item)
        return total
    issue_count = row.get("trace_issue_count")
    return _safe_int(issue_count) if issue_count is not None else 0


def _issue_entry_count(item: Any) -> int:
    if not isinstance(item, dict):
        return 1
    value = item.get("issue_count")
    if value is not None:
        parsed = _safe_int(value)
        if parsed > 0:
            return parsed
    issues = item.get("issues")
    if isinstance(issues, list) and issues:
        return len(issues)
    return 1


def _trace_issue_types(row: dict[str, Any]) -> list[str]:
    spans = row.get("trace_low_issue_spans")
    if not isinstance(spans, list):
        return []
    types: list[str] = []
    for item in spans:
        if not isinstance(item, dict):
            continue
        nested = item.get("issues")
        if isinstance(nested, list):
            for issue in nested:
                if isinstance(issue, dict):
                    issue_type = str(issue.get("type") or "").strip()
                    if issue_type:
                        types.append(issue_type)
        issue_type = str(item.get("type") or item.get("issue_type") or "").strip()
        if issue_type:
            types.append(issue_type)
    return types


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _preview(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
