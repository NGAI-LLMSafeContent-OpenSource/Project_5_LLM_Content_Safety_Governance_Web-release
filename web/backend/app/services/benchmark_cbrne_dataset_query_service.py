"""CBRNE anomaly seedbank searchable projection + deterministic query (#118).

Builds a list-safe projection (filter fields + masked excerpt + stable refs)
from the registered dataset_snapshot artifact. Does not expose full sample text
or evaluator execution actions.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_cbrne_dataset_snapshot_service import (
    BENCHMARK_TYPE,
    SOURCE_MODE,
)


ALLOWED_LABELS = frozenset({"safe", "unsafe"})
ALLOWED_EXPOSURE_TIERS = frozenset({"T1", "T2", "T3", "T4"})


class BenchmarkCbrneDatasetQueryError(RuntimeError):
    """Raised when CBRNE query filters or asset shape are invalid."""


class BenchmarkCbrneDatasetQueryNotFoundError(BenchmarkCbrneDatasetQueryError):
    """Raised when the requested CBRNE dataset asset does not exist."""


class BenchmarkCbrneDatasetQueryService:
    async def query_samples(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        label: str | None = None,
        cbrne_category: str | None = None,
        source: str | None = None,
        exposure_tier: str | None = None,
        difficulty_min: int | None = None,
        difficulty_max: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = await self._get_cbrne_asset(db, asset_id)
        projection = _load_projection(asset)
        query = _normalize_query(
            label=label,
            cbrne_category=cbrne_category,
            source=source,
            exposure_tier=exposure_tier,
            difficulty_min=difficulty_min,
            difficulty_max=difficulty_max,
        )
        filtered = _filter_projection(projection["rows"], query)
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        page = filtered[safe_offset : safe_offset + safe_limit]
        return {
            "asset_id": asset.asset_id,
            "asset_version": projection["asset_version"],
            "record_version": projection["record_version"],
            "query": query,
            "total": len(filtered),
            "limit": safe_limit,
            "offset": safe_offset,
            "distributions": _distributions_for_rows(filtered),
            "samples": [dict(item) for item in page],
        }

    async def _get_cbrne_asset(self, db: AsyncSession, asset_id: str) -> BenchmarkAsset:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkCbrneDatasetQueryNotFoundError("asset not found")
        manifest = _loads_json_object(asset.manifest_json)
        if (
            asset.source_mode != SOURCE_MODE
            or manifest.get("benchmark_type") != BENCHMARK_TYPE
        ):
            raise BenchmarkCbrneDatasetQueryError(
                "asset is not a CBRNE anomaly_seedbank dataset_snapshot"
            )
        if not Path(asset.artifact_dir).is_dir():
            raise BenchmarkCbrneDatasetQueryError("asset artifact directory not found")
        return asset


def _normalize_query(
    *,
    label: str | None,
    cbrne_category: str | None,
    source: str | None,
    exposure_tier: str | None,
    difficulty_min: int | None,
    difficulty_max: int | None,
) -> dict[str, Any]:
    normalized_label = _optional_str(label)
    if normalized_label is not None and normalized_label not in ALLOWED_LABELS:
        raise BenchmarkCbrneDatasetQueryError("label must be safe or unsafe")

    normalized_category = _optional_str(cbrne_category)
    normalized_source = _optional_str(source)

    normalized_tier = _optional_str(exposure_tier)
    if normalized_tier is not None and normalized_tier not in ALLOWED_EXPOSURE_TIERS:
        raise BenchmarkCbrneDatasetQueryError("exposure_tier must be T1–T4")

    if difficulty_min is not None and (
        isinstance(difficulty_min, bool) or not isinstance(difficulty_min, int)
    ):
        raise BenchmarkCbrneDatasetQueryError("difficulty_min must be an integer")
    if difficulty_max is not None and (
        isinstance(difficulty_max, bool) or not isinstance(difficulty_max, int)
    ):
        raise BenchmarkCbrneDatasetQueryError("difficulty_max must be an integer")
    if difficulty_min is not None and difficulty_min < 0:
        raise BenchmarkCbrneDatasetQueryError("difficulty_min must be >= 0")
    if difficulty_max is not None and difficulty_max < 0:
        raise BenchmarkCbrneDatasetQueryError("difficulty_max must be >= 0")
    if (
        difficulty_min is not None
        and difficulty_max is not None
        and difficulty_min > difficulty_max
    ):
        raise BenchmarkCbrneDatasetQueryError(
            "difficulty_min must be <= difficulty_max"
        )

    return {
        "label": normalized_label,
        "cbrne_category": normalized_category,
        "source": normalized_source,
        "exposure_tier": normalized_tier,
        "difficulty_min": difficulty_min,
        "difficulty_max": difficulty_max,
    }


def _filter_projection(
    rows: tuple[dict[str, Any], ...],
    query: dict[str, Any],
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if query["label"] is not None and row["label"] != query["label"]:
            continue
        if (
            query["cbrne_category"] is not None
            and row["cbrne_category"] != query["cbrne_category"]
        ):
            continue
        if query["source"] is not None and row["source"] != query["source"]:
            continue
        if (
            query["exposure_tier"] is not None
            and row["exposure_tier"] != query["exposure_tier"]
        ):
            continue
        difficulty = int(row["evaluator_relative_difficulty"])
        if query["difficulty_min"] is not None and difficulty < query["difficulty_min"]:
            continue
        if query["difficulty_max"] is not None and difficulty > query["difficulty_max"]:
            continue
        filtered.append(row)
    return filtered


def _distributions_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts = Counter(str(row["label"]) for row in rows)
    category_counts = Counter(str(row["cbrne_category"]) for row in rows)
    source_counts = Counter(str(row["source"]) for row in rows)
    tier_counts = Counter(str(row["exposure_tier"]) for row in rows)
    difficulty_counts = Counter(
        str(int(row["evaluator_relative_difficulty"])) for row in rows
    )
    return {
        "sample_count": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "cbrne_category_counts": dict(sorted(category_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "exposure_tier_counts": dict(sorted(tier_counts.items())),
        "evaluator_relative_difficulty_counts": dict(sorted(difficulty_counts.items())),
    }


def _load_projection(asset: BenchmarkAsset) -> dict[str, Any]:
    return _load_projection_cached(
        asset.asset_id,
        asset.artifact_sha256,
        asset.artifact_dir,
        asset.manifest_json or "",
    )


@lru_cache(maxsize=32)
def _load_projection_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
    manifest_json: str,
) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir_value)
    dataset_path = artifact_dir / "dataset.jsonl"
    if not dataset_path.is_file():
        raise BenchmarkCbrneDatasetQueryError("asset is missing dataset.jsonl")

    manifest = _loads_json_object(manifest_json)
    if not manifest:
        platform_path = artifact_dir / "manifest.platform.json"
        if platform_path.is_file():
            manifest = _loads_json_object(platform_path.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkCbrneDatasetQueryError(
                f"dataset.jsonl:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise BenchmarkCbrneDatasetQueryError(
                f"dataset.jsonl:{line_number} must contain a JSON object"
            )
        sample_id = str(raw.get("id") or "").strip()
        if not sample_id:
            raise BenchmarkCbrneDatasetQueryError(
                f"dataset.jsonl:{line_number}.id must be a non-empty string"
            )
        rows.append(
            {
                "sample_id": sample_id,
                "label": str(raw.get("label", "")),
                "cbrne_category": str(raw.get("cbrne_category", "")),
                "source": str(raw.get("source", "")),
                "exposure_tier": str(raw.get("exposure_tier", "")),
                "evaluator_relative_difficulty": int(
                    raw.get("evaluator_relative_difficulty", 0)
                ),
                "text_excerpt": _masked_excerpt(raw.get("prompt")),
                "resource_ref": {
                    "kind": "benchmark.cbrne_sample",
                    "asset_id": asset_id,
                    "sample_id": sample_id,
                },
            }
        )

    rows.sort(key=lambda item: item["sample_id"])
    record_version = str(
        manifest.get("dataset_content_sha256")
        or manifest.get("version")
        or artifact_sha256
    )
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "asset_version": str(manifest.get("version") or ""),
        "record_version": record_version,
        "rows": tuple(rows),
    }


def _masked_excerpt(value: Any) -> str:
    """List-safe summary: length only, never copies prompt characters into list data."""
    text = " ".join(str(value or "").split())
    return f"[masked excerpt · {len(text)} chars]"


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
