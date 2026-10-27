from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import get_db
from app.schemas.indicators import CandidateUpdate, ReviewRequest
from app.services.indicator_service import (
    adopt_candidate,
    get_candidate_history,
    get_indicator_framework,
    reject_candidate,
    update_candidate,
)


router = APIRouter(tags=["indicators"])


@router.post("/api/candidate-indicators/{candidate_id}/adopt")
async def adopt(
    candidate_id: int,
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await adopt_candidate(db, candidate_id, payload.comment)
    if data is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return ok(data)


@router.post("/api/candidate-indicators/{candidate_id}/reject")
async def reject(
    candidate_id: int,
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await reject_candidate(db, candidate_id, payload.comment)
    if data is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return ok(data)


@router.put("/api/candidate-indicators/{candidate_id}")
async def edit(
    candidate_id: int,
    payload: CandidateUpdate,
    db: AsyncSession = Depends(get_db),
):
    data = await update_candidate(db, candidate_id, payload)
    if data is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return ok(data)


@router.get("/api/candidate-indicators/{candidate_id}/history")
async def candidate_history(candidate_id: int, db: AsyncSession = Depends(get_db)):
    data = await get_candidate_history(db, candidate_id)
    if data is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return ok(data)


@router.get("/api/indicators/framework")
async def framework(db: AsyncSession = Depends(get_db)):
    return ok(await get_indicator_framework(db))
