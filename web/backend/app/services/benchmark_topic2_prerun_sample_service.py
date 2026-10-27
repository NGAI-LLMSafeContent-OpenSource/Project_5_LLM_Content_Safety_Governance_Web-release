from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService


class BenchmarkTopic2PrerunSampleError(RuntimeError):
    """Raised when topic2 prerun samples cannot be read."""


class BenchmarkTopic2PrerunSampleNotFoundError(BenchmarkTopic2PrerunSampleError):
    """Raised when the requested topic2 prerun asset does not exist."""


class BenchmarkTopic2PrerunSampleService:
    async def list_pairs(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        moderator: str | None = None,
        verdict: str | None = None,
        difficulty: str | None = None,
        strategy: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = await self._get_topic2_prerun_asset(db, asset_id)
        pairs = list(_load_asset_pairs(asset)["pairs"])
        filtered = _filter_pairs(
            pairs,
            moderator=moderator,
            verdict=verdict,
            difficulty=difficulty,
            strategy=strategy,
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        page = filtered[safe_offset : safe_offset + safe_limit]
        return {
            "asset_id": asset.asset_id,
            "total": len(filtered),
            "limit": safe_limit,
            "offset": safe_offset,
            "moderators": _load_asset_pairs(asset)["moderators"],
            "pairs": page,
        }

    async def _get_topic2_prerun_asset(
        self,
        db: AsyncSession,
        asset_id: str,
    ) -> BenchmarkAsset:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkTopic2PrerunSampleNotFoundError("asset not found")
        manifest = _loads_json_object(asset.manifest_json)
        if manifest.get("source_mode") != "prerun_snapshot":
            raise BenchmarkTopic2PrerunSampleError("asset is not a prerun snapshot")
        if manifest.get("benchmark_type") == "risk_content_generation":
            raise BenchmarkTopic2PrerunSampleError("asset is not a topic2 prerun asset")
        artifact_dir = Path(asset.artifact_dir)
        if not artifact_dir.is_dir():
            raise BenchmarkTopic2PrerunSampleError("asset artifact directory not found")
        return asset


def _load_asset_pairs(asset: BenchmarkAsset) -> dict[str, Any]:
    return _load_asset_pairs_cached(
        asset.asset_id,
        asset.artifact_sha256,
        asset.artifact_dir,
    )


@lru_cache(maxsize=32)
def _load_asset_pairs_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
) -> dict[str, Any]:
    path = Path(artifact_dir_value) / "dynbench.jsonl"
    if not path.is_file():
        raise BenchmarkTopic2PrerunSampleError("asset is missing dynbench.jsonl")

    grouped: dict[str, dict[str, Any]] = {}
    moderators: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic2PrerunSampleError(
                f"dynbench.jsonl:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic2PrerunSampleError(
                f"dynbench.jsonl:{line_number} must contain a JSON object"
            )
        pair_id = str(row.get("simple_hard_pair_id") or row.get("seedbank_id") or line_number)
        pair = grouped.setdefault(
            pair_id,
            {
                "pair_id": pair_id,
                "seedbank_id": _string_or_none(row.get("seedbank_id")),
                "root_seed_id": _string_or_none(row.get("root_seed_id")),
                "source_row_id": _string_or_none(row.get("source_row_id")),
                "harm_category_l1": _string_or_none(row.get("harm_category_L1")),
                "harm_category_l2": _string_or_none(row.get("harm_category_L2")),
                "simple": None,
                "hard": None,
            },
        )
        for key in ("seedbank_id", "root_seed_id", "source_row_id", "harm_category_l1", "harm_category_l2"):
            if not pair.get(key):
                source_key = {
                    "harm_category_l1": "harm_category_L1",
                    "harm_category_l2": "harm_category_L2",
                }.get(key, key)
                pair[key] = _string_or_none(row.get(source_key))
        difficulty = row.get("difficulty_level")
        if difficulty in {"simple", "hard"}:
            sample = _to_sample_item(row)
            pair[difficulty] = sample
            moderators.update(sample["moderator_results"])

    pairs = sorted(grouped.values(), key=lambda item: item["pair_id"])
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "moderators": sorted(moderators),
        "pairs": tuple(pairs),
    }


