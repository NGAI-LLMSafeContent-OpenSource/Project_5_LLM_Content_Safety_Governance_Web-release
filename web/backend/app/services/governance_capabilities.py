"""Governance capability registry.

Each capability declares its domain, intent key, parameter Schema, result Schema,
capability version and an execution adapter. The assistant model may only select
a capability registered for the active domain; results never come from the model
itself but from registered assets and professional services.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GovernanceMessage
from app.schemas.governance import (
    RISK_REFERENCE_LABELS,
    AssetSourceRef,
    CbrneDatasetDiscoverParams,
    CbrneDatasetDiscoverResult,
    CbrneDatasetFullTextParams,
    CbrneDatasetFullTextResult,
    CbrneDatasetOverviewParams,
    CbrneDatasetOverviewResult,
    CbrneDatasetSearchParams,
    CbrneDatasetSearchResult,
    CulturalSystemRecordDetailParams,
    CulturalSystemRecordDetailResult,
    CulturalSystemRecordSearchParams,
    CulturalSystemRecordSearchResult,
    RiskCorpusOverviewParams,
    RiskCorpusOverviewResult,
    RiskCorpusRescanParams,
    RiskCorpusRescanPreviewResult,
    RiskCorpusRescanRunResult,
    RiskCorpusSearchParams,
    RiskCorpusSearchResult,
    RiskSystemRecordDetailParams,
    RiskSystemRecordDetailResult,
    RiskSystemRecordSearchParams,
    RiskSystemRecordSearchResult,
    Topic1CorpusToolCatalogParams,
    ValueCorpusOverviewParams,
    ValueCorpusOverviewResult,
    ValueQaGroupDetailParams,
    ValueQaGroupDetailResult,
    ValueQaSearchParams,
    ValueQaSearchResult,
)
from app.schemas.topic1_corpus_tools import Topic1CorpusToolCatalogResult
from app.services.benchmark_topic1_value_qa_sample_service import (
    BenchmarkTopic1ValueQaSampleError,
    BenchmarkTopic1ValueQaSampleNotFoundError,
    BenchmarkTopic1ValueQaSampleService,
)
from app.services.data_input_corpus_catalog_service import (
    RISK_STATIC_ASSET_ID,
    RISK_STATIC_ASSET_NAME,
    list_risk_static_records,
    risk_static_overview,
)
from app.services.data_input_value_qa_common import (
    loads_json_object,
    manifest_distribution,
    resolve_value_qa_asset,
)
from app.services.governance_cbrne_dataset_service import (
    build_cbrne_dataset_overview,
    list_cbrne_dataset_assets,
    refuse_cbrne_full_text,
    search_cbrne_dataset_samples,
    GovernanceCbrneDatasetError,
    GovernanceCbrneDatasetNotFoundError,
)
from app.services.governance_risk_rescan_service import resolve_rescan_scope
from app.services.governance_system_record_service import (
    STATUS_ALIASES,
    build_cultural_system_record_detail,
    build_risk_system_record_detail,
    get_cultural_system_record_asset,
    get_risk_system_record_asset,
    list_cultural_system_records,
    list_risk_system_records,
)
from app.services.topic1_corpus_tool_service import (
    Topic1CorpusToolCatalogError,
    load_topic1_corpus_tool_catalog,
    unavailable_topic1_corpus_tool_catalog,
)

VALUE_QA_FILTER_KEYS = (
    "keyword",
    "topic",
    "primary_dimension",
    "secondary_dimension",
)

SYSTEM_RECORD_FILTER_KEYS = (
    "source",
    "status",
    "asset_version",
    "completed_after",
    "completed_before",
)

CULTURAL_SYSTEM_RECORD_FILTER_KEYS = (
    "source",
    "status",
    "completed_after",
    "completed_before",
    "difficulty_level",
    "ethnic_group",
    "background_type",
    "query_type",
)

RISK_FILTER_KEYS = (
    "keyword",
    "reference_label",
    "source",
    "harm_category_L1",
    "harm_category_L2",
)

CBRNE_FILTER_KEYS = (
    "asset_id",
    "label",
    "cbrne_category",
    "source",
    "exposure_tier",
    "difficulty_min",
    "difficulty_max",
)


@dataclass(frozen=True)
class CapabilityContext:
    """Server-owned execution context. Never populated from model parameters,
    so a capability cannot be pointed at another session's records."""

    session_id: str
    client_id: str


@dataclass(frozen=True)
class CapabilityResult:
    payload: dict
    content: str


def _value_qa_source_refs(asset) -> list[AssetSourceRef]:
    return [
        AssetSourceRef(
            ref_id=asset.asset_id,
            name=asset.name,
            source_repo=asset.source_repo,
            source_commit=asset.source_commit,
        )
    ]


async def _aggregate_dimensions_from_groups(
    db: AsyncSession, asset_id: str
) -> tuple[dict[str, int], dict[str, int]]:
    try:
        listed = await BenchmarkTopic1ValueQaSampleService().list_groups(
            db, asset_id=asset_id, limit=100, offset=0
        )
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


