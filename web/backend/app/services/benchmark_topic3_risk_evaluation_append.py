"""Append same-version evaluation runs to a current or historical topic3 risk asset (#153).

A run package holds ``evaluations/<run_id>/`` and no asset CSV. Registration is
bound to the target asset's registered content hash, which the run's own
``evaluation_manifest.json`` must declare. Appending never changes the asset
content, its version row, the current-version pointer or an already registered
run. Files are placed before the manifest is updated, so a failed append leaves
no run visible to ordinary queries.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.benchmark_topic3_risk_delivery_package import (
    EVALUATIONS_DIR,
    RAW_FILE,
    RUN_CORE_FILES,
    RUN_FILES,
    RUN_MANIFEST_NAME,
)
from app.services.benchmark_topic3_risk_delivery_service import delivery_limits
from app.services.benchmark_topic3_risk_delivery_validation import (
    extract_evaluation_run_package,
)
from app.services.benchmark_topic3_risk_identity import sha256_file
from app.services.benchmark_topic3_risk_series_service import (
    EVAL_MODE,
    RESULT_SOURCE,
    ResolvedTopic3RiskAsset,
    build_resolved_evaluation_summary,
    loads_json_object,
    resolve_asset,
)
from app.services.benchmark_topic3_risk_v6_service import BenchmarkTopic3RiskV6Service


logger = logging.getLogger(__name__)

APPEND_STAGING_DIR = ".evaluation-appends"
_VALID_ROLES = frozenset({"primary", "baseline"})
_MAX_MODEL_ID_CHARS = 200
_LOCKS: dict[str, asyncio.Lock] = {}


class BenchmarkEvaluationAppendError(RuntimeError):
    """The run package is valid HTTP-wise but cannot be registered."""


class BenchmarkEvaluationAppendConflictError(BenchmarkEvaluationAppendError):
    """A run id is already registered with different content."""


class BenchmarkEvaluationAppendNotFoundError(BenchmarkEvaluationAppendError):
    """The target asset is not a registered topic3 risk Benchmark version."""


class BenchmarkEvaluationAppendFailed(RuntimeError):
    """Registration failed after validation; nothing new is visible."""


@dataclass
class _IncomingRun:
    run_id: str
    source_dir: Path
    entry: dict[str, Any]
    content_sha256: str


def append_staging_root() -> Path:
    """Same volume as the catalog so a validated run can be moved atomically."""
    return BenchmarkTopic3RiskV6Service()._artifact_root() / APPEND_STAGING_DIR


async def append_evaluation_runs(
    db: AsyncSession,
    *,
    asset_id: str,
    package_path: Path,
    package_sha256: str,
    uploaded_by: str,
) -> dict[str, Any]:
    """Register every run in ``package_path`` under ``asset_id``.

    Idempotent per ``(run_id, run content)``. A different package for an already
    registered run id is rejected without changing that run or any other.
    """
    resolved = await resolve_asset(db, asset_id=asset_id)
    if resolved.asset_status == "unregistered":
        raise BenchmarkEvaluationAppendNotFoundError(
            f"asset is not a registered topic3 risk benchmark version: {asset_id}"
        )

    attempt_id = uuid.uuid4().hex
    attempt_dir = append_staging_root() / attempt_id
    content_dir = attempt_dir / "content"
    registered_at = datetime.now(timezone.utc).isoformat()
    try:
        extraction = await asyncio.to_thread(
            extract_evaluation_run_package,
            package_path,
            content_dir,
            limits=delivery_limits(),
        )
        if extraction.errors:
            raise BenchmarkEvaluationAppendError(_issue_message(extraction.errors))
        incoming = await asyncio.to_thread(
            validate_run_package,
            content_dir,
            resolved,
            package_sha256=package_sha256,
            uploaded_by=uploaded_by,
            registered_at=registered_at,
        )

        async with _lock_for(asset_id):
            db.expire_all()
            resolved = await resolve_asset(db, asset_id=asset_id)
            # The asset could have been re-registered while extraction ran;
            # never place a run bound to a hash other than the current one.
            _ensure_identity(incoming, resolved)
            return await _register(db, resolved, incoming, package_sha256)
    finally:
        shutil.rmtree(attempt_dir, ignore_errors=True)


def validate_run_package(
    content_dir: Path,
    resolved: ResolvedTopic3RiskAsset,
    *,
    package_sha256: str,
    uploaded_by: str,
    registered_at: str,
) -> list[_IncomingRun]:
    """Validate every run dir against the target asset and build manifest entries."""
    evaluations_dir = content_dir / EVALUATIONS_DIR
    if not evaluations_dir.is_dir():
        raise BenchmarkEvaluationAppendError(
            "evaluation run package has no evaluations/<run_id>/ directories"
        )
    run_dirs = sorted(item for item in evaluations_dir.iterdir() if item.is_dir())
    if not run_dirs:
        raise BenchmarkEvaluationAppendError(
            "evaluation run package has no evaluations/<run_id>/ directories"
        )
    if any(item.is_file() for item in evaluations_dir.iterdir()):
        raise BenchmarkEvaluationAppendError(
            "evaluations/ may contain only run directories"
        )

    target_manifest = loads_json_object(resolved.asset.manifest_json)
    sample_count = target_manifest.get("sample_count")
    incoming = [
        _validate_run(
            run_dir,
            resolved,
            sample_count=sample_count if isinstance(sample_count, int) else None,
            package_sha256=package_sha256,
            uploaded_by=uploaded_by,
            registered_at=registered_at,
        )
        for run_dir in run_dirs
    ]
    ids = [run.run_id for run in incoming]
    if len(ids) != len(set(ids)):
        raise BenchmarkEvaluationAppendError("evaluation run package repeats a run_id")
    return incoming


def _validate_run(
    run_dir: Path,
    resolved: ResolvedTopic3RiskAsset,
    *,
    sample_count: int | None,
    package_sha256: str,
    uploaded_by: str,
    registered_at: str,
) -> _IncomingRun:
    run_id = run_dir.name
    missing = [name for name in RUN_CORE_FILES if not (run_dir / name).is_file()]
    if missing:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: missing required files: {', '.join(missing)}"
        )

    manifest = _read_object(run_dir / RUN_MANIFEST_NAME, f"run {run_id}")
    if str(manifest.get("run_id") or "") != run_id:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: evaluation_manifest.run_id does not match its directory"
        )
    if str(manifest.get("asset_id") or "") != resolved.asset.asset_id:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: asset_id does not match the target asset "
            f"{resolved.asset.asset_id}"
        )
    if str(manifest.get("asset_sha256") or "") != resolved.asset_sha256:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: asset_sha256 does not match the target asset content hash"
        )

    metrics_doc = _read_object(run_dir / "metrics.json", f"run {run_id} metrics")
    metrics = metrics_doc.get("metrics")
    if not isinstance(metrics, dict):
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: metrics.json must contain a metrics object"
        )
    if str(metrics_doc.get("asset_id") or "") not in ("", resolved.asset.asset_id):
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: metrics.asset_id does not match the target asset"
        )
    if str(metrics_doc.get("asset_sha256") or "") not in ("", resolved.asset_sha256):
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: metrics.asset_sha256 does not match the target asset content hash"
        )
    if str(metrics_doc.get("run_id") or "") not in ("", run_id):
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: metrics.run_id does not match the run"
        )

    model = _single_model(run_id, manifest.get("models"))
    role = str(model.get("role") or "").strip().lower()
    if role not in _VALID_ROLES:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: model role must be primary or baseline"
        )
    model_id = str(model.get("model_id") or "").strip()
    if not model_id or len(model_id) > _MAX_MODEL_ID_CHARS:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: model_id is missing or too long"
        )

    predictions_count = _count_jsonl(run_dir / "predictions.jsonl", run_id)
    declared = manifest.get("predictions")
    declared_count = declared.get("count") if isinstance(declared, dict) else None
    if declared_count != predictions_count:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: predictions.jsonl has {predictions_count} records but "
            f"evaluation_manifest predictions.count is {declared_count!r}"
        )
    if sample_count is not None and predictions_count != sample_count:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: predictions cover {predictions_count} of {sample_count} samples"
        )

    raw_count = _check_raw(run_dir, run_id, manifest, predictions_count)
    root = f"{EVALUATIONS_DIR}/{run_id}"
    entry = {
        "run_id": run_id,
        "asset_id": resolved.asset.asset_id,
        "asset_sha256": resolved.asset_sha256,
        "model_id": model_id,
        "model_name": str(model.get("model_name") or model_id),
        "model_version": str(model.get("model_version") or ""),
        "model_run_id": str(model.get("model_run_id") or ""),
        "role": role,
        "eval_mode": EVAL_MODE,
        "result_source": str(manifest.get("result_source") or RESULT_SOURCE),
        "evaluated_at": str(manifest.get("evaluated_at") or ""),
        "predictions_count": predictions_count,
        "raw_count": raw_count,
        "metrics_path": f"{root}/metrics.json",
        "predictions_path": f"{root}/predictions.jsonl",
        "manifest_path": f"{root}/{RUN_MANIFEST_NAME}",
        "report_path": f"{root}/report.md",
        "run_content_sha256": run_content_sha256(run_dir),
        "source_package_sha256": package_sha256,
        "registered_by": uploaded_by,
        "registered_at": registered_at,
    }
    return _IncomingRun(
        run_id=run_id,
        source_dir=run_dir,
        entry=entry,
        content_sha256=entry["run_content_sha256"],
    )


def _ensure_identity(
    incoming: list[_IncomingRun], resolved: ResolvedTopic3RiskAsset
) -> None:
    for run in incoming:
        if (
            run.entry["asset_id"] != resolved.asset.asset_id
            or run.entry["asset_sha256"] != resolved.asset_sha256
        ):
            raise BenchmarkEvaluationAppendError(
                f"run {run.run_id}: asset identity changed while the package was validated"
            )


def _single_model(run_id: str, models: Any) -> dict[str, Any]:
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: evaluation_manifest.models must contain exactly one model"
        )
    return models[0]


def _check_raw(
    run_dir: Path, run_id: str, manifest: dict[str, Any], predictions_count: int
) -> int:
    if not (run_dir / RAW_FILE).is_file():
        return 0
    raw_count = _count_jsonl(run_dir / RAW_FILE, run_id)
    declared = manifest.get("raw")
    declared_count = declared.get("count") if isinstance(declared, dict) else None
    if declared_count is not None and declared_count != raw_count:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: raw has {raw_count} records but evaluation_manifest "
            f"raw.count is {declared_count!r}"
        )
    if raw_count != predictions_count:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: raw has {raw_count} records but predictions has "
            f"{predictions_count}"
        )
    return raw_count


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkEvaluationAppendError(f"{label}: {path.name} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BenchmarkEvaluationAppendError(
            f"{label}: {path.name} must contain a JSON object"
        )
    return payload


def _count_jsonl(path: Path, run_id: str) -> int:
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise BenchmarkEvaluationAppendError(
                        f"run {run_id}: {path.name}:{line_number} is not valid JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise BenchmarkEvaluationAppendError(
                        f"run {run_id}: {path.name}:{line_number} must contain a JSON object"
                    )
                count += 1
    except OSError as exc:
        raise BenchmarkEvaluationAppendError(
            f"run {run_id}: {path.name} cannot be read"
        ) from exc
    if count == 0:
        raise BenchmarkEvaluationAppendError(f"run {run_id}: {path.name} is empty")
    return count


def run_content_sha256(run_dir: Path) -> str:
    """Stable digest of a run's source files, excluding derived normalized output."""
    digest = hashlib.sha256()
    for name in sorted(name for name in RUN_FILES if (run_dir / name).is_file()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(run_dir / name).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


async def _register(
    db: AsyncSession,
    resolved: ResolvedTopic3RiskAsset,
    incoming: list[_IncomingRun],
    package_sha256: str,
) -> dict[str, Any]:
    asset = resolved.asset
    asset_dir = Path(asset.artifact_dir)
    manifest = loads_json_object(asset.manifest_json)
    existing_entries = [
        item for item in manifest.get("evaluation_results", []) if isinstance(item, dict)
    ]
    existing_by_id = {str(item.get("run_id") or ""): item for item in existing_entries}

    statuses: dict[str, dict[str, Any]] = {}
    new_runs: list[_IncomingRun] = []
    for run in incoming:
        existing = existing_by_id.get(run.run_id)
        if existing is not None:
            if _existing_run_digest(asset_dir, existing) != run.content_sha256:
                raise BenchmarkEvaluationAppendConflictError(
                    f"run {run.run_id} is already registered with different content"
                )
            statuses[run.run_id] = _run_status(run, "already_registered")
            continue
        new_runs.append(run)

    if new_runs:
        placed: list[Path] = []
        try:
            for run in new_runs:
                final = asset_dir / EVALUATIONS_DIR / run.run_id
                final.parent.mkdir(parents=True, exist_ok=True)
                if final.exists():
                    # An unregistered leftover is invisible; the incoming content wins.
                    shutil.rmtree(final)
                os.replace(run.source_dir, final)
                placed.append(final)
            entries = existing_entries + [run.entry for run in new_runs]
            entries.sort(key=_entry_sort_key)
            manifest["evaluation_results"] = entries
            manifest["evaluation_status"] = "evaluation_imported"
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            asset.manifest_json = json.dumps(manifest, ensure_ascii=False)
            await db.commit()
        except BenchmarkEvaluationAppendError:
            await db.rollback()
            _remove_placed(placed)
            raise
        except Exception as exc:
            logger.exception("Appending evaluation runs to %s failed", asset.asset_id)
            await db.rollback()
            _remove_placed(placed)
            raise BenchmarkEvaluationAppendFailed("evaluation run append failed") from exc
        statuses.update({run.run_id: _run_status(run, "appended") for run in new_runs})

    await db.refresh(asset)
    current = await resolve_asset(db, asset_id=asset.asset_id)
    sample_count = loads_json_object(current.asset.manifest_json).get("sample_count")
    return {
        **current.identity(),
        "name": current.asset.name,
        "sample_count": sample_count if isinstance(sample_count, int) else None,
        "package_sha256": package_sha256,
        "runs": [statuses[run.run_id] for run in incoming],
        "evaluation": build_resolved_evaluation_summary(current),
    }


def _existing_run_digest(asset_dir: Path, entry: dict[str, Any]) -> str | None:
    run_id = str(entry.get("run_id") or "")
    if not run_id:
        return None
    root = str(entry.get("path") or f"{EVALUATIONS_DIR}/{run_id}")
    run_dir = asset_dir / root
    if run_dir.is_dir():
        # Read what is actually registered, not just what was recorded at
        # registration time: a run changed on disk must not look idempotent.
        return run_content_sha256(run_dir)
    stored = entry.get("run_content_sha256")
    return stored if isinstance(stored, str) and stored else None


def _run_status(run: _IncomingRun, status: str) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": status,
        "run_content_sha256": run.content_sha256,
        "model_id": run.entry["model_id"],
        "role": run.entry["role"],
    }


def _entry_sort_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    role = str(entry.get("role") or "")
    return (
        0 if role == "primary" else 1 if role == "baseline" else 2,
        str(entry.get("model_id") or ""),
        str(entry.get("run_id") or ""),
    )


def _remove_placed(placed: list[Path]) -> None:
    for path in placed:
        shutil.rmtree(path, ignore_errors=True)


def _lock_for(asset_id: str) -> asyncio.Lock:
    lock = _LOCKS.get(asset_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[asset_id] = lock
    return lock


def _issue_message(errors: list[dict[str, str]]) -> str:
    codes = sorted({str(item.get("code") or "invalid") for item in errors})
    return f"evaluation run package failed validation: {', '.join(codes)}"
