"""Load frozen V7 + Base evaluation packages from a Topic3 risk asset.

Reads only files under the asset ``artifact_dir``; never calls Topic3 online.
Both primary (qwen3.5-9B-V7) and baseline (qwen3.5-9B-base) packages are
required — they are never silently merged.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.db.models import BenchmarkAsset
from app.services.benchmark_topic3_risk_sample_service import V6_SAMPLES_FILE
from app.services.benchmark_topic3_risk_metrics import (
    model_display_name,
    primary_metric_values,
    supporting_metrics,
)
from app.services.benchmark_topic3_risk_v6_service import REQUIRED_RESULT_FILES

_CATEGORY_RE = re.compile(r"C(0[1-9]|1[0-7])")

PRIMARY_MODEL_ID = "qwen3.5-9B-V7"
BASELINE_MODEL_ID = "qwen3.5-9B-base"

BINARY_METRIC_KEYS = [
    "accuracy_safe_unsafe",
    "precision_safe_unsafe",
    "recall_safe_unsafe",
    "f1_safe_unsafe",
    "risk_false_positive_count",
    "tp",
    "tn",
    "fp",
    "fn",
]
LEVEL_METRIC_KEYS = [
    "risk_severity_accuracy",
    "level_accuracy_total",
]
MULTILABEL_METRIC_KEYS = [
    "micro_f1",
    "macro_f1",
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _category_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        joined = ",".join(str(item) for item in value)
    else:
        joined = str(value or "")
    return sorted({f"C{code}" for code in _CATEGORY_RE.findall(joined)})


def _normalize_prediction_row(row: dict[str, Any]) -> dict[str, Any]:
    """Typed V7/Base prediction fields used for recognition diffs (#91).

    Omits ``raw_output`` and any free-text prompt/response so freeze/export
    never carry full high-risk content from the prediction package.
    """
    sample_id = str(row.get("sample_id") or row.get("index") or "").strip()
    safe_type = (
        str(
            row.get("predicted_safe_type")
            or row.get("pred")
            or row.get("response_safetype")
            or ""
        )
        .strip()
        .lower()
    )
    risk_level = (
        str(row.get("predicted_risk_level") or row.get("risk_level_id") or "")
        .strip()
        .lower()
    )
    if not risk_level and safe_type == "safe":
        risk_level = "safe"
    if not safe_type and risk_level == "safe":
        safe_type = "safe"
    if not safe_type and risk_level in {"low", "medium", "high"}:
        safe_type = "unsafe"
    codes = _category_codes(
        row.get("predicted_risk_category_code")
        or row.get("risk_category_code")
        or row.get("risk_category")
        or ""
    )
    return {
        "sample_id": sample_id,
        "predicted_safe_type": safe_type,
        "predicted_risk_level": risk_level,
        "predicted_category_codes": codes,
    }


def _read_predictions(
    path: Path,
) -> tuple[list[str], list[str], int, list[dict[str, Any]]]:
    sample_ids: list[str] = []
    row_digests: list[str] = []
    prediction_rows: list[dict[str, Any]] = []
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    f"{path.name}:{line_number} must contain a JSON object"
                )
            # v7 keeps the source prediction nested and adds the standard
            # identity at the top level. Prefer that identity, but hash the
            # stored line itself so restore identity is unchanged.
            normalized = row.get("prediction")
            if isinstance(normalized, dict):
                source = dict(normalized)
                top_level_id = row.get("sample_id")
                if top_level_id not in (None, ""):
                    source["sample_id"] = str(top_level_id)
            else:
                source = row
            typed = _normalize_prediction_row(source)
            sample_ids.append(typed["sample_id"])
            row_digests.append(_canonical_digest(row))
            prediction_rows.append(typed)
            count += 1
    if count <= 0:
        raise ValueError(f"{path.name} must not be empty")
    return sample_ids, row_digests, count, prediction_rows


def _reference_samples_path(asset: BenchmarkAsset) -> Path | None:
    """Resolve the gold samples file: manifest ``files.samples`` first, then
    the v6 freeze name ``samples_v6.jsonl``, then legacy ``samples.jsonl``."""
    artifact_dir = Path(asset.artifact_dir or "")
    try:
        manifest = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        manifest = {}
    files = manifest.get("files") if isinstance(manifest, dict) else None
    declared = files.get("samples") if isinstance(files, dict) else None
    for name in (declared, V6_SAMPLES_FILE, "samples.jsonl"):
        if name and (artifact_dir / str(name)).is_file():
            return artifact_dir / str(name)
    return None


def load_risk_reference_sample_rows(asset: BenchmarkAsset) -> list[dict[str, Any]]:
    """Load gold labels from a versioned risk asset (create-time only)."""
    path = _reference_samples_path(asset)
    if path is None:
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    f"{path.name}:{line_number} must contain a JSON object"
                )
            sample_id = str(row.get("sample_id") or row.get("index") or "").strip()
            safetype = str(row.get("response_safetype") or "").strip().lower()
            level = str(row.get("risk_level_id") or "").strip().lower()
            if not level and safetype == "safe":
                level = "safe"
            raw_category = str(
                row.get("risk_category") or row.get("risk_category_name") or ""
            )
            codes = _category_codes(
                row.get("risk_category_code") or raw_category or ""
            )
            # Title tokens for label_reason alignment (create-time only).
            title_from_field = _CATEGORY_RE.sub("", raw_category)
            title_from_field = re.sub(r"^[\s:：\-–—/|]+", "", title_from_field).strip()
            category_titles = [title_from_field] if len(title_from_field) >= 2 else []
            rows.append(
                {
                    "sample_id": sample_id,
                    "response_safetype": safetype,
                    "risk_level_id": level,
                    "category_codes": codes,
                    "category_titles": category_titles,
                    "label_reason": str(row.get("label_reason") or ""),
                    "label_source": str(row.get("label_source") or ""),
                    "source_index": str(
                        row.get("source_index")
                        if row.get("source_index") is not None
                        else ""
                    ),
                    # Create-time only: used for redaction guards, never frozen.
                    "prompt": str(row.get("prompt") or ""),
                    "response": str(row.get("response") or ""),
                }
            )
    return rows


def _manifest_entries(asset: BenchmarkAsset) -> list[dict[str, Any]]:
    try:
        manifest = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return []
    if not isinstance(manifest, dict):
        return []
    return [
        item
        for item in manifest.get("evaluation_results", [])
        if isinstance(item, dict)
    ]


def _benchmark_version(asset: BenchmarkAsset) -> str:
    try:
        manifest = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return "v6"
    if not isinstance(manifest, dict):
        return "v6"
    return str(manifest.get("asset_version") or "v6")


def _pick_entry(
    entries: list[dict[str, Any]], *, role: str, model_id: str
) -> dict[str, Any] | None:
    for entry in entries:
        if entry.get("role") == role:
            return entry
    for entry in entries:
        # Legacy v6 manifests did not consistently declare roles. Preserve the
        # established model-id fallback without constraining newer series runs.
        if entry.get("model_id") == model_id:
            return entry
    return None


def _package_dir(asset: BenchmarkAsset, entry: dict[str, Any]) -> Path:
    run_id = str(entry.get("run_id") or "").strip()
    if not run_id:
        raise ValueError(f"evaluation entry for {entry.get('model_id')} missing run_id")
    root = Path(asset.artifact_dir or "")
    if not root.is_dir():
        raise FileNotFoundError(f"risk asset artifact_dir not found: {root}")
    package = root / "evaluations" / run_id
    if not package.is_dir():
        raise FileNotFoundError(
            f"risk evaluation package missing for {entry.get('model_id')}: {package}"
        )
    return package


def _load_package(
    asset: BenchmarkAsset,
    entry: dict[str, Any],
    *,
    role: str,
) -> dict[str, Any]:
    package = _package_dir(asset, entry)
    missing = [name for name in REQUIRED_RESULT_FILES if not (package / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"risk evaluation package for {entry.get('model_id')} is missing "
            f"required files: {', '.join(missing)}"
        )

    eval_manifest = _read_json(package / "evaluation_manifest.json")
    metrics_doc = _read_json(package / "metrics.json")
    metrics = metrics_doc.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(
            f"metrics.metrics must be an object for {entry.get('model_id')}"
        )
    # v7 publishes source predictions plus a normalized file that carries the
    # CSV sample_id; the review joins that identity. v6 has no such entry.
    predictions_path = package / "predictions.jsonl"
    normalized_rel = str(entry.get("normalized_predictions_path") or "").strip()
    normalized_path = None
    if normalized_rel:
        candidate = Path(asset.artifact_dir or "") / normalized_rel
        if candidate.is_file():
            predictions_path = candidate
            normalized_path = candidate
    sample_ids, row_digests, predictions_count, prediction_rows = _read_predictions(
        predictions_path
    )
    report_present = (package / "report.md").is_file()

    files = []
    for name in REQUIRED_RESULT_FILES:
        path = package / name
        rel = f"evaluations/{entry.get('run_id')}/{name}"
        files.append(
            {
                "role": f"{role}_{Path(name).stem}",
                "path": rel,
                "sha256": _sha256_file(path) if path.is_file() else "",
                "present": path.is_file(),
            }
        )
    if normalized_path is not None:
        files.append(
            {
                "role": f"{role}_predictions_normalized",
                "path": normalized_rel,
                "sha256": _sha256_file(normalized_path),
                "present": True,
            }
        )

    primary_values = primary_metric_values(metrics)
    supporting = supporting_metrics(metrics)
    binary = {key: metrics.get(key) for key in BINARY_METRIC_KEYS}
    level = {key: metrics.get(key) for key in LEVEL_METRIC_KEYS}
    multilabel = {key: metrics.get(key) for key in MULTILABEL_METRIC_KEYS}
    multilabel["per_category_metrics"] = metrics.get("per_category_metrics") or {}

    return {
        "role": role,
        "model_id": str(entry.get("model_id") or ""),
        "model_name": str(entry.get("model_name") or ""),
        "model_version": str(entry.get("model_version") or ""),
        "display_name": model_display_name(entry),
        "run_id": str(entry.get("run_id") or eval_manifest.get("run_id") or ""),
        "evaluated_at": str(
            entry.get("evaluated_at") or eval_manifest.get("evaluated_at") or ""
        ),
        "predictions_count": predictions_count,
        "sample_ids": sample_ids,
        "prediction_row_sha256": row_digests,
        "prediction_rows": prediction_rows,
        "asset_sha256": str(eval_manifest.get("asset_sha256") or ""),
        "report_present": report_present,
        "primary_metrics": primary_values,
        "supporting_metrics": supporting,
        "per_category_metrics": metrics.get("per_category_metrics") or {},
        "binary_metrics": binary,
        "level_metrics": level,
        "multilabel_metrics": multilabel,
        "metrics_keys_present": sorted(metrics.keys()),
        "files": files,
        "package_dir": str(package),
        "evaluation_manifest": {
            "asset_id": eval_manifest.get("asset_id"),
            "run_id": eval_manifest.get("run_id"),
            "asset_sha256": eval_manifest.get("asset_sha256"),
        },
    }


def load_risk_review_evidence(asset: BenchmarkAsset) -> dict[str, Any]:
    """Load the asset's primary package and optional same-version baseline."""
    entries = _manifest_entries(asset)
    primary_entry = _pick_entry(
        entries, role="primary", model_id=PRIMARY_MODEL_ID
    )
    baseline_entry = _pick_entry(
        entries, role="baseline", model_id=BASELINE_MODEL_ID
    )
    if primary_entry is None:
        raise FileNotFoundError(
            "risk review evidence missing primary package (role=primary)"
        )
    primary = _load_package(asset, primary_entry, role="primary")
    baseline = (
        _load_package(asset, baseline_entry, role="baseline")
        if baseline_entry is not None
        else None
    )
    files = list(primary["files"])
    if baseline is not None:
        files.extend(baseline["files"])
    return {
        # Compatibility identifier consumed by existing v6 snapshots/tests;
        # benchmark_version below carries the actual v6/v7 asset identity.
        "source": "topic3_risk_v6_evaluation",
        "benchmark_version": _benchmark_version(asset),
        "primary": primary,
        "baseline": baseline,
        "files": files,
    }
