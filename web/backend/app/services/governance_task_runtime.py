"""Database-backed leases and persistent safe events for governance workers."""

from __future__ import annotations

import asyncio
import importlib
import json
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GovernanceCapabilityStep,
    GovernanceCompletionRecord,
    GovernanceMessage,
    GovernanceSession,
    GovernanceSkillRun,
    GovernanceTask,
    GovernanceTaskEvent,
    GovernanceTaskLease,
    utc_now,
)
from app.db.session import AsyncSessionLocal
from app.schemas.governance import GovernanceValidatedSkillPlan
from app.services.governance_product_metrics import emit_product_event
from app.services.governance_risk_report_service import (
    build_completed_payload,
    build_notice_payload,
)
from app.services.governance_risk_rescan_service import (
    capability_version_from_scope,
    derive_source_revision,
    sample_content_digest,
)
from app.services.governance_skills import SkillContractError, validate_step_completion
from app.services.governance_capability_run_service import (
    load_capability_run_by_skill_run,
    mark_status,
)
from app.services.governance_task_adapter import adapter_for


TERMINAL_TASK_STATUSES = frozenset(
    {"completed", "completed_partial", "failed", "timeout", "cancelled"}
)
_COUNT_KEYS = frozenset({"completed", "failed", "total"})
_RESOURCE_REF_KEYS = frozenset({"ref_type", "ref_id", "name"})


def _sample_fact_tuple(sample: dict | object) -> tuple[str, str, str, str]:
    if isinstance(sample, dict):
        sample_id = str(sample.get("sample_id") or "")
        text = str(sample.get("text") or "")
        content_digest = str(sample.get("content_digest") or "") or sample_content_digest(
            text
        )
        source = str(sample.get("source") or "")
        source_revision = str(
            sample.get("source_revision") or ""
        ) or derive_source_revision(source, sample_id, content_digest)
        return (
            sample_id,
            content_digest,
            str(sample.get("reference_label") or ""),
            source_revision,
        )
    return (
        str(getattr(sample, "sample_id", "") or ""),
        str(getattr(sample, "content_digest", "") or ""),
        str(getattr(sample, "reference_label", "") or ""),
        str(getattr(sample, "source_revision", "") or ""),
    )


def _scope_matches_plan(scope: dict, plan: GovernanceValidatedSkillPlan) -> bool:
    preview_facts = [_sample_fact_tuple(sample) for sample in scope.get("samples") or []]
    plan_facts = [_sample_fact_tuple(fact) for fact in plan.scope.samples]
    return preview_facts == plan_facts


@dataclass(frozen=True)
class TaskClaim:
    task_id: str
    lease_token: str
    recovered: bool


def _safe_counts(counts: dict[str, int]) -> dict[str, int]:
    if not set(counts).issubset(_COUNT_KEYS):
        raise ValueError("任务事件计数包含未允许字段")
    safe = {key: int(value) for key, value in counts.items()}
    if any(value < 0 for value in safe.values()):
        raise ValueError("任务事件计数不得为负数")
    return safe


def _safe_resource_refs(resource_refs: list[dict]) -> list[dict]:
    safe: list[dict] = []
    for item in resource_refs:
        if not set(item).issubset(_RESOURCE_REF_KEYS):
            raise ValueError("任务事件资源引用包含未允许字段")
        ref_type = str(item.get("ref_type") or "").strip()
        ref_id = str(item.get("ref_id") or "").strip()
        if not ref_type or not ref_id:
            raise ValueError("任务事件资源引用缺少类型或标识")
        normalized = {"ref_type": ref_type, "ref_id": ref_id}
        if item.get("name"):
            normalized["name"] = str(item["name"])
        safe.append(normalized)
    return safe


