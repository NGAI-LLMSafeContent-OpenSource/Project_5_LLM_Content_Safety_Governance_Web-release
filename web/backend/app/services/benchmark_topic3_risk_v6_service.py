from __future__ import annotations

import csv
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset
from app.services.benchmark_topic3_risk_series_service import (
    BENCHMARK_TYPE,
    EVAL_MODE,
    LEGACY_V6_ASSET_ID,
    LEGACY_V6_RELEASE_KIND,
    RESULT_SOURCE,
    SOURCE_MODE,
    BenchmarkTopic3RiskSeriesError,
    build_evaluation_summary,
    describe_asset,
    is_legacy_v6_manifest,
    load_json_object,
    loads_json_object,
    manifest_sha256,
    register_legacy_v6_if_unclaimed,
    sha256_file,
)


# Re-exported for governance consumers that still import them from here.
ASSET_ID = LEGACY_V6_ASSET_ID
RELEASE_KIND = LEGACY_V6_RELEASE_KIND
AGENT_ID = "topic3-risk-benchmark-generation"

CSV_FIELDS = [
    "index",
    "version",
    "culture",
    "language",
    "prompt",
    "response",
    "response_safetype",
    "risk_category",
    "risk_sub_category",
    "risk_level_id",
    "label_source",
    "response_text_original",
    "response_text_source",
    "source_index",
    "safe_type",
    "safe_mode",
    "label_reason",
]

REQUIRED_RESULT_FILES = [
    "evaluation_manifest.json",
    "predictions.jsonl",
    "metrics.json",
    "report.md",
]

BenchmarkTopic3RiskV6Error = BenchmarkTopic3RiskSeriesError


def _resolve_external_path(value: Path | str) -> Path:
    raw_value = str(value).strip()
    normalized = raw_value.replace("\\", "/")
    windows_match = re.match(r"^([a-zA-Z]):/(.*)$", normalized)
    if windows_match and os.name != "nt":
        raw_value = f"/mnt/{windows_match.group(1).lower()}/{windows_match.group(2)}"
    try:
        return Path(raw_value).expanduser().resolve()
    except OSError as exc:
        raise BenchmarkTopic3RiskV6Error(
            f"path is invalid or inaccessible: {raw_value}"
        ) from exc


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError as exc:
        raise BenchmarkTopic3RiskV6Error(
            f"path is invalid or inaccessible: {path}"
        ) from exc


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError as exc:
        raise BenchmarkTopic3RiskV6Error(
            f"path is invalid or inaccessible: {path}"
        ) from exc


