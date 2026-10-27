"""Output eval task persistence — thin CRUD over OutputEvalTask DB model."""
import json
import logging

from sqlalchemy import select

from app.db.models import OutputEvalTask
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def save_task(
    task_id: str,
    dataset_ids: list[str],
    selected_dimensions: list[str] | None = None,
    source: str = "benchmark",
    benchmark_job_id: str | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(OutputEvalTask).where(OutputEvalTask.task_id == task_id)
            )
            record = existing.scalar_one_or_none()
            if record is None:
                record = OutputEvalTask(task_id=task_id)
                db.add(record)
            record.dataset_ids_json = json.dumps(dataset_ids or [], ensure_ascii=False)
            record.selected_dimensions_json = json.dumps(selected_dimensions or [], ensure_ascii=False)
            record.status = "running"
            record.source = source
            if benchmark_job_id:
                record.benchmark_job_id = benchmark_job_id
            await db.commit()
    except Exception:
        logger.warning("Failed to save OutputEvalTask %s", task_id, exc_info=True)


async def get_task_job_id(task_id: str) -> str | None:
    """从 DB 读取 benchmark_job_id（服务重启/多 worker 时的恢复路径）。"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutputEvalTask.benchmark_job_id).where(OutputEvalTask.task_id == task_id)
            )
            row = result.one_or_none()
            return row.benchmark_job_id if row else None
    except Exception:
        logger.warning("Failed to read benchmark_job_id for %s", task_id, exc_info=True)
        return None


async def get_task_dimensions(task_id: str) -> list[str] | None:
    """从 DB 读取 selected_dimensions（服务重启/多 worker/mock 路径的恢复）。"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutputEvalTask.selected_dimensions_json).where(OutputEvalTask.task_id == task_id)
            )
            row = result.one_or_none()
            if row and row.selected_dimensions_json:
                return json.loads(row.selected_dimensions_json)
            return None
    except Exception:
        logger.warning("Failed to read selected_dimensions for %s", task_id, exc_info=True)
        return None


async def update_task_status(task_id: str, status: str, source: str = "") -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutputEvalTask).where(OutputEvalTask.task_id == task_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return
            record.status = status
            if source:
                record.source = source
            from datetime import datetime, timezone
            if status in ("finished", "error"):
                record.finished_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        logger.warning("Failed to update OutputEvalTask %s", task_id, exc_info=True)


async def save_task_results(
    task_id: str,
    metrics: dict,
    samples: list[dict],
    source: str = "",
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutputEvalTask).where(OutputEvalTask.task_id == task_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return
            record.metrics_json = json.dumps(metrics, ensure_ascii=False)
            record.samples_json = json.dumps(samples, ensure_ascii=False)
            record.status = "finished"
            if source:
                record.source = source
            from datetime import datetime, timezone
            record.finished_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        logger.warning("Failed to save results for OutputEvalTask %s", task_id, exc_info=True)
