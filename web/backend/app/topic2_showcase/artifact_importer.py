from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import tempfile
from typing import Any
import zipfile

from pydantic import ValidationError

from app.topic2_showcase.contracts import (
    ImportResult,
    PRIVATE_DYNBENCH_REPOSITORY,
    PrerunMetadata,
)


ALLOWED_MEMBERS = {
    "manifest.json",
    "report.md",
    "report_clear.md",
    "results.json",
    "dynbench.jsonl",
}


class ArtifactImportError(RuntimeError):
    """Raised when a DynBench artifact cannot be safely imported."""


def import_artifact(
    *,
    archive_path: Path | str,
    asset_root: Path | str,
    commit: str,
    moderators: list[str],
    budget: int,
    sampling_seed: int,
    attack_strategies: list[str],
) -> ImportResult:
    archive_path = Path(archive_path).expanduser().resolve()
    asset_root = Path(asset_root).expanduser().resolve()
    members = _validated_members(archive_path)

    if "manifest.json" not in members:
        raise ArtifactImportError("artifact is missing manifest.json")
    if "report.md" not in members:
        raise ArtifactImportError("artifact is missing required report.md")

    source_manifest = _read_json_member(
        archive_path,
        members["manifest.json"],
        "manifest.json",
    )
    created_at = _parse_created_at(source_manifest.get("created_at"))
    run_id = _build_run_id(created_at, commit)

    results = {}
    if "results.json" in members:
        results = _read_json_member(
            archive_path,
            members["results.json"],
            "results.json",
        )
    lifecycle = _extract_lifecycle(results)
    metrics = _extract_metrics(results)

    try:
        metadata = PrerunMetadata(
            run_id=run_id,
            created_at=created_at,
            repository=PRIVATE_DYNBENCH_REPOSITORY,
            commit=commit,
            moderators=moderators,
            budget=budget,
            sampling_seed=sampling_seed,
            attack_strategies=attack_strategies,
            metrics=metrics,
            report_file="report.md",
            lifecycle_file="lifecycle.json",
            lifecycle_available=bool(lifecycle),
        )
    except ValidationError as exc:
        raise ArtifactImportError(f"invalid run metadata: {exc}") from exc

    root_manifest_path = asset_root / "manifest.json"
    root_manifest = _read_root_manifest(root_manifest_path)
    prerun_root = asset_root / "prerun"
    final_dir = prerun_root / run_id
    if final_dir.exists():
        raise ArtifactImportError(f"run already exists: {run_id}")

    prerun_root.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=".topic2-import-", dir=prerun_root)
    )
    extracted_dir = stage_root / "source"
    output_dir = stage_root / "output"

    try:
        extracted_dir.mkdir()
        output_dir.mkdir()
        _extract_allowed_members(
            archive_path,
            members,
            extracted_dir,
        )

        shutil.copyfile(extracted_dir / "report.md", output_dir / "report.md")
        _write_json(
            output_dir / "run.json",
            metadata.model_dump(mode="json"),
        )
        _write_json(output_dir / "lifecycle.json", lifecycle)

        os.replace(output_dir, final_dir)
        updated_manifest = dict(root_manifest)
        updated_manifest["active_prerun"] = run_id
        try:
            _atomic_write_json(root_manifest_path, updated_manifest)
        except Exception:
            shutil.rmtree(final_dir, ignore_errors=True)
            raise
    except ArtifactImportError:
        raise
    except OSError as exc:
        raise ArtifactImportError(f"unable to publish imported run: {exc}") from exc
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    return ImportResult(
        run_id=run_id,
        output_dir=final_dir,
        files=["run.json", "report.md", "lifecycle.json"],
        lifecycle_available=bool(lifecycle),
    )


