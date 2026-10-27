"""Validation of uploaded topic3 risk Benchmark delivery packages (#151).

DB-free. Checks an archive against the layout written by
``benchmark_topic3_risk_delivery_package``, extracts it into an isolated
directory and returns a structured report. Report messages carry identifiers,
counts, hashes and archive paths only, never sample, label or model text.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import stat
import unicodedata
import zipfile
import zlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.benchmark_topic3_risk_delivery_package import (
    ASSET_DIR,
    EVALUATIONS_DIR,
    MANIFEST_NAME,
    RAW_FILE,
    RUN_FILES,
    RUN_MANIFEST_NAME,
    SAMPLE_ID_FIELD,
    SCHEMA_VERSION,
    is_reserved_path_segment,
    is_safe_id,
)
from app.services.benchmark_topic3_risk_identity import SERIES_ID, read_json_object
from app.services.benchmark_topic3_risk_v6_service import CSV_FIELDS


REPORT_SCHEMA_VERSION = "topic5.benchmark_delivery_report.v1"
# Columns every topic3 risk asset CSV must carry; later versions add columns
# (v7 has 27) and extra columns are accepted.
REQUIRED_CSV_COLUMNS = (*CSV_FIELDS, SAMPLE_ID_FIELD)
# Where a topic3 raw record keeps the standard (CSV) sample_id. The raw
# top-level ``sample_id`` repeats the source ``index`` and is not unique in v7.
RAW_SAMPLE_ID_PATH = ("source_prediction_record", "algorithm_prediction", SAMPLE_ID_FIELD)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DRIVE = re.compile(r"^[A-Za-z]:")
_CHUNK_SIZE = 1024 * 1024
_SHOWN = 5
# Report strings come from the uploaded package and stay bounded.
_MAX_MESSAGE_CHARS = 500
_MAX_PATH_CHARS = 300
_MAX_MODEL_ID_CHARS = 200
_MAX_ROLE_CHARS = 64


@dataclass(frozen=True)
class DeliveryLimits:
    max_entries: int
    max_entry_bytes: int
    max_total_bytes: int
    max_compression_ratio: float


class _Rejected(Exception):
    """Stops validation after a failure that makes further checks meaningless."""


class _InvalidJson(Exception):
    pass


class _Issues:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def error(self, code: str, message: str, path: str | None = None) -> None:
        self.errors.append(_issue(code, message, path))

    def warning(self, code: str, message: str, path: str | None = None) -> None:
        self.warnings.append(_issue(code, message, path))


def _issue(code: str, message: str, path: str | None) -> dict[str, str]:
    issue = {"code": code, "message": _truncate(message, _MAX_MESSAGE_CHARS)}
    if path is not None:
        issue["path"] = _truncate(path, _MAX_PATH_CHARS)
    return issue


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def empty_report() -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "manifest": None,
        "file_count": 0,
        "total_uncompressed_bytes": 0,
        "asset": None,
        "runs": [],
        "errors": [],
        "warnings": [],
    }


def validate_delivery_package(
    package_path: Path,
    content_dir: Path,
    *,
    delivery_id: str,
    limits: DeliveryLimits,
) -> dict[str, Any]:
    """Extract ``package_path`` into the new directory ``content_dir`` and validate it.

    The delivery is publishable iff the returned report has no ``errors``.
    """
    report = empty_report()
    issues = _Issues()
    report["errors"], report["warnings"] = issues.errors, issues.warnings
    try:
        digests = _extract(package_path, content_dir, limits, issues, report)
        _validate_content(content_dir, digests, delivery_id, issues, report)
    except _Rejected:
        pass
    return report


def _extract(
    package_path: Path,
    content_dir: Path,
    limits: DeliveryLimits,
    issues: _Issues,
    report: dict[str, Any],
    *,
    allowed_path: Callable[[str], bool] | None = None,
) -> dict[str, tuple[str, int]]:
    allowed = allowed_path or _allowed_path
    try:
        archive = zipfile.ZipFile(package_path)
    except (zipfile.BadZipFile, OSError):
        issues.error("zip_invalid", "package is not a readable ZIP archive")
        raise _Rejected
    with archive:
        infos = archive.infolist()
        report["file_count"] = len(infos)
        report["total_uncompressed_bytes"] = sum(info.file_size for info in infos)
        _check_entries(infos, limits, issues, allowed_path=allowed)
        if issues.errors:
            raise _Rejected

        content_dir.mkdir(parents=True)
        digests: dict[str, tuple[str, int]] = {}
        total = 0
        for info in infos:
            # Entry names passed the whitelist, so every target stays inside content_dir.
            target = content_dir.joinpath(*info.filename.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            size = 0
            try:
                with archive.open(info) as source, target.open("xb") as sink:
                    for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
                        size += len(chunk)
                        total += len(chunk)
                        # Header sizes are only declarations; the written bytes decide.
                        if size > limits.max_entry_bytes:
                            issues.error(
                                "zip_entry_too_large",
                                f"entry decompresses beyond the {limits.max_entry_bytes}-byte "
                                "limit",
                                info.filename,
                            )
                            raise _Rejected
                        if total > limits.max_total_bytes:
                            issues.error(
                                "zip_total_too_large",
                                f"archive decompresses beyond the {limits.max_total_bytes}-byte "
                                "limit",
                            )
                            raise _Rejected
                        digest.update(chunk)
                        sink.write(chunk)
            except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError):
                issues.error(
                    "zip_invalid",
                    "archive entry is corrupt or uses an unsupported compression method",
                    info.filename,
                )
                raise _Rejected
            digests[info.filename] = (digest.hexdigest(), size)
    report["total_uncompressed_bytes"] = total
    return digests


def _check_entries(
    infos: list[zipfile.ZipInfo],
    limits: DeliveryLimits,
    issues: _Issues,
    *,
    allowed_path: Callable[[str], bool] | None = None,
) -> None:
    allowed = allowed_path or _allowed_path
    if len(infos) > limits.max_entries:
        issues.error(
            "zip_too_many_entries",
            f"archive has {len(infos)} entries; the limit is {limits.max_entries}",
        )
        return
    seen: set[str] = set()
    for info in infos:
        name = info.filename
        file_type = stat.S_IFMT(info.external_attr >> 16)
        if file_type == stat.S_IFLNK:
            issues.error("zip_symlink", "archive entry is a symbolic link", name)
        elif name.startswith(("/", "\\")) or _DRIVE.match(name):
            issues.error("zip_absolute_path", "archive entry has an absolute path", name)
        elif ".." in re.split(r"[\\/]", name):
            issues.error("zip_path_traversal", "archive entry escapes the package root", name)
        elif any(is_reserved_path_segment(segment) for segment in name.rstrip("/").split("/")):
            issues.error(
                "zip_reserved_name",
                "archive path uses a Windows reserved name or ends a segment with '.' or ' '",
                name,
            )
        elif info.is_dir() or file_type not in (0, stat.S_IFREG) or not allowed(name):
            issues.error(
                "zip_path_not_allowed",
                "archive entry is not a delivery manifest, asset CSV or evaluation run file",
                name,
            )
        if info.flag_bits & 0x1:
            issues.error("zip_encrypted", "archive entry is encrypted", name)
        key = unicodedata.normalize("NFC", name).casefold()
        if key in seen:
            issues.error("zip_duplicate_path", "archive contains this path more than once", name)
        seen.add(key)
        if info.file_size > limits.max_entry_bytes:
            issues.error(
                "zip_entry_too_large",
                f"entry is {info.file_size} bytes uncompressed; the limit is "
                f"{limits.max_entry_bytes}",
                name,
            )
        if info.file_size > limits.max_compression_ratio * max(info.compress_size, 1):
            issues.error(
                "zip_compression_ratio",
                f"entry expands {info.file_size} bytes from {info.compress_size}; the ratio "
                f"limit is {limits.max_compression_ratio:g}",
                name,
            )
    total = sum(info.file_size for info in infos)
    if total > limits.max_total_bytes:
        issues.error(
            "zip_total_too_large",
            f"archive is {total} bytes uncompressed; the limit is {limits.max_total_bytes}",
        )


def _allowed_path(name: str) -> bool:
    if name == MANIFEST_NAME:
        return True
    parts = name.split("/")
    if len(parts) == 2 and parts[0] == ASSET_DIR and parts[1].endswith(".csv"):
        return is_safe_id(parts[1][: -len(".csv")])
    return _allowed_run_path(name)


def _allowed_run_path(name: str) -> bool:
    """Whitelist of an evaluation-run-only package (no asset CSV, no manifest)."""
    parts = name.split("/")
    if len(parts) >= 3 and parts[0] == EVALUATIONS_DIR and is_safe_id(parts[1]):
        return "/".join(parts[2:]) in RUN_FILES
    return False


@dataclass(frozen=True)
class ExtractedRunPackage:
    content_dir: Path
    digests: dict[str, tuple[str, int]]
    file_count: int
    total_uncompressed_bytes: int
    errors: list[dict[str, str]]
    warnings: list[dict[str, str]]


def extract_evaluation_run_package(
    package_path: Path, content_dir: Path, *, limits: DeliveryLimits
) -> ExtractedRunPackage:
    """Safely extract ``evaluations/<run_id>/...`` from an append package.

    The caller checks ``errors`` before reading ``content_dir``: a failed
    extraction leaves no trusted content behind.
    """
    issues = _Issues()
    report = empty_report()
    report["errors"], report["warnings"] = issues.errors, issues.warnings
    digests: dict[str, tuple[str, int]] = {}
    try:
        digests = _extract(
            package_path,
            content_dir,
            limits,
            issues,
            report,
            allowed_path=_allowed_run_path,
        )
    except _Rejected:
        pass
    return ExtractedRunPackage(
        content_dir=content_dir,
        digests=digests,
        file_count=report["file_count"],
        total_uncompressed_bytes=report["total_uncompressed_bytes"],
        errors=issues.errors,
        warnings=issues.warnings,
    )


def _validate_content(
    content_dir: Path,
    digests: dict[str, tuple[str, int]],
    delivery_id: str,
    issues: _Issues,
    report: dict[str, Any],
) -> None:
    manifest = _read_manifest(content_dir, issues)
    report["manifest"] = {
        key: manifest[key]
        for key in (
            "delivery_id",
            "provider",
            "series_id",
            "asset_id",
            "asset_version",
            "sample_count",
            "generated_at",
        )
    }
    if manifest["delivery_id"] != delivery_id:
        issues.error(
            "delivery_id_mismatch",
            f"manifest delivery_id {manifest['delivery_id']} does not match the uploaded "
            f"delivery_id {delivery_id}",
        )
    asset_file = f"{ASSET_DIR}/{manifest['asset_id']}.csv"
    if manifest["asset_file"] != asset_file:
        issues.error("asset_file_mismatch", f"asset_file must be {asset_file}")
    _check_files(manifest, asset_file, digests, issues)

    asset_sha256 = digests[asset_file][0] if asset_file in digests else None
    sample_ids, column_count = None, None
    if asset_sha256 is not None:
        if asset_sha256 != manifest["asset_sha256"]:
            issues.error(
                "asset_hash_mismatch",
                f"asset CSV sha256 is {asset_sha256} but the manifest declares "
                f"{manifest['asset_sha256']}",
                asset_file,
            )
        sample_ids, column_count = _check_csv(content_dir / asset_file, asset_file, issues)
        if sample_ids is not None and len(sample_ids) != manifest["sample_count"]:
            issues.error(
                "sample_count_mismatch",
                f"asset CSV has {len(sample_ids)} samples but the manifest declares "
                f"{manifest['sample_count']}",
                asset_file,
            )
    report["asset"] = {
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "asset_sha256": asset_sha256,
        "sample_count": len(sample_ids) if sample_ids is not None else None,
        "column_count": column_count,
    }
    for entry in manifest["evaluation_runs"]:
        report["runs"].append(
            _check_run(content_dir, entry, manifest["asset_id"], asset_sha256, sample_ids, issues)
        )


def _read_object(
    path: Path, display: str, code: str, issues: _Issues, *, issue_path: str | None = None
) -> dict[str, Any] | None:
    """JSON object at ``path``, or ``None`` after recording ``code`` when it is not one."""
    try:
        return read_json_object(path, display, _InvalidJson)
    except UnicodeDecodeError:
        issues.error(code, f"{display} is not UTF-8", issue_path)
    except _InvalidJson as exc:
        issues.error(code, str(exc), issue_path)
    return None


def _read_manifest(content_dir: Path, issues: _Issues) -> dict[str, Any]:
    path = content_dir / MANIFEST_NAME
    if not path.is_file():
        issues.error("manifest_missing", f"archive has no {MANIFEST_NAME}")
        raise _Rejected
    payload = _read_object(path, MANIFEST_NAME, "manifest_invalid_json", issues)
    if payload is None:
        raise _Rejected
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.error(
            "manifest_schema_version",
            f"schema_version {str(payload.get('schema_version'))[:100]!r} is not supported; "
            f"expected {SCHEMA_VERSION}",
            "schema_version",
        )
        raise _Rejected
    problems = _manifest_problems(payload)
    for field, message in problems:
        issues.error("manifest_schema", message, field)
    if problems:
        raise _Rejected
    return payload


def _manifest_problems(payload: dict[str, Any]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []

    def need(field: str, valid: bool, description: str) -> None:
        if not valid:
            problems.append((field, f"{field} must be {description}"))

    for key in ("delivery_id", "provider", "asset_id", "asset_version"):
        need(key, is_safe_id(payload.get(key)), "a safe identifier")
    need("series_id", payload.get("series_id") == SERIES_ID, SERIES_ID)
    need("asset_sha256", _is_sha256(payload.get("asset_sha256")), "a lowercase hex SHA-256")
    need("asset_file", isinstance(payload.get("asset_file"), str), "a string")
    need("sample_count", _is_count(payload.get("sample_count"), positive=True), "a positive integer")
    need(
        "generated_at",
        _is_timestamp(payload.get("generated_at")),
        "an ISO 8601 timestamp with timezone",
    )

    files = payload.get("files")
    if not isinstance(files, list) or not files:
        problems.append(("files", "files must be a non-empty list"))
    else:
        for index, item in enumerate(files):
            if not (
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and _is_sha256(item.get("sha256"))
                and _is_count(item.get("size"))
            ):
                problems.append((f"files[{index}]", "each file needs path, sha256 and size"))
        paths = [item.get("path") for item in files if isinstance(item, dict)]
        if len(paths) != len(set(paths)):
            problems.append(("files", "files lists a path more than once"))

    runs = payload.get("evaluation_runs")
    if not isinstance(runs, list) or not runs:
        problems.append(("evaluation_runs", "evaluation_runs must be a non-empty list"))
        return problems
    run_ids = []
    for index, run in enumerate(runs):
        prefix = f"evaluation_runs[{index}]"
        if not isinstance(run, dict):
            problems.append((prefix, f"{prefix} must be an object"))
            continue
        run_id = run.get("run_id")
        run_ids.append(run_id)
        need(f"{prefix}.run_id", is_safe_id(run_id), "a safe identifier")
        need(
            f"{prefix}.path",
            run.get("path") == f"{EVALUATIONS_DIR}/{run_id}",
            f"{EVALUATIONS_DIR}/<run_id>",
        )
        need(
            f"{prefix}.models",
            _models(run.get("models")) is not None,
            "a non-empty list of models with model_id",
        )
        for key in ("predictions_count", "raw_count"):
            need(f"{prefix}.{key}", _is_count(run.get(key)), "a non-negative integer")
    if len(run_ids) != len(set(map(str, run_ids))):
        problems.append(("evaluation_runs", "evaluation_runs lists a run_id more than once"))
    return problems


def _check_files(
    manifest: dict[str, Any],
    asset_file: str,
    digests: dict[str, tuple[str, int]],
    issues: _Issues,
) -> None:
    listed = {item["path"]: item for item in manifest["files"]}
    present = set(digests) - {MANIFEST_NAME}
    required = {asset_file} | {
        f"{run['path']}/{name}" for run in manifest["evaluation_runs"] for name in RUN_FILES
    }
    for path in sorted(required - present):
        issues.error("file_missing", "required delivery file is missing from the archive", path)
    for path in sorted(set(listed) - present - required):
        issues.error("file_missing", "listed file is missing from the archive", path)
    for path in sorted(present - set(listed)):
        issues.error("file_unlisted", "archive file is not listed in the manifest files", path)
    for path in sorted(present - required):
        issues.error(
            "file_unexpected", "archive file belongs to no declared asset or evaluation run", path
        )
    for path in sorted(present & set(listed)):
        sha256, size = digests[path]
        entry = listed[path]
        if sha256 != entry["sha256"] or size != entry["size"]:
            issues.error(
                "file_hash_mismatch",
                f"file is {size} bytes with sha256 {sha256} but the manifest declares "
                f"{entry['size']} bytes with sha256 {entry['sha256']}",
                path,
            )


def _check_csv(
    path: Path, display: str, issues: _Issues
) -> tuple[list[str] | None, int | None]:
    csv.field_size_limit(2**31 - 1)
    sample_ids: list[str] = []
    empty_rows: list[int] = []
    ragged_rows: list[int] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if not header:
                issues.error("csv_empty", "asset CSV has no header", display)
                return None, None
            repeated = sorted(name for name, count in Counter(header).items() if count > 1)
            if repeated:
                issues.error(
                    "csv_duplicate_columns", f"asset CSV repeats columns {repeated}", display
                )
            missing = [name for name in REQUIRED_CSV_COLUMNS if name not in header]
            if missing:
                issues.error(
                    "csv_missing_columns", f"asset CSV lacks required columns {missing}", display
                )
                return None, len(header)
            position = header.index(SAMPLE_ID_FIELD)
            for row_number, row in enumerate(reader, 1):
                if not row:
                    continue
                if len(row) != len(header):
                    ragged_rows.append(row_number)
                    continue
                sample_id = row[position].strip()
                if sample_id:
                    sample_ids.append(sample_id)
                else:
                    empty_rows.append(row_number)
    except UnicodeDecodeError:
        issues.error("csv_not_utf8", "asset CSV is not UTF-8", display)
        return None, None
    except csv.Error:
        issues.error("csv_malformed", "asset CSV cannot be parsed", display)
        return None, None

    if ragged_rows:
        issues.error(
            "csv_malformed",
            f"{len(ragged_rows)} data rows do not have {len(header)} fields "
            f"(rows {ragged_rows[:_SHOWN]})",
            display,
        )
    if empty_rows:
        issues.error(
            "sample_id_empty",
            f"{len(empty_rows)} data rows have an empty {SAMPLE_ID_FIELD} (rows {empty_rows[:_SHOWN]})",
            display,
        )
    duplicates = sorted(value for value, count in Counter(sample_ids).items() if count > 1)
    if duplicates:
        issues.error(
            "sample_id_duplicate",
            f"{len(duplicates)} {SAMPLE_ID_FIELD} values repeat, e.g. {duplicates[:_SHOWN]}",
            display,
        )
    if not sample_ids:
        issues.error("csv_empty", "asset CSV has no samples", display)
    if ragged_rows or empty_rows or duplicates or not sample_ids:
        return None, len(header)
    return sample_ids, len(header)


def _check_run(
    content_dir: Path,
    entry: dict[str, Any],
    asset_id: str,
    asset_sha256: str | None,
    sample_ids: list[str] | None,
    issues: _Issues,
) -> dict[str, Any]:
    run_id = entry["run_id"]
    root = entry["path"]
    run_dir = content_dir / root
    models = _models(entry["models"])
    summary: dict[str, Any] = {
        "run_id": run_id,
        "models": models,
        "predictions_count": None,
        "raw_count": None,
    }

    run_manifest = _load_object(run_dir, root, RUN_MANIFEST_NAME, "evaluation_manifest_invalid", issues)
    manifest_path = f"{root}/{RUN_MANIFEST_NAME}"
    if run_manifest is not None:
        if run_manifest.get("run_id") != run_id:
            issues.error("evaluation_run_id_mismatch", f"run_id must be {run_id}", manifest_path)
        if run_manifest.get("asset_id") != asset_id:
            issues.error(
                "evaluation_asset_id_mismatch",
                f"evaluation asset_id does not match the delivery asset {asset_id}",
                manifest_path,
            )
        if asset_sha256 is not None and run_manifest.get("asset_sha256") != asset_sha256:
            issues.error(
                "evaluation_asset_hash_mismatch",
                f"evaluation asset_sha256 does not match the asset CSV sha256 {asset_sha256}",
                manifest_path,
            )
        run_models = _models(run_manifest.get("models"))
        if run_models is None:
            issues.error(
                "evaluation_models_invalid",
                "models must be a non-empty list of models with model_id",
                manifest_path,
            )
        elif run_models != models:
            issues.error(
                "evaluation_models_mismatch",
                "models differ from the delivery manifest run models",
                manifest_path,
            )

    metrics = _load_object(run_dir, root, "metrics.json", "metrics_invalid", issues)
    if metrics is not None:
        if not isinstance(metrics.get("metrics"), dict):
            issues.error("metrics_invalid", "metrics.json has no metrics object", f"{root}/metrics.json")
        for key, expected in (("asset_id", asset_id), ("asset_sha256", asset_sha256), ("run_id", run_id)):
            if key in metrics and expected is not None and metrics[key] != expected:
                issues.error(
                    "metrics_identity_mismatch",
                    f"metrics.json {key} does not match this run and asset",
                    f"{root}/metrics.json",
                )

    predictions = _read_jsonl(run_dir, root, "predictions.jsonl", "predictions_invalid", issues)
    if predictions is not None:
        count = len(predictions)
        summary["predictions_count"] = count
        expectations = [("delivery manifest predictions_count", entry["predictions_count"])]
        if run_manifest is not None:
            expectations.append(
                ("evaluation manifest predictions.count", _declared_count(run_manifest, "predictions"))
            )
        if sample_ids is not None:
            expectations.append(("the asset sample count", len(sample_ids)))
        for label, expected in expectations:
            if expected != count:
                issues.error(
                    "predictions_count_mismatch",
                    f"predictions.jsonl has {count} records but {label} is {expected}",
                    f"{root}/predictions.jsonl",
                )
        repeated = [
            value
            for value, seen in Counter(
                str(record.get(SAMPLE_ID_FIELD)) for _, record in predictions
            ).items()
            if seen > 1
        ]
        if repeated:
            issues.warning(
                "predictions_sample_id_not_unique",
                f"{len(repeated)} {SAMPLE_ID_FIELD} values repeat across predictions.jsonl "
                "records; the standard sample identity comes from the raw evaluation evidence",
                f"{root}/predictions.jsonl",
            )

    raw = _read_jsonl(run_dir, root, RAW_FILE, "raw_invalid", issues)
    if raw is not None:
        count = len(raw)
        summary["raw_count"] = count
        expectations = [("delivery manifest raw_count", entry["raw_count"])]
        declared_raw = _declared_count(run_manifest, "raw") if run_manifest is not None else None
        if declared_raw is not None:
            expectations.append(("evaluation manifest raw.count", declared_raw))
        elif run_manifest is not None:
            issues.warning(
                "raw_count_undeclared", "evaluation manifest declares no raw.count", manifest_path
            )
        for label, expected in expectations:
            if expected != count:
                issues.error(
                    "raw_count_mismatch",
                    f"{RAW_FILE} has {count} records but {label} is {expected}",
                    f"{root}/{RAW_FILE}",
                )
        if sample_ids is not None:
            _check_raw_sample_ids(raw, set(sample_ids), f"{root}/{RAW_FILE}", issues)
    return summary


def _check_raw_sample_ids(
    raw: list[tuple[int, dict[str, Any]]],
    csv_sample_ids: set[str],
    display: str,
    issues: _Issues,
) -> None:
    raw_ids: list[str] = []
    missing_lines: list[int] = []
    for line_number, record in raw:
        value: Any = record
        for key in RAW_SAMPLE_ID_PATH:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, str) and value.strip():
            raw_ids.append(value.strip())
        else:
            missing_lines.append(line_number)
    field = ".".join(RAW_SAMPLE_ID_PATH)
    if missing_lines:
        issues.error(
            "raw_sample_id_missing",
            f"{len(missing_lines)} raw records have no {field} (lines {missing_lines[:_SHOWN]})",
            display,
        )
    duplicates = sorted(value for value, count in Counter(raw_ids).items() if count > 1)
    if duplicates:
        issues.error(
            "raw_sample_id_duplicate",
            f"{len(duplicates)} raw {field} values repeat, e.g. {duplicates[:_SHOWN]}",
            display,
        )
    unknown = sorted(set(raw_ids) - csv_sample_ids)
    if unknown:
        issues.error(
            "raw_sample_id_unknown",
            f"{len(unknown)} raw {field} values are not asset CSV sample_ids, "
            f"e.g. {unknown[:_SHOWN]}",
            display,
        )
    uncovered = sorted(csv_sample_ids - set(raw_ids))
    if uncovered:
        issues.error(
            "raw_sample_id_uncovered",
            f"{len(uncovered)} asset CSV sample_ids have no raw record, e.g. {uncovered[:_SHOWN]}",
            display,
        )


def _load_object(
    run_dir: Path, root: str, name: str, code: str, issues: _Issues
) -> dict[str, Any] | None:
    path = run_dir / name
    if not path.is_file():
        return None
    return _read_object(path, name, code, issues, issue_path=f"{root}/{name}")


def _read_jsonl(
    run_dir: Path, root: str, name: str, code: str, issues: _Issues
) -> list[tuple[int, dict[str, Any]]] | None:
    path = run_dir / name
    if not path.is_file():
        return None
    records = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = None
                if not isinstance(payload, dict):
                    issues.error(
                        code, f"line {line_number} is not a JSON object", f"{root}/{name}"
                    )
                    return None
                records.append((line_number, payload))
    except UnicodeDecodeError:
        issues.error(code, f"{name} is not UTF-8", f"{root}/{name}")
        return None
    return records


def _declared_count(run_manifest: dict[str, Any], key: str) -> Any:
    section = run_manifest.get(key)
    return section.get("count") if isinstance(section, dict) else None


def _models(value: Any) -> list[dict[str, str]] | None:
    if not isinstance(value, list) or not value:
        return None
    models = []
    for model in value:
        if not isinstance(model, dict):
            return None
        model_id, role = model.get("model_id"), model.get("role") or ""
        if not (
            isinstance(model_id, str)
            and 0 < len(model_id) <= _MAX_MODEL_ID_CHARS
            and isinstance(role, str)
            and len(role) <= _MAX_ROLE_CHARS
        ):
            return None
        models.append({"model_id": model_id, "role": role})
    return models


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.match(value) is not None


def _is_count(value: Any, *, positive: bool = False) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= (1 if positive else 0)


def _is_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
