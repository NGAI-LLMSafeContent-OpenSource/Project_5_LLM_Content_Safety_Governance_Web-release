from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import get_db
from app.schemas.data_input import (
    RiskAttributionRequest,
    InputGuardrailLiveRunStartRequest,
    Topic2KeywordPredictRequest,
    Topic2RiskScanTaskStartRequest,
    Topic4LineageBuildRequest,
)
from app.schemas.data_input_workflows import DataInputWorkflowSaveRequest
from app.services.data_input_corpus_catalog_service import (
    list_input_corpus_catalog,
    select_input_corpus,
)
from app.services.data_input_risk_attribution_service import build_risk_attribution
from app.services.data_input_workflow_service import (
    WorkflowConflictError,
    WorkflowNotFoundError,
    get_workflow_detail,
    list_workflows,
    save_workflow_draft,
    submit_workflow,
)
from app.services.data_input_topic2_service import (
    cancel_topic2_risk_scan_task,
    check_topic2_filterguard_health,
    get_topic2_risk_scan_task,
    load_topic2_prerun_samples,
    run_topic2_keyword_detection,
    start_topic2_risk_scan_task,
)
from app.services.data_input_topic4_service import (
    build_topic4_records_from_documents,
    build_topic4_lineage,
    check_topic4_input_workflow_health,
    load_topic4_static_lineage,
)
from app.services.data_input_value_attribution_service import build_value_attribution
from app.services.data_input_value_track_service import (
    build_value_assessment,
    get_value_qa_asset_status,
    list_value_qa_dimensions,
)
from app.services.input_guardrail_live_service import (
    InputGuardrailLiveRunError,
    get_live_run,
    list_demo_packs,
    start_live_run,
)
from app.services.topic1_corpus_tool_service import (
    Topic1CorpusToolCatalogError,
    load_topic1_corpus_tool_catalog,
)

router = APIRouter(prefix="/api/data-input", tags=["data-input"])


