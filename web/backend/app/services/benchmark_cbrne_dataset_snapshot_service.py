"""CBRNE anomaly seedbank dataset_snapshot import (#117).

Independent from AutoBench prerun_snapshot; reuses archive-safety helpers only.
"""

from __future__ import annotations

import json
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
from app.services.benchmark_asset_registry_service import (
    BenchmarkAssetRegistryError,
    _extract_members,
    _is_unsafe_member,
    _read_archive_bytes,
    sha256_bytes,
)


SOURCE_MODE = "dataset_snapshot"
BENCHMARK_TYPE = "anomaly_seedbank"
SCHEMA_ID = "topic2.cbrne.anomaly_seedbank.v1"

REQUIRED_MEMBERS = {
    "manifest.json",
    "dataset.jsonl",
    "profile.json",
    "DATASET_NOTE.md",
}

REQUIRED_MANIFEST_FIELDS = {
    "asset_id",
    "asset_key",
    "schema_id",
    "source_mode",
    "benchmark_type",
    "name",
    "version",
    "source_repo",
    "original_filename",
    "sample_count",
    "sensitivity",
    "disclosure_policy",
    "licence_notes",
    "source_limitations",
}

REQUIRED_ROW_FIELDS = {
    "id",
    "label",
    "cbrne_category",
    "source",
    "exposure_tier",
    "evaluator_relative_difficulty",
}

REQUIRED_PROFILE_FIELDS = {
    "sample_count",
    "label_counts",
    "cbrne_category_counts",
    "source_counts",
    "exposure_tier_counts",
    "evaluator_relative_difficulty_counts",
}

DIFFICULTY_DEFINITION = {
    "field": "evaluator_relative_difficulty",
    "label": "evaluator-relative difficulty",
    "display_label_zh": "评估器相对难度",
    "basis": (
        "Number of configured Guard judgements that were incorrect or null "
        "for the source sample (ten-Guard error/null-count basis)."
    ),
    "basis_zh": "十 Guard 错误/空判计数；不是样本固有难度，也不等同于 T1–T4。",
    "not_difficulty_fields": ["exposure_tier", "T1", "T2", "T3", "T4"],
}


class BenchmarkCbrneDatasetSnapshotError(RuntimeError):
    """Raised when a CBRNE dataset_snapshot package cannot be imported."""


class BenchmarkCbrneDatasetSnapshotService:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def import_dataset(
        self,
        db: AsyncSession,
        *,
        archive_path: Path | str,
    ) -> tuple[BenchmarkAsset, bool]:
        archive_path = Path(archive_path).expanduser().resolve()
        try:
            archive_bytes = _read_archive_bytes(archive_path)
        except BenchmarkAssetRegistryError as exc:
            raise BenchmarkCbrneDatasetSnapshotError(str(exc)) from exc
        artifact_sha256 = sha256_bytes(archive_bytes)
        members = _validated_dataset_members(archive_path)

        manifest = _read_json_member(archive_path, members["manifest.json"], "manifest.json")
        profile = _read_json_member(archive_path, members["profile.json"], "profile.json")
        note_text = _read_text_member(archive_path, members["DATASET_NOTE.md"], "DATASET_NOTE.md")
        dataset_bytes = _read_member_bytes(archive_path, members["dataset.jsonl"])
        dataset_content_sha256 = sha256_bytes(dataset_bytes)
        rows = _parse_dataset_jsonl(dataset_bytes)

        _validate_delivery_manifest(manifest)
        _validate_rows(rows)
        platform_stats = _compute_platform_stats(rows)
        _validate_profile(profile, platform_stats)

        asset_key = str(manifest["asset_key"]).strip()
        existing_same = await _find_by_content(
            db,
            asset_key=asset_key,
            dataset_content_sha256=dataset_content_sha256,
        )
        if existing_same is not None:
            if bool(manifest.get("mark_as_current", True)):
                await _set_current_pointer(db, asset_key=asset_key, current=existing_same)
            await db.refresh(existing_same)
            return existing_same, True

        asset_id = _clean_asset_id(str(manifest["asset_id"]))
        if not asset_id:
            raise BenchmarkCbrneDatasetSnapshotError("manifest.asset_id is invalid")
        if await _get_asset(db, asset_id) is not None:
            raise BenchmarkCbrneDatasetSnapshotError(f"asset already exists: {asset_id}")

        root_dir = self._artifact_root() / SOURCE_MODE / asset_id
        artifacts_dir = root_dir / "artifacts"
        if root_dir.exists():
            raise BenchmarkCbrneDatasetSnapshotError(
                f"asset directory already exists: {root_dir}"
            )

        mark_as_current = bool(manifest.get("mark_as_current", True))
        try:
            artifacts_dir.mkdir(parents=True, exist_ok=False)
            archive_copy_path = artifacts_dir / "cbrne_dataset_snapshot.zip"
            archive_copy_path.write_bytes(archive_bytes)
            _extract_members(archive_path, members, root_dir)

            platform_manifest = _build_platform_manifest(
                manifest=manifest,
                profile=profile,
                platform_stats=platform_stats,
                note_text=note_text,
                artifact_sha256=artifact_sha256,
                dataset_content_sha256=dataset_content_sha256,
                is_current=mark_as_current,
                rejected_row_count=0,
            )
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(platform_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            shutil.rmtree(root_dir, ignore_errors=True)
            raise

        asset = BenchmarkAsset(
            asset_id=asset_id,
            task_id=f"dataset_{asset_id[:56]}",
            source_mode=SOURCE_MODE,
            name=str(platform_manifest["name"]),
            manifest_json=json.dumps(platform_manifest, ensure_ascii=False),
            artifact_dir=str(root_dir),
            artifact_zip_path=str(archive_copy_path),
            artifact_sha256=artifact_sha256,
            source_repo=str(platform_manifest["source_repo"]),
            source_commit=str(platform_manifest["source_commit"]),
        )
        db.add(asset)
        await db.flush()

        if mark_as_current:
            await _set_current_pointer(db, asset_key=asset_key, current=asset)
        else:
            await db.commit()
            await db.refresh(asset)

        return asset, False


async def _get_asset(db: AsyncSession, asset_id: str) -> BenchmarkAsset | None:
    result = await db.execute(
        select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id)
    )
    return result.scalar_one_or_none()


