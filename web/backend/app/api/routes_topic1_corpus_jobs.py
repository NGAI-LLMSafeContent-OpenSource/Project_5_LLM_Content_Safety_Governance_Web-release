from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic1.corpus_tools import CorpusToolError
from app.core.config import get_settings
from app.core.response import ok
from app.db.session import get_db
from app.schemas.topic1_corpus_jobs import CorpusJobStart
from app.services import topic1_corpus_job_service as service

router = APIRouter(prefix="/api/data-input/topic1/jobs", tags=["data-input"])


def client_identity(x_input_client_id: UUID = Header(...)) -> str:
    # Same trusted-network deployment boundary as the anonymous governance shell.
    # This isolates browser workspaces, not an account authentication system.
    return str(x_input_client_id)


async def respond(awaitable):
    try:
        return ok(await awaitable)
    except service.CorpusJobError as exc:
        raise HTTPException(exc.status, detail=str(exc)) from exc
    except CorpusToolError as exc:
        raise HTTPException(502, detail=str(exc)) from exc


@router.get("/models")
async def models():
    return ok([{"alias": alias, "label": config.get("label", alias)}
               for alias, config in get_settings().topic1_detection_models.items()])


@router.get("")
async def list_jobs(offset: int = Query(0, ge=0), client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.list_jobs(db, client_id, offset))


@router.post("/fingerprint")
async def fingerprint(payload: CorpusJobStart, client_id: str = Depends(client_identity)):
    # HTTP intranet browsers lack SubtleCrypto; hash without persisting input.
    return ok(service.digest(service.encode(payload.model_dump(mode="json", exclude={"request_id"}))))


@router.post("", status_code=202)
async def start(payload: CorpusJobStart, client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.start_job(db, client_id, payload))


@router.post("/{job_id}/refresh")
async def refresh(job_id: UUID, client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.refresh_job(db, client_id, str(job_id)))


@router.post("/{job_id}/cancel")
async def cancel(job_id: UUID, client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.refresh_job(db, client_id, str(job_id), cancel=True))


@router.get("/{job_id}/result")
async def result(job_id: UUID, client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.get_result(db, client_id, str(job_id)))


@router.get("/{job_id}/assets/{asset_key}")
async def download(job_id: UUID, asset_key: str, client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    try:
        name, content = await service.download_asset(db, client_id, str(job_id), asset_key)
    except service.CorpusJobError as exc:
        raise HTTPException(exc.status, detail=str(exc)) from exc
    except CorpusToolError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return Response(content, media_type="application/octet-stream", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


class ArchiveConfirmation(BaseModel):
    confirmed: Literal[True]


@router.post("/{job_id}/assets/{asset_key}/archive")
async def archive(job_id: UUID, asset_key: str, payload: ArchiveConfirmation,
                  client_id: str = Depends(client_identity), db: AsyncSession = Depends(get_db)):
    return await respond(service.archive_asset(db, client_id, str(job_id), asset_key))
