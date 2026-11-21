"""Shared builders for Topic2 CBRNE dataset_snapshot delivery packages (#121).

Expects already platform-normalized rows (id/label/cbrne_category/source/
exposure_tier/evaluator_relative_difficulty). Does not invent 12,420 counts or
missing Guard-derived fields.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


ASSET_KEY = "topic2.cbrne.anomaly_seedbank"
SCHEMA_ID = "topic2.cbrne.anomaly_seedbank.v1"
SOURCE_MODE = "dataset_snapshot"
BENCHMARK_TYPE = "anomaly_seedbank"
REQUIRED_MEMBERS = (
    "manifest.json",
    "dataset.jsonl",
    "profile.json",
    "DATASET_NOTE.md",
)
REQUIRED_ROW_FIELDS = (
    "id",
    "label",
    "cbrne_category",
    "source",
    "exposure_tier",
    "evaluator_relative_difficulty",
)


class CbrnePackageError(ValueError):
    """Raised when a delivery package cannot be built or verified."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dumps_jsonl_record(row: dict[str, Any]) -> str:
    """One JSON object, safe to split with ``str.splitlines``.

    Upstream prompts can contain U+2028/U+2029. ``json.dumps`` leaves those
    characters raw when ``ensure_ascii`` is false, and ``splitlines`` treats
    them as line breaks. Escape them so each record stays on one ``\\n`` line.
    """
    return (
        json.dumps(row, ensure_ascii=False)
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def load_normalized_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CbrnePackageError(
                f"{path}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise CbrnePackageError(f"{path}:{line_number} must be a JSON object")
        rows.append(row)
    if not rows:
        raise CbrnePackageError(f"{path} contains no rows")
    validate_rows(rows)
    return rows


def validate_rows(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            raise CbrnePackageError(
                f"row {index} missing required fields: {', '.join(missing)}"
            )
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise CbrnePackageError(f"row {index}.id must be a non-empty string")
        normalized_id = sample_id.strip()
        if normalized_id in seen:
            raise CbrnePackageError(f"duplicate sample id: {normalized_id}")
        seen.add(normalized_id)
        if row.get("label") not in {"safe", "unsafe"}:
            raise CbrnePackageError(f"row {index}.label must be safe or unsafe")
        if not _non_empty_str(row.get("cbrne_category")):
            raise CbrnePackageError(f"row {index}.cbrne_category must be non-empty")
        if not _non_empty_str(row.get("source")):
            raise CbrnePackageError(f"row {index}.source must be non-empty")
        if row.get("exposure_tier") not in {"T1", "T2", "T3", "T4"}:
            raise CbrnePackageError(f"row {index}.exposure_tier must be T1–T4")
        difficulty = row.get("evaluator_relative_difficulty")
        if isinstance(difficulty, bool) or not isinstance(difficulty, int) or difficulty < 0:
            raise CbrnePackageError(
                f"row {index}.evaluator_relative_difficulty must be an integer >= 0"
            )


def compute_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(rows),
        "unique_id_count": len({str(row["id"]).strip() for row in rows}),
        "label_counts": dict(sorted(Counter(str(row["label"]) for row in rows).items())),
        "cbrne_category_counts": dict(
            sorted(Counter(str(row["cbrne_category"]).strip() for row in rows).items())
        ),
        "source_counts": dict(
            sorted(Counter(str(row["source"]).strip() for row in rows).items())
        ),
        "exposure_tier_counts": dict(
            sorted(Counter(str(row["exposure_tier"]) for row in rows).items())
        ),
        "evaluator_relative_difficulty_counts": dict(
            sorted(
                Counter(
                    str(int(row["evaluator_relative_difficulty"])) for row in rows
                ).items()
            )
        ),
    }


def build_manifest(
    *,
    asset_id: str,
    version: str,
    source_repo: str,
    source_commit: str | None,
    source_tag: str | None,
    sample_count: int,
    original_filename: str,
    licence_notes: str,
    source_limitations: list[str],
    name: str = "Topic2 CBRNE anomaly seedbank",
    mark_as_current: bool = True,
) -> dict[str, Any]:
    if not source_commit and not source_tag:
        raise CbrnePackageError("source_commit or source_tag is required")
    if not licence_notes.strip():
        raise CbrnePackageError("licence_notes must be non-empty")
    if not source_limitations:
        raise CbrnePackageError("source_limitations must not be empty")
    return {
        "asset_id": asset_id,
        "asset_key": ASSET_KEY,
        "schema_id": SCHEMA_ID,
        "source_mode": SOURCE_MODE,
        "benchmark_type": BENCHMARK_TYPE,
        "name": name,
        "version": version,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_tag": source_tag,
        "original_filename": original_filename,
        "sample_count": sample_count,
        "sensitivity": "restricted_cbrne",
        "disclosure_policy": "full_text_benchmark_detail_only",
        "licence_notes": licence_notes,
        "source_limitations": source_limitations,
        "mark_as_current": mark_as_current,
    }


def default_dataset_note(*, source_repo: str, source_commit: str | None, source_tag: str | None) -> str:
    ref = source_commit or source_tag or "unknown"
    return (
        "# Topic2 CBRNE anomaly seedbank — delivery note\n\n"
        "## Provenance\n\n"
        f"- Source repository: `{source_repo}`\n"
        f"- Frozen revision: `{ref}`\n"
        "- Asset type: `dataset_snapshot` / `anomaly_seedbank`\n"
        f"- Schema: `{SCHEMA_ID}`\n\n"
        "## Sensitivity and disclosure\n\n"
        "- Sample full text is restricted CBRNE content.\n"
        "- Platform list/governance surfaces must show masked excerpts only.\n"
        "- Full text is available only through an explicit Benchmark detail action,\n"
        "  which records an access event.\n\n"
        "## Licence / use caveats\n\n"
        "- Contributing sources have mixed licences and intended uses.\n"
        "- Some sources are evaluation-only or carry contamination risk.\n"
        "- Successful import does **not** imply blanket training permission.\n\n"
        "## Difficulty definition\n\n"
        "- `evaluator_relative_difficulty` is the ten-Guard error/null-count basis.\n"
        "- It is not an intrinsic human difficulty label.\n"
        "- `exposure_tier` (T1–T4) is Guard exposure information, not difficulty.\n\n"
        "## Out of scope for this package\n\n"
        "- Activation Probe execution\n"
        "- AutoBench prerun_snapshot\n"
        "- VLM-Moderator / multimodal assets\n"
        "- Changes to Spec #87 / #115\n"
    )


def write_package_members(
    staging_dir: Path,
    *,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    note_text: str,
) -> dict[str, Any]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    profile = compute_profile(rows)
    if profile["sample_count"] != manifest["sample_count"]:
        raise CbrnePackageError(
            "manifest.sample_count does not match dataset row count "
            f"({manifest['sample_count']} vs {profile['sample_count']})"
        )
    if profile["unique_id_count"] != profile["sample_count"]:
        raise CbrnePackageError("unique_id_count must equal sample_count")

    dataset_text = "\n".join(dumps_jsonl_record(row) for row in rows) + "\n"
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (staging_dir / "dataset.jsonl").write_text(dataset_text, encoding="utf-8")
    (staging_dir / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (staging_dir / "DATASET_NOTE.md").write_text(note_text, encoding="utf-8")
    return profile


def zip_package_members(staging_dir: Path, output_zip: Path) -> dict[str, str]:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in REQUIRED_MEMBERS:
            path = staging_dir / name
            if not path.is_file():
                raise CbrnePackageError(f"missing package member: {name}")
            archive.write(path, arcname=name)
    hashes = {
        "artifact_zip_sha256": sha256_file(output_zip),
        "dataset_jsonl_sha256": sha256_file(staging_dir / "dataset.jsonl"),
        "manifest_json_sha256": sha256_file(staging_dir / "manifest.json"),
        "profile_json_sha256": sha256_file(staging_dir / "profile.json"),
        "dataset_note_sha256": sha256_file(staging_dir / "DATASET_NOTE.md"),
    }
    return hashes


def verify_package(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise CbrnePackageError(f"package not found: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        missing = set(REQUIRED_MEMBERS) - names
        if missing:
            raise CbrnePackageError(
                "package missing required members: " + ", ".join(sorted(missing))
            )
        unexpected = names - set(REQUIRED_MEMBERS)
        if unexpected:
            raise CbrnePackageError(
                "package has unexpected members: " + ", ".join(sorted(unexpected))
            )
        for info in archive.infolist():
            if info.is_dir():
                raise CbrnePackageError(f"directory members are not allowed: {info.filename}")
            if ".." in info.filename.replace("\\", "/") or info.filename.startswith("/"):
                raise CbrnePackageError(f"unsafe zip member: {info.filename}")

        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        profile = json.loads(archive.read("profile.json").decode("utf-8"))
        note = archive.read("DATASET_NOTE.md").decode("utf-8")
        dataset_bytes = archive.read("dataset.jsonl")

    rows = [
        json.loads(line)
        for line in dataset_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    validate_rows(rows)
    computed = compute_profile(rows)
    for key, expected in computed.items():
        if profile.get(key) != expected:
            raise CbrnePackageError(
                f"profile.{key} does not match dataset.jsonl "
                f"(profile={profile.get(key)!r}, computed={expected!r})"
            )
    if manifest.get("sample_count") != computed["sample_count"]:
        raise CbrnePackageError("manifest.sample_count does not match dataset")
    if not note.strip():
        raise CbrnePackageError("DATASET_NOTE.md must not be empty")

    return {
        "archive_path": str(archive_path),
        "artifact_zip_sha256": sha256_file(archive_path),
        "dataset_jsonl_sha256": sha256_bytes(dataset_bytes),
        "sample_count": computed["sample_count"],
        "unique_id_count": computed["unique_id_count"],
        "label_counts": computed["label_counts"],
        "cbrne_category_counts": computed["cbrne_category_counts"],
        "source_counts": computed["source_counts"],
        "exposure_tier_counts": computed["exposure_tier_counts"],
        "evaluator_relative_difficulty_counts": computed[
            "evaluator_relative_difficulty_counts"
        ],
        "source_repo": manifest.get("source_repo"),
        "source_commit": manifest.get("source_commit"),
        "source_tag": manifest.get("source_tag"),
        "licence_notes": manifest.get("licence_notes"),
        "source_limitations": manifest.get("source_limitations"),
        "asset_id": manifest.get("asset_id"),
        "version": manifest.get("version"),
    }


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
