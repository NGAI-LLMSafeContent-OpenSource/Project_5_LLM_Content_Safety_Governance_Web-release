from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset


REQUIRED_PRERUN_MEMBERS = {
    "manifest.json",
    "report.md",
    "results.json",
    "dynbench.jsonl",
}

REQUIRED_MANIFEST_FIELDS = {
    "source_mode",
    "source_repo",
    "source_commit",
    "seed_set_id",
    "sample_count",
    "language",
    "l1",
    "moderators",
    "evaluator_version",
    "asr_definition",
}

REQUIRED_DYNBENCH_FIELDS = {
    "difficulty_level",
    "rewrite_rounds",
    "strategy_chain",
    "simple_hard_pair_id",
}

TRACE_FIELD_GROUPS = (
    ("seedbank_id", "seed_id"),
    ("source_row_id",),
)


class BenchmarkAssetRegistryError(RuntimeError):
    """Raised when a Benchmark asset cannot be registered safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class BenchmarkAssetRegistryService:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def list_assets(
        self,
        db: AsyncSession,
        *,
        source_mode: str | None = None,
    ) -> list[BenchmarkAsset]:
        query = select(BenchmarkAsset).order_by(BenchmarkAsset.created_at.desc())
        if source_mode:
            query = query.where(BenchmarkAsset.source_mode == source_mode)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_asset(self, db: AsyncSession, asset_id: str) -> BenchmarkAsset | None:
        result = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def ensure_prerun_assets_registered(self, db: AsyncSession) -> list[BenchmarkAsset]:
        prerun_root = self._artifact_root() / "prerun"
        if not prerun_root.is_dir():
            return []

        registered: list[BenchmarkAsset] = []
        for manifest_path in sorted(prerun_root.glob("*/manifest.platform.json")):
            manifest = _read_json_file(manifest_path)
            if not manifest:
                continue
            if manifest.get("source_mode") != "prerun_snapshot":
                continue

            asset_id = _asset_id_from_manifest(manifest)
            if not asset_id or await self.get_asset(db, asset_id) is not None:
                continue

            asset_dir = manifest_path.parent
            artifact_zip_path = _artifact_zip_path(asset_dir, manifest)
            artifact_sha256 = _artifact_sha256_from_manifest(manifest)
            if artifact_zip_path is None or artifact_sha256 is None:
                continue

            asset = BenchmarkAsset(
                asset_id=asset_id,
                task_id=_task_id_from_manifest(manifest, asset_id),
                source_mode="prerun_snapshot",
                name=str(manifest.get("name") or "Benchmark prerun snapshot"),
                manifest_json=json.dumps(manifest, ensure_ascii=False),
                artifact_dir=str(asset_dir),
                artifact_zip_path=str(artifact_zip_path),
                artifact_sha256=artifact_sha256,
                source_repo=str(manifest.get("source_repo") or ""),
                source_commit=str(manifest.get("source_commit") or ""),
            )
            db.add(asset)
            registered.append(asset)

        if registered:
            await db.commit()
            for asset in registered:
                await db.refresh(asset)
        return registered

    async def import_prerun_asset(
        self,
        db: AsyncSession,
        *,
        archive_path: Path | str,
    ) -> BenchmarkAsset:
        archive_path = Path(archive_path).expanduser().resolve()
        archive_bytes = _read_archive_bytes(archive_path)
        artifact_sha256 = sha256_bytes(archive_bytes)
        members = _validated_prerun_members(archive_path)

        manifest = _read_json_member(archive_path, members["manifest.json"], "manifest.json")
        results = _read_json_member(archive_path, members["results.json"], "results.json")
        dynbench_rows = _read_jsonl_member(archive_path, members["dynbench.jsonl"])

        _validate_prerun_manifest(manifest)
        _validate_results(results)
        _validate_dynbench_rows(dynbench_rows)

        asset_id = _asset_id_from_manifest(manifest) or f"asset_prerun_{uuid.uuid4().hex[:12]}"
        existing = await self.get_asset(db, asset_id)
        if existing is not None:
            raise BenchmarkAssetRegistryError(f"asset already exists: {asset_id}")

        task_id = _task_id_from_manifest(manifest, asset_id)
        root_dir = self._artifact_root() / "prerun" / asset_id
        artifacts_dir = root_dir / "artifacts"
        if root_dir.exists():
            raise BenchmarkAssetRegistryError(f"asset directory already exists: {root_dir}")

        try:
            artifacts_dir.mkdir(parents=True, exist_ok=False)
            archive_copy_path = artifacts_dir / "autobench_prerun_artifacts.zip"
            archive_copy_path.write_bytes(archive_bytes)
            _extract_members(archive_path, members, root_dir)

            platform_manifest = _build_platform_manifest(
                asset_id=asset_id,
                task_id=task_id,
                manifest=manifest,
                results=results,
                dynbench_rows=dynbench_rows,
                artifact_sha256=artifact_sha256,
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
            task_id=task_id,
            source_mode="prerun_snapshot",
            name=str(manifest.get("name") or "Topic2 AutoBench prerun snapshot"),
            manifest_json=json.dumps(platform_manifest, ensure_ascii=False),
            artifact_dir=str(root_dir),
            artifact_zip_path=str(archive_copy_path),
            artifact_sha256=artifact_sha256,
            source_repo=str(manifest["source_repo"]),
            source_commit=str(manifest["source_commit"]),
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset


def _read_archive_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise BenchmarkAssetRegistryError(f"artifact zip not found: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BenchmarkAssetRegistryError(f"unable to read artifact zip: {exc}") from exc


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_zip_path(asset_dir: Path, manifest: dict[str, Any]) -> Path | None:
    files = manifest.get("files")
    artifact_zip = (
        files.get("artifact_zip")
        if isinstance(files, dict) and isinstance(files.get("artifact_zip"), str)
        else "artifacts/autobench_prerun_artifacts.zip"
    )
    path = asset_dir / artifact_zip
    return path if path.is_file() else None


def _artifact_sha256_from_manifest(manifest: dict[str, Any]) -> str | None:
    checksums = manifest.get("checksums")
    value = checksums.get("artifact_zip_sha256") if isinstance(checksums, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def _validated_prerun_members(archive_path: Path) -> dict[str, zipfile.ZipInfo]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            seen: set[str] = set()
            for info in archive.infolist():
                if info.is_dir():
                    raise BenchmarkAssetRegistryError(
                        f"directory members are not allowed: {info.filename}"
                    )
                name = info.filename
                if _is_unsafe_member(name):
                    raise BenchmarkAssetRegistryError(f"unsafe zip member: {name}")
                duplicate_key = name.replace("\\", "/").casefold()
                if duplicate_key in seen:
                    raise BenchmarkAssetRegistryError(f"duplicate zip member: {name}")
                seen.add(duplicate_key)
                members[name] = info
    except zipfile.BadZipFile as exc:
        raise BenchmarkAssetRegistryError("invalid artifact zip") from exc

    missing = REQUIRED_PRERUN_MEMBERS - set(members)
    if missing:
        raise BenchmarkAssetRegistryError(
            f"prerun artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def _is_unsafe_member(name: str) -> bool:
    if not name or "\x00" in name:
        return True
    windows_path = PureWindowsPath(name)
    posix_path = PurePosixPath(name.replace("\\", "/"))
    if windows_path.is_absolute() or posix_path.is_absolute():
        return True
    return ".." in posix_path.parts


def _read_json_member(
    archive_path: Path,
    info: zipfile.ZipInfo,
    display_name: str,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            payload = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkAssetRegistryError(f"invalid JSON in {display_name}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkAssetRegistryError(f"{display_name} must contain a JSON object")
    return payload


def _read_jsonl_member(
    archive_path: Path,
    info: zipfile.ZipInfo,
) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            text = archive.read(info).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkAssetRegistryError("dynbench.jsonl must be utf-8") from exc

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkAssetRegistryError(
                f"invalid JSON in dynbench.jsonl:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkAssetRegistryError(
                f"dynbench.jsonl:{line_number} must contain a JSON object"
            )
        rows.append(row)
    if not rows:
        raise BenchmarkAssetRegistryError("dynbench.jsonl must not be empty")
    return rows


def _validate_prerun_manifest(manifest: dict[str, Any]) -> None:
    missing = sorted(field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest)
    if missing:
        raise BenchmarkAssetRegistryError(
            f"manifest.json is missing required fields: {', '.join(missing)}"
        )
    if manifest.get("source_mode") != "prerun_snapshot":
        raise BenchmarkAssetRegistryError("manifest.source_mode must be prerun_snapshot")
    if not isinstance(manifest.get("sample_count"), int) or manifest.get("sample_count") <= 0:
        raise BenchmarkAssetRegistryError("manifest.sample_count must be a positive integer")
    if not isinstance(manifest.get("moderators"), list) or not manifest.get("moderators"):
        raise BenchmarkAssetRegistryError("manifest.moderators must be a non-empty list")


def _validate_results(results: dict[str, Any]) -> None:
    if not any(key in results for key in ("metrics", "moderators", "evaluations", "results")):
        raise BenchmarkAssetRegistryError(
            "results.json must contain metrics, moderators, evaluations, or results"
        )


def _validate_dynbench_rows(rows: list[dict[str, Any]]) -> None:
    difficulties: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = sorted(field for field in REQUIRED_DYNBENCH_FIELDS if field not in row)
        if missing:
            raise BenchmarkAssetRegistryError(
                f"dynbench.jsonl:{index} is missing required fields: {', '.join(missing)}"
            )
        if not any(any(field in row for field in group) for group in TRACE_FIELD_GROUPS):
            raise BenchmarkAssetRegistryError(
                f"dynbench.jsonl:{index} must include seedbank_id/seed_id or source_row_id"
            )
        difficulty = row.get("difficulty_level")
        if difficulty not in {"simple", "hard"}:
            raise BenchmarkAssetRegistryError(
                f"dynbench.jsonl:{index}.difficulty_level must be simple or hard"
            )
        difficulties.add(difficulty)
    if difficulties != {"simple", "hard"}:
        raise BenchmarkAssetRegistryError(
            "dynbench.jsonl must include both simple and hard samples"
        )


def _extract_members(
    archive_path: Path,
    members: dict[str, zipfile.ZipInfo],
    destination: Path,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for name, info in members.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))


def _asset_id_from_manifest(manifest: dict[str, Any]) -> str | None:
    value = manifest.get("asset_id") or manifest.get("run_id")
    if not isinstance(value, str) or not value.strip():
        return None
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in value.strip())
    return safe[:64] or None


def _task_id_from_manifest(manifest: dict[str, Any], asset_id: str) -> str:
    value = manifest.get("task_id") or manifest.get("run_id")
    if isinstance(value, str) and value.strip():
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in value.strip())
        return safe[:64]
    return f"prerun_{asset_id[:56]}"


def _build_platform_manifest(
    *,
    asset_id: str,
    task_id: str,
    manifest: dict[str, Any],
    results: dict[str, Any],
    dynbench_rows: list[dict[str, Any]],
    artifact_sha256: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    platform_manifest = dict(manifest)
    platform_manifest.update(
        {
            "schema_version": manifest.get("schema_version", "benchmark-manifest-v0.1"),
            "asset_id": asset_id,
            "task_id": task_id,
            "source_mode": "prerun_snapshot",
            "created_at": now,
            "files": {
                "artifact_zip": "artifacts/autobench_prerun_artifacts.zip",
                "manifest": "manifest.json",
                "report": "report.md",
                "results": "results.json",
                "dynbench": "dynbench.jsonl",
            },
            "checksums": {
                **(
                    manifest.get("checksums")
                    if isinstance(manifest.get("checksums"), dict)
                    else {}
                ),
                "artifact_zip_sha256": artifact_sha256,
            },
            "validation": {
                "requires_simple_hard_pair_fields": True,
                "strict_imported_at": now,
            },
            "platform_summary": _build_platform_summary(dynbench_rows),
            "delivery_validation": _build_delivery_validation(
                manifest=manifest,
                artifact_sha256=artifact_sha256,
            ),
            "evaluation_summary": _build_evaluation_summary(
                manifest=manifest,
                results=results,
            ),
        }
    )
    return platform_manifest


def _build_platform_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    difficulty_counts = {"simple": 0, "hard": 0}
    pair_difficulties: dict[str, set[str]] = {}
    trace_field_coverage = {
        "simple_hard_pair_id": 0,
        "seedbank_id_or_seed_id": 0,
        "source_row_id": 0,
    }
    rewrite_round_values: dict[str, list[float]] = {"simple": [], "hard": []}
    strategy_counts: dict[str, int] = {}
    qa_gate_summary = {
        "hard_total": 0,
        "passed_true": 0,
        "semantic_ok_true": 0,
        "format_ok_true": 0,
        "reason_available": 0,
        "label_preservation_true": 0,
    }
    moderator_bypass_summary: dict[str, dict[str, dict[str, int]]] = {}

    for row in rows:
        difficulty = str(row.get("difficulty_level"))
        if difficulty in difficulty_counts:
            difficulty_counts[difficulty] += 1

        pair_id = row.get("simple_hard_pair_id")
        if isinstance(pair_id, str) and pair_id.strip():
            trace_field_coverage["simple_hard_pair_id"] += 1
            pair_difficulties.setdefault(pair_id, set()).add(difficulty)

        if _has_non_empty(row, "seedbank_id") or _has_non_empty(row, "seed_id"):
            trace_field_coverage["seedbank_id_or_seed_id"] += 1
        if _has_non_empty(row, "source_row_id"):
            trace_field_coverage["source_row_id"] += 1

        rewrite_rounds = _number_or_none(row.get("rewrite_rounds"))
        if rewrite_rounds is not None and difficulty in rewrite_round_values:
            rewrite_round_values[difficulty].append(rewrite_rounds)

        if difficulty == "hard":
            qa_gate_summary["hard_total"] += 1
            for strategy in _string_list(row.get("strategy_chain")):
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            qa_values = _qa_gate_values(row)
            if qa_values["passed"] is True:
                qa_gate_summary["passed_true"] += 1
            if qa_values["semantic_ok"] is True:
                qa_gate_summary["semantic_ok_true"] += 1
            if qa_values["format_ok"] is True:
                qa_gate_summary["format_ok_true"] += 1
            if qa_values["reason_available"] is True:
                qa_gate_summary["reason_available"] += 1
            if qa_values["label_preservation"] is True:
                qa_gate_summary["label_preservation_true"] += 1

        for moderator, result in _moderator_results(row).items():
            by_difficulty = moderator_bypass_summary.setdefault(
                moderator,
                {
                    "simple": {"total": 0, "blocked": 0, "bypassed": 0},
                    "hard": {"total": 0, "blocked": 0, "bypassed": 0},
                },
            )
            if difficulty not in by_difficulty:
                continue
            by_difficulty[difficulty]["total"] += 1
            label = result.get("label")
            if label == "unsafe":
                by_difficulty[difficulty]["blocked"] += 1
            elif label == "safe":
                by_difficulty[difficulty]["bypassed"] += 1

    return {
        "difficulty_coverage": [
            difficulty for difficulty, count in difficulty_counts.items() if count > 0
        ],
        "difficulty_counts": difficulty_counts,
        "pair_count": sum(
            1 for difficulties in pair_difficulties.values() if {"simple", "hard"} <= difficulties
        ),
        "trace_field_coverage": trace_field_coverage,
        "rewrite_rounds": {
            difficulty: _summarize_numbers(values)
            for difficulty, values in rewrite_round_values.items()
        },
        "strategy_counts": dict(
            sorted(strategy_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "qa_gate_summary": qa_gate_summary,
        "moderator_bypass_summary": moderator_bypass_summary,
    }


def _build_delivery_validation(
    *,
    manifest: dict[str, Any],
    artifact_sha256: str,
) -> dict[str, Any]:
    return {
        "required_files": {
            "manifest.json": True,
            "report.md": True,
            "results.json": True,
            "dynbench.jsonl": True,
        },
        "strict_import_passed": True,
        "artifact_zip_sha256": artifact_sha256,
        "source_commit": manifest.get("source_commit"),
        "asr_definition": manifest.get("asr_definition"),
        "evaluator_version": manifest.get("evaluator_version"),
    }


def _build_evaluation_summary(
    *,
    manifest: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    moderators = results.get("moderators")
    if not isinstance(moderators, list):
        return _unavailable_evaluation_summary(
            manifest=manifest,
            reason="results.moderators must be a list",
        )

    normalized = [
        item
        for item in (_normalize_moderator_result(value) for value in moderators)
        if item is not None
    ]
    if not normalized:
        return _unavailable_evaluation_summary(
            manifest=manifest,
            reason="results.moderators has no by_difficulty metrics",
        )

    return {
        "available": True,
        "source": "results.json",
        "asr_definition": results.get("asr_definition") or manifest.get("asr_definition"),
        "evaluator_version": results.get("evaluator_version")
        or manifest.get("evaluator_version"),
        "run_at": results.get("run_at"),
        "moderators": normalized,
    }


def _unavailable_evaluation_summary(
    *,
    manifest: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "available": False,
        "source": "results.json",
        "reason": reason,
        "asr_definition": manifest.get("asr_definition"),
        "evaluator_version": manifest.get("evaluator_version"),
        "moderators": [],
    }


def _normalize_moderator_result(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    by_difficulty = value.get("by_difficulty")
    if not isinstance(by_difficulty, dict):
        return None

    simple = _normalize_difficulty_metrics(by_difficulty.get("simple"))
    hard = _normalize_difficulty_metrics(by_difficulty.get("hard"))
    if simple is None or hard is None:
        return None

    return {
        "name": _string_or_none(value.get("name")) or "unknown",
        "provider": _string_or_none(value.get("provider")),
        "model_version": _string_or_none(value.get("model_version"))
        or _string_or_none(value.get("version")),
        "run_at": _string_or_none(value.get("run_at")),
        "by_difficulty": {
            "simple": simple,
            "hard": hard,
        },
        "delta": _metric_delta(simple, hard),
    }


def _normalize_difficulty_metrics(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    metrics: dict[str, Any] = {}
    if isinstance(value.get("sample_count"), int):
        metrics["sample_count"] = value["sample_count"]
    elif isinstance(value.get("n"), int):
        metrics["sample_count"] = value["n"]
    for key in ("recall", "fnr", "f1", "asr"):
        number = _number_or_none(value.get(key))
        if number is None:
            return None
        metrics[key] = number
    metrics["fpr"] = _number_or_none(value.get("fpr"))
    return metrics


def _qa_gate_values(row: dict[str, Any]) -> dict[str, bool]:
    rewrite_qa = row.get("rewrite_qa")
    if not isinstance(rewrite_qa, dict):
        rewrite_qa = {}
    reason = rewrite_qa.get("reason")
    return {
        "passed": any(
            item is True
            for item in (
                row.get("qa_passed"),
                row.get("label_preservation"),
                row.get("semantic_ok"),
                rewrite_qa.get("passed"),
            )
        ),
        "semantic_ok": row.get("semantic_ok") is True
        or rewrite_qa.get("semantic_ok") is True,
        "format_ok": row.get("format_ok") is True
        or rewrite_qa.get("format_ok") is True,
        "label_preservation": row.get("label_preservation") is True,
        "reason_available": isinstance(reason, str) and bool(reason.strip()),
    }


def _moderator_results(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = row.get("moderator_results")
    if not isinstance(value, dict):
        return {}
    results: dict[str, dict[str, Any]] = {}
    for name, result in value.items():
        if isinstance(name, str) and isinstance(result, dict):
            results[name] = result
    return results


def _metric_delta(simple: dict[str, Any], hard: dict[str, Any]) -> dict[str, float]:
    return {
        key: round(float(hard[key]) - float(simple[key]), 6)
        for key in ("recall", "fnr", "fpr", "f1", "asr")
        if simple.get(key) is not None and hard.get(key) is not None
    }


def _summarize_numbers(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 3),
    }


def _has_non_empty(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    return value is not None and str(value).strip() != ""


def _number_or_none(value: Any) -> float | None:
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
