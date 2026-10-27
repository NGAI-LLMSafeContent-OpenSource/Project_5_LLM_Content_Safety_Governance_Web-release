import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import (
    AgentLog,
    CandidateIndicator,
    MiningInput,
    MiningTask,
    SourceDocument,
)
from app.schemas.mining_inputs import MiningInputSave
from app.services.agent_orchestrator import build_candidate_indicators
from app.services.mining_input_service import get_mining_input, save_mining_input
from app.services.topic1_artifact_service import (
    read_task_artifacts,
    replace_task_artifacts,
)
from app.services.topic1_mining_service import run_topic1_task


async def add_log(
    db: AsyncSession,
    task_id: str,
    agent_name: str,
    status: str,
    message: str,
    *,
    created_at: datetime | None = None,
) -> None:
    db.add(
        AgentLog(
            task_id=task_id,
            agent_name=agent_name,
            status=status,
            message=message,
            created_at=created_at or datetime.utcnow(),
        )
    )
    await db.commit()


def _utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


async def combined_text_for_input(db: AsyncSession, data: dict) -> str:
    parts = [data.get("policy_text") or "", data.get("sample_text") or ""]
    ids = data.get("uploaded_document_ids") or []
    if ids:
        result = await db.execute(select(SourceDocument).where(SourceDocument.id.in_(ids)))
        parts.extend(row.content for row in result.scalars().all())
    parts.extend(data.get("web_links") or [])
    parts.extend(data.get("lookup_names") or [])
    return "\n".join(part for part in parts if part)


async def start_mining_task(
    db: AsyncSession,
    *,
    task_type: str,
    definition_scope: str | None = None,
    input_id: int | None,
    inline_input: MiningInputSave | None,
    parent_task_id: str | None = None,
    retry_count: int = 0,
    runtime_options: dict | None = None,
) -> dict:
    input_id, input_data = await _resolve_task_input(db, input_id, inline_input)
    task = await _create_mining_task_record(
        db=db,
        task_type=task_type,
        definition_scope=definition_scope,
        input_id=input_id,
        input_data=input_data,
        parent_task_id=parent_task_id,
        retry_count=retry_count,
        runtime_options=runtime_options,
    )
    return await _execute_mining_task_flow(
        db=db,
        task=task,
        input_id=input_id,
        input_data=input_data,
    )


async def create_mining_task(
    db: AsyncSession,
    *,
    task_type: str,
    definition_scope: str | None = None,
    input_id: int | None,
    inline_input: MiningInputSave | None,
    parent_task_id: str | None = None,
    retry_count: int = 0,
    runtime_options: dict | None = None,
) -> dict:
    input_id, input_data = await _resolve_task_input(db, input_id, inline_input)
    task = await _create_mining_task_record(
        db=db,
        task_type=task_type,
        definition_scope=definition_scope,
        input_id=input_id,
        input_data=input_data,
        parent_task_id=parent_task_id,
        retry_count=retry_count,
        runtime_options=runtime_options,
    )
    return {
        "task_id": task.task_id,
        "input_id": input_id,
        "task_type": task.task_type,
        "definition_scope": task.definition_scope,
        "subject_area": task.subject_area,
        "parent_task_id": task.parent_task_id,
        "retry_count": task.retry_count,
        "status": task.status,
        "stats": {},
        "progress": 12,
    }


