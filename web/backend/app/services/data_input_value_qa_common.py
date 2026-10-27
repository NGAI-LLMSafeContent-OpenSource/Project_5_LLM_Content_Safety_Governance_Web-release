"""Shared helpers for Topic 1 value_qa assets used by input value track."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService

PREFERRED_VALUE_QA_ASSET_IDS = (
    "topic1_value_qa_marked_merged_round3",
    "topic1_value_qa_risk_cause_demo0606",
)

OFFICIAL_VALUE_QA_ASSET_ID = PREFERRED_VALUE_QA_ASSET_IDS[0]
DEMO_VALUE_QA_ASSET_ID = PREFERRED_VALUE_QA_ASSET_IDS[1]
OFFICIAL_VALUE_QA_ASSET_NAME = "Topic1 value_qa marked merged with round3 QC"
DEMO_VALUE_QA_ASSET_NAME = "Topic1 value_qa from Risk Cause DEMO-0606"

VALUE_LEVEL_DISPLAY = {
    "high": "优",
    "medium": "良",
    "low": "待提升",
}
VALUE_LEVEL_SCORE = {
    "high": "0.92",
    "medium": "0.74",
    "low": "0.42",
}

IMPORT_NEXT_ACTION = (
    "请先导入课题一 value_qa 资产。在课题五仓库执行："
    "node scripts/import-topic1-value-qa-asset.mjs --path-style windows"
    "（优先读取 web/backend/data/input_corpora/value_qa；"
    "其次 Project_1_Sample_evaluation_Generation；"
    "再回退 Project_1_Risk_Cause_Determination/DEMO-0606）。"
)


async def resolve_value_qa_asset(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
) -> BenchmarkAsset | None:
    registry = BenchmarkAssetRegistryService()
    if asset_id:
        asset = await registry.get_asset(db, asset_id)
        if asset is None:
            return None
        manifest = loads_json_object(asset.manifest_json)
        return asset if manifest.get("benchmark_type") == "value_qa" else None

    for preferred_id in PREFERRED_VALUE_QA_ASSET_IDS:
        asset = await registry.get_asset(db, preferred_id)
        if asset is None:
            continue
        manifest = loads_json_object(asset.manifest_json)
        if manifest.get("benchmark_type") == "value_qa":
            return asset

    candidates: list[tuple[int, BenchmarkAsset]] = []
    for source_mode in ("prerun_snapshot", None):
        assets = (
            await registry.list_assets(db, source_mode=source_mode)
            if source_mode
            else await registry.list_assets(db)
        )
        for asset in assets:
            manifest = loads_json_object(asset.manifest_json)
            if manifest.get("benchmark_type") != "value_qa":
                continue
            score = 0
            if manifest.get("qc_status") not in (None, "", "not_imported"):
                score += 2
            if manifest.get("trace_status") == "imported":
                score += 1
            candidates.append((score, asset))
        if candidates:
            break
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def manifest_distribution(manifest: dict[str, Any], key: str) -> dict[str, int]:
    raw = manifest.get(key)
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for name, count in raw.items():
        label = str(name).strip()
        if not label:
            continue
        try:
            result[label] = int(count)
        except (TypeError, ValueError):
            result[label] = 0
    return result
