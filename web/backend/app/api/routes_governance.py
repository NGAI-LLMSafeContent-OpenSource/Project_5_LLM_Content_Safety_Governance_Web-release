import asyncio
import json
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.governance import (
    CreateGovernanceShareRequest,
    CulturalPrerunReviewRequest,
    GovernanceShareCreated,
    GovernanceShareReviewPayload,
    GovernanceTaskRetryRequest,
    RiskPrerunReviewRequest,
)
from app.services.governance_cultural_export_service import (
    CulturalExportNotFoundError,
    get_cultural_evidence_pack,
)
from app.services.governance_cultural_review_service import (
    CulturalReviewConflictError,
    CulturalReviewEvidenceError,
    CulturalReviewNotFoundError,
)
from app.services.governance_risk_rescan_export_service import (
    RiskRescanExportNotFoundError,
    get_input_risk_rescan_evidence_pack,
)
from app.services.governance_risk_export_service import (
    RiskExportNotFoundError,
    get_risk_evidence_pack,
)
from app.services.governance_risk_review_service import (
    RiskReviewConflictError,
    RiskReviewEvidenceError,
    RiskReviewNotFoundError,
)
from app.services.governance_session_service import (
    GovernancePlanningContextError,
    GovernanceTaskStateError,
    append_turn,
    cancel_task,
    confirm_task,
    create_cultural_prerun_review,
    create_risk_prerun_review,
    create_session,
    get_session,
    get_task,
    get_task_for_review,
    list_sessions,
    register_client,
    retry_task,
    soft_delete_session,
)
from app.services.governance_skill_catalog import build_skill_catalog
from app.services.governance_suggestions import build_task_suggestions
from app.services.governance_share_service import (
    ACCESS_RESULT_OK,
    apply_share_disclosure,
    classify_share_token,
    create_share,
    emit_review_find_success,
    record_access_event,
    revoke_share,
    scrub_review_actions,
)
from app.services.governance_task_runtime import (
    TERMINAL_TASK_STATUSES,
    list_task_events,
)


router = APIRouter(prefix="/api/governance", tags=["governance"])


class FirstTurn(BaseModel):
    domain: Literal["input", "output"]
    prompt: str
    request_id: UUID | None = None
    # Optional skill-entry key for Skill Runtime (#67 / #84). Ignored when
    # GOVERNANCE_SKILL_RUNTIME_MODE=off.
    requested_skill_key: str | None = None
    # Optional capability key from a bound recommendation. Read-only keys
    # execute with empty parameters; confirmation-required keys still follow
    # the prompt. Unknown keys are rejected.
    requested_capability: str | None = None
    # Optional parameters bound by a control-plane action (for example a list
    # card's "open detail"). Only valid together with ``requested_capability``;
    # the server validates them against that capability's registered model and
    # never hands them to the planner as trusted input.
    requested_parameters: dict[str, Any] | None = None
    # A client must echo both fields to continue the exact durable planning
    # context it last read. Omitting them starts a new goal.
    clarification_plan_id: UUID | None = None
    clarification_plan_version: int | None = None

    @model_validator(mode="after")
    def _bound_parameters_require_a_capability(self) -> "FirstTurn":
        if self.requested_parameters is not None and not (
            self.requested_capability or ""
        ).strip():
            raise ValueError("requested_parameters 只能与 requested_capability 一起提交")
        return self


class ClientRegistration(BaseModel):
    client_id: UUID


@router.get("/skills")
async def list_governance_skills(
    domain: Literal["input", "output"] | None = Query(None),
):
    """Read-only skill catalog; no client header, never hides other domains."""
    return ok(build_skill_catalog(domain))


@router.post("/clients")
async def create_governance_client(
    payload: ClientRegistration,
    db: AsyncSession = Depends(get_db),
):
    return ok(await register_client(db, str(payload.client_id)))


@router.get("/sessions")
async def list_governance_sessions(
    x_governance_client_id: UUID = Header(...),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_sessions(db, str(x_governance_client_id), limit, offset))


@router.post("/sessions", status_code=201)
async def create_governance_session(
    payload: FirstTurn,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="请求不能为空")
    try:
        result = await create_session(
            db,
            str(x_governance_client_id),
            payload.domain,
            payload.prompt,
            str(payload.request_id) if payload.request_id else None,
            requested_skill_key=payload.requested_skill_key,
            requested_capability=payload.requested_capability,
            requested_parameters=payload.requested_parameters,
            clarification_plan_id=(
                str(payload.clarification_plan_id)
                if payload.clarification_plan_id
                else None
            ),
            clarification_plan_version=payload.clarification_plan_version,
        )
    except GovernancePlanningContextError:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ok(result)