def _validated_members(archive_path: Path) -> dict[str, zipfile.ZipInfo]:
    if not archive_path.is_file():
        raise ArtifactImportError(f"artifact zip not found: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            seen: set[str] = set()
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if _is_unsafe_member(name):
                    raise ArtifactImportError(f"unsafe zip member: {name}")
                duplicate_key = name.replace("\\", "/").casefold()
                if duplicate_key in seen:
                    raise ArtifactImportError(f"duplicate zip member: {name}")
                seen.add(duplicate_key)
                if name not in ALLOWED_MEMBERS:
                    raise ArtifactImportError(
                        f"unsupported zip member: {name}"
                    )
                members[name] = info
            return members
    except zipfile.BadZipFile as exc:
        raise ArtifactImportError("invalid artifact zip") from exc


def _is_unsafe_member(name: str) -> bool:
    if not name or "\x00" in name:
        return True
    windows_path = PureWindowsPath(name)
    posix_path = PurePosixPath(name.replace("\\", "/"))
    if windows_path.is_absolute() or posix_path.is_absolute():
        return True
    return ".." in posix_path.parts


def _extract_allowed_members(
    archive_path: Path,
    members: dict[str, zipfile.ZipInfo],
    destination: Path,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for name, info in members.items():
            target = destination / name
            target.write_bytes(archive.read(info))


def _read_json_member(
    archive_path: Path,
    info: zipfile.ZipInfo,
    display_name: str,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            value = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactImportError(f"invalid JSON in {display_name}") from exc
    if not isinstance(value, dict):
        raise ArtifactImportError(f"{display_name} must contain an object")
    return value


def _read_root_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ArtifactImportError(f"showcase manifest unavailable: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ArtifactImportError("showcase manifest contains invalid JSON") from exc
    if not isinstance(value, dict):
        raise ArtifactImportError("showcase manifest must contain an object")
    return value


def _parse_created_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactImportError("artifact manifest is missing created_at")
    try:
        created_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactImportError("artifact created_at is invalid") from exc
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at


def _build_run_id(created_at: datetime, commit: str) -> str:
    normalized_commit = commit.strip()
    if not normalized_commit:
        raise ArtifactImportError("commit must not be empty")
    safe_commit = re.sub(r"[^A-Za-z0-9._-]", "-", normalized_commit)
    safe_commit = safe_commit.strip("-._")[:12]
    if not safe_commit:
        raise ArtifactImportError("commit has no safe identifier characters")
    timestamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{safe_commit}"


def _extract_lifecycle(results: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("lifecycle", "lifecycle_tracking", "all_lifecycles"):
        value = results.get(key)
        if isinstance(value, list) and all(
            isinstance(item, dict) for item in value
        ):
            return value
    return []


def _extract_metrics(results: dict[str, Any]) -> dict[str, float | int]:
    direct_metrics = results.get("metrics")
    if isinstance(direct_metrics, dict):
        return _numeric_values(direct_metrics)

    moderators = results.get("moderators")
    if not isinstance(moderators, list):
        return {}

    valid_moderators = [
        item for item in moderators if isinstance(item, dict)
    ]
    if len(valid_moderators) == 1:
        moderator = valid_moderators[0]
        metrics = _numeric_values(moderator.get("overall_metrics"))
        tested = moderator.get("total_samples")
        if isinstance(tested, int) and not isinstance(tested, bool):
            metrics["tested"] = tested
        return metrics

    flattened: dict[str, float | int] = {}
    for moderator in valid_moderators:
        name = moderator.get("name")
        if not isinstance(name, str) or not name:
            continue
        for key, value in _numeric_values(
            moderator.get("overall_metrics")
        ).items():
            flattened[f"{name}.{key}"] = value
    return flattened


def _numeric_values(value: Any) -> dict[str, float | int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _atomic_write_json(path: Path, value: Any) -> None:
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        _write_json(temporary_path, value)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将 DynBench artifact zip 转换为课题二展示工件"
    )
    parser.add_argument("--zip", dest="archive_path", required=True)
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--moderator", action="append", required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--sampling-seed", type=int, required=True)
    parser.add_argument(
        "--attack-strategy",
        action="append",
        required=True,
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = import_artifact(
        archive_path=args.archive_path,
        asset_root=args.asset_root,
        commit=args.commit,
        moderators=args.moderator,
        budget=args.budget,
        sampling_seed=args.sampling_seed,
        attack_strategies=args.attack_strategy,
    )
    print(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