async def _find_by_content(
    db: AsyncSession,
    *,
    asset_key: str,
    dataset_content_sha256: str,
) -> BenchmarkAsset | None:
    result = await db.execute(
        select(BenchmarkAsset).where(BenchmarkAsset.source_mode == SOURCE_MODE)
    )
    for asset in result.scalars().all():
        manifest = _loads_manifest(asset.manifest_json)
        if (
            manifest.get("asset_key") == asset_key
            and manifest.get("dataset_content_sha256") == dataset_content_sha256
        ):
            return asset
    return None


async def _set_current_pointer(
    db: AsyncSession,
    *,
    asset_key: str,
    current: BenchmarkAsset,
) -> None:
    result = await db.execute(
        select(BenchmarkAsset).where(BenchmarkAsset.source_mode == SOURCE_MODE)
    )
    for asset in result.scalars().all():
        manifest = _loads_manifest(asset.manifest_json)
        if manifest.get("asset_key") != asset_key:
            continue
        desired = asset.asset_id == current.asset_id
        if bool(manifest.get("is_current")) == desired:
            continue
        manifest["is_current"] = desired
        asset.manifest_json = json.dumps(manifest, ensure_ascii=False)
        platform_path = Path(asset.artifact_dir) / "manifest.platform.json"
        if platform_path.is_file():
            platform_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    await db.commit()
    await db.refresh(current)


def _validated_dataset_members(archive_path: Path) -> dict[str, zipfile.ZipInfo]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            seen: set[str] = set()
            for info in archive.infolist():
                if info.is_dir():
                    raise BenchmarkCbrneDatasetSnapshotError(
                        f"directory members are not allowed: {info.filename}"
                    )
                name = info.filename
                if _is_unsafe_member(name):
                    raise BenchmarkCbrneDatasetSnapshotError(f"unsafe zip member: {name}")
                duplicate_key = name.replace("\\", "/").casefold()
                if duplicate_key in seen:
                    raise BenchmarkCbrneDatasetSnapshotError(f"duplicate zip member: {name}")
                seen.add(duplicate_key)
                members[name] = info
    except zipfile.BadZipFile as exc:
        raise BenchmarkCbrneDatasetSnapshotError("invalid artifact zip") from exc

    names = set(members)
    missing = REQUIRED_MEMBERS - names
    if missing:
        raise BenchmarkCbrneDatasetSnapshotError(
            "dataset snapshot is missing required members: "
            + ", ".join(sorted(missing))
        )
    unexpected = names - REQUIRED_MEMBERS
    if unexpected:
        raise BenchmarkCbrneDatasetSnapshotError(
            "dataset snapshot contains unexpected members: "
            + ", ".join(sorted(unexpected))
        )
    return members