def _raise_live_run_error(exc: InputGuardrailLiveRunError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/guardrail/demo-packs")
async def input_guardrail_demo_packs():
    return ok(list_demo_packs())


@router.post("/guardrail/live-run")
async def input_guardrail_live_run_start(payload: InputGuardrailLiveRunStartRequest):
    try:
        data = await start_live_run(
            pack_id=payload.pack_id,
            items=payload.items,
            max_samples=payload.max_samples,
        )
    except InputGuardrailLiveRunError as exc:
        _raise_live_run_error(exc)
    return ok(data)


@router.get("/guardrail/live-run/{job_id}")
async def input_guardrail_live_run_detail(job_id: str):
    try:
        data = await get_live_run(job_id)
    except InputGuardrailLiveRunError as exc:
        _raise_live_run_error(exc)
    return ok(data)


@router.post("/workflows/draft")
async def data_input_workflow_draft(
    payload: DataInputWorkflowSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await save_workflow_draft(db, payload)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data)


@router.post("/workflows/submit")
async def data_input_workflow_submit(
    payload: DataInputWorkflowSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await submit_workflow(db, payload)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data)


@router.get("/workflows")
async def data_input_workflows(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    data = await list_workflows(db, status=status, source=source, limit=limit)
    return ok(data)


@router.get("/workflows/{workflow_id}")
async def data_input_workflow_detail(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    data = await get_workflow_detail(db, workflow_id)
    if data is None:
        raise HTTPException(status_code=404, detail="未找到输入护栏草稿")
    return ok(data)


@router.get("/corpus-catalog")
async def corpus_catalog(db: AsyncSession = Depends(get_db)):
    data = await list_input_corpus_catalog(db)
    return ok(data.model_dump())


@router.get("/topic1/corpus-tools")
async def topic1_corpus_tools():
    """Return the reviewed Topic 1 tool readiness snapshot for input governance."""

    try:
        data = load_topic1_corpus_tool_catalog()
    except Topic1CorpusToolCatalogError as exc:
        raise HTTPException(status_code=503, detail=exc.public_message) from exc
    return ok(data.model_dump())


@router.get("/corpus/{asset_id}/records")
async def corpus_records(
    asset_id: str,
    kind: str | None = Query(default=None),
    # Both Step 1 corpus tracks can request the complete cataloged pack.
    # 500 is only the records endpoint's transport safety ceiling.
    limit: int = Query(default=500, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    data = await select_input_corpus(db, asset_id=asset_id, kind=kind, limit=limit)
    return ok(data.model_dump())


@router.get("/topic2/filterguard/health")
async def topic2_filterguard_health(method: str | None = Query(default=None)):
    data = await check_topic2_filterguard_health(method=method)
    return ok(data.model_dump())


@router.post("/topic2/filterguard/predict")
async def topic2_filterguard_predict(payload: Topic2KeywordPredictRequest):
    if not any(text.strip() for text in payload.texts):
        raise HTTPException(status_code=400, detail="未提供待检测文本，未调用在线检测。")
    data = await run_topic2_keyword_detection(
        payload.texts,
        method=payload.method or None,
    )
    return ok(data.model_dump())


@router.post("/topic2/risk-scan-tasks")
async def topic2_risk_scan_task_start(payload: Topic2RiskScanTaskStartRequest):
    data = await start_topic2_risk_scan_task(payload.items, method=payload.method or None)
    return ok(data.model_dump())


@router.get("/topic2/risk-scan-tasks/{task_id}")
async def topic2_risk_scan_task_detail(task_id: str):
    data = await get_topic2_risk_scan_task(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="未找到课题二输入风险识别任务")
    return ok(data.model_dump())


@router.post("/topic2/risk-scan-tasks/{task_id}/cancel")
async def topic2_risk_scan_task_cancel(task_id: str):
    data = await cancel_topic2_risk_scan_task(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="未找到课题二输入风险识别任务")
    return ok(data.model_dump())


@router.get("/topic2/prerun-samples")
async def topic2_prerun_samples(
    asset_id: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    data = await load_topic2_prerun_samples(db, asset_id=asset_id, limit=limit)
    return ok(data.model_dump())


@router.post("/attribution/risk")
async def attribution_risk(
    payload: RiskAttributionRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    request_payload = payload or RiskAttributionRequest()
    data = await build_risk_attribution(
        db,
        task_id=request_payload.task_id,
        predictions=request_payload.predictions,
        use_prerun=request_payload.use_prerun,
        asset_id=request_payload.asset_id,
        limit=request_payload.limit,
    )
    return ok(data.model_dump())


@router.get("/attribution/value")
async def attribution_value(
    asset_id: str | None = None,
    limit: int = 24,
    prefer_low: bool = True,
    db: AsyncSession = Depends(get_db),
):
    data = await build_value_attribution(
        db,
        asset_id=asset_id,
        limit=limit,
        prefer_low=prefer_low,
    )
    return ok(data.model_dump())


@router.get("/value-qa/status")
async def value_qa_status(
    asset_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    data = await get_value_qa_asset_status(db, asset_id=asset_id)
    return ok(data.model_dump())


@router.get("/value-qa/dimensions")
async def value_qa_dimensions(
    asset_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    data = await list_value_qa_dimensions(db, asset_id=asset_id)
    return ok(data.model_dump())


@router.get("/value-qa/assessment")
async def value_qa_assessment(
    asset_id: str | None = None,
    primary_dimension: list[str] | None = Query(default=None),
    secondary_dimension: list[str] | None = Query(default=None),
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
):
    data = await build_value_assessment(
        db,
        asset_id=asset_id,
        primary_dimensions=primary_dimension,
        secondary_dimensions=secondary_dimension,
        limit=limit,
    )
    return ok(data.model_dump())


@router.get("/topic4/lineage/health")
async def topic4_lineage_health():
    data = await check_topic4_input_workflow_health()
    return ok(data.model_dump())


@router.get("/topic4/lineage/static")
async def topic4_lineage_static():
    data = load_topic4_static_lineage()
    if not data.connected:
        raise HTTPException(status_code=503, detail=data.message)
    return ok(data.model_dump())


@router.post("/topic4/lineage/parse-records")
async def topic4_lineage_parse_records(
    files: list[UploadFile] = File(...),
    dataset_name: str = Form(""),
    dataset_domain: str = Form(""),
    dataset_volume: str = Form(""),
    dataset_desc: str = Form(""),
):
    documents = [
        {
            "filename": upload.filename or "unknown",
            "content_type": upload.content_type or "",
            "raw": await upload.read(),
        }
        for upload in files
    ]
    data = build_topic4_records_from_documents(
        documents,
        dataset_name=dataset_name,
        dataset_domain=dataset_domain,
        dataset_volume=dataset_volume,
        dataset_desc=dataset_desc,
    )
    if not data.records:
        detail = "; ".join(f"{item.name}: {item.reason}" for item in data.failures)
        raise HTTPException(status_code=400, detail=detail or "未能从上传文件中提取有效文本")
    return ok(data.model_dump())


@router.post("/topic4/lineage/build")
async def topic4_lineage_build(payload: Topic4LineageBuildRequest | None = None):
    request_payload = payload or Topic4LineageBuildRequest()
    if not request_payload.records:
        raise HTTPException(status_code=400, detail="请先上传并解析训练语料文件，再生成课题四血缘图谱")
    data = await build_topic4_lineage(
        records=request_payload.records,
        risk_annotations=request_payload.risk_annotations or None,
    )
    return ok(data.model_dump())
