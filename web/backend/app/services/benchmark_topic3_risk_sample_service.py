from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic3_risk_series_service import (
    BENCHMARK_TYPE,
    BenchmarkTopic3RiskSeriesError,
    ResolvedTopic3RiskAsset,
    describe_asset,
    is_series_manifest,
    loads_json_object,
)
from app.services.benchmark_topic3_risk_taxonomy_service import TOPIC3_RISK_CATEGORIES


LOW_WARNING_NOTE = "该样本为低风险边界样本，包含轻度风险信号，仅用于内部评测解释。"
_MISSING_LABEL_REASON = "未提供"
_MISALIGNED_LABEL_REASON = "misaligned_label_reason"
_TAXONOMY_TITLES = dict(TOPIC3_RISK_CATEGORIES)
RISK_LEVEL_FILES = {
    "safe": ("safe.jsonl", "safe_400.jsonl"),
    "low": ("low.jsonl", "low_400.jsonl"),
}
V6_SAMPLES_FILE = "samples_v6.jsonl"


class BenchmarkTopic3RiskSampleError(RuntimeError):
    """Raised when dynamic risk benchmark samples cannot be read."""


class BenchmarkTopic3RiskSampleNotFoundError(BenchmarkTopic3RiskSampleError):
    """Raised when the requested asset or sample does not exist."""