def _read_member_bytes(archive_path: Path, info: zipfile.ZipInfo) -> bytes:
    with zipfile.ZipFile(archive_path) as archive:
        return archive.read(info)


def _read_json_member(
    archive_path: Path,
    info: zipfile.ZipInfo,
    display_name: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(_read_member_bytes(archive_path, info).decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"{display_name} must be utf-8"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"invalid JSON in {display_name}"
        ) from exc
    if not isinstance(payload, dict):
        raise BenchmarkCbrneDatasetSnapshotError(
            f"{display_name} must contain a JSON object"
        )
    return payload


def _read_text_member(
    archive_path: Path,
    info: zipfile.ZipInfo,
    display_name: str,
) -> str:
    try:
        text = _read_member_bytes(archive_path, info).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"{display_name} must be utf-8"
        ) from exc
    if not text.strip():
        raise BenchmarkCbrneDatasetSnapshotError(f"{display_name} must not be empty")
    return text


def _parse_dataset_jsonl(dataset_bytes: bytes) -> list[dict[str, Any]]:
    try:
        text = dataset_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkCbrneDatasetSnapshotError("dataset.jsonl must be utf-8") from exc

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"invalid JSON in dataset.jsonl:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{line_number} must contain a JSON object"
            )
        rows.append(row)
    if not rows:
        raise BenchmarkCbrneDatasetSnapshotError("dataset.jsonl must not be empty")
    return rows


def _validate_delivery_manifest(manifest: dict[str, Any]) -> None:
    missing = sorted(field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest)
    if missing:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"manifest.json is missing required fields: {', '.join(missing)}"
        )
    if manifest.get("source_mode") != SOURCE_MODE:
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest.source_mode must be dataset_snapshot"
        )
    if manifest.get("benchmark_type") != BENCHMARK_TYPE:
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest.benchmark_type must be anomaly_seedbank"
        )
    if manifest.get("schema_id") != SCHEMA_ID:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"manifest.schema_id must be {SCHEMA_ID}"
        )
    if not _non_empty_str(manifest.get("asset_key")):
        raise BenchmarkCbrneDatasetSnapshotError("manifest.asset_key must be non-empty")
    if not _non_empty_str(manifest.get("source_repo")):
        raise BenchmarkCbrneDatasetSnapshotError("manifest.source_repo must be non-empty")
    source_commit = manifest.get("source_commit")
    source_tag = manifest.get("source_tag")
    if not _non_empty_str(source_commit) and not _non_empty_str(source_tag):
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest must include source_commit or source_tag"
        )
    if not isinstance(manifest.get("sample_count"), int) or manifest["sample_count"] <= 0:
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest.sample_count must be a positive integer"
        )
    if not isinstance(manifest.get("source_limitations"), list):
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest.source_limitations must be a list"
        )
    if not _non_empty_str(manifest.get("licence_notes")):
        raise BenchmarkCbrneDatasetSnapshotError(
            "manifest.licence_notes must be non-empty"
        )


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = sorted(field for field in REQUIRED_ROW_FIELDS if field not in row)
        if missing:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index} is missing required fields: {', '.join(missing)}"
            )
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.id must be a non-empty string"
            )
        normalized_id = sample_id.strip()
        if normalized_id in seen_ids:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"duplicate sample id: {normalized_id}"
            )
        seen_ids.add(normalized_id)

        label = row.get("label")
        if label not in {"safe", "unsafe"}:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.label must be safe or unsafe"
            )
        if not _non_empty_str(row.get("cbrne_category")):
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.cbrne_category must be non-empty"
            )
        if not _non_empty_str(row.get("source")):
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.source must be non-empty"
            )
        tier = row.get("exposure_tier")
        if tier not in {"T1", "T2", "T3", "T4"}:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.exposure_tier must be T1–T4"
            )
        difficulty = row.get("evaluator_relative_difficulty")
        if isinstance(difficulty, bool) or not isinstance(difficulty, int):
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.evaluator_relative_difficulty must be an integer"
            )
        if difficulty < 0:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"dataset.jsonl:{index}.evaluator_relative_difficulty must be >= 0"
            )


