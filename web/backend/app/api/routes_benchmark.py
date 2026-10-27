import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.benchmark.topic1_value_qa import (
    Topic1ValueQaCliAdapter,
    read_topic1_llm_runtime,
)
from app.adapters.benchmark.topic2_autobench import (
    Topic2AutoBenchAdapter,
    Topic2AutoBenchProtocolError,
    Topic2AutoBenchUpstreamError,
)
from app.core.config import get_settings
from app.core.response import ok
from app.db.models import BenchmarkAsset, BenchmarkTask, BenchmarkTaskLog
from app.db.session import get_db
from app.schemas.benchmark import (
    BenchmarkAssetRegistryResponse,
    BenchmarkArtifactItem,
    BenchmarkArtifactsResponse,
    BenchmarkCbrneSampleDetailResponse,
    BenchmarkCbrneSampleDisclosureRequest,
    BenchmarkCbrneSampleDisclosureResponse,
    BenchmarkCbrneSampleRefResponse,
    BenchmarkCbrneSampleRefsResponse,
    BenchmarkCbrneSamplesQueryResponse,
    BenchmarkDatasetSnapshotImportRequest,
    BenchmarkDatasetSnapshotImportResponse,
    BenchmarkPrerunImportRequest,
    BenchmarkPrerunImportResponse,
    BenchmarkTopic1ValueQaGroupDetailResponse,
    BenchmarkTopic1ValueQaGroupsResponse,
    BenchmarkTopic1ValueQaImportRequest,
    BenchmarkTopic1ValueQaImportResponse,
    BenchmarkTopic1ValueQaRecheckSummaryResponse,
    BenchmarkTopic2PrerunPairsResponse,
    BenchmarkTopic3RiskAssetOverview,
    BenchmarkTopic3RiskAssetVersionsResponse,
    BenchmarkTopic3RiskImportRequest,
    BenchmarkTopic3RiskImportResponse,
    BenchmarkTopic3RiskEvaluationImportRequest,
    BenchmarkTopic3RiskEvaluationImportResponse,
    BenchmarkTopic3RiskEvaluationSummaryResponse,
    BenchmarkTopic3RiskSampleDetailResponse,
    BenchmarkTopic3RiskSamplesResponse,
    BenchmarkTopic3RiskTaxonomyResponse,
    BenchmarkTopic3CulturalEnsureResponse,
    BenchmarkTopic3CulturalSampleDetailResponse,
    BenchmarkTopic3CulturalSamplesResponse,
    BenchmarkTopic3CulturalSummaryResponse,
    BenchmarkTopic3RiskV6ImportRequest,
    BenchmarkTopic3RiskV6ImportResponse,
    BenchmarkTaskCreate,
    BenchmarkTaskLogItem,
    BenchmarkTaskLogsResponse,
    BenchmarkTaskResponse,
)
from app.services.benchmark_asset_registry_service import (
    BenchmarkAssetRegistryError,
    BenchmarkAssetRegistryService,
)
from app.services.benchmark_cbrne_dataset_query_service import (
    BenchmarkCbrneDatasetQueryError,
    BenchmarkCbrneDatasetQueryNotFoundError,
    BenchmarkCbrneDatasetQueryService,
)
from app.services.benchmark_cbrne_dataset_snapshot_service import (
    BenchmarkCbrneDatasetSnapshotError,
    BenchmarkCbrneDatasetSnapshotService,
)
from app.services.benchmark_cbrne_sample_detail_service import (
    BenchmarkCbrneSampleDetailError,
    BenchmarkCbrneSampleDetailNotFoundError,
    BenchmarkCbrneSampleDisclosureConflictError,
    BenchmarkCbrneSampleDetailService,
)
from app.services.benchmark_evalset_export_service import (
    BenchmarkEvalsetExportError,
    build_evalset_zip_bytes,
)
from app.services.benchmark_live_run_summary_service import (
    BenchmarkLiveRunSummaryError,
    BenchmarkLiveRunSummaryNotFoundError,
    build_live_run_summary,
)
from app.services.benchmark_topic1_value_qa_asset_service import (
    BenchmarkTopic1ValueQaAssetError,
    BenchmarkTopic1ValueQaAssetService,
)
from app.services.benchmark_topic1_value_qa_sample_service import (
    BenchmarkTopic1ValueQaSampleError,
    BenchmarkTopic1ValueQaSampleNotFoundError,
    BenchmarkTopic1ValueQaSampleService,
)
from app.services.benchmark_topic2_prerun_sample_service import (
    BenchmarkTopic2PrerunSampleError,
    BenchmarkTopic2PrerunSampleNotFoundError,
    BenchmarkTopic2PrerunSampleService,
)
from app.services.benchmark_topic3_risk_asset_service import (
    BenchmarkTopic3RiskAssetError,
    BenchmarkTopic3RiskAssetService,
)
from app.services.benchmark_topic3_risk_sample_service import (
    BenchmarkTopic3RiskSampleError,
    BenchmarkTopic3RiskSampleNotFoundError,
    BenchmarkTopic3RiskSampleService,
)
from app.services import benchmark_topic3_risk_series_service as topic3_risk_series
from app.services.benchmark_topic3_risk_series_service import (
    BenchmarkTopic3RiskSeriesError,
    BenchmarkTopic3RiskSeriesNotFoundError,
    ResolvedTopic3RiskAsset,
)
from app.services.benchmark_topic3_risk_taxonomy_service import (
    get_topic3_risk_taxonomy,
)
from app.services.benchmark_topic3_risk_v6_service import (
    BenchmarkTopic3RiskV6Error,
    BenchmarkTopic3RiskV6Service,
)
from app.services.benchmark_topic3_cultural_asset_service import (
    BenchmarkTopic3CulturalAssetError,
    BenchmarkTopic3CulturalAssetService,
)
from app.services.benchmark_topic3_cultural_sample_service import (
    BenchmarkTopic3CulturalSampleError,
    BenchmarkTopic3CulturalSampleNotFoundError,
    BenchmarkTopic3CulturalSampleService,
)
from app.services.benchmark_task_scheduler import schedule_benchmark_task
from app.services.benchmark_task_service import BenchmarkTaskService


