"""Local packaging of topic3 risk Benchmark delivery packages (#150).

Stdlib only, so ``scripts/package_topic3_risk_delivery.py`` runs without the
backend's DB dependencies. The archive layout and delivery manifest defined
here are the contract the Benchmark management import (#151) will validate.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable

from app.services.benchmark_topic3_risk_identity import (
    SERIES_ID,
    hash_file,
    read_json_object,
)


SCHEMA_VERSION = "topic5.benchmark_delivery.v1"
DEFAULT_PROVIDER = "topic3"
MANIFEST_NAME = "delivery_manifest.json"
ASSET_DIR = "asset"
EVALUATIONS_DIR = "evaluations"
RUN_MANIFEST_NAME = "evaluation_manifest.json"
RAW_FILE = "raw/optional_raw_outputs.jsonl"
RUN_CORE_FILES = (
    RUN_MANIFEST_NAME,
    "metrics.json",
    "predictions.jsonl",
    "report.md",
)
RUN_FILES = (*RUN_CORE_FILES, RAW_FILE)
SAMPLE_ID_FIELD = "sample_id"
IGNORED_DIR_NAMES = frozenset({"__MACOSX"})
# The zip epoch: entry timestamps must not depend on source mtimes so that
# identical inputs and options produce byte-identical packages.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_DESCRIPTION = (
    "1-200 characters of letters, digits, '.', '_' or '-' that start with a letter or digit, "
    "do not end with '.' and are not a Windows reserved device name"
)
# Windows device names are reserved with any extension and in any case.
_RESERVED_NAME = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.IGNORECASE)
_ASSET_VERSION_SUFFIX = re.compile(r"_(v\d+)$", re.IGNORECASE)
_CHUNK_SIZE = 1024 * 1024


class BenchmarkTopic3RiskDeliveryPackageError(RuntimeError):
    """Raised when inputs cannot form a valid Benchmark delivery package."""


@dataclass(frozen=True)
class _SourceFile:
    archive_path: str
    source: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class _Run:
    entry: dict[str, Any]
    files: list[_SourceFile]
    source_dir: Path
    evaluated_at: datetime | None

    @property
    def run_id(self) -> str:
        return self.entry["run_id"]


@dataclass(frozen=True)
class DeliveryPackageResult:
    package_path: Path
    package_size: int
    manifest: dict[str, Any]
    summary: str

    @property
    def source_file_count(self) -> int:
        return len(self.manifest["files"])


@dataclass(frozen=True)
class EvaluationRunPackageResult:
    package_path: Path
    package_size: int
    asset_id: str
    asset_sha256: str
    runs: list[dict[str, Any]]
    summary: str


def build_delivery_package(
    asset_csv: Path | str,
    result_dirs: Iterable[Path | str],
    output: Path | str,
    *,
    delivery_id: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    asset_id: str | None = None,
    asset_version: str | None = None,
    generated_at: str | None = None,
    overwrite: bool = False,
) -> DeliveryPackageResult:
    """Validate the sources and write the delivery zip atomically to ``output``.

    Sources are only read. On any failure no file is left at ``output``.
    """
    asset_csv = Path(asset_csv)
    output = Path(output)
    result_dirs = [Path(path) for path in result_dirs]
    if output.exists() and not overwrite:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"output already exists: {output}; remove it or pass --overwrite"
        )
    if not result_dirs:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            "at least one evaluation result dir is required"
        )
    if not asset_csv.is_file():
        raise BenchmarkTopic3RiskDeliveryPackageError(f"asset CSV not found: {asset_csv}")

    asset_id = asset_id or asset_csv.stem
    _require_safe_id("asset id", asset_id, hint="pass --asset-id")
    asset_version = _resolve_asset_version(asset_id, asset_version)
    _require_safe_id("provider", provider)
    if generated_at is not None:
        _check_generated_at(generated_at)

    asset_sha256, asset_size = hash_file(asset_csv)
    sample_count = _count_unique_sample_ids(asset_csv)
    asset_file = f"{ASSET_DIR}/{asset_id}.csv"

    runs: dict[str, _Run] = {}
    for result_dir in result_dirs:
        run = _validate_run(
            _locate_run_dir(result_dir), asset_id=asset_id, asset_sha256=asset_sha256
        )
        if run.run_id in runs:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"duplicate run_id {run.run_id}: declared by both "
                f"{runs[run.run_id].source_dir} and {run.source_dir}"
            )
        runs[run.run_id] = run
    ordered_runs = [runs[run_id] for run_id in sorted(runs)]
    generated_at = generated_at or _default_generated_at(ordered_runs)

    files = [_SourceFile(asset_file, asset_csv, asset_sha256, asset_size)]
    for run in ordered_runs:
        files.extend(run.files)
    delivery_id = delivery_id or _default_delivery_id(provider, asset_id, files)
    _require_safe_id("delivery id", delivery_id, hint="pass a different --delivery-id")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "delivery_id": delivery_id,
        "provider": provider,
        "series_id": SERIES_ID,
        "asset_id": asset_id,
        "asset_version": asset_version,
        "asset_sha256": asset_sha256,
        "asset_file": asset_file,
        "sample_count": sample_count,
        "evaluation_runs": [run.entry for run in ordered_runs],
        "files": [
            {"path": item.archive_path, "sha256": item.sha256, "size": item.size}
            for item in files
        ],
        "generated_at": generated_at,
    }
    _write_archive(output, manifest, files)
    package_size = output.stat().st_size
    return DeliveryPackageResult(
        package_path=output,
        package_size=package_size,
        manifest=manifest,
        summary=_format_summary(output, package_size, manifest),
    )


def build_evaluation_run_package(
    result_dirs: Iterable[Path | str],
    output: Path | str,
    *,
    overwrite: bool = False,
) -> EvaluationRunPackageResult:
    """Zip one or more evaluation runs for appending to an existing asset (#153).

    The archive holds ``evaluations/<run_id>/`` for every source run and no asset
    CSV: the target asset is named by the append endpoint, while each run's own
    ``evaluation_manifest.json`` carries the asset id and content hash it was
    evaluated against. Sources are only read.
    """
    output = Path(output)
    result_dirs = [Path(path) for path in result_dirs]
    if output.exists() and not overwrite:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"output already exists: {output}; remove it or pass --overwrite"
        )
    if not result_dirs:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            "at least one evaluation result dir is required"
        )

    runs: dict[str, _Run] = {}
    asset_id = ""
    asset_sha256 = ""
    for result_dir in result_dirs:
        run_dir = _locate_run_dir(result_dir)
        manifest = _load_json_object(run_dir, RUN_MANIFEST_NAME)
        run_asset_id = manifest.get("asset_id")
        run_asset_sha256 = manifest.get("asset_sha256")
        if not isinstance(run_asset_id, str) or not run_asset_id:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{run_dir / RUN_MANIFEST_NAME}: asset_id is required to append a run"
            )
        if not isinstance(run_asset_sha256, str) or not _SHA256_PATTERN.match(run_asset_sha256):
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{run_dir / RUN_MANIFEST_NAME}: asset_sha256 must be 64 lowercase hex characters"
            )
        if not asset_id:
            asset_id, asset_sha256 = run_asset_id, run_asset_sha256
        elif (run_asset_id, run_asset_sha256) != (asset_id, asset_sha256):
            raise BenchmarkTopic3RiskDeliveryPackageError(
                "all runs in one package must declare the same asset_id and asset_sha256"
            )
        run = _validate_run(
            run_dir, asset_id=asset_id, asset_sha256=asset_sha256, require_raw=False
        )
        if run.run_id in runs:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"duplicate run_id {run.run_id}: declared by both "
                f"{runs[run.run_id].source_dir} and {run.source_dir}"
            )
        runs[run.run_id] = run

    ordered_runs = [runs[run_id] for run_id in sorted(runs)]
    files = [item for run in ordered_runs for item in run.files]
    # A run-only package has no delivery manifest: the endpoint names the target
    # asset and each run manifest carries the identity it was evaluated against.
    _write_archive(output, None, files, manifest_name=None)
    package_size = output.stat().st_size
    return EvaluationRunPackageResult(
        package_path=output,
        package_size=package_size,
        asset_id=asset_id,
        asset_sha256=asset_sha256,
        runs=[run.entry for run in ordered_runs],
        summary=_format_run_package_summary(output, package_size, asset_id, asset_sha256, ordered_runs),
    )


def _format_run_package_summary(
    package_path: Path,
    package_size: int,
    asset_id: str,
    asset_sha256: str,
    runs: list[_Run],
) -> str:
    total = sum(item.size for run in runs for item in run.files)
    lines = [
        f"Benchmark evaluation run package: {package_path}",
        f"asset: {asset_id}",
        f"asset sha256: {asset_sha256}",
        f"evaluation runs: {len(runs)}",
    ]
    for run in runs:
        models = ", ".join(
            f"{model['model_id']} ({model['role'] or 'no role'})" for model in run.entry["models"]
        )
        lines += [
            f"  - {run.run_id}",
            f"    models: {models}",
            f"    predictions: {run.entry['predictions_count']}; "
            f"raw: {run.entry['raw_count']}",
        ]
    lines += [
        f"total uncompressed: {total} bytes ({_mib(total)})",
        f"package size: {package_size} bytes ({_mib(package_size)})",
    ]
    return "\n".join(lines) + "\n"


def _locate_run_dir(result_dir: Path) -> Path:
    """The single directory under ``result_dir`` holding an evaluation manifest."""
    if not result_dir.is_dir():
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"evaluation result dir not found: {result_dir}"
        )
    found = []
    for root, dirs, names in os.walk(result_dir):
        dirs[:] = sorted(
            name for name in dirs if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        )
        if RUN_MANIFEST_NAME in names:
            found.append(Path(root))
    if not found:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"no {RUN_MANIFEST_NAME} found under {result_dir}"
        )
    if len(found) > 1:
        listed = ", ".join(str(path.relative_to(result_dir)) for path in found)
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"multiple {RUN_MANIFEST_NAME} found under {result_dir} ({listed}); "
            "pass each run directory with its own --result-dir"
        )
    return found[0]


def _format_summary(package_path: Path, package_size: int, manifest: dict[str, Any]) -> str:
    total = sum(entry["size"] for entry in manifest["files"])
    lines = [
        f"Benchmark delivery package: {package_path}",
        f"delivery_id: {manifest['delivery_id']}",
        f"provider: {manifest['provider']}",
        f"series_id: {manifest['series_id']}",
        f"asset: {manifest['asset_id']} ({manifest['asset_version']})",
        f"asset sha256: {manifest['asset_sha256']}",
        f"samples: {manifest['sample_count']} (unique {SAMPLE_ID_FIELD})",
        f"evaluation runs: {len(manifest['evaluation_runs'])}",
    ]
    for run in manifest["evaluation_runs"]:
        models = ", ".join(
            f"{model['model_id']} ({model['role'] or 'no role'})" for model in run["models"]
        )
        lines += [
            f"  - {run['run_id']}",
            f"    models: {models}",
            f"    predictions: {run['predictions_count']}; raw: {run['raw_count']}",
        ]
    lines.append(f"source files: {len(manifest['files'])}")
    lines += [
        f"  {entry['size']:>12}  {entry['sha256']}  {entry['path']}"
        for entry in manifest["files"]
    ]
    lines += [
        f"total uncompressed: {total} bytes ({_mib(total)})",
        f"package size: {package_size} bytes ({_mib(package_size)})",
        f"generated_at: {manifest['generated_at']}",
    ]
    return "\n".join(lines) + "\n"


def _validate_run(
    run_dir: Path, *, asset_id: str, asset_sha256: str, require_raw: bool = True
) -> _Run:
    required_files = RUN_FILES if require_raw else RUN_CORE_FILES
    missing = [name for name in required_files if not (run_dir / name).is_file()]
    if missing:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"evaluation result {run_dir} is missing required files: {', '.join(missing)}"
        )
    manifest = _load_json_object(run_dir, RUN_MANIFEST_NAME)
    metrics = _load_json_object(run_dir, "metrics.json")

    run_id = str(manifest.get("run_id") or "")
    _require_safe_id(f"{run_dir / RUN_MANIFEST_NAME} run_id", run_id)
    _check_asset_identity(run_dir / RUN_MANIFEST_NAME, manifest, asset_id, asset_sha256)
    _check_asset_identity(
        run_dir / "metrics.json", metrics, asset_id, asset_sha256, required=False
    )
    declared_run_id = metrics.get("run_id", run_id)
    if declared_run_id != run_id:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"{run_dir / 'metrics.json'}: run_id {declared_run_id!r} does not match "
            f"{RUN_MANIFEST_NAME} run_id {run_id!r}; the metrics belong to another run"
        )
    models = _run_models(run_dir, manifest.get("models"))

    predictions = manifest.get("predictions")
    declared_count = predictions.get("count") if isinstance(predictions, dict) else None
    predictions_count = _count_jsonl(run_dir, "predictions.jsonl")
    if predictions_count == 0 or declared_count != predictions_count:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"{run_dir}: predictions.jsonl has {predictions_count} records but "
            f"{RUN_MANIFEST_NAME} predictions.count is {declared_count!r}"
        )
    raw = manifest.get("raw")
    declared_raw = raw.get("count") if isinstance(raw, dict) else None
    raw_count = 0
    if (run_dir / RAW_FILE).is_file():
        raw_count = _count_jsonl(run_dir, RAW_FILE)
        if declared_raw is not None and declared_raw != raw_count:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{run_dir}: {RAW_FILE} has {raw_count} records but "
                f"{RUN_MANIFEST_NAME} raw.count is {declared_raw!r}"
            )

    run_root = f"{EVALUATIONS_DIR}/{run_id}"
    files = []
    for name in RUN_FILES:
        if not (run_dir / name).is_file():
            continue
        sha256, size = hash_file(run_dir / name)
        files.append(_SourceFile(f"{run_root}/{name}", run_dir / name, sha256, size))
    entry = {
        "run_id": run_id,
        "path": run_root,
        "models": models,
        "predictions_count": predictions_count,
        "raw_count": raw_count,
    }
    return _Run(
        entry=entry,
        files=files,
        source_dir=run_dir,
        evaluated_at=_parse_timestamp(manifest.get("evaluated_at")),
    )


def _check_asset_identity(
    path: Path,
    payload: dict[str, Any],
    asset_id: str,
    asset_sha256: str,
    *,
    required: bool = True,
) -> None:
    """``payload`` must name this asset; with ``required=False`` absent keys pass."""
    if required or "asset_id" in payload:
        declared_asset_id = payload.get("asset_id")
        if declared_asset_id != asset_id:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{path}: asset_id {declared_asset_id!r} does not match asset id {asset_id!r}; "
                "pass --asset-id if the CSV filename differs from the asset id"
            )
    if required or "asset_sha256" in payload:
        declared_sha256 = payload.get("asset_sha256")
        if declared_sha256 != asset_sha256:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{path}: asset_sha256 {declared_sha256!r} does not match the asset CSV "
                f"sha256 {asset_sha256}; this result was not produced from this CSV"
            )


def _run_models(run_dir: Path, models: Any) -> list[dict[str, str]]:
    if not isinstance(models, list) or not models:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"{run_dir / RUN_MANIFEST_NAME}: models must be a non-empty list"
        )
    result = []
    for model in models:
        model_id = model.get("model_id") if isinstance(model, dict) else None
        if not isinstance(model_id, str) or not model_id:
            raise BenchmarkTopic3RiskDeliveryPackageError(
                f"{run_dir / RUN_MANIFEST_NAME}: every model needs a non-empty model_id"
            )
        result.append({"model_id": model_id, "role": str(model.get("role") or "")})
    return result


def _count_unique_sample_ids(path: Path) -> int:
    csv.field_size_limit(2**31 - 1)
    seen: set[str] = set()
    duplicates: set[str] = set()
    empty_rows = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if SAMPLE_ID_FIELD not in (reader.fieldnames or []):
                raise BenchmarkTopic3RiskDeliveryPackageError(
                    f"asset CSV {path} has no {SAMPLE_ID_FIELD} column"
                )
            for row_number, row in enumerate(reader, 1):
                sample_id = (row.get(SAMPLE_ID_FIELD) or "").strip()
                if not sample_id:
                    empty_rows.append(row_number)
                elif sample_id in seen:
                    duplicates.add(sample_id)
                seen.add(sample_id)
    except UnicodeDecodeError as exc:
        raise BenchmarkTopic3RiskDeliveryPackageError(f"asset CSV {path} is not UTF-8") from exc
    except csv.Error as exc:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"asset CSV {path} is malformed: {exc}"
        ) from exc
    if empty_rows:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"asset CSV {path} has empty {SAMPLE_ID_FIELD} in data rows {empty_rows[:5]}"
        )
    if duplicates:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"asset CSV {path} has duplicate {SAMPLE_ID_FIELD} values: {sorted(duplicates)[:5]}"
        )
    if not seen:
        raise BenchmarkTopic3RiskDeliveryPackageError(f"asset CSV {path} has no samples")
    return len(seen)


def _load_json_object(run_dir: Path, name: str) -> dict[str, Any]:
    path = run_dir / name
    try:
        return read_json_object(path, str(path), BenchmarkTopic3RiskDeliveryPackageError)
    except UnicodeDecodeError as exc:
        raise BenchmarkTopic3RiskDeliveryPackageError(f"{path} is not UTF-8") from exc


def _count_jsonl(run_dir: Path, name: str) -> int:
    count = 0
    with (run_dir / name).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkTopic3RiskDeliveryPackageError(
                    f"{run_dir}: {name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise BenchmarkTopic3RiskDeliveryPackageError(
                    f"{run_dir}: {name}:{line_number} must contain a JSON object"
                )
            count += 1
    return count


def is_reserved_path_segment(segment: str) -> bool:
    """Path segments Windows cannot store faithfully: device names and trailing dots/spaces."""
    return segment.endswith((".", " ")) or _RESERVED_NAME.match(segment) is not None


def is_safe_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and SAFE_ID_PATTERN.match(value) is not None
        and not is_reserved_path_segment(value)
    )


def _require_safe_id(label: str, value: str, *, hint: str = "") -> None:
    if not is_safe_id(value):
        suffix = f"; {hint}" if hint else ""
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"{label} {value!r} must be {SAFE_ID_DESCRIPTION}{suffix}"
        )


def _resolve_asset_version(asset_id: str, asset_version: str | None) -> str:
    if asset_version and asset_version.strip():
        return asset_version.strip().lower()
    match = _ASSET_VERSION_SUFFIX.search(asset_id)
    if match is None:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"cannot derive the asset version from asset id {asset_id!r}; pass --asset-version"
        )
    return match.group(1).lower()


def _check_generated_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"generated_at {value!r} is not an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"generated_at {value!r} must include a timezone"
        )


def _default_generated_at(runs: list[_Run]) -> str:
    """Latest run ``evaluated_at`` in UTC, so repackaging the same content is byte-identical."""
    evaluated = [run.evaluated_at for run in runs if run.evaluated_at is not None]
    if not evaluated:
        raise BenchmarkTopic3RiskDeliveryPackageError(
            f"no {RUN_MANIFEST_NAME} declares a timezone-aware ISO 8601 evaluated_at to derive "
            "generated_at from; pass --generated-at"
        )
    return max(evaluated).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _default_delivery_id(provider: str, asset_id: str, files: list[_SourceFile]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(f"{item.archive_path}\t{item.sha256}\n".encode("utf-8"))
    return f"{provider}-{asset_id}-{digest.hexdigest()[:12]}"


def _write_archive(
    output: Path,
    manifest: dict[str, Any] | None,
    files: list[_SourceFile],
    *,
    manifest_name: str | None = MANIFEST_NAME,
) -> None:
    manifest_bytes = (
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if manifest is not None
        else b""
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".partial", dir=output.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w") as archive:
            if manifest_name is not None:
                _write_entry(
                    archive, manifest_name, io.BytesIO(manifest_bytes), len(manifest_bytes)
                )
            for item in files:
                with item.source.open("rb") as source:
                    sha256 = _write_entry(archive, item.archive_path, source, item.size)
                if sha256 != item.sha256:
                    raise BenchmarkTopic3RiskDeliveryPackageError(
                        f"{item.source} changed while packaging; re-run the tool"
                    )
        os.replace(temp_path, output)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _write_entry(archive: zipfile.ZipFile, name: str, source: BinaryIO, size: int) -> str:
    info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.file_size = size
    digest = hashlib.sha256()
    with archive.open(info, "w") as entry:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
            entry.write(chunk)
    return digest.hexdigest()


def _mib(size: int) -> str:
    return f"{size / (1024 * 1024):.2f} MiB"