async def _run_value_corpus_overview(
    db: AsyncSession, _ctx: CapabilityContext, params: ValueCorpusOverviewParams
) -> CapabilityResult:
    asset = await resolve_value_qa_asset(db, asset_id=params.asset_id)
    if asset is None:
        result = ValueCorpusOverviewResult(source="topic1_value_qa", available=False)
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    manifest = loads_json_object(asset.manifest_json)
    quality = manifest_distribution(manifest, "quality_level_distribution")
    primary = manifest_distribution(manifest, "primary_dimension_distribution")
    secondary = manifest_distribution(manifest, "secondary_dimension_distribution")
    if not primary and not secondary:
        primary, secondary = await _aggregate_dimensions_from_groups(db, asset.asset_id)
    result = ValueCorpusOverviewResult(
        source="topic1_value_qa",
        available=True,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        sample_count=int(manifest.get("sample_count") or sum(quality.values()) or 0),
        group_count=int(manifest.get("group_count") or 0),
        quality_level_distribution=quality,
        primary_dimension_distribution=primary,
        secondary_dimension_distribution=secondary,
        source_refs=_value_qa_source_refs(asset),
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_topic1_corpus_tool_catalog(
    db: AsyncSession,
    _ctx: CapabilityContext,
    _params: Topic1CorpusToolCatalogParams,
) -> CapabilityResult:
    del db
    try:
        result: Topic1CorpusToolCatalogResult = load_topic1_corpus_tool_catalog()
    except Topic1CorpusToolCatalogError:
        result = unavailable_topic1_corpus_tool_catalog()
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_value_qa_search(
    db: AsyncSession, ctx: CapabilityContext, params: ValueQaSearchParams
) -> CapabilityResult:
    asset = await resolve_value_qa_asset(db)
    if asset is None:
        result = ValueQaSearchResult(available=False)
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    filters = {
        key: value
        for key in VALUE_QA_FILTER_KEYS
        if (value := getattr(params, key))
    }
    offset = params.offset
    if params.continuation:
        previous = await _latest_snapshot_payload(db, ctx.session_id, "value_qa_search")
        filters, continued_offset = _continuation_scope(
            previous, filters, VALUE_QA_FILTER_KEYS
        )
        if continued_offset is not None:
            offset = continued_offset

    try:
        listed = await BenchmarkTopic1ValueQaSampleService().list_group_details(
            db,
            asset_id=asset.asset_id,
            keyword=filters.get("keyword"),
            topic=filters.get("topic"),
            primary_dimension=filters.get("primary_dimension"),
            secondary_dimension=filters.get("secondary_dimension"),
            limit=params.limit,
            offset=offset,
        )
    except BenchmarkTopic1ValueQaSampleError:
        result = ValueQaSearchResult(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            filters=filters,
            source_refs=_value_qa_source_refs(asset),
        )
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    result = ValueQaSearchResult(
        available=True,
        asset_id=listed["asset_id"],
        asset_name=asset.name,
        total=listed["total"],
        offset=listed["offset"],
        limit=listed["limit"],
        filters=filters,
        group_ids=listed["group_ids"],
        groups=listed["groups"],
        source_refs=_value_qa_source_refs(asset),
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_value_qa_group_detail(
    db: AsyncSession, _ctx: CapabilityContext, params: ValueQaGroupDetailParams
) -> CapabilityResult:
    asset = await resolve_value_qa_asset(db)
    service = BenchmarkTopic1ValueQaSampleService()
    if asset is None:
        result = ValueQaGroupDetailResult(group_id=params.group_id, available=False)
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    try:
        detail = await service.get_group(
            db, asset_id=asset.asset_id, group_id=params.group_id
        )
    except (BenchmarkTopic1ValueQaSampleError, BenchmarkTopic1ValueQaSampleNotFoundError):
        result = ValueQaGroupDetailResult(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            group_id=params.group_id,
            available=False,
        )
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    try:
        listed = await service.list_groups(db, asset_id=asset.asset_id, limit=100, offset=0)
        group_ids = [str(item.get("group_id")) for item in listed.get("groups", [])]
    except BenchmarkTopic1ValueQaSampleError:
        group_ids = [params.group_id]

    try:
        group_index = group_ids.index(str(detail.get("group_id")))
    except ValueError:
        group_index = 0

    result = ValueQaGroupDetailResult(
        available=True,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        group_id=str(detail.get("group_id")),
        topic=str(detail.get("topic") or ""),
        primary_dimension=str(detail.get("primary_dimension") or ""),
        secondary_dimension=str(detail.get("secondary_dimension") or ""),
        levels=detail.get("levels") or {},
        groups=group_ids,
        group_index=group_index,
        source_refs=_value_qa_source_refs(asset),
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


def _risk_source_refs() -> list[AssetSourceRef]:
    return [
        AssetSourceRef(
            ref_type="risk_static_corpus",
            ref_id=RISK_STATIC_ASSET_ID,
            name=RISK_STATIC_ASSET_NAME,
        )
    ]


async def _run_risk_corpus_overview(
    db: AsyncSession, _ctx: CapabilityContext, params: RiskCorpusOverviewParams
) -> CapabilityResult:
    overview = risk_static_overview()
    available = overview["available"]
    result = RiskCorpusOverviewResult(
        available=available,
        asset_id=RISK_STATIC_ASSET_ID if available else None,
        asset_name=RISK_STATIC_ASSET_NAME if available else None,
        sample_count=overview["sample_count"],
        reference_label_distribution=overview["reference_label_distribution"],
        harm_category_L1_distribution=overview["harm_category_L1_distribution"],
        harm_category_L2_distribution=overview["harm_category_L2_distribution"],
        source_distribution=overview["source_distribution"],
        source_refs=_risk_source_refs() if available else [],
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _latest_snapshot_payload(
    db: AsyncSession, session_id: str, kind: str
) -> dict | None:
    """Return the most recent snapshot message of ``kind`` in this session.

    Continuation and version-change detection both reuse exactly what the
    previous executable result returned, so a later page always reproduces the
    same filter scope. The lookup is scoped by server-owned session id, never by
    model-supplied parameters."""
    result = await db.execute(
        select(GovernanceMessage)
        .where(
            GovernanceMessage.session_id == session_id,
            GovernanceMessage.kind == kind,
        )
        .order_by(GovernanceMessage.id.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None
    try:
        payload = json.loads(message.payload_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _continuation_scope(
    previous: dict | None, filters: dict[str, Any], filter_keys: tuple[str, ...]
) -> tuple[dict[str, Any], int | None]:
    """Merge the previous page's filters into this request and advance the
    offset by the previous page size. Returns ``(filters, offset)``; offset is
    ``None`` when there is no previous page to continue from."""
    if not isinstance(previous, dict):
        return filters, None
    inherited = previous.get("filters")
    merged = filters
    if isinstance(inherited, dict):
        merged = {key: value for key, value in inherited.items() if key in filter_keys and value}
        merged.update(filters)
    offset = int(previous.get("offset") or 0) + int(previous.get("limit") or 0)
    return merged, offset


async def _run_risk_corpus_search(
    db: AsyncSession, ctx: CapabilityContext, params: RiskCorpusSearchParams
) -> CapabilityResult:
    filters: dict[str, Any] = {
        key: value for key in RISK_FILTER_KEYS if (value := getattr(params, key))
    }
    offset = params.offset

    if params.continuation:
        previous = await _latest_snapshot_payload(db, ctx.session_id, "risk_corpus_search")
        filters, continued_offset = _continuation_scope(previous, filters, RISK_FILTER_KEYS)
        if continued_offset is not None:
            offset = continued_offset

    listed = list_risk_static_records(
        keyword=filters.get("keyword"),
        reference_label=filters.get("reference_label"),
        source=filters.get("source"),
        harm_category_L1=filters.get("harm_category_L1"),
        harm_category_L2=filters.get("harm_category_L2"),
        limit=params.limit,
        offset=offset,
    )
    available = listed["available"]
    result = RiskCorpusSearchResult(
        available=available,
        asset_id=RISK_STATIC_ASSET_ID if available else None,
        asset_name=RISK_STATIC_ASSET_NAME if available else None,
        total=listed["total"],
        offset=listed["offset"],
        limit=listed["limit"],
        filters=filters,
        records=listed["records"],
        source_refs=_risk_source_refs() if available else [],
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_risk_corpus_rescan_preview(
    db: AsyncSession, _ctx: CapabilityContext, params: RiskCorpusRescanParams
) -> CapabilityResult:
    """Resolve a re-detection request into a frozen scope; never detects.

    The task id is server-owned and injected by the session orchestrator when
    it creates the awaiting-confirmation task; the model can never author it."""
    scope = resolve_rescan_scope(params)
    result = RiskCorpusRescanPreviewResult(**scope)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


def _collect_filters(params: BaseModel, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value for key in keys if (value := getattr(params, key))}
def _system_record_filters(params: RiskSystemRecordSearchParams) -> dict[str, Any]:
    return _collect_filters(params, SYSTEM_RECORD_FILTER_KEYS)


async def _run_risk_system_record_search(
    db: AsyncSession, ctx: CapabilityContext, params: RiskSystemRecordSearchParams
) -> CapabilityResult:
    filters = _system_record_filters(params)
    offset = params.offset

    if params.continuation:
        previous = await _latest_snapshot_payload(
            db, ctx.session_id, "risk_system_record_search"
        )
        filters, continued_offset = _continuation_scope(
            previous, filters, SYSTEM_RECORD_FILTER_KEYS
        )
        if continued_offset is not None:
            offset = continued_offset

    listed = await list_risk_system_records(
        db,
        source=filters.get("source"),
        status=filters.get("status"),
        asset_version=filters.get("asset_version"),
        completed_after=filters.get("completed_after"),
        completed_before=filters.get("completed_before"),
        limit=params.limit,
        offset=offset,
    )
    result = RiskSystemRecordSearchResult(
        available=listed["available"],
        total=listed["total"],
        offset=listed["offset"],
        limit=listed["limit"],
        filters=filters,
        records=listed["records"],
        source_refs=listed["source_refs"],
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


def _previous_record_version(previous: dict | None, record_id: str) -> str | None:
    """Version recorded for this record in the session's own last list snapshot.

    Returns ``None`` when the snapshot does not mention the record or stored no
    version, so unknown provenance is never mistaken for a version change."""
    if not isinstance(previous, dict):
        return None
    records = previous.get("records")
    if not isinstance(records, list):
        return None
    for record in records:
        if isinstance(record, dict) and record.get("record_id") == record_id:
            version = record.get("record_version")
            return str(version) if isinstance(version, str) and version else None
    return None


async def _run_risk_system_record_detail(
    db: AsyncSession, ctx: CapabilityContext, params: RiskSystemRecordDetailParams
) -> CapabilityResult:
    asset = await get_risk_system_record_asset(db, params.record_id)
    if asset is None:
        result = RiskSystemRecordDetailResult(
            available=False,
            source_status="missing",
            record_id=params.record_id,
        )
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    payload = await build_risk_system_record_detail(db, asset)
    previous = await _latest_snapshot_payload(
        db, ctx.session_id, "risk_system_record_search"
    )
    previous_version = _previous_record_version(previous, params.record_id)
    # Version change is derived from this session's own earlier snapshot, so the
    # assistant cannot claim a match (or hide a mismatch) through parameters.
    if previous_version is not None and previous_version != payload["record_version"]:
        payload["source_status"] = "changed"

    result = RiskSystemRecordDetailResult(**payload)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_cultural_system_record_search(
    db: AsyncSession, ctx: CapabilityContext, params: CulturalSystemRecordSearchParams
) -> CapabilityResult:
    filters = _collect_filters(params, CULTURAL_SYSTEM_RECORD_FILTER_KEYS)
    offset = params.offset

    if params.continuation:
        previous = await _latest_snapshot_payload(
            db, ctx.session_id, "cultural_system_record_search"
        )
        filters, continued_offset = _continuation_scope(
            previous, filters, CULTURAL_SYSTEM_RECORD_FILTER_KEYS
        )
        if continued_offset is not None:
            offset = continued_offset

    listed = await list_cultural_system_records(
        db,
        source=filters.get("source"),
        status=filters.get("status"),
        completed_after=filters.get("completed_after"),
        completed_before=filters.get("completed_before"),
        difficulty_level=filters.get("difficulty_level"),
        ethnic_group=filters.get("ethnic_group"),
        background_type=filters.get("background_type"),
        query_type=filters.get("query_type"),
        limit=params.limit,
        offset=offset,
    )
    result = CulturalSystemRecordSearchResult(
        available=listed["available"],
        total=listed["total"],
        offset=listed["offset"],
        limit=listed["limit"],
        filters=filters,
        records=listed["records"],
        source_refs=listed["source_refs"],
    )
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_cultural_system_record_detail(
    db: AsyncSession, ctx: CapabilityContext, params: CulturalSystemRecordDetailParams
) -> CapabilityResult:
    asset = await get_cultural_system_record_asset(db, params.record_id)
    if asset is None:
        result = CulturalSystemRecordDetailResult(
            available=False,
            source_status="missing",
            record_id=params.record_id,
        )
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())

    payload = build_cultural_system_record_detail(asset)
    previous = await _latest_snapshot_payload(
        db, ctx.session_id, "cultural_system_record_search"
    )
    previous_version = _previous_record_version(previous, params.record_id)
    # Same server-derived version-change rule as risk safety: the model never
    # passes a version, so it cannot hide or fake a mismatch.
    if previous_version is not None and previous_version != payload["record_version"]:
        payload["source_status"] = "changed"

    result = CulturalSystemRecordDetailResult(**payload)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_cbrne_dataset_discover(
    db: AsyncSession, _ctx: CapabilityContext, _params: CbrneDatasetDiscoverParams
) -> CapabilityResult:
    listed = await list_cbrne_dataset_assets(db)
    result = CbrneDatasetDiscoverResult(**listed)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_cbrne_dataset_overview(
    db: AsyncSession, _ctx: CapabilityContext, params: CbrneDatasetOverviewParams
) -> CapabilityResult:
    payload = await build_cbrne_dataset_overview(db, asset_id=params.asset_id)
    result = CbrneDatasetOverviewResult(**payload)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


def _cbrne_search_filters(params: CbrneDatasetSearchParams) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key in CBRNE_FILTER_KEYS:
        value = getattr(params, key)
        if value is None or value == "":
            continue
        filters[key] = value
    return filters


async def _run_cbrne_dataset_search(
    db: AsyncSession, ctx: CapabilityContext, params: CbrneDatasetSearchParams
) -> CapabilityResult:
    filters = _cbrne_search_filters(params)
    offset = params.offset
    limit = params.limit

    if params.continuation:
        previous = await _latest_snapshot_payload(
            db, ctx.session_id, "cbrne_dataset_search"
        )
        filters, continued_offset = _continuation_scope(
            previous, filters, CBRNE_FILTER_KEYS
        )
        if continued_offset is not None:
            offset = continued_offset
        if isinstance(previous, dict) and previous.get("limit"):
            try:
                limit = int(previous["limit"])
            except (TypeError, ValueError):
                pass

    try:
        listed = await search_cbrne_dataset_samples(
            db,
            asset_id=filters.get("asset_id"),
            label=filters.get("label"),
            cbrne_category=filters.get("cbrne_category"),
            source=filters.get("source"),
            exposure_tier=filters.get("exposure_tier"),
            difficulty_min=filters.get("difficulty_min"),
            difficulty_max=filters.get("difficulty_max"),
            limit=limit,
            offset=offset,
        )
    except GovernanceCbrneDatasetNotFoundError:
        result = CbrneDatasetSearchResult(available=False)
        return CapabilityResult(payload=result.model_dump(), content=result.render_content())
    except GovernanceCbrneDatasetError as exc:
        # Invalid filters surface as a clear empty/error payload, never mock rows.
        result = CbrneDatasetSearchResult(
            available=True,
            asset_id=filters.get("asset_id"),
            total=0,
            offset=offset,
            limit=limit,
            filters=filters,
            query=filters,
        )
        return CapabilityResult(
            payload=result.model_dump(),
            content=f"CBRNE 筛选无效：{exc}",
        )

    result = CbrneDatasetSearchResult(**listed)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


async def _run_cbrne_dataset_full_text(
    db: AsyncSession, _ctx: CapabilityContext, params: CbrneDatasetFullTextParams
) -> CapabilityResult:
    payload = await refuse_cbrne_full_text(
        db, asset_id=params.asset_id, sample_id=params.sample_id
    )
    result = CbrneDatasetFullTextResult(**payload)
    return CapabilityResult(payload=result.model_dump(), content=result.render_content())


@dataclass(frozen=True)
class CapabilityDef:
    key: str
    domain: str
    label: str
    version: str
    description: str
    params_model: type[BaseModel]
    runner: Callable[
        [AsyncSession, CapabilityContext, BaseModel], Awaitable[CapabilityResult]
    ]
    param_help: dict[str, str] = field(default_factory=dict)
    enumerations: Callable[[], dict[str, list[str]]] | None = None
    # Remote/paid/long-running actions freeze their execution scope and wait for
    # an explicit user confirmation before the runner's side effect may happen.
    requires_confirmation: bool = False
    result_schema: str | None = None
    result_model: type[BaseModel] | None = None


def _system_record_enumerations() -> dict[str, list[str]]:
    """Allowed status values for system prerun records.

    ``source`` values live in the registry, which this prompt-time hook cannot
    query, so only the static status vocabulary is exposed here."""
    return {"status": sorted({*STATUS_ALIASES.values()})}


def _cultural_system_record_enumerations() -> dict[str, list[str]]:
    """Cultural records share the status vocabulary; their business dimensions
    (difficulty/ethnic/background/query type) live in asset manifests and can
    only be discovered from a result, so only ``status`` is enumerated here."""
    return {"status": sorted({*STATUS_ALIASES.values()})}


def _risk_search_enumerations() -> dict[str, list[str]]:
    """Allowed filter values for the static risk pack, sourced from the same
    distributions the overview exposes so the assistant can map a user's wording
    onto exact stored values."""
    overview = risk_static_overview()
    return {
        "reference_label": list(RISK_REFERENCE_LABELS),
        "source": sorted(overview["source_distribution"]),
        "harm_category_L1": sorted(overview["harm_category_L1_distribution"]),
        "harm_category_L2": sorted(overview["harm_category_L2_distribution"]),
    }


CAPABILITIES: tuple[CapabilityDef, ...] = (
    CapabilityDef(
        key="value_corpus_overview",
        domain="input",
        label="查看价值语料构成",
        version="v1",
        description="查询课题一 value_qa 资产的样本总数、三档质量分布与一/二级维度分布。",
        params_model=ValueCorpusOverviewParams,
        runner=_run_value_corpus_overview,
        param_help={
            "asset_id": "指定价值语料资产 ID；通常省略以使用当前优选资产。",
        },
    ),
    CapabilityDef(
        key="topic1_corpus_tool_catalog",
        domain="input",
        label="查看课题一训练语料工具接入状态",
        version="v1",
        description=(
            "查看稀缺度评估、数据去噪、数据去害和数据选择四项输入工具的交付状态、"
            "平台运行状态、数据元信息和下一步；不会把源码已交付误报为在线可执行。"
        ),
        params_model=Topic1CorpusToolCatalogParams,
        runner=_run_topic1_corpus_tool_catalog,
    ),
    CapabilityDef(
        key="value_qa_search",
        domain="input",
        label="检索价值问题组",
        version="v1",
        description=(
            "浏览当前优选资产的价值问题组，或按关键词、主题、价值维度收窄。"
            "筛选字段都可省略；省略时列出全部问题组，并返回高/中/低三档对照与来源。"
            "结果分页返回；用户要求继续、下一页或更多时，设置 continuation=true "
            "复用上一轮筛选并读取下一页。"
        ),
        params_model=ValueQaSearchParams,
        runner=_run_value_qa_search,
        param_help={
            "keyword": "可选。匹配组 ID、主题、价值维度、问题与回答。省略则不按关键词收窄。",
            "topic": "可选。主题精确匹配。省略则不按主题收窄。",
            "primary_dimension": "可选。一级价值维度精确匹配。省略则不按该维度收窄。",
            "secondary_dimension": "可选。二级价值维度精确匹配。省略则不按该维度收窄。",
            "limit": "单页返回组数。",
            "offset": "起始偏移；翻页请优先使用 continuation。",
            "continuation": "true 表示沿用上一轮筛选并读取下一页。",
        },
    ),
    CapabilityDef(
        key="value_qa_group_detail",
        domain="input",
        label="打开指定价值问题组",
        version="v1",
        description=(
            "仅当用户给出价值问题组 ID 时打开该组，查看高/中/低三档答疑与来源依据。"
            "没有组 ID 时使用 value_qa_search。"
        ),
        params_model=ValueQaGroupDetailParams,
        runner=_run_value_qa_group_detail,
        param_help={"group_id": "要打开的价值问题组 ID。"},
    ),
    CapabilityDef(
        key="cbrne_dataset_discover",
        domain="input",
        label="发现课题二 CBRNE 异常数据资产",
        version="v1",
        description=(
            "列出已登记的课题二 CBRNE 异常数据资产（dataset_snapshot / anomaly_seedbank），"
            "标明当前版本、样本规模与稳定 Benchmark 跳转；只读，不创建评测任务。"
        ),
        params_model=CbrneDatasetDiscoverParams,
        runner=_run_cbrne_dataset_discover,
    ),
    CapabilityDef(
        key="cbrne_dataset_overview",
        domain="input",
        label="查看 CBRNE 资产总览与分布",
        version="v1",
        description=(
            "查看登记的 CBRNE 异常数据资产规模与标签、类别、来源、T1–T4、"
            "评估器相对难度分布；默认使用当前版本，可指定 asset_id。"
        ),
        params_model=CbrneDatasetOverviewParams,
        runner=_run_cbrne_dataset_overview,
        param_help={
            "asset_id": "可选。指定资产 ID；省略则使用当前标记版本。",
        },
    ),
    CapabilityDef(
        key="cbrne_dataset_search",
        domain="input",
        label="筛选 CBRNE 样本摘要",
        version="v1",
        description=(
            "按标签、CBRNE 类别、来源、T1–T4 与评估器相对难度范围筛选脱敏摘要，"
            "稳定分页返回命中数与 Benchmark 跳转；从不返回全文，也不提供评测执行入口。"
            "用户要求继续、下一页或更多时，设置 continuation=true 复用上一轮筛选并读取下一页。"
        ),
        params_model=CbrneDatasetSearchParams,
        runner=_run_cbrne_dataset_search,
        param_help={
            "asset_id": "可选。指定资产 ID；省略则使用当前标记版本。",
            "label": "可选。safe 或 unsafe。",
            "cbrne_category": "可选。CBRNE 二级类别精确匹配。",
            "source": "可选。样本来源精确匹配。",
            "exposure_tier": "可选。T1–T4 暴露层级。",
            "difficulty_min": "可选。评估器相对难度下界（含）。",
            "difficulty_max": "可选。评估器相对难度上界（含）。",
            "limit": "单页返回条数。",
            "offset": "起始偏移；翻页请优先使用 continuation。",
            "continuation": "true 表示沿用上一轮筛选并读取下一页。",
        },
    ),
    CapabilityDef(
        key="cbrne_dataset_full_text",
        domain="input",
        label="CBRNE 全文披露说明",
        version="v1",
        description=(
            "当用户在治理会话中要求 CBRNE 样本全文时调用："
            "返回披露说明与 Benchmark 受控详情跳转，绝不把全文写入会话消息。"
        ),
        params_model=CbrneDatasetFullTextParams,
        runner=_run_cbrne_dataset_full_text,
        param_help={
            "asset_id": "可选。资产 ID；省略则使用当前标记版本。",
            "sample_id": "要查看全文的样本 ID。",
        },
    ),
    CapabilityDef(
        key="risk_corpus_overview",
        domain="input",
        label="查看风险语料构成",
        version="v1",
        description="查询课题二静态风险语料的样本总数、参考标注分布、风险分类与来源分布。",
        params_model=RiskCorpusOverviewParams,
        runner=_run_risk_corpus_overview,
    ),
    CapabilityDef(
        key="risk_corpus_search",
        domain="input",
        label="浏览与筛选风险样本",
        version="v1",
        description=(
            "按关键词、参考标注、来源及 L1/L2 风险分类筛选风险样本，展示样本文本与来源；"
            "分页返回，可用 limit/offset 翻页。"
            "用户要求继续、下一页或更多时，设置 continuation=true 复用上一轮筛选并读取下一页。"
        ),
        params_model=RiskCorpusSearchParams,
        runner=_run_risk_corpus_search,
        param_help={
            "keyword": "匹配样本文本与样本 ID。",
            "reference_label": "来源参考标注，只读事实，不是本次检测结论。",
            "source": "样本来源数据集。",
            "harm_category_L1": "一级风险分类。",
            "harm_category_L2": "二级风险分类。",
            "limit": "单页返回条数。",
            "offset": "起始偏移，用于翻页；翻页请优先使用 continuation。",
            "continuation": "true 表示沿用上一轮筛选并读取下一页。",
        },
        enumerations=_risk_search_enumerations,
    ),
    CapabilityDef(
        key="risk_corpus_rescan",
        domain="input",
        label="输入风险语料在线二次检测",
        version="v2",
        description=(
            "把检测请求解析为明确的样本集合和数量（数据来源、筛选范围、实际条数），"
            "并冻结资产内容哈希与 internal_validation 披露；先展示执行范围并等待确认；"
            "确认后才调用课题二在线检测服务，取消不产生检测调用；单次最多 30 条。"
            "可选 evaluator（activation_probe / keyword）在确认前冻结，未指定时使用服务端默认；"
            "产出风险命中与参考标注分歧两份问题视图，不计算准确率；"
            "初始请求可携带 export_requested，完成后即可下载 HTML/CSV/JSON/manifest 证据包。"
        ),
        params_model=RiskCorpusRescanParams,
        runner=_run_risk_corpus_rescan_preview,
        requires_confirmation=True,
        result_schema="risk_corpus_rescan.result.v2",
        result_model=RiskCorpusRescanRunResult,
        param_help={
            "keyword": "匹配样本文本与样本 ID，用于缩小检测范围。",
            "reference_label": "按来源参考标注筛选要检测的样本，只读事实。",
            "source": "样本来源数据集。",
            "harm_category_L1": "一级风险分类。",
            "harm_category_L2": "二级风险分类。",
            "limit": "本次检测的样本条数，服务端最多 30 条。",
            "evaluator": "可选评估器：activation_probe 或 keyword；省略则使用服务端默认。",
            "export_requested": "true 表示完成后立即提供证据包下载入口。",
        },
        enumerations=_risk_search_enumerations,
    ),
    CapabilityDef(
        key="risk_system_record_search",
        domain="output",
        label="浏览与筛选系统预跑记录",
        version="v1",
        description=(
            "查询已注册的风险安全系统预跑记录（系统资产，不是用户本次执行结果），"
            "可按来源仓库、评测状态、评测对象资产版本和完成时间筛选，并按完成时间倒序分页返回。"
            "省略 asset_version 时只返回资产系列当前版本；用户明确要求历史版本（如 v6）时才传 asset_version。"
            "用户要求继续、下一页或更多时，设置 continuation=true 复用上一轮筛选并读取下一页。"
        ),
        params_model=RiskSystemRecordSearchParams,
        runner=_run_risk_system_record_search,
        param_help={
            "source": (
                "来源仓库，精确匹配；可用值来自注册表。"
                "「课题三」「课题三数据」是资产系列名称，不是来源仓库，不要填入 source。"
            ),
            "status": "评测状态；已完成等价于 evaluation_imported，待导入等价于 evaluation_pending。",
            "asset_version": (
                "评测对象资产版本（如 v6、v7）。"
                "「课题三 v7」「课题三数据 v7」「数据集 v7」都映射到这里；"
                "不要填评估器版本（如 Qwen3.5-9B-V7）。省略表示当前版本。"
            ),
            "completed_after": "完成时间下界，ISO 日期或日期时间，含当天。",
            "completed_before": "完成时间上界，ISO 日期或日期时间，含当天。",
            "limit": "单页返回条数。",
            "offset": "起始偏移，用于翻页；翻页请优先使用 continuation。",
            "continuation": "true 表示沿用上一轮筛选并读取下一页。",
        },
        enumerations=_system_record_enumerations,
    ),
    CapabilityDef(
        key="risk_system_record_detail",
        domain="output",
        label="打开系统预跑记录详情",
        version="v1",
        description=(
            "按 record_id 打开一条风险安全系统预跑记录，返回模型、数据集、指标、"
            "样本摘要与来源版本。记录不存在或版本变化时返回明确状态，不补造结果。"
        ),
        params_model=RiskSystemRecordDetailParams,
        runner=_run_risk_system_record_detail,
        param_help={"record_id": "要打开的系统预跑记录 ID，来自列表结果。"},
    ),
    CapabilityDef(
        key="cultural_system_record_search",
        domain="output",
        label="浏览与筛选文化多样性系统预跑记录",
        version="v1",
        description=(
            "查询已注册的文化多样性系统预跑记录（系统资产，不是用户本次执行结果），"
            "可按来源仓库、评测状态、完成时间以及语境难度、民族、背景类型、问题类型筛选，"
            "并按完成时间倒序分页返回。"
            "用户要求继续、下一页或更多时，设置 continuation=true 复用上一轮筛选并读取下一页。"
        ),
        params_model=CulturalSystemRecordSearchParams,
        runner=_run_cultural_system_record_search,
        param_help={
            "source": "来源仓库，精确匹配；可用值来自注册表。",
            "status": "模型评测状态；已完成等价于 evaluation_imported，待导入等价于 evaluation_pending。",
            "completed_after": "完成时间下界，ISO 日期或日期时间，含当天。",
            "completed_before": "完成时间上界，ISO 日期或日期时间，含当天。",
            "difficulty_level": "语境难度（如 L1/L2/L3），精确匹配记录分布中已有的取值。",
            "ethnic_group": "民族，精确匹配记录分布中已有的取值。",
            "background_type": "背景类型，精确匹配记录分布中已有的取值。",
            "query_type": "问题类型，精确匹配记录分布中已有的取值。",
            "limit": "单页返回条数。",
            "offset": "起始偏移，用于翻页；翻页请优先使用 continuation。",
            "continuation": "true 表示沿用上一轮筛选并读取下一页。",
        },
        enumerations=_cultural_system_record_enumerations,
    ),
    CapabilityDef(
        key="cultural_system_record_detail",
        domain="output",
        label="打开文化多样性系统预跑记录详情",
        version="v1",
        description=(
            "按 record_id 打开一条文化多样性系统预跑记录，返回语境难度、民族、背景类型、"
            "问题类型分布、审校通过率、样本预览与来源版本。"
            "记录不存在或版本变化时返回明确状态，不补造结果。"
        ),
        params_model=CulturalSystemRecordDetailParams,
        runner=_run_cultural_system_record_detail,
        param_help={"record_id": "要打开的文化多样性系统预跑记录 ID，来自列表结果。"},
    ),
)


def capabilities_for_domain(domain: str) -> tuple[CapabilityDef, ...]:
    return tuple(capability for capability in CAPABILITIES if capability.domain == domain)


def resolve_capability(domain: str, key: str) -> CapabilityDef | None:
    for capability in CAPABILITIES:
        if capability.domain == domain and capability.key == key:
            return capability
    return None


def resolve_capability_by_key(key: str) -> CapabilityDef | None:
    """Resolve a registered capability by key across every business domain."""

    for capability in CAPABILITIES:
        if capability.key == key:
            return capability
    return None


def capability_prompt_block(domain: str) -> str:
    blocks = []
    for capability in capabilities_for_domain(domain):
        header = f"- {capability.key}（{capability.label}）：{capability.description}"
        contract = capability_params_contract(capability)
        blocks.append(f"{header}\n{contract}" if contract else header)
    if not blocks:
        return "（当前业务域没有可用的治理能力。）"
    return "\n".join(blocks)


def _json_schema_types(spec: dict) -> list[str]:
    if "anyOf" in spec:
        types = [branch.get("type") for branch in spec["anyOf"] if branch.get("type")]
        return types or ["string"]
    node_type = spec.get("type")
    return [node_type] if node_type else ["string"]


def _format_capability_param(
    name: str, spec: dict, help_text: str, allowed: list[str] | None
) -> str:
    types = _json_schema_types(spec)
    optional = "null" in types or "default" in spec
    type_label = "/".join(item for item in types if item != "null") or "string"
    parts = [f"{name}: {type_label}", "可选" if optional else "必填"]

    values = allowed or spec.get("enum")
    if values:
        parts.append("只能取 " + "、".join(str(value) for value in values))

    minimum = spec.get("minimum")
    maximum = spec.get("maximum")
    if minimum is not None and maximum is not None:
        parts.append(f"范围 {minimum}–{maximum}")
    elif minimum is not None:
        parts.append(f"≥ {minimum}")
    elif maximum is not None:
        parts.append(f"≤ {maximum}")

    default = spec.get("default")
    if default is not None:
        if default is True:
            label = "true"
        elif default is False:
            label = "false"
        else:
            label = default
        parts.append(f"默认 {label}")
    if help_text:
        parts.append(help_text)
    return "  - " + "；".join(parts)


def capability_params_contract(capability: CapabilityDef) -> str:
    """Render the exact parameter contract for a capability.

    The assistant prompt must expose field names (and allowed values) verbatim;
    otherwise a model can guess a plausible but wrong key such as ``l1`` and the
    request degrades to an unfiltered result."""
    properties = capability.params_model.model_json_schema().get("properties") or {}
    if not properties:
        return "  参数：无（只提交空对象 {}）。"
    enumerations = capability.enumerations() if capability.enumerations else {}
    lines = ["  参数（只允许以下字段名，未使用的可省略）："]
    for name, spec in properties.items():
        lines.append(
            _format_capability_param(
                name,
                spec,
                capability.param_help.get(name, ""),
                enumerations.get(name),
            )
        )
    return "\n".join(lines)


async def execute_capability(
    db: AsyncSession,
    ctx: CapabilityContext,
    capability: CapabilityDef,
    params: BaseModel,
) -> CapabilityResult:
    outcome = await capability.runner(db, ctx, params)
    payload = dict(outcome.payload)
    payload["capability_version"] = capability.version
    return CapabilityResult(payload=payload, content=outcome.content)


def serialize_params(capability: CapabilityDef, params: BaseModel) -> str:
    return json.dumps(params.model_dump(), ensure_ascii=False)
