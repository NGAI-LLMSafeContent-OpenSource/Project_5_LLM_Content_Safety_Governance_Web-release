"""Publish one validated topic3 risk delivery as the current Benchmark version (#152).

Normalization pairs each prediction with the raw record at the same position
only after their source indexes match, then with the CSV row whose standard
``sample_id`` is the raw record's unique id. Nothing is reordered to force a
match. Original predictions, metrics, report and raw bytes are copied unchanged.
The asset directory is prepared outside the catalog, then the asset, its
same-version results and the current-version pointer commit together.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset, BenchmarkDelivery
from app.services.benchmark_topic3_risk_delivery_package import (
    MANIFEST_NAME,
    RAW_FILE,
    RUN_FILES,
    RUN_MANIFEST_NAME,
    SAMPLE_ID_FIELD,
)
from app.services.benchmark_topic3_risk_delivery_service import (
    CONTENT_DIR,
    PACKAGE_FILE,
    DeliveryStatus,
    PublishClaim,
    begin_publish,
    get_delivery,
    mark_delivery_published,
    release_publish_claim,
)
from app.services.benchmark_topic3_risk_delivery_validation import RAW_SAMPLE_ID_PATH
from app.services.benchmark_topic3_risk_identity import SERIES_ID, sha256_file
from app.services.benchmark_topic3_risk_series_service import (
    BENCHMARK_TYPE,
    EVAL_MODE,
    RESULT_SOURCE,
    SOURCE_MODE,
    BenchmarkTopic3RiskSeriesError,
    register_asset_version,
)
from app.services.benchmark_topic3_risk_v6_service import BenchmarkTopic3RiskV6Service


logger = logging.getLogger(__name__)

NORMALIZED_PREDICTIONS_FILE = "predictions.normalized.jsonl"
SAMPLES_FILE = "samples.jsonl"
_ARTIFACT_ZIP = "artifacts/topic3_risk_asset.zip"
_CATEGORY_RE = re.compile(r"C(0[1-9]|1[0-7])")
_MAPPING_MESSAGE = (
    "benchmark delivery cannot be published because its records do not map uniquely"
)


class _StringEnum(str, Enum):
    """Python 3.10-compatible string enum."""

    def __str__(self) -> str:
        return self.value


class PublishOutcome(_StringEnum):
    PUBLISHED = "published"
    IDEMPOTENT = "idempotent"
    IN_PROGRESS = "in_progress"
    NOT_PUBLISHABLE = "not_publishable"
    NOT_FOUND = "not_found"
    MAPPING_REJECTED = "mapping_rejected"
    REJECTED = "rejected"


class BenchmarkDeliveryPublishError(RuntimeError):
    """Raised when a publish attempt cannot be completed."""


class BenchmarkDeliveryMappingError(BenchmarkDeliveryPublishError):
    """Raised when records cannot be paired without guessing."""

    def __init__(self, reason: str) -> None:
        super().__init__(_MAPPING_MESSAGE)
        self.reason = reason


class BenchmarkDeliveryPublishFailed(BenchmarkDeliveryPublishError):
    """Raised after a failed publish has been rolled back."""


@dataclass
class AssetBlueprint:
    asset_id: str
    asset_version: str
    task_id: str
    name: str
    csv_name: str
    csv_bytes: bytes
    samples_jsonl: bytes
    files: dict[str, bytes]
    manifest: dict[str, Any]
    artifact_sha256: str = ""
    source_repo: str = ""
    source_commit: str = ""


async def commit_publish(db: AsyncSession) -> None:
    """Commit the publish transaction. Tests replace this to simulate a failure."""
    await db.commit()


async def publish_delivery(
    db: AsyncSession, delivery_id: str
) -> tuple[BenchmarkDelivery | None, PublishOutcome]:
    """Publish ``delivery_id`` or leave the current Benchmark version untouched."""
    row = await get_delivery(db, delivery_id)
    if row is None:
        return None, PublishOutcome.NOT_FOUND
    early = _early_outcome(row)
    if early is not None:
        return row, early
    try:
        blueprint = await asyncio.to_thread(build_asset_blueprint, row)
    except BenchmarkDeliveryMappingError as exc:
        logger.info(
            "Benchmark delivery %s was not published (%s)", delivery_id, exc.reason
        )
        return row, PublishOutcome.MAPPING_REJECTED
    except OSError as exc:
        logger.exception("Benchmark delivery %s could not be read for publish", delivery_id)
        raise BenchmarkDeliveryPublishFailed("benchmark delivery publish failed") from exc

    row, claim = await begin_publish(db, delivery_id)
    if claim != PublishClaim.CLAIMED or row is None:
        return row, _from_claim(claim)
    directory_exists = _asset_directory(blueprint.asset_id).exists()
    if await _asset_exists(db, blueprint.asset_id) or directory_exists:
        await release_publish_claim(db, delivery_id, row.attempt_id)
        return await get_delivery(db, delivery_id), PublishOutcome.REJECTED

    placed: Path | None = None
    preparing = _preparing_dir(row.attempt_id or "")
    committed = False
    try:
        placed = await asyncio.to_thread(place_asset_directory, blueprint, row.attempt_id or "")
        await _register(db, row, blueprint, placed)
        await commit_publish(db)
        committed = True
    except Exception as exc:
        logger.exception("Benchmark delivery publish failed: %s", delivery_id)
        if not committed:
            await _abandon(db, delivery_id, row.attempt_id or "", placed, preparing, blueprint.asset_id)
        raise BenchmarkDeliveryPublishFailed("benchmark delivery publish failed") from exc
    return await get_delivery(db, delivery_id), PublishOutcome.PUBLISHED


def build_asset_blueprint(row: BenchmarkDelivery) -> AssetBlueprint:
    """Read the staged package and build the asset tree in memory."""
    content = _content_dir(row)
    manifest = _read_json(content / MANIFEST_NAME)
    asset_id = str(row.asset_id or "")
    asset_version = str(row.asset_version or "")
    if row.series_id != SERIES_ID or not asset_version or len(asset_id) > 64:
        raise BenchmarkDeliveryMappingError("delivery_identity")
    package_path = Path(row.staging_dir or "") / PACKAGE_FILE
    if sha256_file(package_path) != row.package_sha256:
        raise BenchmarkDeliveryMappingError("package_hash_mismatch")

    asset_file = str(manifest.get("asset_file") or "")
    csv_path = content / asset_file
    csv_bytes = csv_path.read_bytes()
    asset_sha256 = sha256_file(csv_path)
    if asset_sha256 != str(manifest.get("asset_sha256") or ""):
        raise BenchmarkDeliveryMappingError("asset_hash_mismatch")
    csv_rows = _read_csv_rows(csv_bytes)
    runs = manifest.get("evaluation_runs")
    if not isinstance(runs, list) or not runs:
        raise BenchmarkDeliveryMappingError("missing_runs")

    files: dict[str, bytes] = {}
    entries = []
    for run in runs:
        if not isinstance(run, dict):
            raise BenchmarkDeliveryMappingError("missing_runs")
        entries.append(_prepare_run(content, run, csv_rows, asset_id, asset_sha256, files))
    entries.sort(key=lambda item: (0 if item.get("role") == "primary" else 1, item["model_id"]))

    csv_name = f"{asset_id}.csv"
    task_id = f"prerun_{asset_id[:56]}"
    lineage = {
        "provider": row.provider,
        "delivery_id": row.delivery_id,
        "package_sha256": row.package_sha256,
        "uploaded_by": row.uploaded_by,
        "received_at": row.received_at.isoformat(),
    }
    asset_manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "task_id": task_id,
        "name": f"课题三风险分级分类 Benchmark {asset_version}",
        "source_mode": SOURCE_MODE,
        "benchmark_type": BENCHMARK_TYPE,
        "series_id": SERIES_ID,
        "asset_version": asset_version,
        "taxonomy_schema": "C01-C17",
        "asset_sha256": asset_sha256,
        "sample_count": len(csv_rows),
        "evaluation_status": "evaluation_imported",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "content_csv": csv_name,
            "samples": SAMPLES_FILE,
            "artifact_zip": _ARTIFACT_ZIP,
        },
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "raw_download_allowed": False,
            "note": "完整样本仅内部详情查看；raw 不提供下载地址。",
        },
        "lineage": lineage,
        "evaluation_results": entries,
        "checksums": {"asset_csv_sha256": asset_sha256},
    }
    return AssetBlueprint(
        asset_id=asset_id,
        asset_version=asset_version,
        task_id=task_id,
        name=str(asset_manifest["name"]),
        csv_name=csv_name,
        csv_bytes=csv_bytes,
        samples_jsonl=_samples_jsonl(csv_rows),
        files=files,
        manifest=asset_manifest,
        source_repo=row.provider,
        source_commit=row.package_sha256,
    )


def materialize_asset_directory(destination: Path, blueprint: AssetBlueprint) -> None:
    """Write one complete asset tree. The destination must not already exist."""
    if destination.exists():
        raise OSError("publish preparation directory already exists")
    destination.mkdir(parents=True)
    try:
        _write_bytes(destination / blueprint.csv_name, blueprint.csv_bytes)
        _write_bytes(destination / SAMPLES_FILE, blueprint.samples_jsonl)
        for relative, payload in blueprint.files.items():
            _write_bytes(destination / relative, payload)
        _write_manifest(destination, blueprint.manifest)
        _write_asset_zip(destination, blueprint)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def place_asset_directory(blueprint: AssetBlueprint, attempt_id: str) -> Path:
    """Materialize under a hidden preparing directory, then move it into place."""
    preparing = _preparing_dir(attempt_id)
    final = _asset_directory(blueprint.asset_id)
    shutil.rmtree(preparing, ignore_errors=True)
    materialize_asset_directory(preparing, blueprint)
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        shutil.rmtree(preparing, ignore_errors=True)
        raise BenchmarkDeliveryPublishError(
            "benchmark asset directory already exists and was not replaced"
        )
    os.replace(preparing, final)
    return final


def _prepare_run(
    content: Path,
    run: dict[str, Any],
    csv_rows: list[dict[str, str]],
    asset_id: str,
    asset_sha256: str,
    files: dict[str, bytes],
) -> dict[str, Any]:
    run_id = str(run.get("run_id") or "")
    run_root = str(run.get("path") or "")
    if not run_id or run_root != f"evaluations/{run_id}":
        raise BenchmarkDeliveryMappingError("missing_runs")
    run_dir = content / run_root
    for name in RUN_FILES:
        files[f"{run_root}/{name}"] = (run_dir / name).read_bytes()
    predictions = _read_jsonl(files[f"{run_root}/predictions.jsonl"])
    raw_records = _read_jsonl(files[f"{run_root}/{RAW_FILE}"])
    mapped = _map_records(predictions, raw_records, csv_rows)
    normalized_rel = f"{run_root}/{NORMALIZED_PREDICTIONS_FILE}"
    files[normalized_rel] = _normalized_jsonl(mapped)
    run_manifest = json.loads(files[f"{run_root}/{RUN_MANIFEST_NAME}"].decode("utf-8"))
    if not isinstance(run_manifest, dict):
        raise BenchmarkDeliveryMappingError("missing_runs")
    models = run_manifest.get("models")
    model = _primary_model(models if isinstance(models, list) else [])
    return {
        "run_id": run_id,
        "asset_id": asset_id,
        "asset_sha256": asset_sha256,
        "model_id": str(model.get("model_id") or ""),
        "model_name": str(model.get("model_name") or model.get("model_id") or ""),
        "model_version": str(model.get("model_version") or ""),
        "model_run_id": str(model.get("model_run_id") or ""),
        "role": str(model.get("role") or ""),
        "eval_mode": EVAL_MODE,
        "result_source": str(run_manifest.get("result_source") or RESULT_SOURCE),
        "evaluated_at": str(run_manifest.get("evaluated_at") or ""),
        "predictions_count": len(mapped),
        "metrics_path": f"{run_root}/metrics.json",
        "predictions_path": f"{run_root}/predictions.jsonl",
        "normalized_predictions_path": normalized_rel,
        "manifest_path": f"{run_root}/{RUN_MANIFEST_NAME}",
        "report_path": f"{run_root}/report.md",
    }


def _map_records(
    predictions: list[tuple[int, dict[str, Any]]],
    raw_records: list[tuple[int, dict[str, Any]]],
    csv_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Pair by position only when source indexes already agree. Never reorder.

    The CSV ``source_index`` column is lineage from the upstream source and may
    repeat (or omit the value). Evaluation order is anchored by the CSV
    ``index`` column, which must equal the predictions/raw top-level id.
    """
    if len(predictions) != len(raw_records) or len(predictions) != len(csv_rows):
        raise BenchmarkDeliveryMappingError("count_mismatch")
    by_sample_id: dict[str, dict[str, str]] = {}
    for row in csv_rows:
        sample_id = str(row.get(SAMPLE_ID_FIELD) or "").strip()
        if not sample_id or sample_id in by_sample_id:
            raise BenchmarkDeliveryMappingError("sample_id_not_unique")
        by_sample_id[sample_id] = row

    seen: set[str] = set()
    mapped = []
    for (pred_line, prediction), (raw_line, raw) in zip(predictions, raw_records):
        source_index = _top_level_id(prediction)
        if not source_index or source_index != _top_level_id(raw):
            raise BenchmarkDeliveryMappingError("source_index_mismatch")
        sample_id = _raw_standard_id(raw)
        if not sample_id or sample_id in seen or sample_id not in by_sample_id:
            raise BenchmarkDeliveryMappingError("sample_id_not_unique")
        csv_row = by_sample_id[sample_id]
        csv_index = str(csv_row.get("index") or "").strip()
        if csv_index != source_index:
            raise BenchmarkDeliveryMappingError("source_index_mismatch")
        seen.add(sample_id)
        mapped.append(
            {
                "sample_id": sample_id,
                "source_index": source_index,
                "source_top_level_id": source_index,
                "source_predictions_line": pred_line,
                "source_raw_line": raw_line,
                "prediction": prediction,
            }
        )
    if seen != set(by_sample_id):
        raise BenchmarkDeliveryMappingError("sample_id_set_mismatch")
    return mapped