def _filter_pairs(
    pairs: list[dict[str, Any]],
    *,
    moderator: str | None,
    verdict: str | None,
    difficulty: str | None,
    strategy: str | None,
) -> list[dict[str, Any]]:
    normalized_moderator = moderator.strip() if moderator and moderator.strip() else None
    normalized_verdict = verdict.strip() if verdict and verdict.strip() else None
    normalized_difficulty = difficulty.strip() if difficulty and difficulty.strip() else None
    normalized_strategy = strategy.strip() if strategy and strategy.strip() else None
    if normalized_verdict and normalized_verdict not in {"blocked", "bypassed"}:
        raise BenchmarkTopic2PrerunSampleError("verdict must be blocked or bypassed")
    if normalized_difficulty and normalized_difficulty not in {"simple", "hard"}:
        raise BenchmarkTopic2PrerunSampleError("difficulty must be simple or hard")

    filtered: list[dict[str, Any]] = []
    for pair in pairs:
        samples = [
            sample
            for sample in (pair.get("simple"), pair.get("hard"))
            if isinstance(sample, dict)
        ]
        if normalized_difficulty:
            samples = [
                sample
                for sample in samples
                if sample.get("difficulty_level") == normalized_difficulty
            ]
        if normalized_strategy:
            samples = [
                sample
                for sample in samples
                if normalized_strategy in sample.get("strategy_chain", [])
            ]
        if normalized_moderator or normalized_verdict:
            if _samples_match_moderator_filter(
                samples,
                moderator=normalized_moderator,
                verdict=normalized_verdict,
            ):
                filtered.append(pair)
        elif samples:
            filtered.append(pair)
    return filtered


def _samples_match_moderator_filter(
    samples: list[dict[str, Any]],
    *,
    moderator: str | None,
    verdict: str | None,
) -> bool:
    if not samples:
        return False
    matches = [
        _sample_matches_moderator(
            sample,
            moderator=moderator,
            verdict=verdict,
        )
        for sample in samples
    ]
    if verdict == "blocked":
        return all(matches)
    return any(matches)


def _sample_matches_moderator(
    sample: dict[str, Any],
    *,
    moderator: str | None,
    verdict: str | None,
) -> bool:
    results = sample.get("moderator_results")
    if not isinstance(results, dict):
        return False
    if moderator:
        result = results.get(moderator)
        return _moderator_result_matches(result, verdict=verdict)
    if verdict == "blocked":
        return bool(results) and all(
            _moderator_result_matches(result, verdict=verdict)
            for result in results.values()
        )
    return any(_moderator_result_matches(result, verdict=verdict) for result in results.values())


def _moderator_result_matches(value: Any, *, verdict: str | None) -> bool:
    if not isinstance(value, dict):
        return False
    if verdict is None:
        return True
    label = value.get("label")
    return (verdict == "blocked" and label == "unsafe") or (
        verdict == "bypassed" and label == "safe"
    )


def _to_sample_item(row: dict[str, Any]) -> dict[str, Any]:
    query = str(row.get("query") or "")
    rewrite_qa = row.get("rewrite_qa") if isinstance(row.get("rewrite_qa"), dict) else {}
    return {
        "sample_id": str(row.get("sample_id") or row.get("id") or ""),
        "difficulty_level": str(row.get("difficulty_level") or ""),
        "query_preview": _preview(query),
        "query": query,
        "rewrite_rounds": _number_or_none(row.get("rewrite_rounds")),
        "strategy": _string_or_none(row.get("strategy")),
        "strategy_chain": _string_list(row.get("strategy_chain")),
        "attack_vector": _string_or_none(row.get("attack_vector")),
        "language": _string_or_none(row.get("language")),
        "label": _string_or_none(row.get("label")),
        "rewrite_qa": {
            "passed": rewrite_qa.get("passed") is True,
            "semantic_ok": rewrite_qa.get("semantic_ok") is True,
            "format_ok": rewrite_qa.get("format_ok") is True,
            "reason": _string_or_none(rewrite_qa.get("reason")),
            "source": _string_or_none(rewrite_qa.get("source")),
        },
        "moderator_results": _moderator_results(row),
    }


def _moderator_results(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = row.get("moderator_results")
    if not isinstance(value, dict):
        return {}
    results: dict[str, dict[str, Any]] = {}
    for name, result in value.items():
        if isinstance(name, str) and isinstance(result, dict):
            results[name] = {
                "label": _string_or_none(result.get("label")),
                "confidence": _number_or_none(result.get("confidence")),
                "strength": _number_or_none(result.get("strength")),
            }
    return results


def _preview(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