class BenchmarkTopic3RiskV6Service:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def import_asset(
        self,
        db: AsyncSession,
        *,
        csv_path: Path | str,
        asset_id: str | None = None,
        name: str | None = None,
    ) -> BenchmarkAsset:
        source_path = _resolve_external_path(csv_path)
        if not _is_file(source_path):
            raise BenchmarkTopic3RiskV6Error(f"csv_path not found: {source_path}")
        resolved_asset_id = _clean_asset_id(asset_id) or ASSET_ID

        existing = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == resolved_asset_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise BenchmarkTopic3RiskV6Error(f"asset already exists: {resolved_asset_id}")

        rows = _load_v6_csv(source_path)
        asset_sha256 = sha256_file(source_path)
        summary = _summarize_rows(rows)

        root_dir = self._artifact_root() / "prerun" / resolved_asset_id
        if root_dir.exists():
            raise BenchmarkTopic3RiskV6Error(
                f"asset directory already exists: {root_dir}"
            )
        artifacts_dir = root_dir / "artifacts"
        evaluations_dir = root_dir / "evaluations"

        try:
            root_dir.mkdir(parents=True, exist_ok=False)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            evaluations_dir.mkdir(parents=True, exist_ok=True)

            csv_name = source_path.name
            shutil.copy2(source_path, root_dir / csv_name)
            samples_path = root_dir / "samples_v6.jsonl"
            samples_path.write_text(
                "".join(
                    json.dumps(_row_with_sample_id(row), ensure_ascii=False) + "\n"
                    for row in rows
                ),
                encoding="utf-8",
            )

            manifest = _build_v6_manifest(
                asset_id=resolved_asset_id,
                name=name or "课题三 v6 风险内容分级分类动态评测集",
                csv_name=csv_name,
                asset_sha256=asset_sha256,
                summary=summary,
                source_path=source_path,
            )
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            archive_path = artifacts_dir / "topic3_risk_v6_asset.zip"
            _write_asset_zip(root_dir, archive_path, [csv_name, "samples_v6.jsonl"])
            artifact_sha256 = sha256_file(archive_path)
            manifest["checksums"]["artifact_zip_sha256"] = artifact_sha256
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
            source_repo=get_settings().topic3_risk_benchmark_source_repo,
            source_commit=get_settings().topic3_risk_benchmark_source_commit,
        )
        db.add(asset)
        await register_legacy_v6_if_unclaimed(db, asset)
        await db.commit()
        await db.refresh(asset)
        return asset

    async def import_evaluation_result(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        result_dir: Path | str,
    ) -> dict[str, Any]:
        asset = await _get_legacy_v6_asset(db, asset_id)
        asset_sha256 = (await describe_asset(db, asset)).asset_sha256
        source_dir = _resolve_external_path(result_dir)
        if not _is_dir(source_dir):
            raise BenchmarkTopic3RiskV6Error(f"result_dir not found: {source_dir}")

        result = _load_result_package(source_dir)
        manifest = json.loads(asset.manifest_json or "{}")
        if result["asset_id"] != asset.asset_id:
            raise BenchmarkTopic3RiskV6Error(
                f"result asset_id mismatch: {result['asset_id']} != {asset.asset_id}"
            )
        if asset_sha256 and result["asset_sha256"] != asset_sha256:
            raise BenchmarkTopic3RiskV6Error("result asset_sha256 does not match asset")

        target_dir = Path(asset.artifact_dir) / "evaluations" / result["run_id"]
        if target_dir.exists():
            raise BenchmarkTopic3RiskV6Error(
                f"evaluation result already exists: {result['run_id']}"
            )
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target_dir)

        entry = {
            "run_id": result["run_id"],
            "asset_id": result["asset_id"],
            "asset_sha256": result["asset_sha256"],
            "model_id": result["model_id"],
            "model_name": result["model_name"],
            "model_version": result["model_version"],
            "model_run_id": result["model_run_id"],
            "role": result["role"],
            "eval_mode": EVAL_MODE,
            "result_source": result["result_source"],
            "evaluated_at": result["evaluated_at"],
            "predictions_count": result["predictions_count"],
            "metrics_path": f"evaluations/{result['run_id']}/metrics.json",
            "predictions_path": f"evaluations/{result['run_id']}/predictions.jsonl",
            "manifest_path": f"evaluations/{result['run_id']}/evaluation_manifest.json",
            "report_path": f"evaluations/{result['run_id']}/report.md",
        }
        existing = [
            item
            for item in manifest.get("evaluation_results", [])
            if isinstance(item, dict) and item.get("run_id") != entry["run_id"]
        ]
        existing.append(entry)
        manifest["evaluation_results"] = sorted(
            existing,
            key=lambda item: (0 if item.get("role") == "primary" else 1, item["model_id"]),
        )
        manifest["evaluation_status"] = "evaluation_imported"
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        asset.manifest_json = json.dumps(manifest, ensure_ascii=False)
        await db.commit()
        await db.refresh(asset)
        return self.build_evaluation_summary(asset)

    def build_evaluation_summary(self, asset: BenchmarkAsset) -> dict[str, Any]:
        """Asset-only summary for callers without a database session (governance)."""
        return build_evaluation_summary(asset, asset_sha256=manifest_sha256(asset))


async def _get_legacy_v6_asset(db: AsyncSession, asset_id: str) -> BenchmarkAsset:
    result = await db.execute(select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise BenchmarkTopic3RiskV6Error("asset not found")
    if not is_legacy_v6_manifest(loads_json_object(asset.manifest_json)):
        raise BenchmarkTopic3RiskV6Error("asset is not a topic3 v6 benchmark asset")
    return asset


def _clean_asset_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cleaned):
        raise BenchmarkTopic3RiskV6Error(
            "asset_id must contain only letters, numbers, '_' or '-' and be <= 64 chars"
        )
    return cleaned


def _load_v6_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise BenchmarkTopic3RiskV6Error(
                f"csv schema mismatch; expected={CSV_FIELDS}; actual={reader.fieldnames}"
            )
        rows = [dict(row) for row in reader]
    if not rows:
        raise BenchmarkTopic3RiskV6Error("csv must not be empty")
    for row_number, row in enumerate(rows, 2):
        _validate_v6_row(row, row_number)
    return rows


def _validate_v6_row(row: dict[str, Any], row_number: int) -> None:
    for field in ("index", "culture", "language", "prompt", "response", "response_safetype"):
        if not str(row.get(field, "")).strip():
            raise BenchmarkTopic3RiskV6Error(f"csv:{row_number}.{field} must not be empty")
    safetype = str(row.get("response_safetype", "")).strip()
    if safetype not in {"safe", "unsafe"}:
        raise BenchmarkTopic3RiskV6Error(
            f"csv:{row_number}.response_safetype must be safe or unsafe"
        )
    if safetype == "unsafe":
        if not re.search(r"C(0[1-9]|1[0-7])", str(row.get("risk_category", ""))):
            raise BenchmarkTopic3RiskV6Error(
                f"csv:{row_number}.risk_category must contain C01-C17 for unsafe rows"
            )
        if str(row.get("risk_level_id", "")).strip() not in {"low", "medium", "high"}:
            raise BenchmarkTopic3RiskV6Error(
                f"csv:{row_number}.risk_level_id must be low, medium or high for unsafe rows"
            )


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    safe_total = sum(1 for row in rows if row.get("response_safetype") == "safe")
    risk_rows = [row for row in rows if row.get("response_safetype") == "unsafe"]
    return {
        "sample_count": len(rows),
        "safe_total": safe_total,
        "risk_total": len(risk_rows),
        "culture_distribution": dict(Counter(str(row["culture"]) for row in rows)),
        "language_distribution": dict(Counter(str(row["language"]) for row in rows)),
        "risk_level_distribution": dict(
            Counter(str(row.get("risk_level_id", "") or "safe") for row in rows)
        ),
        "category_distribution": _category_distribution(risk_rows),
    }


