from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic3_cultural_asset_service import (
    AGENT_ID,
    BENCHMARK_TYPE,
)


class BenchmarkTopic3CulturalSampleError(RuntimeError):
    """Raised when topic3 cultural samples cannot be read."""


class BenchmarkTopic3CulturalSampleNotFoundError(BenchmarkTopic3CulturalSampleError):
    """Raised when the requested topic3 cultural asset/sample does not exist."""


class BenchmarkTopic3CulturalSampleService:
    async def list_samples(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        ethnic_group: str | None = None,
        difficulty_level: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = await self._get_asset(db, asset_id)
        index = _load_asset_index(asset)
        rows = _filter_rows(
            index["rows"],
            ethnic_group=ethnic_group,
            difficulty_level=difficulty_level,
            keyword=keyword,
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        page = rows[safe_offset : safe_offset + safe_limit]
        return {
            "asset_id": asset.asset_id,
            "total": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "samples": [_to_list_item(item) for item in page],
        }

    async def get_sample(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        asset = await self._get_asset(db, asset_id)
        index = _load_asset_index(asset)
        row = index["by_sample_id"].get(sample_id)
        if row is None:
            raise BenchmarkTopic3CulturalSampleNotFoundError("sample not found")
        return dict(row)

    async def get_summary(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
    ) -> dict[str, Any]:
        asset = await self._get_asset(db, asset_id)
        manifest = _load_manifest(asset)
        return {
            "asset_id": asset.asset_id,
            "sample_count": _to_int(manifest.get("sample_count")),
            "difficulty_distribution": _to_object(manifest.get("difficulty_distribution")),
            "ethnic_distribution": _to_object(manifest.get("ethnic_distribution")),
            "background_type_distribution": _to_object(
                manifest.get("background_type_distribution")
            ),
            "persona_distribution": _to_object(manifest.get("persona_distribution")),
            "query_type_distribution": _to_object(manifest.get("query_type_distribution")),
            "review_passed_count": _to_int(manifest.get("review_passed_count")),
            "review_passed_rate": _to_float(manifest.get("review_passed_rate")),
            "model_eval_status": str(manifest.get("model_eval_status") or "pending_import"),
        }

    async def _get_asset(self, db: AsyncSession, asset_id: str) -> BenchmarkAsset:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkTopic3CulturalSampleNotFoundError("asset not found")
        manifest = _load_manifest(asset)
        if manifest.get("benchmark_type") != BENCHMARK_TYPE or manifest.get("agent_id") != AGENT_ID:
            raise BenchmarkTopic3CulturalSampleError(
                "asset is not a topic3 cultural corpus benchmark asset"
            )
        artifact_dir = Path(asset.artifact_dir)
        if not artifact_dir.is_dir():
            raise BenchmarkTopic3CulturalSampleError("asset artifact directory not found")
        return asset


def _load_manifest(asset: BenchmarkAsset) -> dict[str, Any]:
    try:
        manifest = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError as exc:
        raise BenchmarkTopic3CulturalSampleError("asset manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise BenchmarkTopic3CulturalSampleError("asset manifest must be a JSON object")
    return manifest


def _load_asset_index(asset: BenchmarkAsset) -> dict[str, Any]:
    return _load_asset_index_cached(asset.asset_id, asset.artifact_sha256, asset.artifact_dir)


@lru_cache(maxsize=32)
def _load_asset_index_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
) -> dict[str, Any]:
    samples_path = Path(artifact_dir_value) / "samples.jsonl"
    if not samples_path.is_file():
        raise BenchmarkTopic3CulturalSampleError("asset is missing samples.jsonl")
    rows: list[dict[str, Any]] = []
    by_sample_id: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(samples_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic3CulturalSampleError(
                f"samples.jsonl line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic3CulturalSampleError(
                f"samples.jsonl line {line_number} must contain a JSON object"
            )
        sample_id = str(row.get("sample_id") or "").strip()
        if not sample_id:
            raise BenchmarkTopic3CulturalSampleError(
                f"samples.jsonl line {line_number} missing sample_id"
            )
        rows.append(row)
        by_sample_id[sample_id] = row
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "rows": tuple(rows),
        "by_sample_id": by_sample_id,
    }


def _filter_rows(
    rows: tuple[dict[str, Any], ...],
    *,
    ethnic_group: str | None,
    difficulty_level: str | None,
    keyword: str | None,
) -> list[dict[str, Any]]:
    normalized_ethnic = ethnic_group.strip() if ethnic_group and ethnic_group.strip() else ""
    normalized_difficulty = (
        difficulty_level.strip() if difficulty_level and difficulty_level.strip() else ""
    )
    normalized_keyword = keyword.strip().lower() if keyword and keyword.strip() else ""
    filtered: list[dict[str, Any]] = []
    for item in rows:
        if normalized_ethnic and str(item.get("ethnic_group") or "") != normalized_ethnic:
            continue
        if normalized_difficulty and str(item.get("difficulty_level") or "") != normalized_difficulty:
            continue
        if normalized_keyword:
            haystack = " ".join(
                [
                    str(item.get("sample_id") or ""),
                    str(item.get("prompt") or ""),
                    str(item.get("background") or ""),
                    str(item.get("user_query") or ""),
                    str(item.get("expected_answer") or ""),
                    str(item.get("persona") or ""),
                    str(item.get("query_type") or ""),
                    str(((item.get("review") or {}).get("reason")) or ""),
                ]
            ).lower()
            if normalized_keyword not in haystack:
                continue
        filtered.append(item)
    return filtered


def _to_list_item(item: dict[str, Any]) -> dict[str, Any]:
    prompt_preview = str(item.get("prompt") or "")
    if len(prompt_preview) > 140:
        prompt_preview = f"{prompt_preview[:137]}..."
    review = item.get("review") if isinstance(item.get("review"), dict) else {}
    return {
        "sample_id": str(item.get("sample_id") or ""),
        "ethnic_group": str(item.get("ethnic_group") or ""),
        "difficulty_level": str(item.get("difficulty_level") or ""),
        "background_type": str(item.get("background_type") or ""),
        "persona": str(item.get("persona") or ""),
        "query_type": str(item.get("query_type") or ""),
        "review_passed": review.get("overall_passed") is True,
        "prompt_preview": prompt_preview,
    }


def _to_object(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, int):
            result[str(key)] = item
    return result


def _to_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 0


def _to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
