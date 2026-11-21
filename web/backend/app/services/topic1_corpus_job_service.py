"""Durable gateway to upstream-owned queues. No local fire-and-forget workers.

Refreshing observes existing work, never starts it again. Unknown submission
outcomes stay unknown until an operator reconciles them with the upstream.
"""
import hashlib
import json
import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic1.corpus_tools import CorpusToolClient, CorpusToolError, result_assets
from app.core.config import get_settings
from app.db.models import Topic1CorpusArchive, Topic1CorpusToolJob, utc_now
from app.schemas.topic1_corpus_jobs import CorpusJobStart

TERMINAL = {"completed", "failed", "cancelled", "submission_unknown"}


class CorpusJobError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configuration(tool: str):
    settings = get_settings()
    url = getattr(settings, f"topic1_{tool}_base_url").strip().rstrip("/")
    if not url:
        raise CorpusJobError(503, "尚未配置此工具的服务，请联系管理员。")
    key = settings.topic1_refinement_api_key.get_secret_value() if tool == "refinement" else ""
    return url, key


def client_for(tool: str, url: str, key: str):
    return CorpusToolClient(tool, url, api_key=key, timeout=get_settings().topic1_corpus_tools_timeout_seconds)


def view(job: Topic1CorpusToolJob) -> dict:
    return {
        "id": job.id, "tool": job.tool, "operation": job.operation,
        "source_name": job.source_name, "sample_count": len(json.loads(job.input_json)),
        "status": job.status, "progress": job.progress, "error_code": job.error_code,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "result_available": job.result_json is not None, "result_sha256": job.result_hash,
    }


async def owned(db: AsyncSession, client_id: str, job_id: str):
    job = await db.scalar(select(Topic1CorpusToolJob).where(Topic1CorpusToolJob.id == job_id, Topic1CorpusToolJob.client_id == client_id))
    if job is None:
        raise CorpusJobError(404, "未找到当前客户端的工具任务。")
    return job


async def list_jobs(db: AsyncSession, client_id: str, offset: int = 0):
    query = select(Topic1CorpusToolJob).where(Topic1CorpusToolJob.client_id == client_id)
    order = (Topic1CorpusToolJob.created_at.desc(), Topic1CorpusToolJob.id.desc())
    jobs = (await db.scalars(query.order_by(*order).offset(offset).limit(31))).all()
    active = (await db.scalars(query.where(Topic1CorpusToolJob.status.notin_(TERMINAL)).order_by(*order))).all()
    return {"items": [view(job) for job in jobs[:30]], "has_more": len(jobs) > 30,
            "active": [view(job) for job in active]}


async def start_job(db: AsyncSession, client_id: str, payload: CorpusJobStart):
    request_hash = digest(payload.model_dump_json())
    existing = await db.scalar(select(Topic1CorpusToolJob).where(Topic1CorpusToolJob.client_id == client_id, Topic1CorpusToolJob.request_id == str(payload.request_id)))
    if existing:
        if existing.request_hash != request_hash:
            raise CorpusJobError(409, "同一提交标识不能用于不同语料或参数。")
        return view(existing)
    url, key = configuration(payload.tool)
    parameters = {}
    if payload.tool == "detection":
        configured = get_settings().topic1_detection_models.get(payload.model_alias)
        if not configured or not configured.get("model") or configured.get("backend") not in {"hf", "vllm"}:
            raise CorpusJobError(422, "所选模型尚未由管理员配置。")
        allowed = {"model", "backend", "tokenizer", "base_url", "device"}
        parameters = {k: v for k, v in configured.items() if k in allowed}
    async with client_for(payload.tool, url, key) as upstream:
        caps = await upstream.capabilities()
        if payload.tool == "detox" and caps.get("backend") != "real":
            raise CorpusJobError(503, "当前去毒服务不是实际运行模式，已阻止提交。")
        job = Topic1CorpusToolJob(
            id=str(uuid4()), client_id=client_id, request_id=str(payload.request_id),
            request_hash=request_hash, tool=payload.tool, operation=payload.operation,
            source_name=payload.source_name, input_json=encode([r.model_dump() for r in payload.records]),
            parameters_json=encode(parameters), endpoint_hash=digest(url), status="submitting",
        )
        db.add(job)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(select(Topic1CorpusToolJob).where(Topic1CorpusToolJob.client_id == client_id, Topic1CorpusToolJob.request_id == str(payload.request_id)))
            if existing and existing.request_hash == request_hash:
                return view(existing)
            raise CorpusJobError(409, "提交发生冲突，请刷新任务列表。")
        try:
            remote = await upstream.start(json.loads(job.input_json), operation=job.operation, parameters=parameters)
            job.upstream_id, job.status, job.progress = remote.task_id, remote.status, remote.progress
        except CorpusToolError as exc:
            # Even a 500 or invalid JSON can occur after upstream queued work.
            job.status = "failed" if exc.code in {"unauthorized", "not_ready", "busy", "not_found"} else "submission_unknown"
            job.error_code = exc.code
        job.updated_at = utc_now()
        await db.commit()
        return view(job)