def _raw_standard_id(record: dict[str, Any]) -> str:
    value: Any = record
    for key in RAW_SAMPLE_ID_PATH:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _top_level_id(record: dict[str, Any]) -> str:
    value = record.get(SAMPLE_ID_FIELD)
    if value is None:
        return ""
    return str(value).strip()


def _primary_model(models: list[Any]) -> dict[str, Any]:
    dicts = [model for model in models if isinstance(model, dict)]
    for model in dicts:
        if str(model.get("role") or "") == "primary":
            return model
    return dicts[0] if dicts else {}


def _samples_jsonl(rows: list[dict[str, str]]) -> bytes:
    lines = []
    for row in rows:
        payload = dict(row)
        payload[SAMPLE_ID_FIELD] = str(row.get(SAMPLE_ID_FIELD) or "").strip()
        payload["risk_category_code"] = ",".join(
            sorted({f"C{code}" for code in _CATEGORY_RE.findall(str(row.get("risk_category") or ""))})
        )
        lines.append(json.dumps(payload, ensure_ascii=False))
    text = "\n".join(lines)
    return (text + "\n").encode("utf-8") if text else b""


def _normalized_jsonl(mapped: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False) for record in mapped]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _read_csv_rows(payload: bytes) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise BenchmarkDeliveryMappingError("csv_unreadable") from exc
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        if row is None or not any((value or "").strip() for value in row.values()):
            continue
        rows.append({str(key): value or "" for key, value in row.items() if key is not None})
    return rows