def _category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for code in re.findall(r"C(0[1-9]|1[0-7])", str(row.get("risk_category", ""))):
            counts[f"C{code}"] += 1
    return dict(sorted(counts.items()))


def _row_with_sample_id(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["sample_id"] = str(row.get("index"))
    if payload.get("response_safetype") == "safe" and not payload.get("risk_level_id"):
        payload["risk_level_id"] = "safe"
    payload["risk_category_code"] = ",".join(
        sorted({f"C{code}" for code in re.findall(r"C(0[1-9]|1[0-7])", str(row.get("risk_category", "")))})
    )
    return payload


def _build_v6_manifest(
    *,
    asset_id: str,
    name: str,
    csv_name: str,
    asset_sha256: str,
    summary: dict[str, Any],
    source_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "task_id": f"prerun_{asset_id[:56]}",
        "name": name,
        "source_mode": SOURCE_MODE,
        "agent_id": AGENT_ID,
        "benchmark_type": BENCHMARK_TYPE,
        "release_kind": RELEASE_KIND,
        "taxonomy_schema": "C01-C17",
        "asset_sha256": asset_sha256,
        "sample_count": summary["sample_count"],
        "safe_total": summary["safe_total"],
        "risk_total": summary["risk_total"],
        "culture_distribution": summary["culture_distribution"],
        "language_distribution": summary["language_distribution"],
        "risk_level_distribution": summary["risk_level_distribution"],
        "category_distribution": summary["category_distribution"],
        "evaluation_status": "evaluation_pending",
        "source_repo": get_settings().topic3_risk_benchmark_source_repo,
        "source_commit": get_settings().topic3_risk_benchmark_source_commit,
        "source_csv_path": str(source_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "v6_csv": csv_name,
            "samples": "samples_v6.jsonl",
            "artifact_zip": "artifacts/topic3_risk_v6_asset.zip",
        },
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "raw_download_allowed": False,
            "note": "完整样本仅内部详情查看；raw output 不开放页面下载。",
        },
        "evaluation_results": [],
        "checksums": {
            "asset_csv_sha256": asset_sha256,
        },
    }


def _load_result_package(result_dir: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_RESULT_FILES if not (result_dir / name).is_file()]
    if missing:
        raise BenchmarkTopic3RiskV6Error(
            f"result package is missing required files: {', '.join(missing)}"
        )
    manifest = load_json_object(result_dir / "evaluation_manifest.json", "evaluation_manifest.json")
    metrics = load_json_object(result_dir / "metrics.json", "metrics.json")
    predictions_count = _count_jsonl(result_dir / "predictions.jsonl")
    manifest_count = (manifest.get("predictions") or {}).get("count")
    if manifest_count != predictions_count:
        raise BenchmarkTopic3RiskV6Error(
            f"predictions count mismatch: manifest={manifest_count}; actual={predictions_count}"
        )
    models = manifest.get("models")
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise BenchmarkTopic3RiskV6Error("evaluation_manifest.models must contain one model")
    model = models[0]
    metrics_doc = metrics.get("metrics")
    if not isinstance(metrics_doc, dict):
        raise BenchmarkTopic3RiskV6Error("metrics.metrics must be an object")
    return {
        "asset_id": str(manifest.get("asset_id", "")),
        "asset_sha256": str(manifest.get("asset_sha256", "")),
        "run_id": str(manifest.get("run_id", "")),
        "result_source": str(manifest.get("result_source") or RESULT_SOURCE),
        "evaluated_at": str(manifest.get("evaluated_at", "")),
        "model_id": str(model.get("model_id", "")),
        "model_name": str(model.get("model_name", "")),
        "model_version": str(model.get("model_version", "")),
        "model_run_id": str(model.get("model_run_id", "")),
        "role": str(model.get("role", "")),
        "predictions_count": predictions_count,
    }


def _count_jsonl(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkTopic3RiskV6Error(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise BenchmarkTopic3RiskV6Error(
                    f"{path.name}:{line_number} must contain a JSON object"
                )
            count += 1
    if count <= 0:
        raise BenchmarkTopic3RiskV6Error(f"{path.name} must not be empty")
    return count


def _write_asset_zip(root_dir: Path, archive_path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(root_dir / "manifest.platform.json", arcname="manifest.platform.json")
        for name in names:
            archive.write(root_dir / name, arcname=name)
