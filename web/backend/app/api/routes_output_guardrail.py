"""Output guardrail live-batch + compliance BFF."""
from fastapi import APIRouter, HTTPException

from app.core.response import ok
from app.schemas.output_guardrail import (
    ComplianceEditRequest,
    CultureGuardrailBatchRequest,
    LiveBatchStartRequest,
)
from app.services.output_guardrail_culture_service import (
    CultureGuardrailError,
    run_culture_guardrail_batch,
)
from app.services.output_guardrail_live_service import (
    LiveBatchError,
    edit_compliance_public,
    get_live_batch,
    list_demo_packs,
    start_live_batch,
)

router = APIRouter(prefix="/api/output", tags=["output-guardrail"])


def _raise(exc: LiveBatchError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _raise_culture(exc: CultureGuardrailError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/guardrail/demo-packs")
async def demo_packs():
    return ok(list_demo_packs())


@router.post("/guardrail/live-batch")
async def live_batch_start(payload: LiveBatchStartRequest):
    try:
        data = await start_live_batch(payload.pack_id, payload.max_samples)
    except LiveBatchError as exc:
        _raise(exc)
    return ok(data)


@router.get("/guardrail/live-batch/{job_id}")
async def live_batch_detail(job_id: str):
    try:
        data = await get_live_batch(job_id)
    except LiveBatchError as exc:
        _raise(exc)
    return ok(data)


@router.post("/guardrail/culture-batch")
async def culture_guardrail_batch(payload: CultureGuardrailBatchRequest):
    try:
        data = await run_culture_guardrail_batch(
            payload.candidate_responses_path,
            limit=payload.limit,
            model_id=payload.model_id,
            language=payload.language,
            generate_neutral_candidate=payload.generate_neutral_candidate,
        )
    except CultureGuardrailError as exc:
        _raise_culture(exc)
    return ok(data)


@router.post("/compliance/edit")
async def compliance_edit(payload: ComplianceEditRequest):
    try:
        data = await edit_compliance_public(
            payload.text,
            payload.request_id,
            payload.language,
            payload.pre_safety_label,
        )
    except LiveBatchError as exc:
        _raise(exc)
    return ok(data)
