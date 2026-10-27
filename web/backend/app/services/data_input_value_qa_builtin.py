"""Resolve and silently ensure preferred Topic1 value_qa prerun packs.

Two fixed asset ids are used so official / DEMO packs cannot collide by display name:

- topic1_value_qa_marked_merged_round3  (official round3, ~222 rows)
- topic1_value_qa_risk_cause_demo0606   (DEMO-0606, ~87 rows)

If a preferred asset already exists but its sample_count does not match the
bundled source file, the wrong asset is removed and re-imported.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic1_value_qa_asset_service import (
    BenchmarkTopic1ValueQaAssetError,
    BenchmarkTopic1ValueQaAssetService,
)
from app.services.data_input_value_qa_common import (
    DEMO_VALUE_QA_ASSET_ID,
    DEMO_VALUE_QA_ASSET_NAME,
    OFFICIAL_VALUE_QA_ASSET_ID,
    OFFICIAL_VALUE_QA_ASSET_NAME,
)

logger = logging.getLogger(__name__)

OFFICIAL_SAMPLES_FILENAME = "verified.marked_merged.jsonl"
OFFICIAL_MARKS_FILENAME = "_marks_verified.marked_merged.jsonl"
OFFICIAL_QC_FILES = {
    "qc_index": "round3_gpt55_index.json",
    "qc_samples": "round3_gpt55_samples.jsonl",
    "qc_scores": "round3_gpt55_scores.jsonl",
    "qc_summary": "round3_gpt55_summary.md",
}
DEMO_SAMPLES_FILENAME = "verified.marked_20260601_031030.jsonl"

_ensure_attempted: dict[str, bool] = {}


def resolve_official_value_qa_root() -> Path | None:
    return _first_existing_pack_root("value_qa", OFFICIAL_SAMPLES_FILENAME)


def resolve_demo_value_qa_root() -> Path | None:
    return _first_existing_pack_root("value_qa_demo0606", DEMO_SAMPLES_FILENAME)


def resolve_official_value_qa_paths() -> dict[str, Path] | None:
    root = resolve_official_value_qa_root()
    if root is None:
        return None
    samples = root / OFFICIAL_SAMPLES_FILENAME
    if not samples.is_file():
        return None
    paths: dict[str, Path] = {"samples": samples}
    marks = root / OFFICIAL_MARKS_FILENAME
    if marks.is_file():
        paths["marks"] = marks
    qc_dir = root / "qc"
    for key, filename in OFFICIAL_QC_FILES.items():
        candidate = qc_dir / filename
        if candidate.is_file():
            paths[key] = candidate
    return paths


def resolve_demo_value_qa_paths() -> dict[str, Path] | None:
    root = resolve_demo_value_qa_root()
    if root is None:
        return None
    samples = root / DEMO_SAMPLES_FILENAME
    if not samples.is_file():
        return None
    return {"samples": samples}


# Backward-compatible aliases used by existing tests / callers.
BUILTIN_VALUE_QA_ASSET_ID = OFFICIAL_VALUE_QA_ASSET_ID
BUILTIN_VALUE_QA_ASSET_NAME = OFFICIAL_VALUE_QA_ASSET_NAME
resolve_builtin_value_qa_root = resolve_official_value_qa_root
resolve_builtin_value_qa_paths = resolve_official_value_qa_paths


def builtin_value_qa_source_summary() -> dict[str, Any]:
    paths = resolve_official_value_qa_paths()
    if paths is None:
        return {"available": False}
    return {
        "available": True,
        "asset_id": OFFICIAL_VALUE_QA_ASSET_ID,
        "samples_path": str(paths["samples"]),
        "expected_sample_count": _count_jsonl_rows(paths["samples"]),
    }


def demo_value_qa_source_summary() -> dict[str, Any]:
    paths = resolve_demo_value_qa_paths()
    if paths is None:
        return {"available": False}
    return {
        "available": True,
        "asset_id": DEMO_VALUE_QA_ASSET_ID,
        "samples_path": str(paths["samples"]),
        "expected_sample_count": _count_jsonl_rows(paths["samples"]),
    }


async def ensure_builtin_value_qa_asset(db: AsyncSession) -> BenchmarkAsset | None:
    """Ensure official preferred pack; kept for backward-compatible call sites."""
    assets = await ensure_preferred_value_qa_assets(db)
    return assets.get(OFFICIAL_VALUE_QA_ASSET_ID)


async def ensure_preferred_value_qa_assets(
    db: AsyncSession,
) -> dict[str, BenchmarkAsset]:
    """Ensure both preferred value_qa packs and repair mismatched DEMO/official rows."""
    if not get_settings().topic1_value_qa_auto_ensure:
        return {}

    results: dict[str, BenchmarkAsset] = {}
    official = await _ensure_one_pack(
        db,
        asset_id=OFFICIAL_VALUE_QA_ASSET_ID,
        asset_name=OFFICIAL_VALUE_QA_ASSET_NAME,
        paths=resolve_official_value_qa_paths(),
        pack_key="official",
    )
    if official is not None:
        results[OFFICIAL_VALUE_QA_ASSET_ID] = official

    demo = await _ensure_one_pack(
        db,
        asset_id=DEMO_VALUE_QA_ASSET_ID,
        asset_name=DEMO_VALUE_QA_ASSET_NAME,
        paths=resolve_demo_value_qa_paths(),
        pack_key="demo",
    )
    if demo is not None:
        results[DEMO_VALUE_QA_ASSET_ID] = demo
    return results


async def _ensure_one_pack(
    db: AsyncSession,
    *,
    asset_id: str,
    asset_name: str,
    paths: dict[str, Path] | None,
    pack_key: str,
) -> BenchmarkAsset | None:
    if paths is None:
        logger.info("value_qa pack %s skipped: bundled source missing", pack_key)
        return None

    expected_count = _count_jsonl_rows(paths["samples"])
    registry = BenchmarkAssetRegistryService()
    existing = await registry.get_asset(db, asset_id)
    if existing is not None:
        current_count = _asset_sample_count(existing)
        if current_count == expected_count and expected_count > 0:
            return existing
        logger.warning(
            "value_qa asset %s sample_count=%s does not match bundled %s (%s); repairing",
            asset_id,
            current_count,
            pack_key,
            expected_count,
        )
        await _delete_value_qa_asset(db, existing)

    if _ensure_attempted.get(pack_key):
        return None
    _ensure_attempted[pack_key] = True

    try:
        asset = await BenchmarkTopic1ValueQaAssetService().import_dataset(
            db,
            samples_path=paths["samples"],
            marks_path=paths.get("marks"),
            qc_index_path=paths.get("qc_index"),
            qc_samples_path=paths.get("qc_samples"),
            qc_scores_path=paths.get("qc_scores"),
            qc_summary_path=paths.get("qc_summary"),
            asset_id=asset_id,
            name=asset_name,
        )
    except BenchmarkTopic1ValueQaAssetError as exc:
        logger.warning("value_qa pack %s ensure skipped: %s", pack_key, exc)
        return None
    except Exception:
        logger.exception("value_qa pack %s ensure failed", pack_key)
        return None

    logger.info(
        "registered value_qa asset %s (%s rows) from %s",
        asset.asset_id,
        expected_count,
        paths["samples"],
    )
    return asset


async def _delete_value_qa_asset(db: AsyncSession, asset: BenchmarkAsset) -> None:
    artifact_dir = Path(str(asset.artifact_dir or "").strip())
    artifact_zip = Path(str(asset.artifact_zip_path or "").strip())
    asset_id = asset.asset_id
    result = await db.execute(select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id))
    row = result.scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()

    if artifact_dir.exists():
        shutil.rmtree(artifact_dir, ignore_errors=True)
    if artifact_zip.exists() and artifact_zip.is_file():
        artifact_zip.unlink(missing_ok=True)


def _first_existing_pack_root(pack_dirname: str, samples_filename: str) -> Path | None:
    here = Path(__file__).resolve()
    backend_root = here.parents[2]
    project_root = here.parents[4]
    candidates = [
        backend_root / "data" / "input_corpora" / pack_dirname,
        project_root / "web" / "backend" / "data" / "input_corpora" / pack_dirname,
        Path.cwd() / "data" / "input_corpora" / pack_dirname,
        Path.cwd() / "web" / "backend" / "data" / "input_corpora" / pack_dirname,
    ]
    for root in candidates:
        if (root / samples_filename).is_file():
            return root
    return None


def _count_jsonl_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _asset_sample_count(asset: BenchmarkAsset) -> int:
    try:
        manifest = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(manifest, dict):
        return 0
    for key in ("sample_count", "group_count"):
        try:
            value = int(manifest.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0
