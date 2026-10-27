from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.benchmark.topic3_cultural_corpus import ARTIFACT_MEMBER_NAMES
from app.db.models import BenchmarkAsset, BenchmarkTaskLog

CULTURAL_SAMPLE_PREVIEW_CAP = 5


class BenchmarkLiveRunSummaryError(RuntimeError):
    """Raised when a live_run asset summary cannot be built."""


class BenchmarkLiveRunSummaryNotFoundError(BenchmarkLiveRunSummaryError):
    """Raised when the requested live_run asset is unavailable."""


async def build_live_run_summary(
    db: AsyncSession,
    *,
    asset_id: str,
    sample_limit: int = 20,
) -> dict[str, Any]:
    asset = await _get_asset(db, asset_id)
    if asset is None:
        raise BenchmarkLiveRunSummaryNotFoundError("asset not found")
    if asset.source_mode != "live_run":
        raise BenchmarkLiveRunSummaryError("asset is not a live_run artifact")

    manifest = _loads_json_object(asset.manifest_json)
    logs = await _list_logs(db, asset.task_id)
    artifact = _read_live_run_artifact(asset, manifest)

    payload = {
        "asset_id": asset.asset_id,
        "task_id": asset.task_id,
        "agent_id": _string_value(manifest.get("agent_id")),
        "source_mode": asset.source_mode,
        "name": asset.name,
        "created_at": asset.created_at,
        "source_commit": asset.source_commit or _string_value(manifest.get("source_commit")),
        "artifact_sha256": asset.artifact_sha256,
        "parameters": _object_value(manifest.get("parameters")),
        "artifact_files": artifact["artifact_files"],
        "event_counts": _event_counts(logs),
        "tool_counts": _tool_counts(logs),
        "event_timeline": _event_timeline(logs),
        "result_summary": _result_summary(
            artifact["results"],
            report_markdown=artifact["report_markdown"],
        ),
        "sample_pool_summary": _sample_pool_summary(
            artifact["dynbench_rows"],
            limit=sample_limit,
        ),
        "lifecycle_samples": _lifecycle_samples(logs),
        "report": {
            "available": bool(artifact["report_markdown"].strip()),
            "source": "artifact" if artifact["report_markdown"].strip() else "missing",
            "markdown": artifact["report_markdown"],
        },
        "warnings": artifact["warnings"],
    }
    if manifest.get("benchmark_type") == "dynamic_difficulty":
        payload["topic3_difficulty_summary"] = _topic3_difficulty_summary(
            manifest,
            artifact,
            limit=sample_limit,
        )
    if manifest.get("benchmark_type") == "value_qa":
        payload["topic1_value_qa_summary"] = _topic1_value_qa_summary(
            manifest,
            artifact,
            limit=sample_limit,
        )
    if manifest.get("benchmark_type") == "cultural_diversity_generation":
        payload["topic3_cultural_summary"] = _topic3_cultural_summary(
            manifest,
            artifact,
            limit=sample_limit,
        )
    return payload


async def _get_asset(db: AsyncSession, asset_id: str) -> BenchmarkAsset | None:
    result = await db.execute(
        select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id)
    )
    return result.scalar_one_or_none()


async def _list_logs(db: AsyncSession, task_id: str) -> list[BenchmarkTaskLog]:
    result = await db.execute(
        select(BenchmarkTaskLog)
        .where(BenchmarkTaskLog.task_id == task_id)
        .order_by(BenchmarkTaskLog.id.asc())
    )
    return list(result.scalars().all())