class BenchmarkTopic3RiskSampleService:
    async def list_samples(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        risk_level_id: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        resolved = await self._describe(db, await self._get_topic3_risk_asset(db, asset_id))
        return self.list_resolved_samples(
            resolved,
            risk_level_id=risk_level_id,
            category=category,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )

    async def get_sample(
        self,
        db: AsyncSession,
        *,
        asset_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        resolved = await self._describe(db, await self._get_topic3_risk_asset(db, asset_id))
        return self.get_resolved_sample(resolved, sample_id=sample_id)

    def list_resolved_samples(
        self,
        resolved: ResolvedTopic3RiskAsset,
        *,
        risk_level_id: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        asset = resolved.asset
        _require_artifact_dir(asset)
        index = _load_asset_index(asset)
        filtered = _filter_rows(
            index["rows"],
            risk_level_id=risk_level_id,
            category=category,
            keyword=keyword,
            allowed_levels=index["allowed_levels"],
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        page = filtered[safe_offset : safe_offset + safe_limit]
        return {
            **resolved.identity(),
            "total": len(filtered),
            "limit": safe_limit,
            "offset": safe_offset,
            "samples": [_to_list_item(asset.asset_id, item) for item in page],
        }

    def get_resolved_sample(
        self,
        resolved: ResolvedTopic3RiskAsset,
        *,
        sample_id: str,
    ) -> dict[str, Any]:
        asset = resolved.asset
        _require_artifact_dir(asset)
        item = _load_asset_index(asset)["by_sample_id"].get(sample_id)
        if item is not None:
            return {**_to_detail_item(asset.asset_id, item), **resolved.identity()}
        raise BenchmarkTopic3RiskSampleNotFoundError("sample not found")

    def summarize_resolved_asset(
        self, resolved: ResolvedTopic3RiskAsset
    ) -> dict[str, Any]:
        """Sample count and distributions for the selected asset version.

        Historical manifests recorded the distributions at import time and stay
        authoritative. Published v7+ manifests only declare ``sample_count``;
        their distributions are derived from the same samples file the detail
        API reads, so data and results stay bound to one asset hash.
        """
        manifest = loads_json_object(resolved.asset.manifest_json)
        risk_levels = _manifest_counts(manifest.get("risk_level_distribution"))
        languages = _manifest_counts(manifest.get("language_distribution"))
        cultures = _manifest_counts(manifest.get("culture_distribution"))
        categories = _manifest_counts(manifest.get("category_distribution"))
        sample_count = _manifest_int(manifest.get("sample_count"))
        safe_count = _manifest_int(manifest.get("safe_total"))
        risk_count = _manifest_int(manifest.get("risk_total"))

        if (
            not risk_levels
            or not languages
            or not cultures
            or not categories
            or sample_count is None
        ):
            _require_artifact_dir(resolved.asset)
            rows = _load_asset_index(resolved.asset)["rows"]
            derived_levels, derived_languages, derived_cultures, derived_categories = (
                _row_distributions(rows)
            )
            risk_levels = risk_levels or derived_levels
            languages = languages or derived_languages
            cultures = cultures or derived_cultures
            categories = categories or derived_categories
            if sample_count is None:
                sample_count = len(rows)

        if safe_count is None:
            safe_count = risk_levels.get("safe", 0)
        if risk_count is None:
            risk_count = max(sample_count - safe_count, 0)

        return {
            "sample_count": sample_count,
            "safe_count": safe_count,
            "risk_count": risk_count,
            "risk_level_distribution": risk_levels,
            "language_distribution": languages,
            "culture_distribution": cultures,
            "category_distribution": categories,
        }

    async def _describe(
        self, db: AsyncSession, asset: BenchmarkAsset
    ) -> ResolvedTopic3RiskAsset:
        try:
            return await describe_asset(db, asset)
        except BenchmarkTopic3RiskSeriesError as exc:
            raise BenchmarkTopic3RiskSampleError(str(exc)) from exc

    async def _get_topic3_risk_asset(
        self,
        db: AsyncSession,
        asset_id: str,
    ) -> BenchmarkAsset:
        asset = await BenchmarkAssetRegistryService().get_asset(db, asset_id)
        if asset is None:
            raise BenchmarkTopic3RiskSampleNotFoundError("asset not found")
        manifest = loads_json_object(asset.manifest_json)
        if manifest.get("benchmark_type") != BENCHMARK_TYPE:
            raise BenchmarkTopic3RiskSampleError(
                "asset is not a topic3 dynamic risk benchmark asset"
            )
        return asset


def _require_artifact_dir(asset: BenchmarkAsset) -> None:
    if not Path(asset.artifact_dir).is_dir():
        raise BenchmarkTopic3RiskSampleError("asset artifact directory not found")


def _load_asset_index(asset: BenchmarkAsset) -> dict[str, Any]:
    manifest = loads_json_object(asset.manifest_json)
    return _load_asset_index_cached(
        asset.asset_id,
        asset.artifact_sha256,
        asset.artifact_dir,
        _samples_file_name(manifest) if is_series_manifest(manifest) else None,
    )


@lru_cache(maxsize=32)
def _load_asset_index_cached(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir_value: str,
    samples_file: str | None,
) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir_value)
    if samples_file is not None:
        return _load_samples_file_index(asset_id, artifact_sha256, artifact_dir, samples_file)
    rows: list[dict[str, Any]] = []
    by_sample_id: dict[str, dict[str, Any]] = {}
    for level, filenames in RISK_LEVEL_FILES.items():
        path = _first_existing_level_file(artifact_dir, filenames)
        if path is None:
            raise BenchmarkTopic3RiskSampleError(
                f"asset is missing {' or '.join(filenames)}"
            )
        filename = path.name
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkTopic3RiskSampleError(
                    f"{filename}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(row, dict):
                raise BenchmarkTopic3RiskSampleError(
                    f"{filename}:{line_number} must contain a JSON object"
                )
            row["_level_file"] = level
            row["_line_number"] = line_number
            row["sample_id"] = f"{level}:{line_number}"
            row["risk_category_code"] = _risk_category_code(row.get("risk_category"))
            rows.append(row)
            by_sample_id[str(row["sample_id"])] = row
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "rows": tuple(rows),
        "by_sample_id": by_sample_id,
        "allowed_levels": ("safe", "low"),
    }


def _samples_file_name(manifest: dict[str, Any]) -> str:
    files = manifest.get("files")
    declared = files.get("samples") if isinstance(files, dict) else None
    return str(declared) if isinstance(declared, str) and declared else V6_SAMPLES_FILE


def _load_samples_file_index(
    asset_id: str,
    artifact_sha256: str,
    artifact_dir: Path,
    samples_file: str,
) -> dict[str, Any]:
    path = artifact_dir / samples_file
    if not path.is_file():
        raise BenchmarkTopic3RiskSampleError(f"asset is missing {samples_file}")
    rows: list[dict[str, Any]] = []
    by_sample_id: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic3RiskSampleError(
                f"{samples_file}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic3RiskSampleError(
                f"{samples_file}:{line_number} must contain a JSON object"
            )
        sample_id = str(row.get("sample_id") or row.get("index") or line_number)
        row["sample_id"] = sample_id
        row["_line_number"] = line_number
        row["risk_category_code"] = str(
            row.get("risk_category_code") or _risk_category_codes(row.get("risk_category"))
        )
        rows.append(row)
        by_sample_id[sample_id] = row
    return {
        "asset_id": asset_id,
        "artifact_sha256": artifact_sha256,
        "rows": tuple(rows),
        "by_sample_id": by_sample_id,
        "allowed_levels": ("safe", "low", "medium", "high"),
    }


def _first_existing_level_file(artifact_dir: Path, filenames: tuple[str, ...]) -> Path | None:
    for name in filenames:
        for candidate in (artifact_dir / name, artifact_dir / "raw" / name):
            if candidate.is_file():
                return candidate
    return None


def _manifest_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts = {
        str(key): count
        for key, count in value.items()
        if isinstance(count, int) and not isinstance(count, bool)
    }
    return dict(sorted(counts.items()))


def _manifest_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _row_distributions(
    rows: tuple[dict[str, Any], ...],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    levels: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    cultures: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for row in rows:
        level = str(row.get("risk_level_id") or "").strip()
        if not level and str(row.get("response_safetype") or "") == "safe":
            level = "safe"
        if level:
            levels[level] += 1
        language = str(row.get("language") or "").strip()
        if language:
            languages[language] += 1
        culture = str(row.get("culture") or "").strip()
        if culture:
            cultures[culture] += 1
        for code in str(row.get("risk_category_code") or "").split(","):
            normalized = code.strip()
            if normalized:
                categories[normalized] += 1
    return (
        dict(sorted(levels.items())),
        dict(sorted(languages.items())),
        dict(sorted(cultures.items())),
        dict(sorted(categories.items())),
    )


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    risk_level_id: str | None,
    category: str | None,
    keyword: str | None,
    allowed_levels: tuple[str, ...] = ("safe", "low"),
) -> list[dict[str, Any]]:
    normalized_level = _normalize_level(risk_level_id, allowed_levels)
    normalized_category = _normalize_category(category)
    normalized_keyword = keyword.strip().lower() if keyword and keyword.strip() else None
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if normalized_level and row.get("risk_level_id") != normalized_level:
            continue
        if normalized_category and normalized_category not in str(
            row.get("risk_category_code", "")
        ).split(","):
            continue
        if normalized_keyword and not _row_contains_keyword(row, normalized_keyword):
            continue
        filtered.append(row)
    return filtered


def _normalize_level(
    value: str | None,
    allowed_levels: tuple[str, ...] = ("safe", "low"),
) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if normalized not in allowed_levels:
        if allowed_levels == ("safe", "low"):
            raise BenchmarkTopic3RiskSampleError("risk_level_id must be safe or low")
        raise BenchmarkTopic3RiskSampleError(
            "risk_level_id must be safe, low, medium or high"
        )
    return normalized


def _normalize_category(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().upper()
    if not re.fullmatch(r"C(0[1-9]|1[0-7])", normalized):
        raise BenchmarkTopic3RiskSampleError("category must be C01-C17")
    return normalized


def _row_contains_keyword(row: dict[str, Any], keyword: str) -> bool:
    haystack = "\n".join(
        str(row.get(field, ""))
        for field in ("prompt", "response", "label_reason")
    ).lower()
    return keyword in haystack


def _to_list_item(asset_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": str(row["sample_id"]),
        "asset_id": asset_id,
        "index": row.get("index", ""),
        "culture": str(row.get("culture", "")),
        "language": str(row.get("language", "")),
        "prompt_preview": _preview(row.get("prompt")),
        "response_preview": _preview(row.get("response")),
        "response_safetype": str(row.get("response_safetype", "")),
        "risk_category": str(row.get("risk_category", "")),
        "risk_category_code": str(row.get("risk_category_code", "")),
        "risk_sub_category": str(row.get("risk_sub_category", "")),
        "risk_level_id": str(row.get("risk_level_id", "")),
        "safe_type": str(row.get("safe_type", "")),
        "safe_mode": str(row.get("safe_mode", "")),
        "label_reason_preview": _preview(row.get("label_reason")),
        "response_text_source": str(row.get("response_text_source", "")),
        "source_index": row.get("source_index", ""),
    }


def _to_detail_item(asset_id: str, row: dict[str, Any]) -> dict[str, Any]:
    risk_level_id = str(row.get("risk_level_id", ""))
    assessment = _label_reason_assessment(row)
    return {
        "sample_id": str(row["sample_id"]),
        "asset_id": asset_id,
        "index": row.get("index", ""),
        "version": str(row.get("version", "")),
        "culture": str(row.get("culture", "")),
        "language": str(row.get("language", "")),
        "prompt": str(row.get("prompt", "")),
        "response": str(row.get("response", "")),
        "response_safetype": str(row.get("response_safetype", "")),
        "risk_category": str(row.get("risk_category", "")),
        "risk_category_code": str(row.get("risk_category_code", "")),
        "risk_sub_category": str(row.get("risk_sub_category", "")),
        "risk_level_id": risk_level_id,
        "label_source": str(row.get("label_source", "")),
        "response_text_original": str(row.get("response_text_original", "")),
        "response_text_source": str(row.get("response_text_source", "")),
        "source_index": row.get("source_index", ""),
        "source_sample_id": str(row.get("source_sample_id") or ""),
        "locale": str(row.get("locale") or ""),
        "is_translation": str(row.get("is_translation") or ""),
        "safe_type": str(row.get("safe_type", "")),
        "safe_mode": str(row.get("safe_mode", "")),
        "label_reason": str(row.get("label_reason", "")),
        "label_reason_status": assessment["label_reason_status"],
        "integrity_warnings": assessment["integrity_warnings"],
        "label_reason_usable_for_automatic_explanation": assessment["usable"],
        "warning_note": LOW_WARNING_NOTE if risk_level_id == "low" else None,
    }


def _label_reason_assessment(row: dict[str, Any]) -> dict[str, Any]:
    """Missing reasons are 「未提供」; category conflicts are not usable for explanation.

    Empty text is missing, not a conflict. A non-empty reason conflicts only when
    ``_reason_aligned_with_categories`` says it shares neither the reference
    category codes nor their titles.
    """
    reason = str(row.get("label_reason") or "").strip()
    codes = [part for part in str(row.get("risk_category_code") or "").split(",") if part]
    if not reason:
        return {
            "label_reason_status": _MISSING_LABEL_REASON,
            "integrity_warnings": [],
            "usable": False,
        }
    if not _reason_is_aligned(reason, codes, _category_titles(codes, row)):
        return {
            "label_reason_status": "已提供",
            "integrity_warnings": [
                {
                    "code": _MISALIGNED_LABEL_REASON,
                    "message": "完整性告警：标注理由与参考类别冲突，不能用于自动治理解释。",
                }
            ],
            "usable": False,
        }
    return {"label_reason_status": "已提供", "integrity_warnings": [], "usable": True}


def _category_titles(codes: list[str], row: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for code in codes:
        title = _TAXONOMY_TITLES.get(code)
        if not title:
            continue
        titles.append(title)
        head = title.split("、")[0].strip()
        if head and head != title:
            titles.append(head)
    category = str(row.get("risk_category") or "").strip()
    if len(category) >= 2:
        titles.append(category)
    return titles


def _reason_is_aligned(reason: str, codes: list[str], titles: list[str]) -> bool:
    # Imported lazily: the review service imports the risk adapter, which imports
    # this module. The alignment rule itself stays in one place.
    from app.services.governance_risk_review_service import _reason_aligned_with_categories

    return _reason_aligned_with_categories(reason, codes, titles)


def _preview(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _risk_category_code(value: Any) -> str:
    match = re.search(r"C(0[1-9]|1[0-7])\b", str(value or ""))
    return match.group(0) if match else ""


def _risk_category_codes(value: Any) -> str:
    return ",".join(
        sorted({f"C{code}" for code in re.findall(r"C(0[1-9]|1[0-7])", str(value or ""))})
    )