async def claim_next_task(
    db: AsyncSession, worker_id: str, *, lease_seconds: int = 30
) -> TaskClaim | None:
    """Claim one queued task, or recover one whose running lease expired."""

    now = utc_now()
    candidates = (
        await db.execute(
            select(GovernanceTask, GovernanceTaskLease)
            .outerjoin(
                GovernanceTaskLease,
                GovernanceTaskLease.task_id == GovernanceTask.task_id,
            )
            .where(
                or_(
                    GovernanceTask.status == "queued",
                    (
                        (GovernanceTask.status.in_(("running", "cancelling")))
                        & or_(
                            GovernanceTaskLease.task_id.is_(None),
                            GovernanceTaskLease.leased_until < now,
                        )
                    ),
                )
            )
            .order_by(GovernanceTask.created_at, GovernanceTask.id)
            .limit(20)
        )
    ).all()

    for task, lease in candidates:
        token = str(uuid4())
        leased_until = now + timedelta(seconds=max(1, lease_seconds))
        recovered = lease is not None
        if lease is None:
            try:
                async with db.begin_nested():
                    db.add(
                        GovernanceTaskLease(
                            task_id=task.task_id,
                            worker_id=worker_id,
                            lease_token=token,
                            leased_until=leased_until,
                            attempt=1,
                            updated_at=now,
                        )
                    )
                    await db.flush()
            except IntegrityError:
                continue
        else:
            acquired = await db.execute(
                update(GovernanceTaskLease)
                .where(
                    GovernanceTaskLease.task_id == task.task_id,
                    GovernanceTaskLease.leased_until < now,
                )
                .values(
                    worker_id=worker_id,
                    lease_token=token,
                    leased_until=leased_until,
                    attempt=GovernanceTaskLease.attempt + 1,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if acquired.rowcount != 1:
                continue

        claimed = await db.execute(
            update(GovernanceTask)
            .where(
                GovernanceTask.task_id == task.task_id,
                GovernanceTask.status.in_(("queued", "running", "cancelling")),
            )
            .values(
                status="cancelling" if task.status == "cancelling" else "running",
                finished_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount == 1:
            return TaskClaim(task_id=task.task_id, lease_token=token, recovered=recovered)
    return None


async def renew_task_lease(
    db: AsyncSession,
    task_id: str,
    worker_id: str,
    lease_token: str,
    *,
    lease_seconds: int = 30,
) -> bool:
    now = utc_now()
    renewed = await db.execute(
        update(GovernanceTaskLease)
        .where(
            GovernanceTaskLease.task_id == task_id,
            GovernanceTaskLease.worker_id == worker_id,
            GovernanceTaskLease.lease_token == lease_token,
            GovernanceTaskLease.leased_until >= now,
        )
        .values(
            leased_until=now + timedelta(seconds=max(1, lease_seconds)),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    return renewed.rowcount == 1


async def append_task_event(
    db: AsyncSession,
    task_id: str,
    *,
    event_type: str,
    stage: str,
    counts: dict[str, int],
    resource_refs: list[dict],
) -> GovernanceTaskEvent:
    if not event_type.strip() or not stage.strip():
        raise ValueError("任务事件必须包含类型和阶段")
    last_sequence = await db.scalar(
        select(func.max(GovernanceTaskEvent.sequence)).where(
            GovernanceTaskEvent.task_id == task_id
        )
    )
    event = GovernanceTaskEvent(
        task_id=task_id,
        sequence=int(last_sequence or 0) + 1,
        event_type=event_type.strip(),
        stage=stage.strip(),
        counts_json=json.dumps(_safe_counts(counts), ensure_ascii=False),
        resource_refs_json=json.dumps(
            _safe_resource_refs(resource_refs), ensure_ascii=False
        ),
        created_at=utc_now(),
    )
    db.add(event)
    await db.flush()
    return event


async def _emit_time_to_first_event_ms(
    db: AsyncSession,
    *,
    task: GovernanceTask,
    run: GovernanceSkillRun,
    event_created_at,
    domain: str = "",
) -> None:
    """Emit once for confirm → first post-confirm progress SSE event latency."""

    if run.confirmed_at is None:
        return
    delta = event_created_at - run.confirmed_at
    latency_ms = max(0, int(delta.total_seconds() * 1000))
    await emit_product_event(
        db,
        "time_to_first_event_ms",
        session_id=task.session_id,
        task_id=task.task_id,
        attributes={
            "domain": domain,
            "capability": task.capability or "",
            "skill_key": run.skill_key,
            "skill_version": run.skill_version,
            "latency_ms": latency_ms,
            "status": "ok",
            "attempt": run.attempt,
            "provider": task.provider or "",
        },
        occurred_at=event_created_at,
    )


async def _emit_runtime_terminal_product_events(
    db: AsyncSession,
    *,
    task: GovernanceTask,
    run: GovernanceSkillRun,
    status: str,
    partial: bool,
    domain: str,
    now,
) -> None:
    """Emit task_completed / task_completed_partial for Worker terminal statuses."""

    if status == "completed":
        event_name = "task_completed"
    elif status == "completed_partial":
        event_name = "task_completed_partial"
    else:
        return
    await emit_product_event(
        db,
        event_name,
        session_id=task.session_id,
        task_id=task.task_id,
        attributes={
            "domain": domain,
            "capability": task.capability or "",
            "skill_key": run.skill_key,
            "skill_version": run.skill_version,
            "status": status,
            "provider": task.provider or "",
            "partial": partial or status == "completed_partial",
            "attempt": run.attempt,
        },
        occurred_at=now,
    )


def serialize_task_event(event: GovernanceTaskEvent) -> dict:
    return {
        "sequence": event.sequence,
        "event_type": event.event_type,
        "stage": event.stage,
        "counts": json.loads(event.counts_json),
        "resource_refs": json.loads(event.resource_refs_json),
        "created_at": event.created_at.isoformat() + "Z",
    }


async def list_task_events(
    db: AsyncSession, task_id: str, *, after_sequence: int = 0
) -> list[dict]:
    result = await db.execute(
        select(GovernanceTaskEvent)
        .where(
            GovernanceTaskEvent.task_id == task_id,
            GovernanceTaskEvent.sequence > max(0, after_sequence),
        )
        .order_by(GovernanceTaskEvent.sequence)
    )
    return [serialize_task_event(event) for event in result.scalars()]


def _json_object(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_results_service():
    """Load #64's sample-result store without coupling #63 deployments to it."""

    try:
        return importlib.import_module("app.services.governance_run_results")
    except ModuleNotFoundError as exc:
        if exc.name != "app.services.governance_run_results":
            raise
        return None


def _result_dict(result: dict | object) -> dict:
    if isinstance(result, dict):
        return dict(result)
    data = {
        key: getattr(result, key)
        for key in (
            "sample_id",
            "status",
            "outcome",
            "reason",
            "completed_at",
        )
        if hasattr(result, key)
    }
    if isinstance(data.get("outcome"), str):
        data["outcome"] = _json_object(data["outcome"])
    return data


async def list_persisted_sample_results(
    db: AsyncSession, task: GovernanceTask, run: GovernanceSkillRun
) -> list[dict]:
    """Read per-sample checkpoints through the storage slice's stable seam."""

    service = _run_results_service()
    if service is not None:
        results = await service.list_run_sample_results(db, run.run_id)
        return [_result_dict(result) for result in results]
    parameters = _json_object(task.parameters_json)
    return [
        dict(result)
        for result in parameters.get("_runtime_sample_results", [])
        if isinstance(result, dict) and result.get("run_id") == run.run_id
    ]


async def _save_sample_result(
    db: AsyncSession,
    task: GovernanceTask,
    run: GovernanceSkillRun,
    *,
    sample_id: str,
    status: str,
    outcome: dict,
    reason: str | None,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
    completed_at,
) -> None:
    service = _run_results_service()
    if service is not None:
        await service.save_sample_result(
            db,
            task_id=task.task_id,
            run_id=run.run_id,
            sample_id=sample_id,
            status=status,
            outcome=outcome,
            reason=reason,
            capability_version=capability_version,
            result_schema=result_schema,
            executor_fingerprint=executor_fingerprint,
            completed_at=completed_at,
        )
        return
    parameters = _json_object(task.parameters_json)
    results = [
        item
        for item in parameters.get("_runtime_sample_results", [])
        if not (
            isinstance(item, dict)
            and item.get("run_id") == run.run_id
            and item.get("sample_id") == sample_id
        )
    ]
    results.append(
        {
            "run_id": run.run_id,
            "sample_id": sample_id,
            "status": status,
            "outcome": dict(outcome),
            "reason": reason or "",
            "completed_at": completed_at.isoformat() + "Z",
        }
    )
    parameters["_runtime_sample_results"] = results
    task.parameters_json = json.dumps(parameters, ensure_ascii=False)


async def _mark_remaining_samples(
    db: AsyncSession,
    task: GovernanceTask,
    run: GovernanceSkillRun,
    *,
    sample_ids: list[str],
    reason: str,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
    completed_at,
) -> None:
    if not sample_ids:
        return
    service = _run_results_service()
    if service is not None:
        await service.mark_remaining_samples(
            db,
            task_id=task.task_id,
            run_id=run.run_id,
            sample_ids=sample_ids,
            reason=reason,
            capability_version=capability_version,
            result_schema=result_schema,
            executor_fingerprint=executor_fingerprint,
            completed_at=completed_at,
        )
        return
    for sample_id in sample_ids:
        await _save_sample_result(
            db,
            task,
            run,
            sample_id=sample_id,
            status="not_executed",
            outcome={},
            reason=reason,
            capability_version=capability_version,
            result_schema=result_schema,
            executor_fingerprint=executor_fingerprint,
            completed_at=completed_at,
        )


def _sample_counts(results: list[dict], total: int) -> dict[str, int]:
    return {
        "completed": sum(
            result.get("status") in {"consistent", "inconsistent"}
            for result in results
        ),
        "failed": sum(result.get("status") == "failed" for result in results),
        "total": total,
    }


def _failed_sample_outcome(
    sample: dict, reason: str, method: str = "", adapter_status: str = "failed"
) -> dict:
    return {
        "sample_id": str(sample.get("sample_id") or ""),
        "text": str(sample.get("text") or ""),
        "reference_label": str(sample.get("reference_label") or ""),
        "detected_label": "",
        "status": "failed",
        "reason": reason,
        "source": str(sample.get("source") or ""),
        "content_digest": str(sample.get("content_digest") or ""),
        "source_revision": str(sample.get("source_revision") or ""),
        "adapter_method": method,
        "adapter_status": adapter_status,
    }


def _assert_scope_text_matches_digests(scope: dict) -> None:
    """Reject tampered preview text that keeps the original content_digest."""

    for sample in scope.get("samples") or []:
        if not isinstance(sample, dict):
            continue
        text_value = str(sample.get("text") or "")
        digest = str(sample.get("content_digest") or "")
        if text_value and digest and sample_content_digest(text_value) != digest:
            raise SkillContractError(
                "confirmation_invalidated",
                "执行样本事实与已确认计划不一致，已中止检测。",
            )


_EXECUTED_CHECKPOINT_STATUSES = frozenset({"consistent", "inconsistent", "failed"})
_CANCEL_NOT_EXECUTED_REASON = "用户请求取消，样本未执行。"
_TRANSPORT_ABORT_REASON = "上游检测中断，未执行后续样本。"
_INTERRUPT_RECOVERY_REASON = "执行中断，未重复调用上游检测。"


def _has_executed_checkpoint(persisted: list[dict]) -> bool:
    return any(
        str(result.get("status") or "") in _EXECUTED_CHECKPOINT_STATUSES
        for result in persisted
    )


def _usable_executed_count(persisted: list[dict]) -> int:
    return sum(
        1
        for result in persisted
        if result.get("status") in {"consistent", "inconsistent", "failed"}
        and str((result.get("outcome") or {}).get("adapter_status") or "")
        == "completed"
    )


def _result_sample_from_row(
    frozen: dict,
    row: dict | None,
    *,
    run_id: str,
    capability_version: str,
) -> dict:
    sample_id = str(frozen.get("sample_id") or "")
    base = {
        "sample_id": sample_id,
        "text": str(frozen.get("text") or ""),
        "reference_label": str(frozen.get("reference_label") or ""),
        "source": str(frozen.get("source") or ""),
        "content_digest": str(frozen.get("content_digest") or ""),
        "source_revision": str(frozen.get("source_revision") or ""),
        "run_id": run_id,
        "capability_version": capability_version,
    }
    if row is None:
        return {
            **base,
            "detected_label": "",
            "status": "not_executed",
            "reason": "",
            "completed_at": "",
        }
    status = str(row.get("status") or "failed")
    if status == "not_executed":
        return {
            **base,
            "detected_label": "",
            "status": "not_executed",
            "reason": str(row.get("reason") or ""),
            "completed_at": "",
            "capability_version": str(row.get("capability_version") or capability_version),
        }
    outcome = dict(row.get("outcome") or {})
    return {
        **base,
        "detected_label": str(outcome.get("detected_label") or ""),
        "status": status,
        "reason": str(row.get("reason") or outcome.get("reason") or ""),
        "completed_at": str(row.get("completed_at") or ""),
        "capability_version": str(row.get("capability_version") or capability_version),
    }


def _build_run_outcome_from_persisted(
    *,
    scope: dict,
    samples: list[dict],
    persisted: list[dict],
    run_id: str,
    capability_version: str,
) -> dict:
    by_id = {str(result.get("sample_id") or ""): result for result in persisted}
    result_samples = [
        _result_sample_from_row(
            sample,
            by_id.get(str(sample.get("sample_id") or "")),
            run_id=run_id,
            capability_version=capability_version,
        )
        for sample in samples
    ]
    consistent = sum(
        sample.get("status") == "consistent" for sample in result_samples
    )
    inconsistent = sum(
        sample.get("status") == "inconsistent" for sample in result_samples
    )
    failed = sum(sample.get("status") == "failed" for sample in result_samples)
    not_executed = sum(
        sample.get("status") == "not_executed" for sample in result_samples
    )
    method = next(
        (
            str((result.get("outcome") or {}).get("adapter_method") or "")
            for result in persisted
            if (result.get("outcome") or {}).get("adapter_method")
        ),
        "",
    )
    return {
        "method": method,
        "samples": result_samples,
        "summary": {
            "consistent_count": consistent,
            "inconsistent_count": inconsistent,
            "failed_count": failed,
            "not_executed_count": not_executed,
        },
    }


def _should_write_run_result(status: str, usable_count: int) -> bool:
    if status in {"completed", "completed_partial"}:
        return usable_count > 0
    return usable_count > 0 and status in {"cancelled", "failed", "timeout"}


async def _write_terminal_state(
    worker: GovernanceTaskWorker,
    db: AsyncSession,
    claim: TaskClaim,
    *,
    task: GovernanceTask,
    run: GovernanceSkillRun,
    execute_step: GovernanceCapabilityStep,
    plan: GovernanceValidatedSkillPlan,
    execute_step_id: str,
    scope: dict,
    samples: list[dict],
    persisted: list[dict],
    status: str,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
    total: int,
    now,
    error_message: str | None = None,
) -> None:
    counts = _sample_counts(persisted, total)
    # Carry the frozen executor identity into the result projection so the v2
    # contract records which adapter/model actually produced the judgement.
    scope = {**scope, "executor_identity": plan.scope.executor.model_dump()}
    usable_count = _usable_executed_count(persisted)
    not_executed_count = sum(
        1 for result in persisted if result.get("status") == "not_executed"
    )
    partial = status != "completed" or not_executed_count > 0
    result_completion_id: str | None = None
    if _should_write_run_result(status, usable_count):
        outcome = _build_run_outcome_from_persisted(
            scope=scope,
            samples=samples,
            persisted=persisted,
            run_id=run.run_id,
            capability_version=capability_version,
        )
        payload, content = build_completed_payload(
            scope,
            outcome,
            task.task_id,
            now.isoformat() + "Z",
            run_status=status,
            partial=partial,
        )
        validate_step_completion(
            plan,
            execute_step_id,
            payload,
            allow_partial=True,
        )
        task.status = status
        task.error_message = error_message
        task.finished_at = now
        message = GovernanceMessage(
            session_id=task.session_id,
            client_id=task.client_id,
            request_id=str(uuid4()),
            role="assistant",
            kind=task.capability or "risk_corpus_rescan",
            content=content,
            payload_json=json.dumps(payload, ensure_ascii=False),
            created_at=now,
        )
        db.add(message)
        await db.flush()
        completion = GovernanceCompletionRecord(
            completion_id=str(uuid4()),
            task_id=task.task_id,
            session_id=task.session_id,
            message_id=message.id,
            capability=task.capability or "",
            capability_version=capability_version_from_scope(scope),
            result_snapshot_json=json.dumps(payload, ensure_ascii=False),
            source_refs_json=json.dumps(
                payload.get("source_refs", []), ensure_ascii=False
            ),
            completed_at=now,
        )
        db.add(completion)
        result_completion_id = completion.completion_id
        run.status = status
        execute_step.status = status
    else:
        persisted_reason = next(
            (
                str(result.get("reason") or "")
                for result in persisted
                if result.get("status") == "failed" and result.get("reason")
            ),
            "",
        )
        reason = error_message or (
            "用户已取消任务，未执行样本已保留。"
            if status == "cancelled"
            else persisted_reason or "全部样本检测失败，逐样本原因已保留。"
        )
        task.status = status
        task.error_message = reason
        task.finished_at = now
        notice_method = next(
            (
                str((result.get("outcome") or {}).get("adapter_method") or "")
                for result in persisted
                if (result.get("outcome") or {}).get("adapter_method")
            ),
            "",
        )
        payload, content = build_notice_payload(
            task.task_id,
            task.status,
            reason,
            capability_version_from_scope(scope),
            scope=scope,
            persisted=persisted,
            method=notice_method,
        )
        db.add(
            GovernanceMessage(
                session_id=task.session_id,
                client_id=task.client_id,
                request_id=str(uuid4()),
                role="assistant",
                kind=task.capability or "risk_corpus_rescan",
                content=content,
                payload_json=json.dumps(payload, ensure_ascii=False),
                created_at=now,
            )
        )
        run.status = task.status
        execute_step.status = task.status

    capability_run = await load_capability_run_by_skill_run(db, run.run_id)
    if capability_run is not None:
        if status == "cancelled":
            failure_phase = "cancelled"
        elif status == "timeout":
            failure_phase = "timeout"
        else:
            failure_phase = "execution" if status == "failed" else None
        mark_status(
            capability_run,
            task.status,
            now=now,
            finished=True,
            result_ref=result_completion_id,
            error_code="cancelled" if status == "cancelled" else None,
            error_message=task.error_message if status != "completed" else None,
            failure_phase=failure_phase,
        )

    session = await db.get(GovernanceSession, task.session_id)
    if session is not None:
        session.updated_at = now
    await append_task_event(
        db,
        task.task_id,
        event_type=(
            "result"
            if _should_write_run_result(status, usable_count)
            else "cancelled"
            if status == "cancelled"
            else "failure"
        ),
        stage=status,
        counts=counts,
        resource_refs=[],
    )
    await _emit_runtime_terminal_product_events(
        db,
        task=task,
        run=run,
        status=status,
        partial=partial,
        domain=session.domain if session is not None else "",
        now=now,
    )
    await worker._release_lease(db, claim)
    await db.commit()


class LeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the task lease and must stop."""


class GovernanceTaskWorker:
    """One independent worker process using only database-owned state."""

    def __init__(self, worker_id: str, *, lease_seconds: int = 30) -> None:
        self.worker_id = worker_id
        self.lease_seconds = max(3, lease_seconds)

    async def run_once(self) -> bool:
        async with AsyncSessionLocal() as db:
            claim = await claim_next_task(
                db, self.worker_id, lease_seconds=self.lease_seconds
            )
            await db.commit()
        if claim is None:
            return False

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat(claim, stop_heartbeat, lease_lost),
            name=f"governance-lease-{claim.task_id}",
        )
        try:
            await self._execute(claim, lease_lost)
        except LeaseLostError:
            return True
        except Exception as exc:  # noqa: BLE001
            await self._fail_claim(claim, exc)
        finally:
            stop_heartbeat.set()
            await heartbeat
        return True

    async def _heartbeat(
        self,
        claim: TaskClaim,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            async with AsyncSessionLocal() as db:
                renewed = await renew_task_lease(
                    db,
                    claim.task_id,
                    self.worker_id,
                    claim.lease_token,
                    lease_seconds=self.lease_seconds,
                )
                await db.commit()
            if not renewed:
                lease_lost.set()
                return

    async def _still_holds_lease(self, claim: TaskClaim) -> bool:
        async with AsyncSessionLocal() as db:
            renewed = await renew_task_lease(
                db,
                claim.task_id,
                self.worker_id,
                claim.lease_token,
                lease_seconds=self.lease_seconds,
            )
            await db.commit()
            return renewed

    async def _ensure_lease(
        self, claim: TaskClaim, lease_lost: asyncio.Event
    ) -> None:
        if lease_lost.is_set() or not await self._still_holds_lease(claim):
            lease_lost.set()
            raise LeaseLostError("治理任务租约已丢失，停止本 Worker 写入。")

    async def _release_lease(self, db: AsyncSession, claim: TaskClaim) -> None:
        await db.execute(
            delete(GovernanceTaskLease).where(
                GovernanceTaskLease.task_id == claim.task_id,
                GovernanceTaskLease.lease_token == claim.lease_token,
            )
        )

    async def _execute(self, claim: TaskClaim, lease_lost: asyncio.Event) -> None:
        async with AsyncSessionLocal() as db:
            task = (
                await db.execute(
                    select(GovernanceTask).where(
                        GovernanceTask.task_id == claim.task_id
                    )
                )
            ).scalar_one()
            run = (
                await db.execute(
                    select(GovernanceSkillRun)
                    .where(GovernanceSkillRun.task_id == claim.task_id)
                    .order_by(
                        GovernanceSkillRun.created_at.desc(),
                        GovernanceSkillRun.id.desc(),
                    )
                )
            ).scalars().first()
            if run is None:
                raise ValueError("治理任务缺少可执行技能运行")
            steps = (
                await db.execute(
                    select(GovernanceCapabilityStep)
                    .where(GovernanceCapabilityStep.run_id == run.run_id)
                    .order_by(GovernanceCapabilityStep.position)
                )
            ).scalars().all()
            execute_step = next(step for step in steps if step.action == "execute")
            scope = _json_object(task.parameters_json).get("frozen_scope") or {}
            total = len(scope.get("samples") or [])
            existing_events = await list_task_events(db, task.task_id, after_sequence=0)
            # Events carry no run id, so scope the "already emitted" guard to
            # this run by ignoring stages written by earlier attempts.
            run_created_at = run.created_at.isoformat() + "Z"
            existing_stages = {
                event["stage"]
                for event in existing_events
                if str(event.get("created_at") or "") >= run_created_at
            }
            already_terminal = (
                run.status in TERMINAL_TASK_STATUSES
                or execute_step.status in TERMINAL_TASK_STATUSES
            )
            if already_terminal:
                if task.status not in TERMINAL_TASK_STATUSES:
                    recovered = (
                        run.status
                        if run.status in TERMINAL_TASK_STATUSES
                        else execute_step.status
                    )
                    task.status = (
                        recovered if recovered in TERMINAL_TASK_STATUSES else "failed"
                    )
                    if task.finished_at is None:
                        task.finished_at = utc_now()
                await self._release_lease(db, claim)
                await db.commit()
                return

            plan = GovernanceValidatedSkillPlan.model_validate_json(run.plan_json)
            execute_plan_step = next(
                step for step in plan.steps if step.action == "execute"
            )
            if not _scope_matches_plan(scope, plan):
                raise SkillContractError(
                    "confirmation_invalidated",
                    "执行样本事实与已确认计划不一致，已中止检测。",
                )
            _assert_scope_text_matches_digests(scope)

            capability_version = execute_plan_step.capability_version
            result_schema = plan.result_schema
            executor_fingerprint = plan.scope.executor.implementation_fingerprint
            scope_samples = list(scope.get("samples") or [])
            await db.refresh(task)
            persisted_pre = await list_persisted_sample_results(db, task, run)
            early_now = utc_now()
            if task.status == "cancelling" and not _has_executed_checkpoint(
                persisted_pre
            ):
                await _mark_remaining_samples(
                    db,
                    task,
                    run,
                    sample_ids=[
                        str(sample.get("sample_id") or "") for sample in scope_samples
                    ],
                    reason=_CANCEL_NOT_EXECUTED_REASON,
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    completed_at=early_now,
                )
                persisted_pre = await list_persisted_sample_results(db, task, run)
                await _write_terminal_state(
                    self,
                    db,
                    claim,
                    task=task,
                    run=run,
                    execute_step=execute_step,
                    plan=plan,
                    execute_step_id=execute_plan_step.step_id,
                    scope=scope,
                    samples=scope_samples,
                    persisted=persisted_pre,
                    status="cancelled",
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    total=total,
                    now=early_now,
                )
                return

            if "started" in existing_stages and not _has_executed_checkpoint(
                persisted_pre
            ):
                await _mark_remaining_samples(
                    db,
                    task,
                    run,
                    sample_ids=[
                        str(sample.get("sample_id") or "") for sample in scope_samples
                    ],
                    reason=_INTERRUPT_RECOVERY_REASON,
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    completed_at=early_now,
                )
                persisted_pre = await list_persisted_sample_results(db, task, run)
                await _write_terminal_state(
                    self,
                    db,
                    claim,
                    task=task,
                    run=run,
                    execute_step=execute_step,
                    plan=plan,
                    execute_step_id=execute_plan_step.step_id,
                    scope=scope,
                    samples=scope_samples,
                    persisted=persisted_pre,
                    status="failed",
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    total=total,
                    now=early_now,
                    error_message=_INTERRUPT_RECOVERY_REASON,
                )
                return

            run.status = "running"
            execute_step.status = "running"
            capability_run = await load_capability_run_by_skill_run(db, run.run_id)
            if capability_run is not None:
                mark_status(capability_run, "running", now=utc_now(), started=True)
            if "claimed" not in existing_stages:
                claimed_event = await append_task_event(
                    db,
                    task.task_id,
                    event_type="stage",
                    stage="claimed",
                    counts={"completed": 0, "failed": 0, "total": total},
                    resource_refs=[],
                )
                session = await db.get(GovernanceSession, task.session_id)
                await _emit_time_to_first_event_ms(
                    db,
                    task=task,
                    run=run,
                    event_created_at=claimed_event.created_at,
                    domain=session.domain if session is not None else "",
                )
            await db.commit()
            await self._ensure_lease(claim, lease_lost)

            adapter = adapter_for(task.capability or "")
            validated_scope = adapter.validate(scope)
            if "validated" not in existing_stages:
                await append_task_event(
                    db,
                    task.task_id,
                    event_type="stage",
                    stage="validated",
                    counts={"completed": 0, "failed": 0, "total": total},
                    resource_refs=[],
                )
                await db.commit()
            await self._ensure_lease(claim, lease_lost)

            if "started" not in existing_stages:
                await append_task_event(
                    db,
                    task.task_id,
                    event_type="stage",
                    stage="started",
                    counts={"completed": 0, "failed": 0, "total": total},
                    resource_refs=[],
                )
                await db.commit()

            capability_version = execute_plan_step.capability_version
            result_schema = plan.result_schema
            executor_fingerprint = plan.scope.executor.implementation_fingerprint
            samples = list(validated_scope.get("samples") or [])
            persisted = await list_persisted_sample_results(db, task, run)
            persisted_ids = {
                str(result.get("sample_id") or "")
                for result in persisted
                if result.get("status") in {"consistent", "inconsistent", "failed"}
            }
            cancelled = False
            transport_aborted = False

            for sample in samples:
                sample_id = str(sample.get("sample_id") or "")
                if sample_id in persisted_ids:
                    continue
                await self._ensure_lease(claim, lease_lost)
                await db.refresh(task)
                if task.status == "cancelling":
                    cancelled = True
                    break

                one_scope = dict(validated_scope, samples=[sample], sample_count=1)
                sample_artifact = await adapter.execute_sample(one_scope)
                await self._ensure_lease(claim, lease_lost)
                now = utc_now()
                artifact_samples = sample_artifact.get("samples") or []
                sample_outcome = dict(artifact_samples[0]) if artifact_samples else {}
                adapter_status = str(sample_artifact.get("status") or "failed")
                method = str(sample_artifact.get("method") or "")
                if sample_outcome:
                    sample_outcome["adapter_method"] = method
                    sample_outcome["adapter_status"] = adapter_status
                successful = (
                    adapter_status == "completed"
                    and sample_outcome.get("status") in {"consistent", "inconsistent"}
                )
                reason = str(
                    sample_outcome.get("reason")
                    or sample_artifact.get("reason")
                    or ("" if successful else "在线服务未返回该样本的有效检测结果。")
                )
                if not sample_outcome:
                    sample_outcome = _failed_sample_outcome(
                        sample, reason, method, adapter_status
                    )
                transport_failure = adapter_status != "completed"
                persisted_status = (
                    str(sample_outcome.get("status"))
                    if successful
                    else "failed"
                )
                await _save_sample_result(
                    db,
                    task,
                    run,
                    sample_id=sample_id,
                    status=persisted_status,
                    outcome=sample_outcome,
                    reason=reason or None,
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    completed_at=now,
                )
                persisted = await list_persisted_sample_results(db, task, run)
                await append_task_event(
                    db,
                    task.task_id,
                    event_type="progress",
                    stage="detecting",
                    counts=_sample_counts(persisted, total),
                    resource_refs=[],
                )
                # Sample result and sanitized event become durable together;
                # SSE only observes committed GovernanceTaskEvent rows.
                await db.commit()
                persisted_ids.add(sample_id)
                if transport_failure:
                    transport_aborted = True
                    break

            await self._ensure_lease(claim, lease_lost)
            await db.refresh(task)
            cancelled = cancelled or task.status == "cancelling"
            persisted = await list_persisted_sample_results(db, task, run)
            completed_or_failed = {
                str(result.get("sample_id") or "")
                for result in persisted
                if result.get("status") in {"consistent", "inconsistent", "failed"}
            }
            remaining_ids = [
                str(sample.get("sample_id") or "")
                for sample in samples
                if str(sample.get("sample_id") or "") not in completed_or_failed
            ]
            now = utc_now()
            if cancelled:
                await _mark_remaining_samples(
                    db,
                    task,
                    run,
                    sample_ids=remaining_ids,
                    reason=_CANCEL_NOT_EXECUTED_REASON,
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    completed_at=now,
                )
                persisted = await list_persisted_sample_results(db, task, run)
            elif transport_aborted and remaining_ids:
                await _mark_remaining_samples(
                    db,
                    task,
                    run,
                    sample_ids=remaining_ids,
                    reason=_TRANSPORT_ABORT_REASON,
                    capability_version=capability_version,
                    result_schema=result_schema,
                    executor_fingerprint=executor_fingerprint,
                    completed_at=now,
                )
                persisted = await list_persisted_sample_results(db, task, run)

            counts = _sample_counts(persisted, total)
            completed_count = counts["completed"]
            usable_count = _usable_executed_count(persisted)
            not_executed_count = sum(
                1 for result in persisted if result.get("status") == "not_executed"
            )
            if cancelled:
                status = "cancelled"
            elif transport_aborted and not_executed_count > 0:
                failed_outcomes = [
                    dict(result.get("outcome") or {})
                    for result in persisted
                    if result.get("status") == "failed"
                ]
                status = (
                    "timeout"
                    if failed_outcomes
                    and all(
                        outcome.get("adapter_status") == "timeout"
                        for outcome in failed_outcomes
                    )
                    else "failed"
                )
            elif usable_count > 0:
                status = (
                    "completed" if completed_count == total else "completed_partial"
                )
            else:
                failed_outcomes = [
                    dict(result.get("outcome") or {})
                    for result in persisted
                    if result.get("status") == "failed"
                ]
                status = (
                    "timeout"
                    if failed_outcomes
                    and all(
                        outcome.get("adapter_status") == "timeout"
                        for outcome in failed_outcomes
                    )
                    else "failed"
                )

            cancel_message = (
                "用户已取消任务，未执行样本已保留。"
                if status == "cancelled" and usable_count > 0
                else None
            )
            await _write_terminal_state(
                self,
                db,
                claim,
                task=task,
                run=run,
                execute_step=execute_step,
                plan=plan,
                execute_step_id=execute_plan_step.step_id,
                scope=scope,
                samples=samples,
                persisted=persisted,
                status=status,
                capability_version=capability_version,
                result_schema=result_schema,
                executor_fingerprint=executor_fingerprint,
                total=total,
                now=now,
                error_message=cancel_message,
            )

    async def _fail_claim(self, claim: TaskClaim, exc: Exception) -> None:
        async with AsyncSessionLocal() as db:
            still_owns = await renew_task_lease(
                db,
                claim.task_id,
                self.worker_id,
                claim.lease_token,
                lease_seconds=self.lease_seconds,
            )
            if not still_owns:
                await db.commit()
                return
            task = await db.scalar(
                select(GovernanceTask).where(GovernanceTask.task_id == claim.task_id)
            )
            if task is None:
                return
            if task.status in TERMINAL_TASK_STATUSES:
                await self._release_lease(db, claim)
                await db.commit()
                return
            scope = _json_object(task.parameters_json).get("frozen_scope") or {}
            total = len(scope.get("samples") or [])
            reason = (
                str(exc)
                if isinstance(exc, SkillContractError)
                else (
                    f"治理任务 Worker 执行失败（{exc.__class__.__name__}），"
                    "未输出上游原始日志。"
                )
            )
            task.status = "failed"
            task.error_message = reason
            task.finished_at = utc_now()
            run = await db.scalar(
                select(GovernanceSkillRun)
                .where(GovernanceSkillRun.task_id == task.task_id)
                .order_by(
                    GovernanceSkillRun.created_at.desc(),
                    GovernanceSkillRun.id.desc(),
                )
            )
            counts = {"completed": 0, "failed": 0, "total": total}
            if run is not None:
                run.status = "failed"
                capability_run = await load_capability_run_by_skill_run(db, run.run_id)
                if capability_run is not None:
                    mark_status(
                        capability_run,
                        "failed",
                        now=utc_now(),
                        finished=True,
                        error_code="worker_failure",
                        error_message=reason,
                        failure_phase="execution",
                    )
                await db.execute(
                    update(GovernanceCapabilityStep)
                    .where(
                        GovernanceCapabilityStep.run_id == run.run_id,
                        GovernanceCapabilityStep.action == "execute",
                    )
                    .values(status="failed")
                )
                try:
                    plan = GovernanceValidatedSkillPlan.model_validate_json(run.plan_json)
                    results = await list_persisted_sample_results(db, task, run)
                    recorded_ids = {
                        str(result.get("sample_id") or "") for result in results
                    }
                    remaining_ids = [
                        str(sample.get("sample_id") or "")
                        for sample in scope.get("samples") or []
                        if str(sample.get("sample_id") or "") not in recorded_ids
                    ]
                    await _mark_remaining_samples(
                        db,
                        task,
                        run,
                        sample_ids=remaining_ids,
                        reason=reason,
                        capability_version=next(
                            step.capability_version
                            for step in plan.steps
                            if step.action == "execute"
                        ),
                        result_schema=plan.result_schema,
                        executor_fingerprint=(
                            plan.scope.executor.implementation_fingerprint
                        ),
                        completed_at=utc_now(),
                    )
                    results = await list_persisted_sample_results(db, task, run)
                    counts = _sample_counts(results, total)
                except Exception:  # noqa: BLE001
                    # Preserve the original worker failure even if its storage
                    # dependency is the component that became unavailable.
                    pass
            await append_task_event(
                db,
                task.task_id,
                event_type="failure",
                stage="failed",
                counts=counts,
                resource_refs=[],
            )
            await self._release_lease(db, claim)
            await db.commit()
