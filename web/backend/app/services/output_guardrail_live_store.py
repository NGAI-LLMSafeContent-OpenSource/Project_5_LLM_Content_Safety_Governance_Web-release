"""SQLite persistence for output guardrail live-batch jobs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OutputGuardrailLiveJob
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _job_to_dict(record: OutputGuardrailLiveJob) -> dict:
    return {
        "job_id": record.job_id,
        "pack_id": record.pack_id,
        "status": record.status,
        "source": record.source or "live",
        "progress": json.loads(record.progress_json or "{}"),
        "samples": json.loads(record.samples_json or "[]"),
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
    }


async def create_job(job: dict) -> dict:
    async with AsyncSessionLocal() as db:
        record = OutputGuardrailLiveJob(
            job_id=job["job_id"],
            pack_id=job.get("pack_id") or "",
            status=job.get("status") or "pending",
            source=job.get("source") or "live",
            progress_json=json.dumps(job.get("progress") or {}, ensure_ascii=False),
            samples_json=json.dumps(job.get("samples") or [], ensure_ascii=False),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return _job_to_dict(record)


async def get_job(job_id: str) -> dict | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OutputGuardrailLiveJob).where(OutputGuardrailLiveJob.job_id == job_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return _job_to_dict(record)


async def save_job(job: dict) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OutputGuardrailLiveJob).where(OutputGuardrailLiveJob.job_id == job["job_id"])
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise KeyError(job["job_id"])
        record.pack_id = job.get("pack_id") or record.pack_id
        record.status = job.get("status") or record.status
        record.source = job.get("source") or record.source
        record.progress_json = json.dumps(job.get("progress") or {}, ensure_ascii=False)
        record.samples_json = json.dumps(job.get("samples") or [], ensure_ascii=False)
        if job.get("status") in {"finished", "partial", "error"}:
            record.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return _job_to_dict(record)