router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


def _topic3_risk_sample_summary(resolved: ResolvedTopic3RiskAsset) -> dict[str, Any]:
    """Sample distributions for a version overview; unreadable samples stay empty."""
    try:
        return BenchmarkTopic3RiskSampleService().summarize_resolved_asset(resolved)
    except (BenchmarkTopic3RiskSampleError, OSError, UnicodeError, ValueError):
        return {}


TOPIC2_PROXY_FALLBACK_OPTIONS: dict[str, Any] = {
    "source": "fallback",
    "languages": ["zh", "en", "zh+en"],
    "moderators": [
        {
            "value": "keyword",
            "label": "keyword",
            "group": "rule",
            "status": "available",
        },
        {
            "value": "deepseek",
            "label": "deepseek",
            "group": "deepseek",
            "status": "requires_key",
        },
    ],
    "agent_models": [
        {
            "value": "claude-sonnet-4-6",
            "label": "claude-sonnet-4-6",
            "status": "requires_dmx_or_compatible",
        }
    ],
    "attack_vectors": [],
    "capabilities": [],
}

TOPIC2_PROXY_FALLBACK_SEEDBANK_STATS: dict[str, Any] = {
    "source": "fallback",
    "static_total": 0,
    "dynbench_total": 0,
    "by_l1": [],
    "by_l2": [],
    "seed_types": [],
}

TOPIC2_RUNTIME_UNKNOWN_CAPABILITIES: dict[str, str] = {
    "rule_moderators": "available",
    "deepseek_moderators": "unknown",
    "dmx_moderators": "unknown",
    "local_vllm_guards": "unknown",
    "agent_deepseek_fallback": "unknown",
}