@router.get("/sessions/{session_id}")
async def get_governance_session(
    session_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    result = await get_session(db, str(x_governance_client_id), str(session_id))
    if result is None:
        raise HTTPException(status_code=404, detail="治理会话不存在")
    return ok(result)


@router.post("/sessions/{session_id}/turns", status_code=201)
async def add_governance_turn(
    session_id: UUID,
    payload: FirstTurn,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="请求不能为空")
    try:
        result = await append_turn(
            db,
            str(x_governance_client_id),
            str(session_id),
            payload.domain,
            payload.prompt,
            str(payload.request_id) if payload.request_id else None,
            requested_skill_key=payload.requested_skill_key,
            requested_capability=payload.requested_capability,
            requested_parameters=payload.requested_parameters,
            clarification_plan_id=(
                str(payload.clarification_plan_id)
                if payload.clarification_plan_id
                else None
            ),
            clarification_plan_version=payload.clarification_plan_version,
        )
    except GovernancePlanningContextError:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="治理会话不存在")
    return ok(result)


@router.delete("/sessions/{session_id}")
async def delete_governance_session(
    session_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    result = await soft_delete_session(db, str(x_governance_client_id), str(session_id))
    if result is None:
        raise HTTPException(status_code=404, detail="治理会话不存在")
    return ok(result)


@router.post("/sessions/{session_id}/cultural-prerun-reviews", status_code=201)
async def create_governance_cultural_prerun_review(
    session_id: UUID,
    payload: CulturalPrerunReviewRequest,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Explicit UI action (#88): freeze a cultural prerun review.

    Browsing the record catalogue/detail never reaches this endpoint, so a
    review task is only ever created by an explicit user action.
    """
    try:
        result = await create_cultural_prerun_review(
            db,
            str(x_governance_client_id),
            str(session_id),
            payload.record_id,
            payload.record_version,
        )
    except CulturalReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CulturalReviewConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CulturalReviewEvidenceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="治理会话不存在")
    return ok(result)


@router.post("/sessions/{session_id}/risk-prerun-reviews", status_code=201)
async def create_governance_risk_prerun_review(
    session_id: UUID,
    payload: RiskPrerunReviewRequest,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Explicit UI action (#90): freeze a risk classifier prerun review.

    Browsing the risk record catalogue/detail never reaches this endpoint.
    """
    try:
        result = await create_risk_prerun_review(
            db,
            str(x_governance_client_id),
            str(session_id),
            payload.record_id,
            payload.record_version,
        )
    except RiskReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RiskReviewConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RiskReviewEvidenceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="治理会话不存在")
    return ok(result)


@router.get("/tasks/{task_id}/cultural-prerun-review/evidence-pack")
async def get_governance_cultural_prerun_evidence_pack(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """#89: export HTML/CSV/JSON/manifest from the frozen cultural review snapshot."""
    try:
        pack = await get_cultural_evidence_pack(
            db, str(x_governance_client_id), str(task_id)
        )
    except CulturalExportNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ok(pack)


@router.get("/tasks/{task_id}/risk-prerun-review/evidence-pack")
async def get_governance_risk_prerun_evidence_pack(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """#91: export restricted HTML/CSV/JSON/manifest from the frozen risk review snapshot."""
    try:
        pack = await get_risk_evidence_pack(
            db, str(x_governance_client_id), str(task_id)
        )
    except RiskExportNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ok(pack)


@router.get("/tasks/{task_id}/input-risk-rescan/evidence-pack")
async def get_input_risk_rescan_evidence_pack_route(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """#167: HTML/CSV/JSON/manifest projection of the persisted v2 result."""
    try:
        pack = await get_input_risk_rescan_evidence_pack(
            db, str(x_governance_client_id), str(task_id)
        )
    except RiskRescanExportNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ok(pack)


@router.get("/tasks/{task_id}")
async def get_governance_task(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    result = await get_task(db, str(x_governance_client_id), str(task_id))
    if result is None:
        raise HTTPException(status_code=404, detail="治理任务不存在")
    return ok(result)


@router.get("/tasks/{task_id}/suggestions")
async def get_governance_task_suggestions(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    result = await build_task_suggestions(
        db, str(x_governance_client_id), str(task_id)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="治理任务不存在")
    return ok(result.model_dump(mode="json"))


def _sse_event(event: dict) -> str:
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return (
        f"id: {event['sequence']}\n"
        f"event: {event['event_type']}\n"
        f"data: {payload}\n\n"
    )


async def _task_event_stream(
    client_id: str, task_id: str, cursor: int, follow: bool
) -> AsyncIterator[str]:
    while True:
        async with AsyncSessionLocal() as session:
            snapshot = await get_task(session, client_id, task_id)
            if snapshot is None:
                return
            events = await list_task_events(
                session, task_id, after_sequence=cursor
            )
        for event in events:
            cursor = event["sequence"]
            yield _sse_event(event)
        if not follow or snapshot["status"] in TERMINAL_TASK_STATUSES:
            return
        if not events:
            yield ": keep-alive\n\n"
        await asyncio.sleep(0.5)


@router.get("/tasks/{task_id}/events")
async def stream_governance_task_events(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    after: int = Query(0, ge=0),
    follow: bool = Query(True),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    db: AsyncSession = Depends(get_db),
):
    client_id = str(x_governance_client_id)
    task_key = str(task_id)
    if await get_task(db, client_id, task_key) is None:
        raise HTTPException(status_code=404, detail="治理任务不存在")
    try:
        header_cursor = max(0, int(last_event_id or 0))
    except ValueError:
        header_cursor = 0
    cursor = max(after, header_cursor)
    return StreamingResponse(
        _task_event_stream(client_id, task_key, cursor, follow),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_task_action(db, client_id, task_id, action):
    """Shared confirm/cancel/retry handling: state conflicts are 409, a task
    that does not belong to the client is reported as 404."""
    try:
        result = await action(db, client_id, task_id)
    except GovernanceTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="治理任务不存在")
    return ok(result)


@router.post("/tasks/{task_id}/confirm", status_code=202)
async def confirm_governance_task(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    return await _run_task_action(
        db, str(x_governance_client_id), str(task_id), confirm_task
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_governance_task(
    task_id: UUID,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    return await _run_task_action(
        db, str(x_governance_client_id), str(task_id), cancel_task
    )


@router.post("/tasks/{task_id}/retry")
async def retry_governance_task(
    task_id: UUID,
    payload: GovernanceTaskRetryRequest | None = None,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    async def retry_with_payload(db, client_id, task_id):
        return await retry_task(db, client_id, task_id, payload)

    return await _run_task_action(
        db, str(x_governance_client_id), str(task_id), retry_with_payload
    )


# ---------------------------------------------------------------------------
# Review shares (#66 / #77) — append-only; anonymous review has no client header
# ---------------------------------------------------------------------------

_REVIEW_SHARE_NOT_FOUND = "评审分享不存在或已失效"


def _share_expires_at_iso(expires_at) -> str:
    return expires_at.isoformat() + "Z"


@router.post("/tasks/{task_id}/shares", status_code=201)
async def create_governance_task_share(
    task_id: UUID,
    payload: CreateGovernanceShareRequest | None = None,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    body = payload or CreateGovernanceShareRequest()
    created = await create_share(
        db,
        str(x_governance_client_id),
        str(task_id),
        ttl_days=body.ttl_days,
        show_sample_text=body.show_sample_text,
    )
    if created is None:
        raise HTTPException(status_code=404, detail="治理任务不存在")
    token, share = created
    await db.commit()
    data = GovernanceShareCreated(
        share_id=share.share_id,
        task_id=share.task_id,
        token=token,
        expires_at=_share_expires_at_iso(share.expires_at),
        show_sample_text=share.show_sample_text,
        review_path=f"/governance/review/{token}",
    )
    return ok(data.model_dump())


@router.delete("/tasks/{task_id}/shares/{share_id}")
async def revoke_governance_task_share(
    task_id: UUID,
    share_id: str,
    x_governance_client_id: UUID = Header(...),
    db: AsyncSession = Depends(get_db),
):
    share = await revoke_share(
        db, str(x_governance_client_id), str(task_id), share_id
    )
    if share is None:
        raise HTTPException(status_code=404, detail="评审分享不存在")
    await db.commit()
    return ok(
        {
            "share_id": share.share_id,
            "task_id": share.task_id,
            "revoked_at": (
                share.revoked_at.isoformat() + "Z" if share.revoked_at else None
            ),
        }
    )


@router.get("/review/{share_token}")
async def get_governance_review_share(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Anonymous read-only review; no X-Governance-Client-Id required."""
    result, share = await classify_share_token(db, share_token)
    await record_access_event(
        db,
        result=result,
        share_id=share.share_id if share is not None else None,
    )
    if result != ACCESS_RESULT_OK or share is None:
        await db.commit()
        raise HTTPException(status_code=404, detail=_REVIEW_SHARE_NOT_FOUND)

    task_detail = await get_task_for_review(db, share.task_id)
    if task_detail is None:
        await db.commit()
        raise HTTPException(status_code=404, detail=_REVIEW_SHARE_NOT_FOUND)

    filtered = apply_share_disclosure(
        task_detail, show_sample_text=share.show_sample_text
    )
    review_task = scrub_review_actions(filtered)
    await emit_review_find_success(
        db,
        task_id=share.task_id,
        task_detail=review_task,
        session_id=review_task.get("session_id"),
    )
    payload = GovernanceShareReviewPayload(
        share_id=share.share_id,
        task_id=share.task_id,
        expires_at=_share_expires_at_iso(share.expires_at),
        show_sample_text=share.show_sample_text,
        task=review_task,
    )
    await db.commit()
    return ok(payload.model_dump())
