"""Input value-track services: asset status, screening dimensions, assessment."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.data_input import (
    AttributionRow,
    AttributionStatItem,
    IntegrationEndpoint,
    ValueQaAssetStatusResponse,
    ValueQaDimensionItem,
    ValueQaDimensionsResponse,
    ValueAssessmentResponse,
)
from app.services.benchmark_topic1_value_qa_sample_service import (
    BenchmarkTopic1ValueQaSampleError,
    BenchmarkTopic1ValueQaSampleNotFoundError,
    BenchmarkTopic1ValueQaSampleService,
)
from app.services.data_input_value_attribution_service import rows_from_group
from app.services.data_input_value_qa_common import (
    IMPORT_NEXT_ACTION,
    VALUE_LEVEL_DISPLAY,
    loads_json_object,
    manifest_distribution,
    resolve_value_qa_asset,
)

TOPIC1_VALUE_TRACK_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/api/data-input/value-qa/status",
        purpose="查询课题一 value_qa 资产连通与摘要状态。",
    ),
    IntegrationEndpoint(
        method="GET",
        path="/api/data-input/value-qa/dimensions",
        purpose="读取 value_qa 一/二级维度，供输入价值轨筛选。",
    ),
    IntegrationEndpoint(
        method="GET",
        path="/api/data-input/value-qa/assessment",
        purpose="基于 value_qa 资产生成输入价值评估统计与样本行。",
    ),
]


async def get_value_qa_asset_status(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
) -> ValueQaAssetStatusResponse:
    asset = await resolve_value_qa_asset(db, asset_id=asset_id)
    if asset is None:
        return ValueQaAssetStatusResponse(
            connected=False,
            service="课题一 value_qa 价值评测语料",
            message="尚未导入课题一 value_qa 预跑资产。",
            source="topic1_value_qa",
            blocking_reason="Benchmark 资产库中没有可用的 value_qa 资产。",
            next_action=IMPORT_NEXT_ACTION,
            endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        )

    manifest = loads_json_object(asset.manifest_json)
    quality = manifest_distribution(manifest, "quality_level_distribution")
    primary = manifest_distribution(manifest, "primary_dimension_distribution")
    secondary = manifest_distribution(manifest, "secondary_dimension_distribution")
    return ValueQaAssetStatusResponse(
        connected=True,
        service="课题一 value_qa 价值评测语料",
        message=f"已连接课题一 value_qa 资产：{asset.name}",
        source="topic1_value_qa",
        next_action="可载入筛选维度、评估样本、归因证据链与待提升修正建议。",
        endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        total=int(manifest.get("sample_count") or sum(quality.values()) or 0),
        group_count=int(manifest.get("group_count") or 0),
        qc_status=str(manifest.get("qc_status") or "not_imported"),
        trace_status=str(manifest.get("trace_status") or "not_imported"),
        quality_level_distribution=quality,
        primary_dimension_distribution=primary,
        secondary_dimension_distribution=secondary,
    )


async def list_value_qa_dimensions(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
) -> ValueQaDimensionsResponse:
    asset = await resolve_value_qa_asset(db, asset_id=asset_id)
    if asset is None:
        return ValueQaDimensionsResponse(
            connected=False,
            service="课题一 value_qa 维度筛选",
            message="尚未导入课题一 value_qa 预跑资产，无法加载价值维度。",
            source="topic1_value_qa",
            blocking_reason="Benchmark 资产库中没有可用的 value_qa 资产。",
            next_action=IMPORT_NEXT_ACTION,
            endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        )

    manifest = loads_json_object(asset.manifest_json)
    primary = manifest_distribution(manifest, "primary_dimension_distribution")
    secondary = manifest_distribution(manifest, "secondary_dimension_distribution")

    if not primary and not secondary:
        primary, secondary = await _aggregate_dimensions_from_groups(db, asset.asset_id)

    dimensions = [
        *[
            ValueQaDimensionItem(name=name, kind="primary", count=count)
            for name, count in sorted(primary.items(), key=lambda item: (-item[1], item[0]))
        ],
        *[
            ValueQaDimensionItem(name=name, kind="secondary", count=count)
            for name, count in sorted(secondary.items(), key=lambda item: (-item[1], item[0]))
        ],
    ]
    return ValueQaDimensionsResponse(
        connected=True,
        service="课题一 value_qa 维度筛选",
        message=f"已从资产「{asset.name}」加载 {len(dimensions)} 个价值维度。",
        source="topic1_value_qa",
        next_action="请在标准体系筛选页勾选本批次关注的价值维度。",
        endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        dimensions=dimensions,
    )


async def build_value_assessment(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
    primary_dimensions: list[str] | None = None,
    secondary_dimensions: list[str] | None = None,
    limit: int = 24,
) -> ValueAssessmentResponse:
    asset = await resolve_value_qa_asset(db, asset_id=asset_id)
    if asset is None:
        return ValueAssessmentResponse(
            connected=False,
            service="课题一 value_qa 价值评估",
            message="尚未导入课题一 value_qa 预跑资产，无法生成价值评估。",
            source="topic1_value_qa",
            blocking_reason="Benchmark 资产库中没有可用的 value_qa 资产。",
            next_action=IMPORT_NEXT_ACTION,
            endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        )

    sample_service = BenchmarkTopic1ValueQaSampleService()
    primary_filter = _first_or_none(primary_dimensions)
    secondary_filter = _first_or_none(secondary_dimensions)
    try:
        listed = await sample_service.list_groups(
            db,
            asset_id=asset.asset_id,
            primary_dimension=primary_filter,
            secondary_dimension=secondary_filter,
            limit=max(1, min(limit, 50)),
            offset=0,
        )
    except (BenchmarkTopic1ValueQaSampleError, BenchmarkTopic1ValueQaSampleNotFoundError) as exc:
        return ValueAssessmentResponse(
            connected=False,
            service="课题一 value_qa 价值评估",
            message=str(exc),
            source="topic1_value_qa",
            asset_id=asset.asset_id,
            asset_name=asset.name,
            blocking_reason="value_qa 样本分组加载失败。",
            next_action="请检查资产 samples.jsonl / group_preview.jsonl。",
            endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        )

    rows: list[AttributionRow] = []
    for group_item in listed.get("groups", []):
        if primary_dimensions and len(primary_dimensions) > 1:
            if str(group_item.get("primary_dimension") or "") not in set(primary_dimensions):
                continue
        if secondary_dimensions and len(secondary_dimensions) > 1:
            if str(group_item.get("secondary_dimension") or "") not in set(secondary_dimensions):
                continue
        group_id = str(group_item.get("group_id") or "")
        try:
            detail = await sample_service.get_group(
                db,
                asset_id=asset.asset_id,
                group_id=group_id,
            )
        except BenchmarkTopic1ValueQaSampleError:
            continue
        rows.extend(rows_from_group(detail, prefer_low=False))

    manifest = loads_json_object(asset.manifest_json)
    quality = manifest_distribution(manifest, "quality_level_distribution")
    excellent = quality.get("high", sum(1 for row in rows if row.quality_level == "high"))
    good = quality.get("medium", sum(1 for row in rows if row.quality_level == "medium"))
    needs = quality.get("low", sum(1 for row in rows if row.quality_level == "low"))
    group_count = int(manifest.get("group_count") or listed.get("total") or 0)

    radar_scores = _radar_scores_from_rows(rows)
    fixes = [row for row in rows if row.quality_level == "low" or row.status == "待提升"]

    return ValueAssessmentResponse(
        connected=True,
        service="课题一 value_qa 价值评估",
        message=f"已基于资产「{asset.name}」生成价值评估样本与统计。",
        source="topic1_value_qa",
        next_action="可进入归因页查看证据链，或进入修正页处理待提升样本。",
        endpoints=TOPIC1_VALUE_TRACK_ENDPOINTS,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        total=len(rows),
        group_count=group_count,
        stats=[
            AttributionStatItem(val=str(group_count), label="价值三联组"),
            AttributionStatItem(val=str(excellent), label="优档样本"),
            AttributionStatItem(val=str(good), label="良档样本"),
            AttributionStatItem(val=str(needs), label="待提升样本"),
        ],
        rows=rows,
        fix_rows=fixes,
        radar_scores=radar_scores,
        quality_level_distribution={
            VALUE_LEVEL_DISPLAY["high"]: excellent,
            VALUE_LEVEL_DISPLAY["medium"]: good,
            VALUE_LEVEL_DISPLAY["low"]: needs,
        },
    )


async def _aggregate_dimensions_from_groups(
    db: AsyncSession,
    asset_id: str,
) -> tuple[dict[str, int], dict[str, int]]:
    sample_service = BenchmarkTopic1ValueQaSampleService()
    try:
        listed = await sample_service.list_groups(db, asset_id=asset_id, limit=100, offset=0)
    except BenchmarkTopic1ValueQaSampleError:
        return {}, {}
    primary: dict[str, int] = {}
    secondary: dict[str, int] = {}
    for group in listed.get("groups", []):
        p = str(group.get("primary_dimension") or "").strip()
        s = str(group.get("secondary_dimension") or "").strip()
        if p:
            primary[p] = primary.get(p, 0) + 1
        if s:
            secondary[s] = secondary.get(s, 0) + 1
    return primary, secondary


def _radar_scores_from_rows(rows: list[AttributionRow]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    score_map = {"优": 0.92, "良": 0.74, "待提升": 0.42}
    for row in rows:
        dim = (row.dimension or "").split(" / ")[-1].strip() or row.dimension or "价值达成"
        buckets.setdefault(dim, []).append(score_map.get(row.status, 0.5))
    return {
        name: round(sum(values) / len(values), 2) if values else 0.5
        for name, values in buckets.items()
    }


def _first_or_none(values: list[str] | None) -> str | None:
    if not values:
        return None
    cleaned = [item.strip() for item in values if item and item.strip()]
    return cleaned[0] if len(cleaned) == 1 else None