def _read_live_run_artifact(
    asset: BenchmarkAsset,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    artifact_zip_path = Path(asset.artifact_zip_path)
    if not artifact_zip_path.is_file():
        raise BenchmarkLiveRunSummaryError("artifact zip not found")

    if manifest.get("benchmark_type") == "dynamic_difficulty":
        return _read_topic3_difficulty_artifact(artifact_zip_path)
    if manifest.get("benchmark_type") == "value_qa":
        return _read_topic1_value_qa_artifact(artifact_zip_path)
    if manifest.get("benchmark_type") == "cultural_diversity_generation":
        return _read_topic3_cultural_artifact(artifact_zip_path)

    warnings: list[str] = []
    artifact_files = {
        "manifest.json": False,
        "report.md": False,
        "results.json": False,
        "dynbench.jsonl": False,
    }
    results: dict[str, Any] | None = None
    dynbench_rows: list[dict[str, Any]] = []
    report_markdown = ""

    try:
        with zipfile.ZipFile(artifact_zip_path) as archive:
            members = _safe_members(archive)
            manifest_files = _object_value(manifest.get("files"))
            names = {
                "manifest.json": _member_name(manifest_files, "manifest", "manifest.json"),
                "report.md": _member_name(manifest_files, "report", "report.md"),
                "results.json": _member_name(manifest_files, "results", "results.json"),
                "dynbench.jsonl": _member_name(manifest_files, "dynbench", "dynbench.jsonl"),
            }

            if names["manifest.json"] in members:
                artifact_files["manifest.json"] = True
            if names["report.md"] in members:
                artifact_files["report.md"] = True
                report_markdown = _read_text_member(archive, names["report.md"])
            if names["results.json"] in members:
                artifact_files["results.json"] = True
                results = _read_json_member(archive, names["results.json"])
            if names["dynbench.jsonl"] in members:
                artifact_files["dynbench.jsonl"] = True
                dynbench_rows = _read_jsonl_member(archive, names["dynbench.jsonl"])
    except zipfile.BadZipFile as exc:
        raise BenchmarkLiveRunSummaryError("invalid artifact zip") from exc

    for file_name, available in artifact_files.items():
        if available:
            continue
        if file_name == "dynbench.jsonl" and _topic2_dynbench_omitted(manifest):
            warnings.append(
                "dynbench.jsonl omitted (dynbench_count=0); run stored no samples"
            )
        else:
            warnings.append(f"{file_name} missing from live_run artifact")

    return {
        "artifact_files": artifact_files,
        "results": results,
        "dynbench_rows": dynbench_rows,
        "report_markdown": report_markdown,
        "warnings": warnings,
    }


def _topic2_dynbench_omitted(manifest: dict[str, Any]) -> bool:
    count = manifest.get("upstream_dynbench_count")
    if isinstance(count, int) and not isinstance(count, bool) and count == 0:
        return True
    upstream = manifest.get("upstream_manifest")
    if isinstance(upstream, dict):
        nested = upstream.get("dynbench_count")
        if isinstance(nested, int) and not isinstance(nested, bool) and nested == 0:
            return True
    return False


def _read_topic1_value_qa_artifact(artifact_zip_path: Path) -> dict[str, Any]:
    artifact_files = {
        "manifest.json": False,
        "samples.jsonl": False,
        "group_preview.jsonl": False,
        "quality_report.json": False,
        "lineage.jsonl": False,
        "worker.log": False,
    }
    warnings: list[str] = []
    samples: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    upstream_manifest: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    worker_log = ""

    try:
        with zipfile.ZipFile(artifact_zip_path) as archive:
            members = _safe_members(archive)
            if "manifest.json" in members:
                artifact_files["manifest.json"] = True
                upstream_manifest = _read_json_member(archive, "manifest.json")
            if "samples.jsonl" in members:
                artifact_files["samples.jsonl"] = True
                samples = _read_jsonl_member(archive, "samples.jsonl")
            if "group_preview.jsonl" in members:
                artifact_files["group_preview.jsonl"] = True
                groups = _read_jsonl_member(archive, "group_preview.jsonl")
            if "quality_report.json" in members:
                artifact_files["quality_report.json"] = True
                quality_report = _read_json_member(archive, "quality_report.json")
            if "lineage.jsonl" in members:
                artifact_files["lineage.jsonl"] = True
            if "worker.log" in members:
                artifact_files["worker.log"] = True
                worker_log = _read_text_member(archive, "worker.log")
    except zipfile.BadZipFile as exc:
        raise BenchmarkLiveRunSummaryError("invalid artifact zip") from exc

    for file_name, available in artifact_files.items():
        if not available:
            warnings.append(f"{file_name} missing from topic1 value_qa artifact")

    return {
        "artifact_files": artifact_files,
        "results": None,
        "dynbench_rows": [],
        "report_markdown": "",
        "warnings": warnings,
        "topic1_samples": samples,
        "topic1_groups": groups,
        "topic1_manifest": upstream_manifest or {},
        "topic1_quality_report": quality_report or {},
        "topic1_worker_log": worker_log,
    }


def _read_topic3_cultural_artifact(artifact_zip_path: Path) -> dict[str, Any]:
    artifact_files = {name: False for name in ARTIFACT_MEMBER_NAMES}
    warnings: list[str] = []
    samples: list[dict[str, Any]] = []
    upstream_manifest: dict[str, Any] | None = None
    generation_config: dict[str, Any] | None = None
    worker_state: dict[str, Any] | None = None
    worker_log = ""

    try:
        with zipfile.ZipFile(artifact_zip_path) as archive:
            members = _safe_members(archive)
            for name in ARTIFACT_MEMBER_NAMES:
                if name not in members:
                    continue
                artifact_files[name] = True
                if name == "samples.jsonl":
                    samples = _read_jsonl_member(archive, name)
                elif name == "manifest.json":
                    upstream_manifest = _read_json_member(archive, name)
                elif name == "generation_config.json":
                    generation_config = _read_json_member(archive, name)
                elif name == "worker_state.json":
                    worker_state = _read_json_member(archive, name)
                elif name == "worker.log":
                    worker_log = _read_text_member(archive, name)
    except zipfile.BadZipFile as exc:
        raise BenchmarkLiveRunSummaryError("invalid artifact zip") from exc

    for file_name, available in artifact_files.items():
        if not available:
            warnings.append(f"{file_name} missing from topic3 cultural artifact")

    return {
        "artifact_files": artifact_files,
        "results": None,
        "dynbench_rows": [],
        "report_markdown": "",
        "warnings": warnings,
        "topic3_cultural_samples": samples,
        "topic3_cultural_manifest": upstream_manifest or {},
        "topic3_cultural_generation_config": generation_config or {},
        "topic3_cultural_worker_state": worker_state or {},
        "topic3_cultural_worker_log": worker_log,
    }


def _read_topic3_difficulty_artifact(artifact_zip_path: Path) -> dict[str, Any]:
    artifact_files = {
        "samples.jsonl": False,
        "manifest.json": False,
        "worker_state.json": False,
        "generation_config.json": False,
        "worker.log": False,
        "batches": False,
    }
    warnings: list[str] = []
    samples: list[dict[str, Any]] = []
    upstream_manifest: dict[str, Any] | None = None
    worker_state: dict[str, Any] | None = None
    generation_config: dict[str, Any] | None = None
    worker_log = ""
    batches: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(artifact_zip_path) as archive:
            members = _safe_members(archive)
            if "samples.jsonl" in members:
                artifact_files["samples.jsonl"] = True
                samples = _read_jsonl_member(archive, "samples.jsonl")
            if "manifest.json" in members:
                artifact_files["manifest.json"] = True
                upstream_manifest = _read_json_member(archive, "manifest.json")
            if "worker_state.json" in members:
                artifact_files["worker_state.json"] = True
                worker_state = _read_json_member(archive, "worker_state.json")
            if "generation_config.json" in members:
                artifact_files["generation_config.json"] = True
                generation_config = _read_json_member(archive, "generation_config.json")
            if "worker.log" in members:
                artifact_files["worker.log"] = True
                worker_log = _read_text_member(archive, "worker.log")
            for name in sorted(item for item in members if item.startswith("batches/")):
                batch = _read_json_member(archive, name)
                if batch is not None:
                    batches.append(batch)
            artifact_files["batches"] = any(item.startswith("batches/") for item in members)
    except zipfile.BadZipFile as exc:
        raise BenchmarkLiveRunSummaryError("invalid artifact zip") from exc

    for file_name, available in artifact_files.items():
        if not available:
            warnings.append(f"{file_name} missing from live_run artifact")

    return {
        "artifact_files": artifact_files,
        "results": None,
        "dynbench_rows": [],
        "report_markdown": "",
        "warnings": warnings,
        "topic3_samples": samples,
        "topic3_manifest": upstream_manifest or {},
        "topic3_worker_state": worker_state or {},
        "topic3_generation_config": generation_config or {},
        "topic3_worker_log": worker_log,
        "topic3_batches": batches,
    }


def _safe_members(archive: zipfile.ZipFile) -> set[str]:
    members: set[str] = set()
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkLiveRunSummaryError(
                f"directory members are not allowed: {info.filename}"
            )
        name = info.filename.replace("\\", "/")
        if _is_unsafe_member(name):
            raise BenchmarkLiveRunSummaryError(f"unsafe zip member: {info.filename}")
        duplicate_key = name.casefold()
        if duplicate_key in seen:
            raise BenchmarkLiveRunSummaryError(f"duplicate zip member: {info.filename}")
        seen.add(duplicate_key)
        members.add(name)
    return members


def _is_unsafe_member(name: str) -> bool:
    if not name or "\x00" in name:
        return True
    windows_path = PureWindowsPath(name)
    posix_path = PurePosixPath(name.replace("\\", "/"))
    if windows_path.is_absolute() or posix_path.is_absolute():
        return True
    return ".." in posix_path.parts


def _member_name(files: dict[str, Any], key: str, fallback: str) -> str:
    value = files.get(key)
    return value.replace("\\", "/") if isinstance(value, str) and value.strip() else fallback


def _read_text_member(archive: zipfile.ZipFile, name: str) -> str:
    try:
        return archive.read(name).decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return ""


def _read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl_member(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    try:
        text = archive.read(name).decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return []

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _result_summary(
    results: dict[str, Any] | None,
    *,
    report_markdown: str = "",
) -> dict[str, Any]:
    if not results:
        return {
            "available": False,
            "source": "results.json",
            "moderators": [],
        }

    moderators = [
        item
        for item in (_normalize_moderator_result(value) for value in _list_value(results.get("moderators")))
        if item is not None
    ]
    source = "results.json"
    results_report_markdown = _string_value(results.get("report_markdown"))
    if not moderators:
        moderators = _moderator_results_from_report_markdown(
            results_report_markdown,
            total_samples=_int_value(results.get("total_samples_evaluated")),
        )
        if moderators:
            source = "results.json.report_markdown"
    if not moderators:
        moderators = _moderator_results_from_report_markdown(
            report_markdown,
            total_samples=_int_value(results.get("total_samples_evaluated")),
        )
        if moderators:
            source = "report.md"
    total_samples = max((item["total_samples"] for item in moderators), default=0)
    return {
        "available": bool(moderators),
        "source": source,
        "setting": _string_value(results.get("setting"))
        or _setting_from_report_markdown(results_report_markdown)
        or _setting_from_report_markdown(report_markdown),
        "timestamp": _string_value(results.get("timestamp")),
        "moderators_tested": _int_value(results.get("moderators_tested"))
        or len(moderators),
        "total_samples": total_samples,
        "moderators": moderators,
    }


def _normalize_moderator_result(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    metrics = _object_value(value.get("overall_metrics"))
    return {
        "name": _string_value(value.get("name")) or "unknown",
        "total_samples": _int_value(value.get("total_samples"))
        or _int_value(metrics.get("n_samples")),
        "accuracy": _float_value(metrics.get("accuracy")),
        "precision": _float_value(metrics.get("precision")),
        "recall": _float_value(metrics.get("recall")),
        "f1": _float_value(metrics.get("f1")),
        "fpr": _float_value(metrics.get("fpr")),
        "fnr": _float_value(metrics.get("fnr")),
        "n_errors": _int_value(metrics.get("n_errors")),
        "avg_latency_ms": _float_value(value.get("avg_latency_ms")),
        "eval_time_seconds": _float_value(value.get("eval_time_seconds")),
        "per_vector": _metric_bucket(value.get("per_vector")),
        "per_category": _metric_bucket(value.get("per_category")),
    }


def _moderator_results_from_report_markdown(
    markdown: str,
    *,
    total_samples: int | None,
) -> list[dict[str, Any]]:
    if not markdown:
        return []

    lines = markdown.splitlines()
    in_ranking = False
    moderators: list[dict[str, Any]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_ranking:
                break
            in_ranking = stripped == "## Overall Ranking"
            continue
        if not in_ranking or not stripped.startswith("|"):
            continue
        cells = [_clean_markdown_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 8 or cells[0].lower() in {"rank", "------"}:
            continue
        if set(cells[0]) <= {"-"}:
            continue
        name = cells[1]
        if not name:
            continue
        moderators.append(
            {
                "name": name,
                "total_samples": total_samples,
                "accuracy": _float_value(cells[2]),
                "precision": None,
                "recall": _float_value(cells[4]),
                "f1": _float_value(cells[3]),
                "fpr": _float_value(cells[5]),
                "fnr": _float_value(cells[6]),
                "n_errors": None,
                "avg_latency_ms": _float_value(cells[7]),
                "eval_time_seconds": None,
                "per_vector": {},
                "per_category": {},
            }
        )
    return moderators


def _setting_from_report_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("**Setting**:"):
            return _clean_markdown_cell(line.split(":", 1)[1])
    return ""


def _clean_markdown_cell(value: str) -> str:
    return value.strip().strip("`").replace("**", "").strip()


def _metric_bucket(value: Any) -> dict[str, dict[str, float | int | None]]:
    result: dict[str, dict[str, float | int | None]] = {}
    if not isinstance(value, dict):
        return result
    for key, metrics in value.items():
        if not isinstance(key, str) or not isinstance(metrics, dict):
            continue
        result[key] = {
            "accuracy": _float_value(metrics.get("accuracy")),
            "precision": _float_value(metrics.get("precision")),
            "recall": _float_value(metrics.get("recall")),
            "f1": _float_value(metrics.get("f1")),
            "fpr": _float_value(metrics.get("fpr")),
            "fnr": _float_value(metrics.get("fnr")),
            "n_samples": _int_value(metrics.get("n_samples")),
            "n_errors": _int_value(metrics.get("n_errors")),
        }
    return result


def _topic3_difficulty_summary(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    samples = _list_value(artifact.get("topic3_samples"))
    upstream_manifest = _object_value(artifact.get("topic3_manifest"))
    generation_config = _object_value(artifact.get("topic3_generation_config"))
    worker_state = _object_value(artifact.get("topic3_worker_state"))
    generation = _object_value(generation_config.get("generation"))
    llm_composer = _object_value(generation_config.get("llm_composer"))
    batches = _list_value(artifact.get("topic3_batches"))

    difficulty_counts: Counter[str] = Counter()
    bridge_review_counts: Counter[str] = Counter()
    final_guard_counts: Counter[str] = Counter()
    risk_category_counts: Counter[str] = Counter()
    risk_level_counts: Counter[str] = Counter()
    sample_rows: list[dict[str, Any]] = []

    for sample in samples:
        if not isinstance(sample, dict):
            continue
        _count(difficulty_counts, sample.get("difficulty_level"))
        _count(bridge_review_counts, sample.get("bridge_review_label"))
        _count(final_guard_counts, sample.get("final_guard_label"))
        _count(risk_category_counts, sample.get("risk_category"))
        _count(risk_level_counts, sample.get("risk_level"))
        if len(sample_rows) < limit:
            sample_rows.append(_topic3_sample_item(sample))

    return {
        "available": bool(samples),
        "total": len(samples),
        "sample_limit": limit,
        "status": _string_value(upstream_manifest.get("status"))
        or _string_value(worker_state.get("status")),
        "generated": _int_value(upstream_manifest.get("total_generated")),
        "requested": _int_value(upstream_manifest.get("total_requested"))
        or _int_value(generation.get("total_sample_count")),
        "batch_size": _int_value(upstream_manifest.get("batch_size"))
        or _int_value(generation.get("batch_size")),
        "composer_concurrency": _int_value(llm_composer.get("concurrency")),
        "random_seed": _int_value(generation.get("random_seed"))
        or _int_value(worker_state.get("random_seed")),
        "sample_mode": _string_value(generation.get("sample_mode")),
        "metric_targets": _string_list(generation.get("metric_targets")),
        "difficulty_counts": dict(difficulty_counts),
        "configured_difficulty_counts": _object_value(generation.get("difficulty_counts")),
        "bridge_review_counts": dict(bridge_review_counts),
        "final_guard_counts": dict(final_guard_counts),
        "risk_category_counts": dict(risk_category_counts),
        "risk_level_counts": dict(risk_level_counts),
        "discard_counts": _object_value(upstream_manifest.get("discard_counts"))
        or _object_value(worker_state.get("discard_counts")),
        "seed_pool_counts": _object_value(upstream_manifest.get("seed_pool_counts")),
        "quality_reports": [
            _object_value(batch.get("quality_report"))
            for batch in batches
            if isinstance(batch, dict) and batch.get("quality_report")
        ],
        "worker_log": _string_value(artifact.get("topic3_worker_log")),
        "samples": sample_rows,
        "readiness": "live_run_smoke",
        "readiness_note": "本资产用于现场链路验证，展示已生成的 H1-H4 动态难度编辑题库；不等同于正式模型评测结果。",
        "manifest_summary": {
            "platform_difficulty_label": _string_value(
                manifest.get("platform_difficulty_label")
            ),
            "platform_difficulty_basis": _string_value(
                manifest.get("platform_difficulty_basis")
            ),
            "native_difficulty_schema": _string_value(
                manifest.get("native_difficulty_schema")
            ),
        },
    }


def _topic1_value_qa_summary(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    parameters = _object_value(manifest.get("parameters"))
    upstream_manifest = _object_value(artifact.get("topic1_manifest"))
    quality_report = _object_value(artifact.get("topic1_quality_report"))
    retrieval = _object_value(manifest.get("retrieval")) or _object_value(
        upstream_manifest.get("retrieval")
    )
    sample_rows = _list_value(artifact.get("topic1_samples"))
    group_rows = _list_value(artifact.get("topic1_groups"))
    quality_distribution = (
        _object_value(manifest.get("quality_level_distribution"))
        or _object_value(upstream_manifest.get("quality_level_distribution"))
        or _object_value(quality_report.get("quality_level_distribution"))
    )

    selected_topics: list[str] = []
    for group in group_rows:
        if not isinstance(group, dict):
            continue
        topic = _string_value(group.get("topic"))
        if topic and topic not in selected_topics:
            selected_topics.append(topic)

    sample_groups = [
        _topic1_group_item(group)
        for group in group_rows[:limit]
        if isinstance(group, dict)
    ]
    validation = (
        _object_value(manifest.get("validation"))
        or _object_value(upstream_manifest.get("validation"))
        or _object_value(quality_report.get("validation"))
    )
    llm_runtime = _object_value(manifest.get("llm_runtime")) or _object_value(
        upstream_manifest.get("llm_runtime")
    )

    return {
        "available": bool(sample_rows or group_rows),
        "sample_limit": limit,
        "generation_mode": _string_value(parameters.get("generation_mode")) or "topic",
        "topic": _string_value(parameters.get("topic")),
        "dimension": _string_value(parameters.get("dimension")),
        "selected_topics": selected_topics,
        "requested_group_count": _int_value(manifest.get("requested_group_count"))
        or _int_value(upstream_manifest.get("requested_group_count")),
        "generated_group_count": _int_value(manifest.get("generated_group_count"))
        or _int_value(upstream_manifest.get("generated_group_count"))
        or len(group_rows),
        "sample_count": _int_value(manifest.get("sample_count"))
        or _int_value(upstream_manifest.get("sample_count"))
        or len(sample_rows),
        "quality_level_distribution": quality_distribution,
        "retrieval_mode": _string_value(retrieval.get("mode"))
        or _string_value(parameters.get("retrieval_mode")),
        "corpus_jsonl": _string_value(retrieval.get("corpus_jsonl"))
        or _string_value(parameters.get("corpus_jsonl")),
        "language": _string_value(parameters.get("language")),
        "model": _string_value(llm_runtime.get("model"))
        or _string_value(parameters.get("model")),
        "llm_api_base": _string_value(llm_runtime.get("api_base")),
        "seed": _int_value(parameters.get("seed")),
        "validation": validation,
        "artifact_files": _object_value(artifact.get("artifact_files")),
        "sample_groups": sample_groups,
        "worker_log": _string_value(artifact.get("topic1_worker_log")),
        "readiness": "live_run_structure_checked",
        "readiness_note": "本资产用于课题一 value_qa 现场生成链路验证，展示三档问答样本、结构校验和冻结产物；不等同于正式模型评测结果。",
    }


def _topic3_cultural_summary(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    parameters = _object_value(manifest.get("parameters"))
    upstream_manifest = _object_value(artifact.get("topic3_cultural_manifest"))
    samples = [
        row for row in _list_value(artifact.get("topic3_cultural_samples")) if isinstance(row, dict)
    ]
    requested = _int_value(parameters.get("total_sample_count")) or _int_value(
        upstream_manifest.get("total_requested")
    )
    generated = _int_value(manifest.get("sample_count")) or len(samples)
    preview_limit = min(CULTURAL_SAMPLE_PREVIEW_CAP, max(0, limit))
    previews = [_topic3_cultural_preview_item(sample) for sample in samples[:preview_limit]]
    return {
        "available": bool(samples),
        "sample_limit": preview_limit,
        "requested": requested,
        "generated": generated,
        "sample_count": generated,
        "scale": _string_value(parameters.get("scale")),
        "structure_band": _string_value(parameters.get("structure_band")),
        "language": _string_value(parameters.get("language")),
        "batch_size": _int_value(parameters.get("batch_size")),
        "random_seed": _int_value(parameters.get("random_seed")),
        "difficulty_counts": _int_map(parameters.get("difficulty_counts")),
        "allowed_ethnic_groups": _string_list(parameters.get("allowed_ethnic_groups")),
        "difficulty_distribution": _int_map(
            manifest.get("difficulty_distribution")
            or upstream_manifest.get("difficulty_distribution")
        ),
        "ethnic_distribution": _int_map(
            manifest.get("ethnic_distribution") or upstream_manifest.get("ethnic_distribution")
        ),
        "background_type_distribution": _int_map(
            manifest.get("background_type_distribution")
            or upstream_manifest.get("background_type_distribution")
        ),
        "persona_distribution": _int_map(
            manifest.get("persona_distribution") or upstream_manifest.get("persona_distribution")
        ),
        "query_type_distribution": _int_map(
            manifest.get("query_type_distribution")
            or upstream_manifest.get("query_type_distribution")
        ),
        "review_passed_count": _int_value(
            manifest.get("review_passed_count") or upstream_manifest.get("review_passed_count")
        ),
        "review_passed_rate": _float_value(
            manifest.get("review_passed_rate") or upstream_manifest.get("review_passed_rate")
        )
        or 0.0,
        "artifact_files": _object_value(artifact.get("artifact_files")),
        "sample_previews": previews,
        "readiness": "live_run",
        "readiness_note": (
            "本资产用于现场文化多样性语料生成验证，展示 L1–L3 语境难度与多民族分布；"
            "不含被测模型评测结果。"
        ),
    }


def _topic3_cultural_preview_item(sample: dict[str, Any]) -> dict[str, Any]:
    background = _string_value(sample.get("background"))
    user_query = _string_value(sample.get("user_query") or sample.get("query"))
    prompt = _string_value(sample.get("prompt"))
    if not prompt:
        prompt = " ".join(part for part in (background, user_query) if part)
    return {
        "sample_id": _string_value(sample.get("sample_id") or sample.get("id")),
        "ethnic_group": _string_value(
            sample.get("ethnic_group") or sample.get("implied_ethnic_group")
        ),
        "difficulty_level": _string_value(sample.get("difficulty_level")),
        "background_type": _string_value(sample.get("background_type")),
        "persona": _string_value(sample.get("persona")),
        "query_type": _string_value(sample.get("query_type")),
        "prompt_preview": _preview(prompt, limit=120),
    }


def _topic1_group_item(group: dict[str, Any]) -> dict[str, Any]:
    levels = _object_value(group.get("levels"))
    return {
        "group_id": _string_value(group.get("group_id")),
        "topic": _string_value(group.get("topic")),
        "primary_dimension": _string_value(group.get("primary_dimension")),
        "secondary_dimension": _string_value(group.get("secondary_dimension")),
        "levels": {
            level: _topic1_level_item(levels.get(level))
            for level in ("high", "medium", "low")
        },
    }


def _topic1_level_item(value: Any) -> dict[str, Any]:
    item = _object_value(value)
    return {
        "sample_id": _string_value(item.get("sample_id")),
        "question": _string_value(item.get("question")),
        "answer": _string_value(item.get("answer")),
    }


def _topic3_sample_item(sample: dict[str, Any]) -> dict[str, Any]:
    edited_input = _string_value(sample.get("edited_input"))
    return {
        "sample_id": _string_value(sample.get("sample_id")),
        "difficulty_level": _string_value(sample.get("difficulty_level")),
        "difficulty_strategy": _string_value(sample.get("difficulty_strategy")),
        "harmful_count": _int_value(sample.get("harmful_count")),
        "harmless_count": _int_value(sample.get("harmless_count")),
        "interleaving": bool(sample.get("interleaving")),
        "risk_category": _string_value(sample.get("risk_category")),
        "risk_category_key": _string_value(sample.get("risk_category_key")),
        "risk_level": _string_value(sample.get("risk_level")),
        "bridge_review_label": _string_value(sample.get("bridge_review_label")),
        "bridge_review_reason": _string_value(sample.get("bridge_review_reason")),
        "coherence_label": _string_value(sample.get("coherence_label")),
        "coherence_reason": _string_value(sample.get("coherence_reason")),
        "final_guard_label": _string_value(sample.get("final_guard_label")),
        "final_guard_categories": _string_list(sample.get("final_guard_categories")),
        "harmful_spans": _span_list(sample.get("harmful_spans")),
        "harmless_spans": _span_list(sample.get("harmless_spans")),
        "edited_input": edited_input,
        "edited_input_preview": _preview(edited_input),
        "bridge_texts": _string_list(sample.get("bridge_texts")),
        "source_boundary_edits": _list_value(sample.get("source_boundary_edits")),
        "source_trace": _topic3_source_trace(sample.get("source_trace")),
    }


def _span_list(value: Any) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for item in _list_value(value):
        if not isinstance(item, dict):
            continue
        start = _int_value(item.get("start"))
        end = _int_value(item.get("end"))
        if end <= start:
            continue
        spans.append(
            {
                "text": _string_value(item.get("text")),
                "start": start,
                "end": end,
            }
        )
    return spans


def _topic3_source_trace(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list_value(value):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": _string_value(item.get("id")),
                "safety_label": _string_value(item.get("safety_label")),
                "risk_category": _string_value(item.get("risk_category")),
                "risk_level": _string_value(item.get("risk_level")),
                "source_trace": _string_value(item.get("source_trace")),
            }
        )
    return rows


def _sample_pool_summary(
    rows: list[dict[str, Any]],
    *,
    limit: int,
) -> dict[str, Any]:
    label_distribution: Counter[str] = Counter()
    l1_distribution: Counter[str] = Counter()
    l2_distribution: Counter[str] = Counter()
    attack_vector_distribution: Counter[str] = Counter()
    language_distribution: Counter[str] = Counter()
    origin_distribution: Counter[str] = Counter()
    fooled_count = 0
    preview_samples: list[dict[str, Any]] = []

    for row in rows:
        _count(label_distribution, row.get("label"))
        _count(l1_distribution, row.get("harm_category_L1"))
        _count(l2_distribution, row.get("harm_category_L2"))
        _count(attack_vector_distribution, row.get("attack_vector"))
        _count(language_distribution, row.get("language"))
        _count(origin_distribution, row.get("origin"))

        moderator_fooled = _string_list(row.get("moderator_fooled"))
        if moderator_fooled:
            fooled_count += 1

        if len(preview_samples) < limit:
            query = _string_value(row.get("query"))
            preview_samples.append(
                {
                    "id": _string_value(row.get("id")),
                    "seedbank_id": _string_value(row.get("seedbank_id")),
                    "label": _string_value(row.get("label")),
                    "harm_category_l1": _string_value(row.get("harm_category_L1")),
                    "harm_category_l2": _string_value(row.get("harm_category_L2")),
                    "attack_vector": _string_value(row.get("attack_vector")),
                    "difficulty": _float_value(row.get("difficulty")),
                    "language": _string_value(row.get("language")),
                    "origin": _string_value(row.get("origin")),
                    "status": _string_value(row.get("status")),
                    "test_count": _int_value(row.get("test_count")),
                    "moderator_fooled": moderator_fooled,
                    "query_preview": _preview(query),
                }
            )

    return {
        "available": bool(rows),
        "total": len(rows),
        "label_distribution": dict(label_distribution),
        "l1_distribution": dict(l1_distribution),
        "l2_distribution": dict(l2_distribution),
        "attack_vector_distribution": dict(attack_vector_distribution),
        "language_distribution": dict(language_distribution),
        "origin_distribution": dict(origin_distribution),
        "fooled_count": fooled_count,
        "preview_samples": preview_samples,
    }


def _event_counts(logs: list[BenchmarkTaskLog]) -> dict[str, int]:
    counts = Counter(log.event_type for log in logs)
    return {
        "total": len(logs),
        "thinking": counts.get("thinking", 0),
        "tool_call": counts.get("tool_call", 0),
        "tool_result": counts.get("tool_result", 0),
        "lifecycle": counts.get("lifecycle", 0),
        "done": counts.get("done", 0),
        "error": counts.get("error", 0),
    }


def _tool_counts(logs: list[BenchmarkTaskLog]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for log in logs:
        raw = _loads_json_object(log.raw_json)
        tool_name = _string_value(raw.get("name")) or _string_value(log.stage)
        if log.event_type == "tool_call" and tool_name:
            counts[tool_name] += 1
    return {
        "test_samples": counts.get("test_samples", 0),
        "generate_report": counts.get("generate_report", 0),
        "list_attack_strategies": counts.get("list_attack_strategies", 0),
    }


def _event_timeline(logs: list[BenchmarkTaskLog]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for log in logs[:80]:
        raw = _loads_json_object(log.raw_json)
        timeline.append(
            {
                "id": log.id,
                "event_type": log.event_type,
                "stage": log.stage,
                "message": log.message,
                "turn": log.turn,
                "tool_name": _string_value(raw.get("name")),
                "created_at": log.created_at,
            }
        )
    return timeline


def _lifecycle_samples(logs: list[BenchmarkTaskLog]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for log in logs:
        if log.event_type != "lifecycle":
            continue
        raw = _loads_json_object(log.raw_json)
        details = _object_value(raw.get("details"))
        query = (
            _string_value(details.get("query_preview"))
            or _string_value(details.get("query"))
            or _string_value(raw.get("query_preview"))
            or _string_value(raw.get("query"))
        )
        samples.append(
            {
                "sample_id": _string_value(raw.get("sample_id"))
                or _string_value(log.message)
                or "unknown",
                "stage": _string_value(raw.get("stage"))
                or _string_value(log.stage)
                or "lifecycle",
                "strategy": _string_value(details.get("strategy"))
                or _string_value(raw.get("strategy")),
                "difficulty": _float_value(details.get("difficulty"))
                or _float_value(raw.get("difficulty")),
                "moderator_results": _object_value(
                    details.get("moderator_results") or raw.get("moderator_results")
                ),
                "query_preview": _preview(query),
            }
        )
    return samples


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_map(value: Any) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for key, item in _object_value(value).items():
        label = str(key).strip()
        if not label:
            continue
        mapping[label] = _int_value(item)
    return mapping


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _count(counter: Counter[str], value: Any) -> None:
    label = _string_value(value)
    if label:
        counter[label] += 1


def _preview(value: str, *, limit: int = 180) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."