def _read_jsonl(payload: bytes) -> list[tuple[int, dict[str, Any]]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise BenchmarkDeliveryMappingError("jsonl_unreadable") from exc
    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkDeliveryMappingError("jsonl_unreadable") from exc
        if not isinstance(record, dict):
            raise BenchmarkDeliveryMappingError("jsonl_unreadable")
        records.append((line_number, record))
    return records


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkDeliveryMappingError("manifest_unreadable") from exc
    if not isinstance(payload, dict):
        raise BenchmarkDeliveryMappingError("manifest_unreadable")
    return payload


def _content_dir(row: BenchmarkDelivery) -> Path:
    if not row.staging_dir:
        raise BenchmarkDeliveryMappingError("staging_missing")
    content = Path(row.staging_dir) / CONTENT_DIR
    if not content.is_dir():
        raise BenchmarkDeliveryMappingError("staging_missing")
    return content


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_manifest(destination: Path, manifest: dict[str, Any]) -> None:
    _write_bytes(
        destination / "manifest.platform.json",
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def _write_asset_zip(destination: Path, blueprint: AssetBlueprint) -> None:
    archive_path = destination / _ARTIFACT_ZIP
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    names = [blueprint.csv_name, SAMPLES_FILE, "manifest.platform.json"]
    names.extend(relative for relative in blueprint.files if not _is_raw_path(relative))
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(destination / name, arcname=name)
    blueprint.artifact_sha256 = sha256_file(archive_path)
    blueprint.manifest.setdefault("checksums", {})["artifact_zip_sha256"] = blueprint.artifact_sha256
    _write_manifest(destination, blueprint.manifest)


def _is_raw_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return normalized.endswith(RAW_FILE) or "/raw/" in normalized


def _early_outcome(row: BenchmarkDelivery) -> PublishOutcome | None:
    if row.status == DeliveryStatus.PUBLISHED:
        return PublishOutcome.IDEMPOTENT
    if row.status == DeliveryStatus.PUBLISHING and not _is_stale(row):
        return PublishOutcome.IN_PROGRESS
    if row.status not in {DeliveryStatus.PUBLISHABLE, DeliveryStatus.PUBLISHING}:
        return PublishOutcome.NOT_PUBLISHABLE
    return None


def _is_stale(row: BenchmarkDelivery) -> bool:
    limit = timedelta(seconds=get_settings().benchmark_delivery_stale_seconds)
    return datetime.now(timezone.utc).replace(tzinfo=None) - row.updated_at >= limit


def _from_claim(claim: PublishClaim) -> PublishOutcome:
    return {
        PublishClaim.IDEMPOTENT: PublishOutcome.IDEMPOTENT,
        PublishClaim.IN_PROGRESS: PublishOutcome.IN_PROGRESS,
        PublishClaim.NOT_FOUND: PublishOutcome.NOT_FOUND,
        PublishClaim.NOT_PUBLISHABLE: PublishOutcome.NOT_PUBLISHABLE,
    }.get(claim, PublishOutcome.NOT_PUBLISHABLE)


def _asset_directory(asset_id: str) -> Path:
    return BenchmarkTopic3RiskV6Service()._artifact_root() / "prerun" / asset_id


def _preparing_dir(attempt_id: str) -> Path:
    return BenchmarkTopic3RiskV6Service()._artifact_root() / ".publish-preparing" / attempt_id


async def _register(
    db: AsyncSession,
    row: BenchmarkDelivery,
    blueprint: AssetBlueprint,
    artifact_dir: Path,
) -> None:
    asset = BenchmarkAsset(
        asset_id=blueprint.asset_id,
        task_id=blueprint.task_id,
        source_mode=SOURCE_MODE,
        name=blueprint.name,
        manifest_json=json.dumps(blueprint.manifest, ensure_ascii=False),
        artifact_dir=str(artifact_dir),
        artifact_zip_path=str(artifact_dir / _ARTIFACT_ZIP),
        artifact_sha256=blueprint.artifact_sha256,
        source_repo=blueprint.source_repo,
        source_commit=blueprint.source_commit,
    )
    db.add(asset)
    try:
        await register_asset_version(
            db,
            asset=asset,
            asset_version=blueprint.asset_version,
            make_current=True,
        )
    except BenchmarkTopic3RiskSeriesError as exc:
        raise BenchmarkDeliveryPublishFailed("benchmark delivery publish failed") from exc
    if not await mark_delivery_published(db, row.delivery_id, row.attempt_id or ""):
        raise BenchmarkDeliveryPublishFailed("benchmark delivery publish lost its claim")


async def _asset_exists(db: AsyncSession, asset_id: str) -> bool:
    found = await db.execute(select(BenchmarkAsset.id).where(BenchmarkAsset.asset_id == asset_id))
    return found.scalar_one_or_none() is not None


async def _abandon(
    db: AsyncSession,
    delivery_id: str,
    attempt_id: str,
    placed: Path | None,
    preparing: Path | None,
    asset_id: str,
) -> None:
    try:
        await release_publish_claim(db, delivery_id, attempt_id)
    except Exception:
        logger.exception("Could not release Benchmark publish claim: %s", delivery_id)
        try:
            await db.rollback()
        except Exception:
            logger.exception("Could not roll back Benchmark publish: %s", delivery_id)
    if placed is not None and placed.name == asset_id and placed.parent.name == "prerun":
        shutil.rmtree(placed, ignore_errors=True)
    if preparing is not None and preparing.exists():
        shutil.rmtree(preparing, ignore_errors=True)