@router.post("/tasks")
async def create_benchmark_task(
    payload: BenchmarkTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTaskService()
    task = await service.create_task(db, payload)
    schedule_benchmark_task(task.task_id)
    return ok(_task_response(task).model_dump(mode="json"))


@router.get("/topic2/options")
async def read_topic2_options():
    payload, _source = await _read_topic2_options_payload()
    return ok(payload)


@router.get("/topic1/value-qa-topics")
async def read_topic1_value_qa_topics():
    from app.services.topic1_value_qa_topics import load_topic1_value_qa_topics

    return ok(load_topic1_value_qa_topics())


@router.get("/topic1/runtime")
async def read_topic1_runtime():
    adapter = Topic1ValueQaCliAdapter.from_settings()
    return ok(await read_topic1_llm_runtime(adapter))


@router.get("/topic2/seedbank-stats")
async def read_topic2_seedbank_stats():
    payload, _source = await _read_topic2_seedbank_stats_payload()
    return ok(payload)


@router.get("/topic2/runtime")
async def read_topic2_runtime():
    adapter = Topic2AutoBenchAdapter.from_settings()
    try:
        upstream_ready, upstream_health, agent_runtime = await _read_topic2_runtime(
            adapter
        )
    finally:
        await adapter.aclose()

    _options_payload, options_source = await _read_topic2_options_payload()
    _stats_payload, stats_source = await _read_topic2_seedbank_stats_payload()
    settings = get_settings()
    return ok(
        {
            "upstream_ready": upstream_ready,
            "upstream_base_url": settings.topic2_autobench_base_url,
            "upstream_health": upstream_health,
            "agent_runtime": agent_runtime,
            "options_source": options_source,
            "seedbank_stats_source": stats_source,
            "capabilities": dict(TOPIC2_RUNTIME_UNKNOWN_CAPABILITIES),
            "limits": {
                "budget_min": 1,
                "budget_max": settings.benchmark_demo_budget_max,
                "max_turns_max": 25,
            },
        }
    )


@router.get("/topic3-risk/taxonomy")
async def read_topic3_risk_taxonomy():
    response: BenchmarkTopic3RiskTaxonomyResponse = get_topic3_risk_taxonomy()
    return ok(response.model_dump(mode="json", by_alias=True))


@router.get("/topic3-risk/assets")
async def read_topic3_risk_asset_versions(db: AsyncSession = Depends(get_db)):
    payload = await topic3_risk_series.list_versions(
        db, summarize=_topic3_risk_sample_summary
    )
    response = BenchmarkTopic3RiskAssetVersionsResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/topic3-risk/assets/resolve")
async def read_topic3_risk_resolved_asset(
    asset_version: str | None = None,
    asset_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    with _topic3_risk_http_errors():
        resolved = await topic3_risk_series.resolve_asset(
            db, asset_version=asset_version, asset_id=asset_id
        )
    response = BenchmarkTopic3RiskAssetOverview(
        **topic3_risk_series.asset_overview(
            resolved, summarize=_topic3_risk_sample_summary
        )
    )
    return ok(response.model_dump(mode="json"))


@router.get("/topic3-risk/samples")
async def read_topic3_risk_versioned_samples(
    asset_version: str | None = None,
    asset_id: str | None = None,
    risk_level_id: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    with _topic3_risk_http_errors():
        resolved = await topic3_risk_series.resolve_asset(
            db, asset_version=asset_version, asset_id=asset_id
        )
        payload = BenchmarkTopic3RiskSampleService().list_resolved_samples(
            resolved,
            risk_level_id=risk_level_id,
            category=category,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
    response = BenchmarkTopic3RiskSamplesResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/topic3-risk/samples/{sample_id}")
async def read_topic3_risk_versioned_sample_detail(
    sample_id: str,
    asset_version: str | None = None,
    asset_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    with _topic3_risk_http_errors():
        resolved = await topic3_risk_series.resolve_asset(
            db, asset_version=asset_version, asset_id=asset_id
        )
        payload = BenchmarkTopic3RiskSampleService().get_resolved_sample(
            resolved, sample_id=sample_id
        )
    response = BenchmarkTopic3RiskSampleDetailResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/topic3-risk/evaluations/summary")
async def read_topic3_risk_versioned_evaluation_summary(
    asset_version: str | None = None,
    asset_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    with _topic3_risk_http_errors():
        resolved = await topic3_risk_series.resolve_asset(
            db, asset_version=asset_version, asset_id=asset_id
        )
        payload = topic3_risk_series.build_resolved_evaluation_summary(resolved)
    response = BenchmarkTopic3RiskEvaluationSummaryResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets")
async def read_benchmark_assets(
    source_mode: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkAssetRegistryService()
    assets = await service.list_assets(db, source_mode=source_mode)
    response = BenchmarkAssetRegistryResponse(
        assets=[_artifact_response(item) for item in assets],
    )
    return ok(response.model_dump(mode="json"))


@router.post("/assets/prerun/import")
async def import_benchmark_prerun_asset(
    payload: BenchmarkPrerunImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkAssetRegistryService()
    try:
        asset = await service.import_prerun_asset(
            db,
            archive_path=payload.archive_path,
        )
    except BenchmarkAssetRegistryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkPrerunImportResponse(asset=_artifact_response(asset))
    return ok(response.model_dump(mode="json"))


@router.post("/assets/dataset-snapshot/import")
async def import_benchmark_dataset_snapshot_asset(
    payload: BenchmarkDatasetSnapshotImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkCbrneDatasetSnapshotService()
    try:
        asset, idempotent = await service.import_dataset(
            db,
            archive_path=payload.archive_path,
        )
    except BenchmarkCbrneDatasetSnapshotError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkDatasetSnapshotImportResponse(
        asset=_artifact_response(asset),
        idempotent=idempotent,
    )
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/cbrne-anomaly/samples")
async def query_cbrne_anomaly_benchmark_samples(
    asset_id: str,
    label: str | None = None,
    cbrne_category: str | None = None,
    source: str | None = None,
    exposure_tier: str | None = None,
    difficulty_min: int | None = None,
    difficulty_max: int | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkCbrneDatasetQueryService()
    try:
        payload = await service.query_samples(
            db,
            asset_id=asset_id,
            label=label,
            cbrne_category=cbrne_category,
            source=source,
            exposure_tier=exposure_tier,
            difficulty_min=difficulty_min,
            difficulty_max=difficulty_max,
            limit=limit,
            offset=offset,
        )
    except BenchmarkCbrneDatasetQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkCbrneDatasetQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkCbrneSamplesQueryResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/cbrne/sample-refs")
async def read_cbrne_benchmark_sample_refs(
    asset_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Stable sample references for detail entry; never returns full text."""
    service = BenchmarkCbrneSampleDetailService()
    try:
        payload = await service.list_sample_refs(
            db,
            asset_id=asset_id,
            limit=limit,
            offset=offset,
        )
    except BenchmarkCbrneSampleDetailNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkCbrneSampleDetailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkCbrneSampleRefsResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/cbrne/sample-refs/{sample_id}")
async def read_cbrne_benchmark_sample_ref(
    asset_id: str,
    sample_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Exact masked sample identity for the stable sample resource route (#175)."""
    service = BenchmarkCbrneSampleDetailService()
    try:
        payload = await service.get_sample_ref(
            db,
            asset_id=asset_id,
            sample_id=sample_id,
        )
    except BenchmarkCbrneSampleDetailNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkCbrneSampleDetailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkCbrneSampleRefResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/cbrne/samples/{sample_id}")
async def read_cbrne_benchmark_sample_detail(
    asset_id: str,
    sample_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Explicit full-text detail for one CBRNE sample; records an access event."""
    service = BenchmarkCbrneSampleDetailService()
    try:
        payload = await service.get_sample_detail(
            db,
            asset_id=asset_id,
            sample_id=sample_id,
        )
    except BenchmarkCbrneSampleDetailNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkCbrneSampleDetailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkCbrneSampleDetailResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.post("/assets/{asset_id}/cbrne/samples/{sample_id}/disclosures")
async def disclose_cbrne_benchmark_sample(
    asset_id: str,
    sample_id: str,
    request: BenchmarkCbrneSampleDisclosureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Disclose one CBRNE sample through an explicitly identified command."""
    service = BenchmarkCbrneSampleDetailService()
    try:
        payload = await service.disclose_sample(
            db,
            asset_id=asset_id,
            sample_id=sample_id,
            disclosure_request_id=str(request.disclosure_request_id),
        )
    except BenchmarkCbrneSampleDetailNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkCbrneSampleDisclosureConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BenchmarkCbrneSampleDetailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkCbrneSampleDisclosureResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.post("/assets/topic1-value-qa/import")
async def import_topic1_value_qa_benchmark_asset(
    payload: BenchmarkTopic1ValueQaImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic1ValueQaAssetService()
    try:
        asset = await service.import_dataset(
            db,
            samples_path=payload.samples_path,
            marks_path=payload.marks_path,
            qc_index_path=payload.qc_index_path,
            qc_samples_path=payload.qc_samples_path,
            qc_scores_path=payload.qc_scores_path,
            qc_summary_path=payload.qc_summary_path,
            trace_predictions_path=payload.trace_predictions_path,
            trace_low_issues_path=payload.trace_low_issues_path,
            asset_id=payload.asset_id,
            name=payload.name,
        )
    except BenchmarkTopic1ValueQaAssetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic1ValueQaImportResponse(asset=_artifact_response(asset))
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic1-value-qa/groups")
async def read_topic1_value_qa_benchmark_groups(
    asset_id: str,
    topic: str | None = None,
    primary_dimension: str | None = None,
    secondary_dimension: str | None = None,
    qc_status: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic1ValueQaSampleService()
    try:
        payload = await service.list_groups(
            db,
            asset_id=asset_id,
            topic=topic,
            primary_dimension=primary_dimension,
            secondary_dimension=secondary_dimension,
            qc_status=qc_status,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
    except BenchmarkTopic1ValueQaSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic1ValueQaSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic1ValueQaGroupsResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic1-value-qa/recheck-summary")
async def read_topic1_value_qa_benchmark_recheck_summary(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic1ValueQaSampleService()
    try:
        payload = await service.get_recheck_summary(db, asset_id=asset_id)
    except BenchmarkTopic1ValueQaSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic1ValueQaSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic1ValueQaRecheckSummaryResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic1-value-qa/groups/{group_id}")
async def read_topic1_value_qa_benchmark_group_detail(
    asset_id: str,
    group_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic1ValueQaSampleService()
    try:
        payload = await service.get_group(db, asset_id=asset_id, group_id=group_id)
    except BenchmarkTopic1ValueQaSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic1ValueQaSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic1ValueQaGroupDetailResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.post("/assets/topic3-risk/import")
async def import_topic3_risk_benchmark_asset(
    payload: BenchmarkTopic3RiskImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3RiskAssetService()
    try:
        asset = await service.import_final_dataset(
            db,
            final_dir=payload.final_dir,
            asset_id=payload.asset_id,
            name=payload.name,
        )
    except BenchmarkTopic3RiskAssetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskImportResponse(asset=_artifact_response(asset))
    return ok(response.model_dump(mode="json"))


@router.post("/assets/topic3-risk/v6/import")
async def import_topic3_risk_v6_benchmark_asset(
    payload: BenchmarkTopic3RiskV6ImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3RiskV6Service()
    try:
        asset = await service.import_asset(
            db,
            csv_path=payload.csv_path,
            asset_id=payload.asset_id,
            name=payload.name,
        )
    except BenchmarkTopic3RiskV6Error as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskV6ImportResponse(asset=_artifact_response(asset))
    return ok(response.model_dump(mode="json"))


@router.post("/assets/topic3-cultural/ensure")
async def ensure_topic3_cultural_benchmark_asset(
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3CulturalAssetService()
    try:
        asset = await service.ensure_default_asset(db)
    except BenchmarkTopic3CulturalAssetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3CulturalEnsureResponse(asset=_artifact_response(asset))
    return ok(response.model_dump(mode="json"))


@router.post("/assets/{asset_id}/topic3-risk/evaluations/import")
async def import_topic3_risk_evaluation_result(
    asset_id: str,
    payload: BenchmarkTopic3RiskEvaluationImportRequest,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3RiskV6Service()
    try:
        summary = await service.import_evaluation_result(
            db,
            asset_id=asset_id,
            result_dir=payload.result_dir,
        )
    except BenchmarkTopic3RiskV6Error as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskEvaluationImportResponse(summary=summary)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-risk/evaluations/summary")
async def read_topic3_risk_evaluation_summary(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        resolved = await topic3_risk_series.get_series_asset(db, asset_id)
        payload = topic3_risk_series.build_resolved_evaluation_summary(resolved)
    except BenchmarkTopic3RiskSeriesError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskEvaluationSummaryResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic2-prerun/samples")
async def read_topic2_prerun_benchmark_samples(
    asset_id: str,
    moderator: str | None = None,
    verdict: str | None = None,
    difficulty: str | None = None,
    strategy: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic2PrerunSampleService()
    try:
        payload = await service.list_pairs(
            db,
            asset_id=asset_id,
            moderator=moderator,
            verdict=verdict,
            difficulty=difficulty,
            strategy=strategy,
            limit=limit,
            offset=offset,
        )
    except BenchmarkTopic2PrerunSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic2PrerunSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic2PrerunPairsResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-cultural/samples")
async def read_topic3_cultural_benchmark_samples(
    asset_id: str,
    ethnic_group: str | None = None,
    difficulty_level: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3CulturalSampleService()
    try:
        payload = await service.list_samples(
            db,
            asset_id=asset_id,
            ethnic_group=ethnic_group,
            difficulty_level=difficulty_level,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
    except BenchmarkTopic3CulturalSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic3CulturalSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3CulturalSamplesResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-cultural/samples/{sample_id}")
async def read_topic3_cultural_benchmark_sample_detail(
    asset_id: str,
    sample_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3CulturalSampleService()
    try:
        payload = await service.get_sample(db, asset_id=asset_id, sample_id=sample_id)
    except BenchmarkTopic3CulturalSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic3CulturalSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3CulturalSampleDetailResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-risk/samples")
async def read_topic3_risk_benchmark_samples(
    asset_id: str,
    risk_level_id: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3RiskSampleService()
    try:
        payload = await service.list_samples(
            db,
            asset_id=asset_id,
            risk_level_id=risk_level_id,
            category=category,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
    except BenchmarkTopic3RiskSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic3RiskSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskSamplesResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-risk/samples/{sample_id}")
async def read_topic3_risk_benchmark_sample_detail(
    asset_id: str,
    sample_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3RiskSampleService()
    try:
        payload = await service.get_sample(db, asset_id=asset_id, sample_id=sample_id)
    except BenchmarkTopic3RiskSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic3RiskSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3RiskSampleDetailResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/topic3-cultural/summary")
async def read_topic3_cultural_benchmark_summary(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTopic3CulturalSampleService()
    try:
        payload = await service.get_summary(db, asset_id=asset_id)
    except BenchmarkTopic3CulturalSampleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkTopic3CulturalSampleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = BenchmarkTopic3CulturalSummaryResponse(**payload)
    return ok(response.model_dump(mode="json"))


@router.get("/assets/{asset_id}/live-run/summary")
async def read_live_run_benchmark_summary(
    asset_id: str,
    sample_limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await build_live_run_summary(
            db,
            asset_id=asset_id,
            sample_limit=max(1, min(sample_limit, 50)),
        )
    except BenchmarkLiveRunSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BenchmarkLiveRunSummaryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(payload)


@router.get("/assets/{asset_id}")
async def read_benchmark_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkAssetRegistryService()
    asset = await service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return ok(_artifact_response(asset).model_dump(mode="json"))


@router.get("/tasks/{task_id}")
async def read_benchmark_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTaskService()
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(_task_response(task).model_dump(mode="json"))


@router.get("/tasks/{task_id}/logs")
async def read_benchmark_task_logs(
    task_id: str,
    after_id: int | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTaskService()
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    logs = await service.list_logs(db, task_id, after_id=after_id, limit=limit)
    response = BenchmarkTaskLogsResponse(
        task_id=task_id,
        logs=[_log_response(item) for item in logs],
    )
    return ok(response.model_dump(mode="json"))


@router.get("/tasks/{task_id}/artifacts")
async def read_benchmark_task_artifacts(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = BenchmarkTaskService()
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    artifacts = await service.list_artifacts(db, task_id)
    response = BenchmarkArtifactsResponse(
        task_id=task_id,
        artifacts=[_artifact_response(item) for item in artifacts],
    )
    return ok(response.model_dump(mode="json"))


@router.get("/tasks/{task_id}/evalset")
async def download_benchmark_task_evalset(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download thin evalset zip (README + meta.json + samples.jsonl) for a succeeded task."""
    service = BenchmarkTaskService()
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"task status must be completed, got {task.status}",
        )
    artifacts = await service.list_artifacts(db, task_id)
    if not artifacts:
        raise HTTPException(status_code=409, detail="task has no frozen artifacts")
    asset = artifacts[-1]
    try:
        zip_bytes = build_evalset_zip_bytes(task=task, asset=asset)
    except BenchmarkEvalsetExportError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    filename = f"{task_id}_evalset.zip"
    encoded = quote(filename)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded}"
            )
        },
    )


@contextmanager
def _topic3_risk_http_errors() -> Iterator[None]:
    try:
        yield
    except (
        BenchmarkTopic3RiskSeriesNotFoundError,
        BenchmarkTopic3RiskSampleNotFoundError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (BenchmarkTopic3RiskSeriesError, BenchmarkTopic3RiskSampleError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def _read_topic2_options_payload() -> tuple[dict[str, Any], str]:
    adapter = Topic2AutoBenchAdapter.from_settings()
    try:
        payload = await adapter.options()
        return _with_topic2_proxy_meta(payload, source="upstream"), "upstream"
    except _topic2_proxy_fallback_errors():
        return _topic2_fallback_options(), "fallback"
    finally:
        await adapter.aclose()


async def _read_topic2_seedbank_stats_payload() -> tuple[dict[str, Any], str]:
    adapter = Topic2AutoBenchAdapter.from_settings()
    try:
        payload = await adapter.seedbank_stats()
        return _normalize_topic2_seedbank_stats(payload, source="upstream"), "upstream"
    except _topic2_proxy_fallback_errors():
        return _topic2_fallback_seedbank_stats(), "fallback"
    finally:
        await adapter.aclose()


async def _read_topic2_health(
    adapter: Topic2AutoBenchAdapter,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    try:
        payload = await adapter.health()
    except _topic2_proxy_fallback_errors():
        return (
            False,
            {"service": "unknown", "status": "unreachable", "version": "unknown"},
            None,
        )
    return True, _whitelist_topic2_health(payload), _whitelist_topic2_agent_runtime(
        payload.get("agent_runtime")
    )


async def _read_topic2_runtime(
    adapter: Topic2AutoBenchAdapter,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    try:
        payload = await adapter.runtime()
    except _topic2_proxy_fallback_errors():
        return await _read_topic2_health(adapter)
    return True, _whitelist_topic2_health(payload), _whitelist_topic2_agent_runtime(
        payload.get("agent_runtime")
    )


def _topic2_proxy_fallback_errors() -> tuple[type[Exception], ...]:
    return (
        Topic2AutoBenchProtocolError,
        Topic2AutoBenchUpstreamError,
        httpx.HTTPError,
        ValueError,
    )


def _with_topic2_proxy_meta(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    response = dict(payload)
    response["source"] = source
    response["upstream_base_url"] = get_settings().topic2_autobench_base_url
    return response


def _topic2_fallback_options() -> dict[str, Any]:
    payload = dict(TOPIC2_PROXY_FALLBACK_OPTIONS)
    payload["moderators"] = [
        dict(item) for item in TOPIC2_PROXY_FALLBACK_OPTIONS["moderators"]
    ]
    payload["agent_models"] = [
        dict(item) for item in TOPIC2_PROXY_FALLBACK_OPTIONS["agent_models"]
    ]
    payload["upstream_base_url"] = get_settings().topic2_autobench_base_url
    return payload


def _topic2_fallback_seedbank_stats() -> dict[str, Any]:
    return dict(TOPIC2_PROXY_FALLBACK_SEEDBANK_STATS)


def _normalize_topic2_seedbank_stats(
    payload: dict[str, Any], *, source: str
) -> dict[str, Any]:
    response = dict(payload)
    response["source"] = source
    response.setdefault("static_total", 0)
    response.setdefault("dynbench_total", 0)
    response["by_l1"] = _first_present(response, "by_l1", "by_L1", "l1", "L1") or []
    response["by_l2"] = _first_present(response, "by_l2", "by_L2", "l2", "L2") or []
    response["seed_types"] = _first_present(
        response,
        "seed_types",
        "by_seed_type",
        "seed_type",
    ) or []
    return response


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _whitelist_topic2_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": _string_or_unknown(payload.get("service")),
        "status": _string_or_unknown(payload.get("status")),
        "version": _string_or_unknown(payload.get("version")),
    }


def _whitelist_topic2_agent_runtime(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "submitted_model_id": _string_or_unknown(value.get("submitted_model_id")),
        "provider": _string_or_unknown(value.get("provider")),
        "provider_label": _string_or_unknown(value.get("provider_label")),
        "credential_policy": _string_or_unknown(value.get("credential_policy")),
        "uses_deepseek_fallback": value.get("uses_deepseek_fallback") is True,
        "anthropic_compatible": value.get("anthropic_compatible") is True,
        "base_url_origin": _string_or_unknown(value.get("base_url_origin")),
    }


def _string_or_unknown(value: Any) -> str:
    return value if isinstance(value, str) and value.strip() else "unknown"


def _task_response(task: BenchmarkTask) -> BenchmarkTaskResponse:
    return BenchmarkTaskResponse(
        task_id=task.task_id,
        agent_id=task.agent_id,
        mode=task.mode,
        status=task.status,
        parameters=_loads_json_object(task.parameters_json),
        upstream_base_url=task.upstream_base_url,
        upstream_contract=task.upstream_contract,
        source_repo=task.source_repo,
        source_commit=task.source_commit,
        adapter_version=task.adapter_version,
        error_message=task.error_message,
        asset_id=task.asset_id,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _log_response(log: BenchmarkTaskLog) -> BenchmarkTaskLogItem:
    return BenchmarkTaskLogItem(
        id=log.id,
        task_id=log.task_id,
        event_type=log.event_type,
        stage=log.stage,
        message=log.message,
        turn=log.turn,
        raw_json=_loads_json_object(log.raw_json),
        created_at=log.created_at,
    )


def _artifact_response(asset: BenchmarkAsset) -> BenchmarkArtifactItem:
    return BenchmarkArtifactItem(
        asset_id=asset.asset_id,
        task_id=asset.task_id,
        source_mode=asset.source_mode,
        name=asset.name,
        manifest=_loads_json_object(asset.manifest_json),
        artifact_sha256=asset.artifact_sha256,
        created_at=asset.created_at,
    )
