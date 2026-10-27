"""First-class capability-run persistence for confirmable governance capabilities (#164 T2).

A :class:`GovernanceCapabilityRun` is the execution-attempt entity behind one
confirmed governance capability call. It owns the frozen execution scope, the
confirmation state, the resolved executor identity, status/result/error facts and
retry lineage. Direct capability execution and skill-orchestrated execution share
these semantics; ``skill_run_id`` is NULL for a direct run.

This module only persists and projects runs. Freeze/confirmation/executor-identity
logic is reused from ``governance_skills`` and ``governance_executor_identity``.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GovernanceCapabilityRun, GovernanceTask, utc_now
from app.schemas.governance import (
    RISK_RESCAN_STATUS_AWAITING,
    GovernanceExecutionScope,
)
from app.services.governance_capabilities import CapabilityDef
from app.services.governance_skills import capability_scope_fingerprint


def _loads_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _iso(value: datetime | None) -> str | None:
    """Serialize a run timestamp as a UTC instant for the task API."""
    return value.isoformat() + "Z" if value else None


def serialize_capability_run(run: GovernanceCapabilityRun) -> dict:
    """Stable, read-only projection of one capability run for the task API."""

    scope = _loads_json(run.scope_json)
    return {
        "run_id": run.run_id,
        "task_id": run.task_id,
        "skill_run_id": run.skill_run_id,
        "capability_key": run.capability_key,
        "capability_version": run.capability_version,
        "parameters": _loads_json(run.parameters_json),
        "scope": scope,
        "scope_fingerprint": run.scope_fingerprint,
        "confirmation_scope_fingerprint": run.confirmation_scope_fingerprint,
        "scope_selection": run.scope_selection,
        "status": run.status,
        "attempt": run.attempt,
        "parent_run_id": run.parent_run_id,
        "root_run_id": run.root_run_id,
        "revision": _loads_json(run.revision_json),
        "executor_fingerprint": run.executor_fingerprint,
        "executor_identity": _loads_json(run.executor_metadata_json),
        "result_schema": run.result_schema,
        "result_ref": run.result_ref,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "failure_phase": run.failure_phase,
        "created_at": _iso(run.created_at),
        "confirmed_at": _iso(run.confirmed_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


async def list_capability_runs(
    db: AsyncSession, task_id: str
) -> list[GovernanceCapabilityRun]:
    result = await db.execute(
        select(GovernanceCapabilityRun)
        .where(GovernanceCapabilityRun.task_id == task_id)
        .order_by(GovernanceCapabilityRun.created_at, GovernanceCapabilityRun.id)
    )
    return list(result.scalars())


async def load_capability_run(
    db: AsyncSession, run_id: str
) -> GovernanceCapabilityRun | None:
    result = await db.execute(
        select(GovernanceCapabilityRun).where(GovernanceCapabilityRun.run_id == run_id)
    )
    return result.scalar_one_or_none()


async def load_capability_run_by_skill_run(
    db: AsyncSession, skill_run_id: str
) -> GovernanceCapabilityRun | None:
    result = await db.execute(
        select(GovernanceCapabilityRun)
        .where(GovernanceCapabilityRun.skill_run_id == skill_run_id)
        .order_by(GovernanceCapabilityRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def active_capability_run(
    db: AsyncSession, task: GovernanceTask
) -> GovernanceCapabilityRun | None:
    """Resolve the capability run currently pointed at by the task parameters."""

    parameters = _loads_json(task.parameters_json)
    run_id = parameters.get("active_capability_run_id")
    if not run_id:
        return None
    return await load_capability_run(db, str(run_id))


def _apply_scope(run: GovernanceCapabilityRun, scope: GovernanceExecutionScope) -> None:
    run.scope_json = scope.model_dump_json()
    run.scope_fingerprint = capability_scope_fingerprint(scope)
    run.executor_fingerprint = scope.executor.implementation_fingerprint
    run.executor_metadata_json = scope.executor.model_dump_json()


async def create_capability_run(
    db: AsyncSession,
    task: GovernanceTask,
    *,
    capability: CapabilityDef,
    parameters: dict,
    scope: GovernanceExecutionScope,
    status: str = RISK_RESCAN_STATUS_AWAITING,
    result_schema: str | None = None,
    attempt: int = 1,
    parent_run_id: str | None = None,
    root_run_id: str | None = None,
    scope_selection: str = "full",
    revision_json: str = "{}",
    confirmed_at: datetime | None = None,
    skill_run_id: str | None = None,
) -> GovernanceCapabilityRun:
    """Insert one immutable capability-run attempt and flush it."""

    run = GovernanceCapabilityRun(
        run_id=str(uuid4()),
        task_id=task.task_id,
        skill_run_id=skill_run_id,
        capability_key=capability.key,
        capability_version=capability.version,
        parameters_json=json.dumps(parameters, ensure_ascii=False, default=str),
        scope_selection=scope_selection,
        status=status,
        attempt=attempt,
        parent_run_id=parent_run_id,
        root_run_id=root_run_id or parent_run_id,
        revision_json=revision_json,
        result_schema=result_schema or capability.result_schema or "",
        confirmed_at=confirmed_at,
        created_at=utc_now(),
    )
    _apply_scope(run, scope)
    if confirmed_at is not None:
        run.confirmation_scope_fingerprint = run.scope_fingerprint
    db.add(run)
    await db.flush()
    return run


def mark_confirmed(
    run: GovernanceCapabilityRun,
    *,
    confirmed_at: datetime,
    skill_run_id: str,
) -> None:
    """Bind the run to its materialized skill run and freeze confirmation state."""

    run.status = "queued"
    run.confirmed_at = confirmed_at
    run.confirmation_scope_fingerprint = run.scope_fingerprint
    run.skill_run_id = skill_run_id


def mark_status(
    run: GovernanceCapabilityRun,
    status: str,
    *,
    now: datetime,
    started: bool = False,
    finished: bool = False,
    result_ref: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    failure_phase: str | None = None,
) -> None:
    """Advance a capability run's status (and optional result/error facts)."""

    run.status = status
    if started and run.started_at is None:
        run.started_at = now
    if finished:
        run.finished_at = now
    if result_ref is not None:
        run.result_ref = result_ref
    if error_code is not None:
        run.error_code = error_code
    if error_message is not None:
        run.error_message = error_message
    if failure_phase is not None:
        run.failure_phase = failure_phase