def _compute_platform_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts = Counter(str(row["label"]) for row in rows)
    category_counts = Counter(str(row["cbrne_category"]) for row in rows)
    source_counts = Counter(str(row["source"]) for row in rows)
    tier_counts = Counter(str(row["exposure_tier"]) for row in rows)
    difficulty_counts = Counter(
        str(int(row["evaluator_relative_difficulty"])) for row in rows
    )
    return {
        "sample_count": len(rows),
        "unique_id_count": len(rows),
        "rejected_row_count": 0,
        "label_counts": dict(sorted(label_counts.items())),
        "cbrne_category_counts": dict(sorted(category_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "exposure_tier_counts": dict(sorted(tier_counts.items())),
        "evaluator_relative_difficulty_counts": dict(sorted(difficulty_counts.items())),
    }


def _validate_profile(profile: dict[str, Any], platform_stats: dict[str, Any]) -> None:
    missing = sorted(field for field in REQUIRED_PROFILE_FIELDS if field not in profile)
    if missing:
        raise BenchmarkCbrneDatasetSnapshotError(
            f"profile.json is missing required fields: {', '.join(missing)}"
        )
    for key in REQUIRED_PROFILE_FIELDS:
        expected = platform_stats[key]
        actual = profile.get(key)
        if key.endswith("_counts"):
            if not isinstance(actual, dict):
                raise BenchmarkCbrneDatasetSnapshotError(
                    f"profile.{key} must be an object"
                )
            normalized_actual = {str(k): int(v) for k, v in actual.items()}
            if normalized_actual != expected:
                raise BenchmarkCbrneDatasetSnapshotError(
                    f"profile.{key} does not match dataset.jsonl statistics"
                )
        elif actual != expected:
            raise BenchmarkCbrneDatasetSnapshotError(
                f"profile.{key} does not match dataset.jsonl statistics"
            )
    if profile.get("sample_count") != platform_stats["sample_count"]:
        raise BenchmarkCbrneDatasetSnapshotError(
            "profile.sample_count does not match dataset.jsonl statistics"
        )


def _build_platform_manifest(
    *,
    manifest: dict[str, Any],
    profile: dict[str, Any],
    platform_stats: dict[str, Any],
    note_text: str,
    artifact_sha256: str,
    dataset_content_sha256: str,
    is_current: bool,
    rejected_row_count: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    source_commit = (
        str(manifest["source_commit"]).strip()
        if _non_empty_str(manifest.get("source_commit"))
        else str(manifest.get("source_tag") or "").strip()
    )
    platform_manifest = {
        "schema_version": "benchmark-dataset-snapshot-v0.1",
        "asset_id": _clean_asset_id(str(manifest["asset_id"])),
        "asset_key": str(manifest["asset_key"]).strip(),
        "schema_id": SCHEMA_ID,
        "source_mode": SOURCE_MODE,
        "benchmark_type": BENCHMARK_TYPE,
        "name": str(manifest["name"]).strip(),
        "version": str(manifest["version"]).strip(),
        "source_repo": str(manifest["source_repo"]).strip(),
        "source_commit": source_commit,
        "source_tag": (
            str(manifest["source_tag"]).strip()
            if _non_empty_str(manifest.get("source_tag"))
            else None
        ),
        "original_filename": str(manifest["original_filename"]).strip(),
        "byte_size": None,
        "sample_count": platform_stats["sample_count"],
        "sensitivity": str(manifest["sensitivity"]).strip(),
        "disclosure_policy": str(manifest["disclosure_policy"]).strip(),
        "licence_notes": str(manifest["licence_notes"]).strip(),
        "source_limitations": [
            str(item).strip()
            for item in manifest.get("source_limitations", [])
            if _non_empty_str(item)
        ],
        "is_current": is_current,
        "created_at": now,
        "files": {
            "artifact_zip": "artifacts/cbrne_dataset_snapshot.zip",
            "manifest": "manifest.json",
            "dataset": "dataset.jsonl",
            "profile": "profile.json",
            "note": "DATASET_NOTE.md",
        },
        "checksums": {
            "artifact_zip_sha256": artifact_sha256,
            "dataset_jsonl_sha256": dataset_content_sha256,
        },
        "dataset_content_sha256": dataset_content_sha256,
        "delivery_profile": profile,
        "platform_stats": {
            **platform_stats,
            "rejected_row_count": rejected_row_count,
        },
        "difficulty_definition": DIFFICULTY_DEFINITION,
        "dataset_note_excerpt": note_text.strip()[:500],
        "import_quality": {
            "record_count": platform_stats["sample_count"],
            "unique_id_count": platform_stats["unique_id_count"],
            "rejected_row_count": rejected_row_count,
            "silent_drop_allowed": False,
        },
    }
    return platform_manifest


def _loads_manifest(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_asset_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in value.strip())
    return safe[:64]


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