async def run_mining_task_in_background(task_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MiningTask).where(MiningTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        input_data = await get_mining_input(db, task.input_id)
        if input_data is None:
            await _finalize_failed_task(
                db=db,
                task=task,
                input_id=task.input_id,
                error=ValueError("input: mining input not found"),
            )
            return

        try:
            await _execute_mining_task_flow(
                db=db,
                task=task,
                input_id=task.input_id,
                input_data=input_data,
            )
        except Exception as exc:
            await _finalize_failed_task(
                db=db,
                task=task,
                input_id=task.input_id,
                error=exc,
            )


async def _resolve_task_input(
    db: AsyncSession,
    input_id: int | None,
    inline_input: MiningInputSave | None,
) -> tuple[int, dict]:
    if input_id is None:
        if inline_input is None:
            raise ValueError("input_id or input is required")
        input_data = await save_mining_input(db, inline_input)
        input_id = input_data["id"]
    else:
        input_data = await get_mining_input(db, input_id)
        if input_data is None:
            raise ValueError("mining input not found")

    return input_id, input_data


async def _create_mining_task_record(
    db: AsyncSession,
    *,
    task_type: str,
    definition_scope: str | None,
    input_id: int,
    input_data: dict,
    parent_task_id: str | None,
    retry_count: int,
    runtime_options: dict | None,
) -> MiningTask:
    task_id = str(uuid.uuid4())
    task = MiningTask(
        task_id=task_id,
        input_id=input_id,
        definition_type=input_data["definition_type"],
        definition_scope=_resolve_definition_scope(
            definition_scope,
            task_type=task_type,
            definition_type=input_data["definition_type"],
        ),
        task_type=task_type,
        subject_area="topic1" if task_type == "topic1_indicator_mining" else "platform",
        parent_task_id=parent_task_id,
        retry_count=retry_count,
        runtime_options_json=json.dumps(runtime_options or {}, ensure_ascii=False),
        status="running",
        started_at=datetime.utcnow(),
        agent_runtime_json=json.dumps({"mode": task_type}, ensure_ascii=False),
    )
    db.add(task)
    await db.commit()

    await add_log(db, task_id, "System", "started", "任务已创建，并已保存本次输入快照。")
    return task


def _resolve_definition_scope(
    definition_scope: str | None,
    *,
    task_type: str,
    definition_type: str,
) -> str:
    if definition_scope:
        return definition_scope
    if task_type == "topic1_indicator_mining":
        return "input-value"
    if definition_type == "culture":
        return "output-culture"
    if definition_type == "risk":
        return "input-risk"
    return "input-value"


async def _execute_mining_task_flow(
    db: AsyncSession,
    *,
    task: MiningTask,
    input_id: int,
    input_data: dict,
) -> dict:
    try:
        if task.task_type == "topic1_indicator_mining":
            stats = await _run_topic1_task_flow(
                db=db,
                task_id=task.task_id,
                input_data=input_data,
            )
        else:
            stats = await _run_platform_task_flow(
                db=db,
                task_id=task.task_id,
                input_data=input_data,
            )
    except Exception as exc:
        return await _finalize_failed_task(
            db=db,
            task=task,
            input_id=input_id,
            error=exc,
        )

    task.status = "completed"
    task.finished_at = datetime.utcnow()
    task.stats_json = json.dumps(stats, ensure_ascii=False)

    result = await db.execute(select(MiningInput).where(MiningInput.id == input_id))
    mining_input = result.scalar_one()
    mining_input.status = "mined"
    mining_input.updated_at = datetime.utcnow()
    await db.commit()

    await add_log(
        db,
        task.task_id,
        "System",
        "completed",
        f"任务已完成，生成 {stats['candidate_count']} 个候选指标。",
    )
    return {
        "task_id": task.task_id,
        "input_id": input_id,
        "task_type": task.task_type,
        "subject_area": task.subject_area,
        "parent_task_id": task.parent_task_id,
        "retry_count": task.retry_count,
        "status": "completed",
        "stats": stats,
        "progress": 100,
    }


async def _run_topic1_task_flow(
    db: AsyncSession,
    *,
    task_id: str,
    input_data: dict,
) -> dict:
    # 按阶段写入时间线，避免任务结束后批量落库导致时间戳几乎相同
    await add_log(
        db,
        task_id,
        "PolicyTextExtractor",
        "running",
        "正在整理上传文档、网页链接和输入文本。",
    )

    topic1_result = await run_topic1_task(
        db=db,
        task_id=task_id,
        input_data=input_data,
    )
    await replace_task_artifacts(
        db,
        task_id=task_id,
        artifacts=topic1_result["artifacts"],
    )

    stats = topic1_result.get("stats") or {}
    prepared_count = int(
        stats.get("input_text_count") or len(topic1_result.get("prepared_texts") or [])
    )
    matched_count = int(
        stats.get("matched_path_count") or len(topic1_result.get("matched_paths") or [])
    )
    candidate_count = int(
        stats.get("candidate_count") or len(topic1_result.get("candidate_indicators") or [])
    )

    timeline_base = datetime.utcnow()
    await add_log(
        db,
        task_id,
        "PolicyTextExtractor",
        "completed",
        f"清洗得到 {prepared_count} 段可挖掘文本。",
        created_at=timeline_base,
    )
    await add_log(
        db,
        task_id,
        "DimensionMatcher",
        "completed",
        f"匹配到 {matched_count} 条预定指标路径。",
        created_at=timeline_base + timedelta(seconds=1),
    )
    await add_log(
        db,
        task_id,
        "IndicatorGenerator",
        "completed",
        f"生成 {candidate_count} 个候选指标，等待人工审核。",
        created_at=timeline_base + timedelta(seconds=2),
    )

    for item in topic1_result["candidate_indicators"]:
        db.add(
            CandidateIndicator(
                task_id=task_id,
                name=item["name"],
                definition_type=item["definition_type"],
                level1=item["level1"],
                level2=item["level2"],
                level3=item["level3"],
                definition=item["definition"],
                source=item["source"],
                formula=item.get("formula", ""),
                rationale=item.get("rationale", ""),
                evidence_text=item["evidence_text"],
                confidence=item["confidence"],
            )
        )
    return {
        **topic1_result["stats"],
        "adapter_version": topic1_result["adapter_version"],
    }


async def _run_platform_task_flow(
    db: AsyncSession,
    *,
    task_id: str,
    input_data: dict,
) -> dict:
    await add_log(
        db,
        task_id,
        "InformationExtractor",
        "running",
        "正在从输入材料中抽取治理关键词。",
    )
    text = await combined_text_for_input(db, input_data)
    await add_log(
        db,
        task_id,
        "InformationExtractor",
        "completed",
        f"已整理 {len(text)} 字输入材料。",
    )
    await add_log(
        db,
        task_id,
        "DimensionMatcher",
        "running",
        "正在匹配一级、二级指标维度。",
    )
    candidates = build_candidate_indicators(
        definition_type=input_data["definition_type"],
        text=text,
        level1=input_data.get("level1"),
        level2=input_data.get("level2"),
    )
    await add_log(
        db,
        task_id,
        "DimensionMatcher",
        "completed",
        "一级、二级维度匹配完成。",
    )
    await add_log(
        db,
        task_id,
        "IndicatorGenerator",
        "running",
        "正在生成候选指标。",
    )
    for item in candidates:
        db.add(CandidateIndicator(task_id=task_id, **item))
    await add_log(
        db,
        task_id,
        "IndicatorGenerator",
        "completed",
        f"生成 {len(candidates)} 个候选指标，等待人工审核。",
    )
    return {"candidate_count": len(candidates), "input_text_length": len(text)}


async def _finalize_failed_task(
    db: AsyncSession,
    *,
    task: MiningTask,
    input_id: int,
    error: Exception,
) -> dict:
    raw_message = str(error)
    stage, _, message = raw_message.partition(":")
    task.status = "failed"
    task.failure_stage = stage or "task"
    task.error_message = message.strip() or raw_message
    task.finished_at = datetime.utcnow()
    task.stats_json = json.dumps({"candidate_count": 0}, ensure_ascii=False)
    await db.commit()
    await add_log(db, task.task_id, task.failure_stage, "failed", task.error_message)
    logs = await get_task_logs(db, task.task_id)
    return {
        "task_id": task.task_id,
        "input_id": input_id,
        "task_type": task.task_type,
        "subject_area": task.subject_area,
        "parent_task_id": task.parent_task_id,
        "retry_count": task.retry_count,
        "status": "failed",
        "failure_stage": task.failure_stage,
        "stats": {"candidate_count": 0},
        "progress": progress_for_task("failed", logs),
    }


async def get_task(db: AsyncSession, task_id: str) -> dict | None:
    result = await db.execute(select(MiningTask).where(MiningTask.task_id == task_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    logs = await get_task_logs(db, task_id)

    return _serialize_task(row, logs=logs)


def _serialize_task(row: MiningTask, *, logs: list[dict] | None = None) -> dict:
    stats = json.loads(row.stats_json or "{}")
    progress_logs = logs if logs is not None else []
    return {
        "task_id": row.task_id,
        "input_id": row.input_id,
        "definition_type": row.definition_type,
        "definition_scope": row.definition_scope,
        "task_type": row.task_type,
        "subject_area": row.subject_area,
        "parent_task_id": row.parent_task_id,
        "retry_count": row.retry_count,
        "failure_stage": row.failure_stage,
        "status": row.status,
        "stats": stats,
        "progress": progress_for_task(row.status, progress_logs),
        "error_message": row.error_message,
        "started_at": _utc_isoformat(row.started_at) if row.started_at else None,
        "finished_at": _utc_isoformat(row.finished_at) if row.finished_at else None,
        "created_at": _utc_isoformat(row.created_at),
        "candidate_count": int(stats.get("candidate_count") or 0),
        "saved_to_history": bool(getattr(row, "saved_to_history", False)),
        "history_title": getattr(row, "history_title", None),
        "saved_at": _utc_isoformat(row.saved_at)
        if getattr(row, "saved_at", None)
        else None,
    }


async def list_saved_mining_tasks(
    db: AsyncSession,
    *,
    definition_scope: str,
    limit: int = 20,
) -> list[dict]:
    safe_limit = max(1, min(int(limit or 20), 50))
    query = (
        select(MiningTask)
        .where(
            MiningTask.definition_scope == definition_scope,
            MiningTask.saved_to_history.is_(True),
        )
        .order_by(MiningTask.saved_at.desc(), MiningTask.id.desc())
        .limit(safe_limit)
    )
    result = await db.execute(query)
    return [_serialize_task(row, logs=[]) for row in result.scalars().all()]


async def save_mining_task_to_history(
    db: AsyncSession,
    *,
    task_id: str,
    title: str = "",
) -> dict | None:
    result = await db.execute(select(MiningTask).where(MiningTask.task_id == task_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.status != "completed":
        raise ValueError("仅已完成的挖掘任务可以保存到历史记录")

    existing_snapshot = _loads_json_object(row.history_snapshot_json)
    if row.saved_to_history and existing_snapshot.get("candidate_indicators") is not None:
        logs = await get_task_logs(db, task_id)
        return _serialize_task(row, logs=logs)

    cleaned = (title or "").strip()
    if not cleaned:
        finished = row.finished_at or row.created_at
        stamp = finished.strftime("%Y-%m-%d %H:%M") if finished else row.task_id[:8]
        cleaned = f"挖掘记录 {stamp}"

    candidates = await _candidate_payloads(db, task_id)
    saved_at = datetime.utcnow()
    row.saved_to_history = True
    row.history_title = cleaned[:200]
    row.saved_at = saved_at
    row.history_snapshot_json = json.dumps(
        {
            "schema_version": 1,
            "definition_scope": row.definition_scope,
            "saved_at": _utc_isoformat(saved_at),
            "candidate_indicators": candidates,
        },
        ensure_ascii=False,
    )
    await db.commit()
    await db.refresh(row)
    logs = await get_task_logs(db, task_id)
    return _serialize_task(row, logs=logs)


async def get_task_history_results(
    db: AsyncSession,
    task_id: str,
    *,
    definition_scope: str,
) -> dict | None:
    result = await db.execute(select(MiningTask).where(MiningTask.task_id == task_id))
    row = result.scalar_one_or_none()
    if (
        row is None
        or not row.saved_to_history
        or row.definition_scope != definition_scope
    ):
        return None
    snapshot = _loads_json_object(row.history_snapshot_json)
    candidates = snapshot.get("candidate_indicators")
    if not isinstance(candidates, list):
        raise ValueError("历史快照不完整，请返回当前结果页重新保存")
    return {**_serialize_task(row, logs=[]), "candidate_indicators": candidates}


def progress_for_task(status: str, logs: list[dict]) -> int:
    if status == "completed":
        return 100

    progress = 8
    agent_steps = {
        "System": 12,
        "PolicyTextExtractor": 28,
        "InformationExtractor": 28,
        "Project1Adapter": 35,
        "Topic1AlgorithmAdapter": 35,
        "adapter": 35,
        "DimensionMatcher": 55,
        "DimensionExtractorAgent": 55,
        "IndicatorGenerator": 82,
    }
    for log in logs:
        progress = max(progress, agent_steps.get(log["agent_name"], progress))
        if log["status"] == "failed":
            return min(max(progress, 8), 92)
        if log["status"] == "completed":
            progress = max(progress, min(agent_steps.get(log["agent_name"], progress) + 10, 92))
    return progress


async def rerun_task(
    db: AsyncSession,
    *,
    task_id: str,
    comment: str,
) -> dict | None:
    task = await get_task(db, task_id)
    if task is None:
        return None

    return await create_mining_task(
        db,
        task_type=task["task_type"],
        definition_scope=task.get("definition_scope"),
        input_id=task["input_id"],
        inline_input=None,
        parent_task_id=task_id,
        retry_count=task.get("retry_count", 0) + 1,
        runtime_options={"rerun_comment": comment},
    )


async def get_task_results(db: AsyncSession, task_id: str) -> dict | None:
    task = await get_task(db, task_id)
    if task is None:
        return None

    candidates = await _candidate_payloads(db, task_id)
    return {**task, "candidate_indicators": candidates}


async def _candidate_payloads(db: AsyncSession, task_id: str) -> list[dict]:
    result = await db.execute(
        select(CandidateIndicator).where(CandidateIndicator.task_id == task_id)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "definition_type": row.definition_type,
            "level1": row.level1,
            "level2": row.level2,
            "level3": row.level3,
            "definition": row.definition,
            "source": row.source,
            "formula": row.formula,
            "rationale": row.rationale,
            "evidence_text": row.evidence_text,
            "confidence": row.confidence,
            "status": row.status,
        }
        for row in result.scalars().all()
    ]


def _loads_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


async def get_task_artifacts(db: AsyncSession, task_id: str) -> dict | None:
    task = await get_task(db, task_id)
    if task is None:
        return None

    return {"task_id": task_id, "artifacts": await read_task_artifacts(db, task_id)}


async def get_task_logs(db: AsyncSession, task_id: str) -> list[dict]:
    result = await db.execute(
        select(AgentLog).where(AgentLog.task_id == task_id).order_by(AgentLog.id)
    )
    return [
        {
            "id": row.id,
            "task_id": row.task_id,
            "agent_name": row.agent_name,
            "status": row.status,
            "message": row.message,
            "created_at": _utc_isoformat(row.created_at),
        }
        for row in result.scalars().all()
    ]
