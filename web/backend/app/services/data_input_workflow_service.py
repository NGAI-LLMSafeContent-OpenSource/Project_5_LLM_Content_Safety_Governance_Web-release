import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataInputWorkflowDraft
from app.schemas.data_input_workflows import DataInputWorkflowSaveRequest

MAX_WORKFLOW_JSON_CHARS = 2_000_000


class WorkflowNotFoundError(ValueError):
    pass


class WorkflowConflictError(ValueError):
    pass


def _json_dumps(value: dict[str, Any]) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) > MAX_WORKFLOW_JSON_CHARS:
        raise ValueError("输入护栏草稿内容过大，请减少本次保存的样本明细后重试")
    return text


def _json_loads(text: str) -> dict[str, Any]:
    if not text:
        return {}
    value = json.loads(text)
    return value if isinstance(value, dict) else {}


def _make_workflow_id() -> str:
    return f"diwf_{datetime.utcnow().strftime('%Y%m%d')}_{secrets.token_hex(4)}"


def _fallback_title(payload: DataInputWorkflowSaveRequest) -> str:
    if payload.title.strip():
        return payload.title.strip()[:200]
    dataset = payload.payload.get("dataset")
    if isinstance(dataset, dict):
        name = str(dataset.get("name") or "").strip()
        if name:
            return name[:200]
    return "输入护栏草稿"


def serialize_workflow_detail(row: DataInputWorkflowDraft) -> dict[str, Any]:
    return {
        "workflowId": row.workflow_id,
        "title": row.title,
        "status": row.status,
        "source": row.source,
        "payload": _json_loads(row.payload_json),
        "summary": _json_loads(row.summary_json),
        "assetRefs": _json_loads(row.asset_refs_json),
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "submittedAt": row.submitted_at,
    }


def serialize_workflow_list_item(row: DataInputWorkflowDraft) -> dict[str, Any]:
    return {
        "workflowId": row.workflow_id,
        "title": row.title,
        "status": row.status,
        "source": row.source,
        "summary": _json_loads(row.summary_json),
        "assetRefs": _json_loads(row.asset_refs_json),
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "submittedAt": row.submitted_at,
    }


def serialize_workflow_save(row: DataInputWorkflowDraft) -> dict[str, Any]:
    return {
        "workflowId": row.workflow_id,
        "status": row.status,
        "savedAt": row.updated_at,
        "title": row.title,
    }


async def save_workflow_draft(
    db: AsyncSession,
    payload: DataInputWorkflowSaveRequest,
) -> dict[str, Any]:
    now = datetime.utcnow()
    if payload.workflow_id.strip():
        row = await _get_row(db, payload.workflow_id.strip())
        if row is None:
            raise WorkflowNotFoundError("未找到输入护栏草稿")
        if row.status != "draft":
            raise WorkflowConflictError("已提交待复核的草稿不能覆盖，请另存一版")
    else:
        row = DataInputWorkflowDraft(
            workflow_id=_make_workflow_id(),
            created_at=now,
        )
        db.add(row)

    row.title = _fallback_title(payload)
    row.status = "draft"
    row.source = payload.source
    row.payload_json = _json_dumps(payload.payload)
    row.summary_json = _json_dumps(payload.summary)
    row.asset_refs_json = _json_dumps(payload.asset_refs)
    row.updated_at = now

    await db.commit()
    await db.refresh(row)
    return serialize_workflow_save(row)


async def submit_workflow(
    db: AsyncSession,
    payload: DataInputWorkflowSaveRequest,
) -> dict[str, Any]:
    now = datetime.utcnow()
    if payload.workflow_id.strip():
        row = await _get_row(db, payload.workflow_id.strip())
        if row is None:
            raise WorkflowNotFoundError("未找到输入护栏草稿")
        if row.status != "draft":
            raise WorkflowConflictError("只有草稿状态可以提交待复核")
        if payload.payload:
            row.payload_json = _json_dumps(payload.payload)
        if payload.summary:
            row.summary_json = _json_dumps(payload.summary)
        if payload.asset_refs:
            row.asset_refs_json = _json_dumps(payload.asset_refs)
        if payload.title.strip():
            row.title = payload.title.strip()[:200]
        row.source = payload.source
    else:
        row = DataInputWorkflowDraft(
            workflow_id=_make_workflow_id(),
            title=_fallback_title(payload),
            source=payload.source,
            payload_json=_json_dumps(payload.payload),
            summary_json=_json_dumps(payload.summary),
            asset_refs_json=_json_dumps(payload.asset_refs),
            created_at=now,
        )
        db.add(row)

    row.status = "submitted"
    row.updated_at = now
    row.submitted_at = now

    await db.commit()
    await db.refresh(row)
    return serialize_workflow_save(row)


async def get_workflow_detail(
    db: AsyncSession,
    workflow_id: str,
) -> dict[str, Any] | None:
    row = await _get_row(db, workflow_id)
    return serialize_workflow_detail(row) if row else None


async def list_workflows(
    db: AsyncSession,
    *,
    status: str | None = None,
    source: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    stmt = select(DataInputWorkflowDraft)
    if status:
        stmt = stmt.where(DataInputWorkflowDraft.status == status)
    if source:
        stmt = stmt.where(DataInputWorkflowDraft.source == source)
    stmt = stmt.order_by(desc(DataInputWorkflowDraft.updated_at)).limit(limit)
    result = await db.execute(stmt)
    return {"items": [serialize_workflow_list_item(row) for row in result.scalars().all()]}


async def _get_row(
    db: AsyncSession,
    workflow_id: str,
) -> DataInputWorkflowDraft | None:
    result = await db.execute(
        select(DataInputWorkflowDraft).where(DataInputWorkflowDraft.workflow_id == workflow_id)
    )
    return result.scalar_one_or_none()
