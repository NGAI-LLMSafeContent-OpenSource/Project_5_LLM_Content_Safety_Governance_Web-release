from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset


SOURCE_MODE = "prerun_snapshot"
AGENT_ID = "topic1-value-qa"
BENCHMARK_TYPE = "value_qa"
SCHEMA_ID = "topic1.value_qa.v0.1"
QUALITY_LEVELS = ("high", "medium", "low")


class BenchmarkTopic1ValueQaAssetError(RuntimeError):
    """Raised when a topic1 value_qa dataset cannot be imported."""


class BenchmarkTopic1ValueQaAssetService:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def import_dataset(
        self,
        db: AsyncSession,
        *,
        samples_path: str | Path | None = None,
        marks_path: str | Path | None = None,
        qc_index_path: str | Path | None = None,
        qc_samples_path: str | Path | None = None,
        qc_scores_path: str | Path | None = None,
        qc_summary_path: str | Path | None = None,
        trace_predictions_path: str | Path | None = None,
        trace_low_issues_path: str | Path | None = None,
        asset_id: str | None = None,
        name: str | None = None,
    ) -> BenchmarkAsset:
        settings = get_settings()
        source_paths = _resolve_source_paths(
            samples_path=samples_path,
            marks_path=marks_path,
            qc_index_path=qc_index_path,
            qc_samples_path=qc_samples_path,
            qc_scores_path=qc_scores_path,
            qc_summary_path=qc_summary_path,
            trace_predictions_path=trace_predictions_path,
            trace_low_issues_path=trace_low_issues_path,
            settings=settings,
        )
        resolved_asset_id = _clean_asset_id(asset_id) or (
            f"topic1_value_qa_{uuid.uuid4().hex[:12]}"
        )

        existing = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == resolved_asset_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise BenchmarkTopic1ValueQaAssetError(
                f"asset already exists: {resolved_asset_id}"
            )

        raw_rows = _load_jsonl(source_paths["samples"], "samples_path")
        normalized_rows = _normalize_sample_rows(
            raw_rows,
            prompt_snapshot=settings.topic1_value_qa_prompt_snapshot,
        )
        groups = _validate_complete_triplets(normalized_rows)

        marks_summary = _apply_marks(normalized_rows, source_paths.get("marks"))
        qc_summary = _apply_qc(
            normalized_rows,
            groups,
            index_path=source_paths.get("qc_index"),
            samples_path=source_paths.get("qc_samples"),
            scores_path=source_paths.get("qc_scores"),
            summary_path=source_paths.get("qc_summary"),
        )
        trace_summary = _apply_trace(
            normalized_rows,
            predictions_path=source_paths.get("trace_predictions"),
            low_issues_path=source_paths.get("trace_low_issues"),
        )

        root_dir = self._artifact_root() / "prerun" / resolved_asset_id
        if root_dir.exists():
            raise BenchmarkTopic1ValueQaAssetError(
                f"asset directory already exists: {root_dir}"
            )
        artifacts_dir = root_dir / "artifacts"

        try:
            root_dir.mkdir(parents=True, exist_ok=False)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            _copy_raw_inputs(root_dir, source_paths)

            _write_jsonl(root_dir / "samples.jsonl", normalized_rows)
            _write_jsonl(root_dir / "group_preview.jsonl", _group_preview(groups))

            quality_report = _build_quality_report(
                rows=normalized_rows,
                groups=groups,
                marks_summary=marks_summary,
                qc_summary=qc_summary,
                trace_summary=trace_summary,
            )
            (root_dir / "quality_report.json").write_text(
                json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _write_lineage(root_dir / "lineage.jsonl", source_paths)
            _write_readme(root_dir / "README.md", resolved_asset_id)

            manifest = _build_manifest(
                asset_id=resolved_asset_id,
                name=name or "Topic1 Value QA verified prerun snapshot",
                source_repo=settings.topic1_value_qa_source_repo,
                source_commit=settings.topic1_value_qa_source_commit,
                source_samples_path=source_paths["samples"],
                rows=normalized_rows,
                groups=groups,
                quality_report=quality_report,
            )
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            archive_path = artifacts_dir / "topic1_value_qa_prerun_artifacts.zip"
            _write_asset_zip(root_dir, archive_path)
            artifact_sha256 = _sha256_file(archive_path)
            manifest["checksums"] = {"artifact_zip_sha256": artifact_sha256}
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            shutil.rmtree(root_dir, ignore_errors=True)
            raise

        asset = BenchmarkAsset(
            asset_id=resolved_asset_id,
            task_id=f"prerun_{resolved_asset_id[:56]}",
            source_mode=SOURCE_MODE,
            name=str(manifest["name"]),
            manifest_json=json.dumps(manifest, ensure_ascii=False),
            artifact_dir=str(root_dir),
            artifact_zip_path=str(archive_path),
            artifact_sha256=artifact_sha256,
            source_repo=str(manifest["source_repo"]),
            source_commit=str(manifest["source_commit"]),
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset


def _resolve_source_paths(
    *,
    samples_path: str | Path | None,
    marks_path: str | Path | None,
    qc_index_path: str | Path | None,
    qc_samples_path: str | Path | None,
    qc_scores_path: str | Path | None,
    qc_summary_path: str | Path | None,
    trace_predictions_path: str | Path | None,
    trace_low_issues_path: str | Path | None,
    settings: Any,
) -> dict[str, Path]:
    return {
        "samples": _resolve_required_file(
            samples_path or settings.topic1_value_qa_default_samples_path,
            "samples_path",
        ),
        **_resolve_optional_files(
            {
                "marks": marks_path or settings.topic1_value_qa_default_marks_path,
                "qc_index": qc_index_path
                or settings.topic1_value_qa_default_qc_index_path,
                "qc_samples": qc_samples_path
                or settings.topic1_value_qa_default_qc_samples_path,
                "qc_scores": qc_scores_path
                or settings.topic1_value_qa_default_qc_scores_path,
                "qc_summary": qc_summary_path
                or settings.topic1_value_qa_default_qc_summary_path,
                "trace_predictions": trace_predictions_path
                or settings.topic1_value_qa_default_trace_predictions_path,
                "trace_low_issues": trace_low_issues_path
                or settings.topic1_value_qa_default_trace_low_issues_path,
            }
        ),
    }


def _resolve_required_file(value: str | Path | None, label: str) -> Path:
    if not value:
        raise BenchmarkTopic1ValueQaAssetError(
            f"{label} is required when no default topic1 value_qa path is configured"
        )
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise BenchmarkTopic1ValueQaAssetError(f"{label} not found: {path}")
    return path


def _resolve_optional_files(values: dict[str, str | Path | None]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for label, value in values.items():
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise BenchmarkTopic1ValueQaAssetError(f"{label} not found: {path}")
        paths[label] = path
    return paths


def _clean_asset_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cleaned):
        raise BenchmarkTopic1ValueQaAssetError(
            "asset_id must contain only letters, numbers, '_' or '-' and be <= 64 chars"
        )
    return cleaned


def _load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic1ValueQaAssetError(
                f"{label}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic1ValueQaAssetError(
                f"{label}:{line_number} must contain a JSON object"
            )
        rows.append(row)
    if not rows:
        raise BenchmarkTopic1ValueQaAssetError(f"{label} must not be empty")
    return rows


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkTopic1ValueQaAssetError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BenchmarkTopic1ValueQaAssetError(f"{label} must contain a JSON object")
    return payload


def _load_json_payload(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkTopic1ValueQaAssetError(f"{label} is not valid JSON") from exc


def _normalize_sample_rows(
    rows: list[dict[str, Any]],
    *,
    prompt_snapshot: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    sample_ids: set[str] = set()
    for index, row in enumerate(rows, 1):
        sample_id = _required_text(row.get("sample_id"), f"samples_path:{index}.sample_id")
        if sample_id in sample_ids:
            raise BenchmarkTopic1ValueQaAssetError(f"duplicate sample_id: {sample_id}")
        sample_ids.add(sample_id)

        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            raise BenchmarkTopic1ValueQaAssetError(
                f"samples_path:{index}.metadata must be an object"
            )
        output = row.get("output")
        if not isinstance(output, dict):
            raise BenchmarkTopic1ValueQaAssetError(
                f"samples_path:{index}.output must be an object"
            )

        fact = _required_text(metadata.get("fact"), f"{sample_id}.metadata.fact")
        secondary_dimension = _required_text(
            metadata.get("evaluation_dimension"),
            f"{sample_id}.metadata.evaluation_dimension",
        )
        quality_level = _quality_level(metadata, row, sample_id)
        artifacts = output.get("artifacts")
        if not isinstance(artifacts, list):
            raise BenchmarkTopic1ValueQaAssetError(
                f"{sample_id}.output.artifacts must be a list"
            )
        question = _artifact_text(artifacts, role="question", key="x", sample_id=sample_id)
        answer = _artifact_text(artifacts, role="answer", key="y", sample_id=sample_id)

        normalized.append(
            {
                "sample_id": sample_id,
                "group_id": _group_id(secondary_dimension, fact),
                "question": question,
                "answer": answer,
                "quality_level": quality_level,
                "primary_dimension": _optional_text(metadata.get("primary_metric")),
                "secondary_dimension": secondary_dimension,
                "topic": _optional_text(metadata.get("topic")),
                "source_reference": _source_reference(row),
                "qc_status": "not_sampled",
                "missing_annotation_count": 0,
                "prompt_snapshot": prompt_snapshot,
                "manual_marked_at": None,
                "trace_predicted_level": None,
                "trace_true_label": None,
                "trace_issue_count": None,
                "trace_low_issue_spans": [],
                "raw": row,
            }
        )
    return normalized


def _required_text(value: Any, label: str) -> str:
    text = _optional_text(value)
    if not text:
        raise BenchmarkTopic1ValueQaAssetError(f"{label} must not be empty")
    return text


def _optional_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _quality_level(metadata: dict[str, Any], row: dict[str, Any], sample_id: str) -> str:
    value = _optional_text(metadata.get("value_level")).lower()
    if not value:
        tags = row.get("tags") or metadata.get("tags") or []
        if isinstance(tags, list):
            for item in tags:
                tag = _optional_text(item).lower()
                if tag.startswith("level_"):
                    value = tag.removeprefix("level_")
                    break
    if value not in QUALITY_LEVELS:
        raise BenchmarkTopic1ValueQaAssetError(
            f"{sample_id}.metadata.value_level must be one of high, medium, low"
        )
    return value


def _artifact_text(
    artifacts: list[Any],
    *,
    role: str,
    key: str,
    sample_id: str,
) -> str:
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        if item.get("role") == role or item.get("key") == key:
            value = (
                item.get("text")
                or item.get("content")
                or item.get("value")
                or item.get("artifact")
            )
            return _required_text(value, f"{sample_id}.output.artifacts.{role}")
    raise BenchmarkTopic1ValueQaAssetError(
        f"{sample_id}.output.artifacts missing {role}"
    )


def _source_reference(row: dict[str, Any]) -> dict[str, Any]:
    refs = row.get("source_refs")
    if isinstance(refs, list) and refs:
        first = refs[0]
        if isinstance(first, dict):
            return {
                key: first.get(key)
                for key in ("source_id", "title", "url", "publisher", "source_type")
                if first.get(key) not in (None, "")
            }
        return {"text": str(first)}
    input_payload = row.get("input")
    if isinstance(input_payload, dict):
        documents = input_payload.get("documents")
        if isinstance(documents, list) and documents:
            first = documents[0]
            if isinstance(first, dict):
                return dict(first)
            return {"text": str(first)}
    return {}


def _group_id(secondary_dimension: str, fact: str) -> str:
    suffix = hashlib.md5(fact.encode("utf-8")).hexdigest()[:8]
    return f"{secondary_dimension}#{suffix}"


def _validate_complete_triplets(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["group_id"])].append(row)
    for group_id, items in groups.items():
        levels = [str(item["quality_level"]) for item in items]
        level_counts = Counter(levels)
        if len(items) != 3 or set(levels) != set(QUALITY_LEVELS):
            raise BenchmarkTopic1ValueQaAssetError(
                f"group {group_id} must contain exactly one high, medium and low sample"
            )
        duplicate_levels = [level for level, count in level_counts.items() if count > 1]
        if duplicate_levels:
            raise BenchmarkTopic1ValueQaAssetError(
                f"group {group_id} contains duplicate levels: {', '.join(duplicate_levels)}"
            )
    return dict(sorted(groups.items()))


def _apply_marks(rows: list[dict[str, Any]], path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "not_imported", "marked_sample_count": 0}
    marks = _load_jsonl(path, "marks")
    marked_at_by_id: dict[str, str] = {}
    for index, mark in enumerate(marks, 1):
        sample_id = _required_text(mark.get("sample_id"), f"marks:{index}.sample_id")
        marked_at_by_id[sample_id] = _optional_text(mark.get("marked_at"))
    joined = 0
    for row in rows:
        marked_at = marked_at_by_id.get(str(row["sample_id"]))
        if marked_at:
            row["manual_marked_at"] = marked_at
            joined += 1
    return {
        "status": "imported",
        "marked_sample_count": len(marked_at_by_id),
        "joined_sample_count": joined,
    }


def _apply_qc(
    rows: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
    *,
    index_path: Path | None,
    samples_path: Path | None,
    scores_path: Path | None,
    summary_path: Path | None,
) -> dict[str, Any]:
    qc_sample_ids: set[str] = set()
    qc_group_ids: set[str] = set()
    if index_path is not None:
        index_payload = _load_json_payload(index_path, "qc_index")
        qc_sample_ids.update(_collect_values(index_payload, {"sample_id", "high_id", "medium_id", "low_id"}))
        qc_group_ids.update(_collect_values(index_payload, {"triplet_id", "group_id"}))
    if samples_path is not None:
        for item in _load_jsonl(samples_path, "qc_samples"):
            qc_sample_ids.update(_collect_values(item, {"sample_id"}))

    score_by_group_id: dict[str, dict[str, Any]] = {}
    if scores_path is not None:
        for index, score in enumerate(_load_jsonl(scores_path, "qc_scores"), 1):
            group_id = _optional_text(score.get("triplet_id") or score.get("group_id"))
            if not group_id:
                raise BenchmarkTopic1ValueQaAssetError(
                    f"qc_scores:{index}.triplet_id must not be empty"
                )
            score_by_group_id[group_id] = score
            qc_group_ids.add(group_id)

    upstream_summary = None
    if summary_path is not None:
        upstream_summary = _load_summary_payload(summary_path, "qc_summary")

    sample_ids = {str(row["sample_id"]) for row in rows}
    group_ids = set(groups)
    overlapped_sample_ids = qc_sample_ids & sample_ids
    overlapped_group_ids = qc_group_ids & group_ids
    for row in rows:
        group_id = str(row["group_id"])
        if str(row["sample_id"]) in overlapped_sample_ids or group_id in overlapped_group_ids:
            row["qc_status"] = "qc_sampled"
            if group_id in score_by_group_id:
                row["qc_score"] = score_by_group_id[group_id]

    status = "imported" if any([index_path, samples_path, scores_path, summary_path]) else "not_imported"
    return {
        "status": status,
        "scope": "sampled_qc" if status == "imported" else "none",
        "sampled_samples": len(qc_sample_ids),
        "overlapped_samples": len(overlapped_sample_ids),
        "sampled_triplets": len(qc_group_ids),
        "overlapped_triplets": len(overlapped_group_ids),
        "upstream_summary": upstream_summary,
    }


def _load_summary_payload(path: Path, label: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"format": path.suffix.lstrip(".") or "text", "text": text}
    if isinstance(payload, dict):
        return payload
    return {"format": "json", "value": payload}


def _apply_trace(
    rows: list[dict[str, Any]],
    *,
    predictions_path: Path | None,
    low_issues_path: Path | None,
) -> dict[str, Any]:
    predictions_by_sample_id: dict[str, dict[str, Any]] = {}
    run_metadata: dict[str, Any] | None = None
    source_schema = "none"
    if predictions_path is not None:
        trace_payload = _load_trace_predictions(predictions_path)
        run_metadata = trace_payload["run_metadata"]
        source_schema = trace_payload["source_schema"]
        for prediction in trace_payload["predictions"]:
            sample_id = _required_text(
                prediction.get("sample_id"),
                "trace_predictions.sample_id",
            )
            predictions_by_sample_id[sample_id] = prediction

    issues_by_sample_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if low_issues_path is not None:
        for index, issue in enumerate(_load_jsonl(low_issues_path, "trace_low_issues"), 1):
            sample_id = _required_text(
                issue.get("sample_id"),
                f"trace_low_issues:{index}.sample_id",
            )
            issues_by_sample_id[sample_id].append(issue)

    joined_predictions = 0
    joined_low_issues = 0
    issue_count = 0
    issue_type_distribution: Counter[str] = Counter()
    gold_distribution: Counter[str] = Counter()
    predicted_distribution: Counter[str] = Counter()
    correct_count = 0
    mismatch_count = 0
    for row in rows:
        sample_id = str(row["sample_id"])
        gold_label = _normalize_trace_label(row.get("quality_level"))
        if gold_label:
            gold_distribution[gold_label] += 1
        prediction = predictions_by_sample_id.get(sample_id)
        if prediction is not None:
            joined_predictions += 1
            predicted_label = _normalize_trace_label(
                prediction.get("label")
                or prediction.get("predicted_level")
                or prediction.get("predicted_label")
                or prediction.get("prediction")
            )
            true_label = _normalize_trace_label(
                prediction.get("true_label") or prediction.get("gold_label")
            )
            row["trace_predicted_level"] = predicted_label
            row["trace_true_label"] = true_label or gold_label
            row["trace_is_consistent"] = bool(predicted_label and predicted_label == gold_label)
            row["trace_match_status"] = (
                "matched" if row["trace_is_consistent"] else "mismatched"
            )
            if predicted_label:
                predicted_distribution[predicted_label] += 1
                if predicted_label == gold_label:
                    correct_count += 1
                else:
                    mismatch_count += 1
            prediction_issues = _normalize_trace_issues(prediction.get("issues"))
            if prediction_issues and low_issues_path is None:
                issues_by_sample_id[sample_id].extend(prediction_issues)
            row["trace_issue_count"] = prediction.get("issue_count")
        issues = issues_by_sample_id.get(sample_id, [])
        if issues:
            row["trace_low_issue_spans"] = issues
            row["trace_issue_count"] = _trace_issue_total(issues)
            joined_low_issues += len(issues)
            issue_count += _trace_issue_total(issues)
            issue_type_distribution.update(_trace_issue_types(issues))

    status = "imported" if predictions_path or low_issues_path else "not_imported"
    coverage_ratio = joined_predictions / len(rows) if rows else 0.0
    accuracy = correct_count / joined_predictions if joined_predictions else 0.0
    return {
        "status": status,
        "scope": "full_sample_join"
        if joined_predictions == len(rows) and rows
        else ("partial_sample_join" if status == "imported" else "none"),
        "source_schema": source_schema,
        "source_file": predictions_path.name if predictions_path else None,
        "run_metadata": run_metadata,
        "prediction_count": len(predictions_by_sample_id),
        "joined_prediction_count": joined_predictions,
        "coverage_ratio": coverage_ratio,
        "correct_count": correct_count,
        "accuracy_against_gold": accuracy,
        "mismatch_count": mismatch_count,
        "gold_distribution": dict(gold_distribution),
        "predicted_distribution": dict(predicted_distribution),
        "low_issue_count": sum(len(items) for items in issues_by_sample_id.values()),
        "joined_low_issue_count": joined_low_issues,
        "issue_count": issue_count,
        "issue_type_distribution": dict(issue_type_distribution),
    }


def _load_trace_predictions(path: Path) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    run_metadata: dict[str, Any] | None = None
    source_schema = "legacy_trace_predictions"
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic1ValueQaAssetError(
                f"trace_predictions:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic1ValueQaAssetError(
                f"trace_predictions:{line_number} must contain a JSON object"
            )
        if row.get("record_type") == "run_metadata":
            run_metadata = row
            source_schema = "risk_cause_data_predictions_v1"
            continue
        predictions.append(row)
    return {
        "predictions": predictions,
        "run_metadata": run_metadata,
        "source_schema": source_schema,
    }


def _normalize_trace_label(value: Any) -> str:
    label = _optional_text(value).lower()
    return label if label in QUALITY_LEVELS else label


def _normalize_trace_issues(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    issues: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        issue = dict(item)
        if issue.get("scope") is None:
            issue["scope"] = "LOCAL" if _optional_text(issue.get("span")) else "GLOBAL"
        issues.append(issue)
    return issues


def _trace_issue_total(issues: list[dict[str, Any]]) -> int:
    total = 0
    for item in issues:
        count = item.get("issue_count")
        if count is not None:
            try:
                parsed = int(count)
            except (TypeError, ValueError):
                parsed = 0
            total += parsed if parsed > 0 else 1
            continue
        nested = item.get("issues")
        total += len(nested) if isinstance(nested, list) and nested else 1
    return total


def _trace_issue_types(issues: list[dict[str, Any]]) -> list[str]:
    types: list[str] = []
    for item in issues:
        nested = item.get("issues")
        if isinstance(nested, list):
            for issue in nested:
                if isinstance(issue, dict):
                    issue_type = _optional_text(issue.get("type") or issue.get("issue_type"))
                    if issue_type:
                        types.append(issue_type)
        issue_type = _optional_text(item.get("type") or item.get("issue_type"))
        if issue_type:
            types.append(issue_type)
    return types


def _collect_values(payload: Any, keys: set[str]) -> set[str]:
    values: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, (str, int)):
                text = str(value).strip()
                if text:
                    values.add(text)
            values.update(_collect_values(value, keys))
    elif isinstance(payload, list):
        for item in payload:
            values.update(_collect_values(item, keys))
    return values


def _copy_raw_inputs(root_dir: Path, paths: dict[str, Path]) -> None:
    raw_dir = root_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for label, path in sorted(paths.items()):
        shutil.copy2(path, raw_dir / f"{label}{path.suffix}")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _group_preview(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for group_id, rows in groups.items():
        first = rows[0]
        levels = {
            str(row["quality_level"]): {
                "sample_id": row["sample_id"],
                "question": row["question"],
                "answer": row["answer"],
            }
            for row in sorted(rows, key=lambda item: QUALITY_LEVELS.index(item["quality_level"]))
        }
        previews.append(
            {
                "group_id": group_id,
                "topic": first["topic"],
                "primary_dimension": first["primary_dimension"],
                "secondary_dimension": first["secondary_dimension"],
                "levels": levels,
            }
        )
    return previews


def _build_quality_report(
    *,
    rows: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
    marks_summary: dict[str, Any],
    qc_summary: dict[str, Any],
    trace_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "sample_count": len(rows),
        "group_count": len(groups),
        "quality_level_distribution": dict(Counter(row["quality_level"] for row in rows)),
        "primary_dimension_distribution": dict(
            Counter(row["primary_dimension"] for row in rows if row["primary_dimension"])
        ),
        "secondary_dimension_distribution": dict(
            Counter(row["secondary_dimension"] for row in rows)
        ),
        "topic_distribution": dict(Counter(row["topic"] for row in rows if row["topic"])),
        "marks": marks_summary,
        "qc": qc_summary,
        "trace": trace_summary,
    }


def _write_lineage(path: Path, source_paths: dict[str, Path]) -> None:
    rows = [
        {
            "role": role,
            "path": str(source_path),
            "file_name": source_path.name,
            "status": "imported",
        }
        for role, source_path in sorted(source_paths.items())
    ]
    _write_jsonl(path, rows)


def _write_readme(path: Path, asset_id: str) -> None:
    path.write_text(
        "\n".join(
            [
                f"# {asset_id}",
                "",
                "Topic1 value_qa prerun snapshot imported for Dynamic Benchmark.",
                "The normalized asset keeps high, medium and low samples grouped by derived group_id.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _build_manifest(
    *,
    asset_id: str,
    name: str,
    source_repo: str,
    source_commit: str,
    source_samples_path: Path,
    rows: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
    quality_report: dict[str, Any],
) -> dict[str, Any]:
    level_distribution = quality_report["quality_level_distribution"]
    trace_summary = quality_report["trace"]
    trace_run_metadata = trace_summary.get("run_metadata") or {}
    trace_model = trace_run_metadata.get("model") if isinstance(trace_run_metadata, dict) else {}
    trace_retrieval = (
        trace_run_metadata.get("retrieval") if isinstance(trace_run_metadata, dict) else {}
    )
    trace_imported = trace_summary.get("status") == "imported"
    return {
        "schema_version": "benchmark-manifest-v0.1",
        "schema_id": SCHEMA_ID,
        "asset_id": asset_id,
        "task_id": f"prerun_{asset_id[:56]}",
        "name": name,
        "source_mode": SOURCE_MODE,
        "agent_id": AGENT_ID,
        "benchmark_type": BENCHMARK_TYPE,
        "release_kind": "verified_value_qa_snapshot",
        "sample_count": len(rows),
        "group_count": len(groups),
        "quality_levels": list(QUALITY_LEVELS),
        "quality_level_distribution": level_distribution,
        "qc_status": quality_report["qc"]["status"],
        "trace_status": quality_report["trace"]["status"],
        "model_eval_status": "imported_result" if trace_imported else "pending_import",
        "trace_source_file": trace_summary.get("source_file"),
        "trace_source_schema": trace_summary.get("source_schema"),
        "trace_model_version": trace_model.get("model_version")
        if isinstance(trace_model, dict)
        else None,
        "trace_architecture": trace_model.get("architecture")
        if isinstance(trace_model, dict)
        else None,
        "trace_retrieval_enabled": trace_retrieval.get("enabled")
        if isinstance(trace_retrieval, dict)
        else None,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_samples_path": str(source_samples_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "samples": "samples.jsonl",
            "group_preview": "group_preview.jsonl",
            "quality_report": "quality_report.json",
            "lineage": "lineage.jsonl",
            "readme": "README.md",
            "artifact_zip": "artifacts/topic1_value_qa_prerun_artifacts.zip",
        },
        "ui_hints": {
            "sample_drawer": "compare_high_medium_low",
            "badge": "prerun_snapshot",
            "model_eval_label": "pending_import",
        },
        "checksums": {},
    }


def _write_asset_zip(root_dir: Path, archive_path: Path) -> None:
    names = [
        "manifest.platform.json",
        "samples.jsonl",
        "group_preview.jsonl",
        "quality_report.json",
        "lineage.jsonl",
        "README.md",
    ]
    names.extend(str(path.relative_to(root_dir)) for path in (root_dir / "raw").iterdir())
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(root_dir / name, arcname=name)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
