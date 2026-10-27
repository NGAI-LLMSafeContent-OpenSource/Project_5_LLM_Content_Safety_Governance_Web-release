"""Output eval service — orchestrates adapter (Benchmark/Audit Tool) + persistence."""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic3.mapper import (
    export_eval_results as _adapter_export,
    get_active_risk_taxonomy as _adapter_taxonomy,
    infer_single_sample as _adapter_infer,
    get_available_datasets as _adapter_datasets,
    get_eval_results as _adapter_eval_results,
    get_eval_task_status as _adapter_task_status,
    start_eval_task as _adapter_start_eval,
)
from app.schemas.output_eval import EvalResultSummary, EvalStartResponse, EvalTaskStatus, ExportQuery
from app.services.output_eval_store import get_task_job_id, save_task, save_task_results

logger = logging.getLogger(__name__)

# Adapter-owned pass-throughs — no platform-side orchestration needed
get_active_risk_taxonomy = _adapter_taxonomy
get_eval_task_status = _adapter_task_status
export_eval_results = _adapter_export

# Catalog identity for the injected current topic3 risk asset. The upstream
# demo catalog has no sample counts and repeats one asset across task groups,
# so the current version is projected from the platform's own asset pointer.
_TOPIC3_RISK_CATALOG_SUBTYPE = "benchmark-risk_classification"
_TOPIC3_RISK_CATALOG_SCENARIO = "风险内容"


def _topic3_risk_catalog_item(overview: dict[str, Any]) -> dict[str, Any] | None:
    """Project a resolved topic3 risk asset into one Step 1 catalog entry.

    Version, sample count and hash all come from the caller's resolution; this
    function never reads the network or the version pointer itself.
    """
    sample_count = overview.get("sample_count")
    if not isinstance(sample_count, int) or sample_count <= 0:
        logger.warning(
            "current topic3 risk asset %s has no sample_count; omitted from the dataset catalog",
            overview.get("asset_id"),
        )
        return None
    version = str(overview.get("asset_version") or "")
    return {
        "id": str(overview.get("asset_id") or ""),
        "name": f"课题三风险分级分类 Benchmark {version}".strip(),
        "type": "science",
        "subType": _TOPIC3_RISK_CATALOG_SUBTYPE,
        "description": (
            f"课题三风险分层分类与多标签联合评测集（{version}），"
            f"共 {sample_count} 条样本；版本与条数来自课题五已发布资产。"
        ),
        "recordCount": sample_count,
        "language": "多语言",
        "riskLevel": "MEDIUM",
        "createdAt": "",
        "updatedAt": "",
        "track": "risk",
        "scenario": _TOPIC3_RISK_CATALOG_SCENARIO,
        "assetVersion": version,
        "assetSha256": str(overview.get("asset_sha256") or ""),
        "dataSource": "topic3_same_version",
        "hasStaticResult": overview.get("evaluation_status") == "evaluation_imported",
        "canDynamicEval": False,
    }


async def get_available_datasets(db: AsyncSession) -> list[dict[str, Any]] | None:
    """Step 1 dataset catalog: upstream demo catalog plus the current risk asset.

    The upstream catalog cannot express the versioned topic3 risk series, and
    the adapter filters it out on purpose so stale or duplicate versions never
    reach the page. The current version is therefore injected here, from the
    same resolution that later serves its samples and same-version results.
    """
    from app.services.benchmark_topic3_risk_series_service import (
        BenchmarkTopic3RiskSeriesError,
        BenchmarkTopic3RiskSeriesNotFoundError,
        asset_overview,
        resolve_asset,
    )

    upstream = await _adapter_datasets()
    try:
        resolved = await resolve_asset(db)
    except BenchmarkTopic3RiskSeriesNotFoundError:
        logger.info("no current topic3 risk asset registered; serving upstream catalog only")
        return upstream
    except BenchmarkTopic3RiskSeriesError as exc:
        # Never fall back to another version: serve the upstream catalog without
        # a risk entry and leave a trace for operators.
        logger.warning("current topic3 risk asset could not be resolved: %s", exc)
        return upstream

    current = _topic3_risk_catalog_item(asset_overview(resolved))
    if current is None:
        return upstream
    return [current, *(upstream or [])]


async def start_eval_task(
    dataset_ids: list[str],
    selected_dimensions: list[str] | None = None,
) -> EvalStartResponse | None:
    resp = await _adapter_start_eval(dataset_ids, selected_dimensions)
    if resp is None:
        return None
    await save_task(
        resp.task_id,
        dataset_ids,
        selected_dimensions,
        source="benchmark",
        benchmark_job_id=resp.task_id,
    )
    return resp


async def get_eval_results(task_id: str) -> EvalResultSummary | None:
    summary = await _adapter_eval_results(task_id)
    if summary is None:
        return None
    await save_task_results(
        task_id,
        metrics=summary.metrics.model_dump(),
        samples=[s.model_dump() for s in summary.samples],
        source="benchmark",
    )
    return summary