def safe_result(tool: str, payload: dict) -> dict:
    """Only data fields; never upstream logs, filesystem paths, URLs or config."""
    samples = payload.get("examples" if tool == "detection" else "samples")
    if not isinstance(samples, list):
        raise CorpusToolError("invalid_contract", "工具结果缺少样本列表。")
    allowed = {"id", "sample_id", "text", "raw_text", "executed_text", "program_status",
               "program", "detoxified_texts", "toxicity", "familiarity", "scarcity", "confidence_flag",
               "familiarity_score", "scarcity_score", "scarcity_score_0_100",
               "familiarity_percentile", "scarcity_percentile", "scarcity_label", "high_confidence_label",
               "method"}
    rows = [{k: v for k, v in row.items() if k in allowed and isinstance(v, (str, int, float, bool, type(None)))} for row in samples[:100] if isinstance(row, dict)]
    for source, row in zip((item for item in samples[:100] if isinstance(item, dict)), rows):
        for field in ("raw_id_ex_toxicity", "raw_implicit_toxicity"):
            score = source.get(field)
            if isinstance(score, dict) and isinstance(score.get("toxicity"), (int, float)):
                row[field] = score["toxicity"]
    if any(not row for row in rows):
        raise CorpusToolError("invalid_contract", "工具结果字段不符合约定。")
    if len(rows) != min(len(samples), 100) or any(
        isinstance(value, float) and not math.isfinite(value)
        for row in rows for value in row.values()
    ):
        raise CorpusToolError("invalid_contract", "工具结果包含无效样本或数值。")
    return {"source": "topic1_remote_service", "tool": tool, "samples": rows,
            "assets": result_assets(tool, payload),
            "scope": "upstream_preview", "is_full_dataset": False,
            "sample_identity": "not_verified", "can_replace_source": False}


async def refresh_job(db: AsyncSession, client_id: str, job_id: str, *, cancel: bool = False):
    job = await owned(db, client_id, job_id)
    if job.status in TERMINAL:
        return view(job)
    if not job.upstream_id:
        if job.updated_at < utc_now() - timedelta(seconds=120):
            job.status, job.error_code = "submission_unknown", "submission_interrupted"
            await db.commit()
        return view(job)
    url, key = configuration(job.tool)
    if digest(url) != job.endpoint_hash:
        raise CorpusJobError(409, "服务地址已变化，已暂停查询，避免读取其他实例的同名任务。")
    observed_status = job.status
    async with client_for(job.tool, url, key) as upstream:
        if cancel:
            await upstream.cancel(job.upstream_id)
        remote = await upstream.status(job.upstream_id)
        values = dict(status=remote.status, progress=remote.progress, updated_at=utc_now(), error_code="")
        if remote.status == "completed":
            result = safe_result(job.tool, await upstream.result(job.upstream_id))
            serialized = encode(result)
            if len(serialized.encode("utf-8")) > 4 * 1024 * 1024:
                raise CorpusToolError("invalid_contract", "工具结果预览超过大小限制。")
            values.update(result_json=serialized, result_hash=digest(serialized))
        # A slower poll must not overwrite a terminal state written by another poll.
        await db.execute(update(Topic1CorpusToolJob).where(Topic1CorpusToolJob.id == job.id, Topic1CorpusToolJob.status == observed_status).values(**values))
        await db.commit()
        await db.refresh(job)
    return view(job)


async def get_result(db: AsyncSession, client_id: str, job_id: str):
    job = await owned(db, client_id, job_id)
    if job.status != "completed" or not job.result_json:
        raise CorpusJobError(409, "尚无已确认完成的结果。")
    result = json.loads(job.result_json)
    archived_keys = set((await db.scalars(select(Topic1CorpusArchive.asset_key).where(
        Topic1CorpusArchive.job_id == job.id))).all())
    for asset in result.get("assets", []):
        asset["archived"] = asset["key"] in archived_keys
    return {"job": view(job), "result": result}


async def find_archive(db: AsyncSession, job_id: str, asset_key: str):
    return await db.scalar(select(Topic1CorpusArchive).where(
        Topic1CorpusArchive.job_id == job_id, Topic1CorpusArchive.asset_key == asset_key))


def archive_view(archive: Topic1CorpusArchive):
    return {"id": archive.id, "key": archive.asset_key, "name": archive.name,
            "sha256": archive.sha256, "size_bytes": len(archive.content),
            "archived": True, "created_at": archive.created_at.isoformat()}


async def archive_asset(db: AsyncSession, client_id: str, job_id: str, asset_key: str):
    await owned(db, client_id, job_id)
    existing = await find_archive(db, job_id, asset_key)
    if existing:
        return archive_view(existing)
    name, content = await download_asset(db, client_id, job_id, asset_key)
    # Bytes and metadata commit together: no partial files or orphaned directories.
    if len(content) > 16 * 1024 * 1024:
        raise CorpusJobError(413, "单个归档文件不能超过16MB。")
    archive = Topic1CorpusArchive(id=str(uuid4()), job_id=job_id, asset_key=asset_key,
        name=name, content=content, sha256=hashlib.sha256(content).hexdigest())
    db.add(archive)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await find_archive(db, job_id, asset_key)
        if existing:
            return archive_view(existing)
        raise
    return archive_view(archive)


async def download_asset(db: AsyncSession, client_id: str, job_id: str, asset_key: str):
    job = await owned(db, client_id, job_id)
    archived = await find_archive(db, job_id, asset_key)
    if archived:
        if hashlib.sha256(archived.content).hexdigest() != archived.sha256:
            raise CorpusJobError(409, "归档校验失败，请联系管理员。")
        return archived.name, archived.content
    if job.status != "completed" or not job.result_json:
        raise CorpusJobError(409, "任务尚无可下载结果。")
    asset = next((item for item in json.loads(job.result_json).get("assets", [])
                  if item["key"] == asset_key), None)
    if asset is None:
        raise CorpusJobError(404, "结果文件不存在。")
    url, key = configuration(job.tool)
    if digest(url) != job.endpoint_hash:
        raise CorpusJobError(409, "服务地址已变化，已暂停下载。")
    async with client_for(job.tool, url, key) as upstream:
        content = await upstream.download(job.upstream_id, asset)
    return asset["name"], content