infer_single_sample = _adapter_infer


def _identity_tuple(payload: dict[str, Any]) -> tuple[str, str | None, str]:
    return (
        str(payload.get("asset_id") or ""),
        payload.get("asset_version") if payload.get("asset_version") is not None else None,
        str(payload.get("asset_sha256") or ""),
    )


async def get_topic3_risk_same_version(
    db: AsyncSession,
    *,
    asset_version: str | None = None,
    asset_id: str | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Read one topic3 risk asset and the evaluation runs that belong to it.

    Omitted version means the current asset. An explicit version or asset id
    selects that asset. Sample rows and evaluator results are taken from the
    same resolved asset; a model id that is not one of those runs is refused.
    """
    from app.services.benchmark_topic3_risk_sample_service import (
        BenchmarkTopic3RiskSampleService,
    )
    from app.services.benchmark_topic3_risk_series_service import (
        BenchmarkTopic3RiskSeriesError,
        asset_overview,
        build_resolved_evaluation_summary,
        list_versions,
        resolve_asset,
    )

    resolved = await resolve_asset(db, asset_version=asset_version, asset_id=asset_id)
    overview = asset_overview(resolved)
    evaluation = build_resolved_evaluation_summary(resolved)
    samples = BenchmarkTopic3RiskSampleService().list_resolved_samples(resolved, limit=20)
    sample_service = BenchmarkTopic3RiskSampleService()
    sample_details = [
        sample_service.get_resolved_sample(resolved, sample_id=str(item["sample_id"]))
        for item in samples["samples"]
    ]
    if _identity_tuple(samples) != _identity_tuple(evaluation):
        raise BenchmarkTopic3RiskSeriesError(
            "topic3 risk data and results are not the same asset version"
        )
    for detail in sample_details:
        if _identity_tuple(detail) != _identity_tuple(evaluation):
            raise BenchmarkTopic3RiskSeriesError(
                "topic3 risk sample does not belong to the selected asset version"
            )

    results = [item for item in evaluation.get("results") or [] if isinstance(item, dict)]
    allowed_models = {str(item.get("model_id") or "") for item in results}
    requested_model = model_id.strip() if model_id and model_id.strip() else None
    if requested_model is not None and requested_model not in allowed_models:
        raise BenchmarkTopic3RiskSeriesError(
            "model_id is not an evaluator of the selected asset version"
        )

    primary_runs = [item for item in results if item.get("role") == "primary"]
    baseline_runs = [item for item in results if item.get("role") == "baseline"]
    chosen = primary_runs[0] if primary_runs else (results[0] if results else None)
    primary = primary_runs[0] if primary_runs else None
    artifact_dir = Path(resolved.asset.artifact_dir)
    task = _primary_evaluator_task(artifact_dir, primary)
    predictions = _primary_prediction_rows(artifact_dir, primary)
    automatic_explanations = []
    for detail in sample_details:
        if not detail.get("label_reason_usable_for_automatic_explanation"):
            continue
        text = str(detail.get("label_reason") or "").strip()
        if not text:
            continue
        automatic_explanations.append(
            {
                "sample_id": detail["sample_id"],
                "asset_id": detail["asset_id"],
                "asset_version": detail.get("asset_version"),
                "asset_sha256": detail["asset_sha256"],
                "text": text,
            }
        )

    versions = await list_versions(db)
    return {
        **resolved.identity(),
        "name": overview["name"],
        "sample_count": overview["sample_count"],
        "evaluation_status": overview["evaluation_status"],
        "samples": samples,
        "sample_details": sample_details,
        "evaluation": evaluation,
        "primary_evaluator": {
            "available": bool(primary_runs),
            "model_id": primary_runs[0].get("model_id") if primary_runs else None,
            "run_id": primary_runs[0].get("run_id") if primary_runs else None,
        },
        "result_display": {
            "available": bool(evaluation.get("available")),
            "requires_baseline": False,
            "model_id": chosen.get("model_id") if chosen else None,
            "run_id": chosen.get("run_id") if chosen else None,
            "role": chosen.get("role") if chosen else None,
            "task": task,
            "primary_metrics": (chosen or {}).get("primary_metrics") or {},
            "supporting_metrics": (chosen or {}).get("supporting_metrics") or {},
        },
        "predictions": predictions,
        "baseline": {
            "available": bool(baseline_runs),
            "same_version": True,
            "model_id": baseline_runs[0].get("model_id") if baseline_runs else None,
            "message": "" if baseline_runs else "暂无同版本基线",
        },
        "automatic_explanations": automatic_explanations,
        "versions": [
            {
                "series_id": item["series_id"],
                "asset_id": item["asset_id"],
                "asset_version": item["asset_version"],
                "asset_sha256": item["asset_sha256"],
                "asset_status": item["asset_status"],
                "name": item["name"],
                "sample_count": item["sample_count"],
            }
            for item in versions["versions"]
        ],
    }


async def get_topic3_risk_same_version_for_dataset(
    db: AsyncSession,
    dataset_id: str,
    model_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the same-version view when ``dataset_id`` is a topic3 risk asset.

    Unknown dataset ids stay ``None`` so older demo catalogs can still be read.
    A model id that belongs to another asset version is refused.
    """
    from app.services.benchmark_topic3_risk_series_service import (
        BenchmarkTopic3RiskSeriesNotFoundError,
    )

    if not dataset_id.strip():
        return None
    try:
        return await get_topic3_risk_same_version(
            db, asset_id=dataset_id, model_id=model_id
        )
    except BenchmarkTopic3RiskSeriesNotFoundError:
        return None


def same_version_static_result(payload: dict[str, Any]) -> dict[str, Any]:
    display = payload["result_display"]
    metrics = {
        **(display.get("primary_metrics") or {}),
        **(display.get("supporting_metrics") or {}),
    }
    if payload.get("sample_count") is not None and metrics.get("num_examples") is None:
        metrics = {**metrics, "num_examples": payload["sample_count"]}
    identity = {
        "series_id": payload["series_id"],
        "asset_id": payload["asset_id"],
        "asset_version": payload["asset_version"],
        "asset_sha256": payload["asset_sha256"],
        "asset_status": payload["asset_status"],
    }
    task = display.get("task") or ""
    return {
        "source": "topic3_same_version",
        **identity,
        "selected": {
            "metrics": metrics,
            "dataset_id": payload["asset_id"],
            "model_id": display.get("model_id") or "",
            "model_name": display.get("model_id") or "",
            "run_name": display.get("run_id") or "",
            "task": task,
            "result_version": payload["asset_version"],
        },
        "results": [
            {
                "dataset_id": payload["asset_id"],
                "model_id": display.get("model_id") or "",
                "task": task,
                **identity,
            }
        ],
    }


def same_version_static_predictions(payload: dict[str, Any]) -> dict[str, Any]:
    by_sample = {
        str(row.get("sample_id") or ""): row
        for row in payload.get("predictions") or []
        if isinstance(row, dict)
    }
    rows = []
    for detail in payload["sample_details"]:
        sample_id = str(detail["sample_id"])
        prediction = by_sample.get(sample_id)
        rows.append(
            {
                "sample_id": sample_id,
                "index": detail.get("index", ""),
                "example": {
                    "prompt": detail.get("prompt", ""),
                    "response": detail.get("response", ""),
                },
                "response": detail.get("response", ""),
                "risk_category": detail.get("risk_category", ""),
                "risk_level_id": detail.get("risk_level_id", ""),
                "label_reason_status": detail.get("label_reason_status", ""),
                "label_reason_usable_for_automatic_explanation": detail.get(
                    "label_reason_usable_for_automatic_explanation", False
                ),
                "prediction_missing": prediction is None,
                "pred_categories": None if prediction is None else prediction.get("pred_categories"),
                "prediction": None if prediction is None else prediction.get("prediction"),
            }
        )
    return {
        "source": "topic3_same_version",
        "series_id": payload["series_id"],
        "asset_id": payload["asset_id"],
        "asset_version": payload["asset_version"],
        "asset_sha256": payload["asset_sha256"],
        "asset_status": payload["asset_status"],
        "rows": rows,
    }


def _primary_evaluator_task(artifact_dir: Path, run: dict[str, Any] | None) -> str | None:
    """Task declared by the primary run. Missing task stays missing."""
    if run is None:
        return None
    direct = _task_text(run.get("task"))
    if direct:
        return direct
    manifest = _read_run_manifest(artifact_dir, run)
    if manifest is None:
        return None
    return _task_text(manifest.get("task"))


def _primary_prediction_rows(
    artifact_dir: Path, run: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Normalized predictions stored with the primary run, keyed by standard sample id."""
    if run is None:
        return []
    relative = run.get("normalized_predictions_path")
    if not isinstance(relative, str) or not relative.strip():
        return []
    path = _artifact_file(artifact_dir, relative)
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        sample_id = str(record.get("sample_id") or "").strip()
        if not sample_id:
            continue
        prediction = record.get("prediction")
        prediction_doc = prediction if isinstance(prediction, dict) else {}
        categories: list[str] | None
        if "pred_categories" not in prediction_doc:
            categories = None
        elif isinstance(prediction_doc.get("pred_categories"), list):
            categories = [
                str(item)
                for item in prediction_doc["pred_categories"]
                if str(item).strip()
            ]
        else:
            categories = None
        rows.append(
            {
                "sample_id": sample_id,
                "prediction": prediction_doc,
                "pred_categories": categories,
            }
        )
    return rows


def _read_run_manifest(artifact_dir: Path, run: dict[str, Any]) -> dict[str, Any] | None:
    run_id = str(run.get("run_id") or "")
    relative = run.get("manifest_path") or f"evaluations/{run_id}/evaluation_manifest.json"
    if not isinstance(relative, str):
        return None
    path = _artifact_file(artifact_dir, relative)
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_file(artifact_dir: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    root = artifact_dir.resolve()
    path = (root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _task_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
