"""Immutable persistence and compatibility-safe aggregation for skill-run samples."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GovernanceRunSampleResult,
    GovernanceSkillRun,
    utc_now,
)


SAMPLE_RESULT_STATUSES = frozenset(
    {"consistent", "inconsistent", "failed", "not_executed"}
)


class ImmutableSampleResultError(ValueError):
    """Raised when a caller tries to change an already-persisted sample result."""


class RunResultNotFoundError(ValueError):
    """Raised when the target run does not exist under the supplied task."""


def _canonical_json(value: Mapping[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized_datetime(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _required_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _result_signature(result: GovernanceRunSampleResult) -> tuple[Any, ...]:
    return (
        result.task_id,
        result.status,
        result.outcome_json,
        result.reason,
        result.capability_version,
        result.result_schema,
        result.executor_fingerprint,
    )


def _requested_signature(
    *,
    task_id: str,
    status: str,
    outcome_json: str,
    reason: str | None,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
) -> tuple[Any, ...]:
    return (
        task_id,
        status,
        outcome_json,
        reason,
        capability_version,
        result_schema,
        executor_fingerprint,
    )


def _compatibility_signature(
    *,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
) -> tuple[str, str, str]:
    return (result_schema, capability_version, executor_fingerprint)


async def _require_run(
    db: AsyncSession, *, task_id: str, run_id: str
) -> GovernanceSkillRun:
    run = (
        await db.execute(
            select(GovernanceSkillRun).where(
                GovernanceSkillRun.run_id == run_id,
                GovernanceSkillRun.task_id == task_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise RunResultNotFoundError(
            f"governance skill run {run_id!r} does not belong to task {task_id!r}"
        )
    return run


async def save_sample_result(
    db: AsyncSession,
    *,
    task_id: str,
    run_id: str,
    sample_id: str,
    status: str,
    outcome: Mapping[str, Any] | None,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
    reason: str | None = None,
    completed_at: datetime | None = None,
) -> GovernanceRunSampleResult:
    """Insert one result, or return the identical row without mutating history.

    The operation is deliberately stricter than a conventional update-on-conflict
    upsert. A repeated delivery is accepted only when all immutable business fields
    match; a conflicting delivery raises instead of replacing the original attempt.
    The caller owns the surrounding transaction.
    """

    normalized_task_id = _required_text("task_id", task_id)
    normalized_run_id = _required_text("run_id", run_id)
    normalized_sample_id = _required_text("sample_id", sample_id)
    normalized_status = status.strip()
    if normalized_status not in SAMPLE_RESULT_STATUSES:
        raise ValueError(f"unsupported sample result status: {status!r}")
    normalized_reason = reason.strip() if reason and reason.strip() else None
    if normalized_status in {"failed", "not_executed"} and not normalized_reason:
        raise ValueError(f"{normalized_status} sample result requires a reason")
    normalized_capability_version = _required_text(
        "capability_version", capability_version
    )
    normalized_result_schema = _required_text("result_schema", result_schema)
    normalized_executor_fingerprint = _required_text(
        "executor_fingerprint", executor_fingerprint
    )
    outcome_json = _canonical_json(outcome)

    await _require_run(
        db, task_id=normalized_task_id, run_id=normalized_run_id
    )
    existing = (
        await db.execute(
            select(GovernanceRunSampleResult).where(
                GovernanceRunSampleResult.run_id == normalized_run_id,
                GovernanceRunSampleResult.sample_id == normalized_sample_id,
            )
        )
    ).scalar_one_or_none()
    requested_signature = _requested_signature(
        task_id=normalized_task_id,
        status=normalized_status,
        outcome_json=outcome_json,
        reason=normalized_reason,
        capability_version=normalized_capability_version,
        result_schema=normalized_result_schema,
        executor_fingerprint=normalized_executor_fingerprint,
    )
    if existing is not None:
        same_completion_time = (
            completed_at is None
            or existing.completed_at == _normalized_datetime(completed_at)
        )
        if _result_signature(existing) == requested_signature and same_completion_time:
            return existing
        raise ImmutableSampleResultError(
            f"sample result {normalized_run_id}/{normalized_sample_id} is immutable"
        )

    run_result = (
        await db.execute(
            select(GovernanceRunSampleResult)
            .where(GovernanceRunSampleResult.run_id == normalized_run_id)
            .order_by(GovernanceRunSampleResult.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if run_result is not None:
        persisted_compatibility = _compatibility_signature(
            capability_version=run_result.capability_version,
            result_schema=run_result.result_schema,
            executor_fingerprint=run_result.executor_fingerprint,
        )
        requested_compatibility = _compatibility_signature(
            capability_version=normalized_capability_version,
            result_schema=normalized_result_schema,
            executor_fingerprint=normalized_executor_fingerprint,
        )
        if persisted_compatibility != requested_compatibility:
            raise ImmutableSampleResultError(
                f"skill run {normalized_run_id} already uses a different result contract"
            )

    result = GovernanceRunSampleResult(
        task_id=normalized_task_id,
        run_id=normalized_run_id,
        sample_id=normalized_sample_id,
        status=normalized_status,
        outcome_json=outcome_json,
        reason=normalized_reason,
        capability_version=normalized_capability_version,
        result_schema=normalized_result_schema,
        executor_fingerprint=normalized_executor_fingerprint,
        completed_at=_normalized_datetime(completed_at),
    )
    db.add(result)
    await db.flush()
    return result


# Public compatibility name for callers that describe the idempotent write as an upsert.
upsert_sample_result = save_sample_result


async def list_run_sample_results(
    db: AsyncSession, run_id: str
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(GovernanceRunSampleResult)
            .where(GovernanceRunSampleResult.run_id == run_id)
            .order_by(
                GovernanceRunSampleResult.completed_at,
                GovernanceRunSampleResult.id,
            )
        )
    ).scalars().all()
    return [_serialize_result(row) for row in rows]


async def mark_remaining_samples(
    db: AsyncSession,
    *,
    task_id: str,
    run_id: str,
    sample_ids: Sequence[str],
    reason: str,
    capability_version: str,
    result_schema: str,
    executor_fingerprint: str,
    completed_at: datetime | None = None,
) -> list[GovernanceRunSampleResult]:
    """Persist not-executed markers for currently absent samples only.

    Existing completed or failed rows are returned unchanged. This lets callers
    pass the frozen scope after cancellation without risking historical overwrite.
    """

    await _require_run(db, task_id=task_id, run_id=run_id)
    ordered_ids = list(
        dict.fromkeys(_required_text("sample_id", item) for item in sample_ids)
    )
    if not ordered_ids:
        return []
    existing_rows = (
        await db.execute(
            select(GovernanceRunSampleResult).where(
                GovernanceRunSampleResult.run_id == run_id,
                GovernanceRunSampleResult.sample_id.in_(ordered_ids),
            )
        )
    ).scalars().all()
    by_sample_id = {row.sample_id: row for row in existing_rows}
    requested_compatibility = _compatibility_signature(
        capability_version=capability_version,
        result_schema=result_schema,
        executor_fingerprint=executor_fingerprint,
    )
    for existing in existing_rows:
        persisted_compatibility = _compatibility_signature(
            capability_version=existing.capability_version,
            result_schema=existing.result_schema,
            executor_fingerprint=existing.executor_fingerprint,
        )
        if persisted_compatibility != requested_compatibility:
            raise ImmutableSampleResultError(
                f"skill run {run_id} already uses a different result contract"
            )
    marked: list[GovernanceRunSampleResult] = []
    for sample_id in ordered_ids:
        existing = by_sample_id.get(sample_id)
        if existing is not None:
            marked.append(existing)
            continue
        marked.append(
            await save_sample_result(
                db,
                task_id=task_id,
                run_id=run_id,
                sample_id=sample_id,
                status="not_executed",
                outcome={},
                reason=reason,
                capability_version=capability_version,
                result_schema=result_schema,
                executor_fingerprint=executor_fingerprint,
                completed_at=completed_at,
            )
        )
    return marked


async def list_task_run_groups(
    db: AsyncSession, task_id: str
) -> list[dict[str, Any]]:
    runs = (
        await db.execute(
            select(GovernanceSkillRun)
            .where(GovernanceSkillRun.task_id == task_id)
            .order_by(GovernanceSkillRun.created_at, GovernanceSkillRun.id)
        )
    ).scalars().all()
    results = (
        await db.execute(
            select(GovernanceRunSampleResult)
            .where(GovernanceRunSampleResult.task_id == task_id)
            .order_by(
                GovernanceRunSampleResult.completed_at,
                GovernanceRunSampleResult.id,
            )
        )
    ).scalars().all()
    results_by_run: dict[str, list[GovernanceRunSampleResult]] = {}
    for result in results:
        results_by_run.setdefault(result.run_id, []).append(result)

    return [
        {
            "run_id": run.run_id,
            "task_id": run.task_id,
            "skill_key": run.skill_key,
            "skill_version": run.skill_version,
            "status": run.status,
            "plan": json.loads(run.plan_json),
            "scope": json.loads(run.scope_json),
            "scope_fingerprint": run.scope_fingerprint,
            "created_at": _iso_datetime(run.created_at),
            "confirmed_at": _iso_datetime(run.confirmed_at),
            "finished_at": _iso_datetime(run.finished_at),
            "sample_results": [
                _serialize_result(result)
                for result in results_by_run.get(run.run_id, [])
            ],
        }
        for run in runs
    ]


def _serialize_result(result: GovernanceRunSampleResult) -> dict[str, Any]:
    return {
        "task_id": result.task_id,
        "run_id": result.run_id,
        "sample_id": result.sample_id,
        "status": result.status,
        "outcome": json.loads(result.outcome_json),
        "reason": result.reason,
        "capability_version": result.capability_version,
        "result_schema": result.result_schema,
        "executor_fingerprint": result.executor_fingerprint,
        "completed_at": _iso_datetime(result.completed_at),
    }


def _compatibility_groups(
    run_groups: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for run in run_groups:
        for result in run["sample_results"]:
            key = (
                run["skill_key"],
                run["skill_version"],
                result["result_schema"],
                result["capability_version"],
                result["executor_fingerprint"],
            )
            group = grouped.setdefault(
                key,
                {
                    "compatibility": {
                        "skill_key": key[0],
                        "skill_version": key[1],
                        "result_schema": key[2],
                        "capability_version": key[3],
                        "executor_fingerprint": key[4],
                    },
                    "run_ids": [],
                    "sample_results": [],
                    "status_counts": {
                        status: 0 for status in sorted(SAMPLE_RESULT_STATUSES)
                    },
                },
            )
            if run["run_id"] not in group["run_ids"]:
                group["run_ids"].append(run["run_id"])
            group["sample_results"].append(result)
            group["status_counts"][result["status"]] += 1
    return list(grouped.values())


async def list_task_compatibility_groups(
    db: AsyncSession, task_id: str
) -> list[dict[str, Any]]:
    return _compatibility_groups(await list_task_run_groups(db, task_id))


async def summarize_task_results(
    db: AsyncSession, task_id: str
) -> dict[str, Any]:
    run_groups = await list_task_run_groups(db, task_id)
    counts: Counter[str] = Counter(
        result["status"]
        for run in run_groups
        for result in run["sample_results"]
    )
    return {
        "task_id": task_id,
        "status_counts": {
            status: counts.get(status, 0) for status in sorted(SAMPLE_RESULT_STATUSES)
        },
        "run_groups": run_groups,
        "compatibility_groups": _compatibility_groups(run_groups),
    }


def _scope_dict(run: Mapping[str, Any]) -> dict[str, Any]:
    scope = run.get("scope")
    return scope if isinstance(scope, dict) else {}


def _plan_dict(run: Mapping[str, Any]) -> dict[str, Any]:
    plan = run.get("plan")
    return plan if isinstance(plan, dict) else {}


def _scope_samples_by_id(run: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for sample in _scope_dict(run).get("samples") or []:
        if isinstance(sample, dict) and sample.get("sample_id"):
            indexed[str(sample["sample_id"])] = sample
    return indexed


def run_compatibility_key(run: Mapping[str, Any]) -> tuple[str, ...]:
    """Contract fingerprint for cross-run aggregation (plan §9)."""

    scope = _scope_dict(run)
    plan = _plan_dict(run)
    executor = scope.get("executor") if isinstance(scope.get("executor"), dict) else {}
    sample_results = run.get("sample_results") or []
    if sample_results:
        first = sample_results[0]
        result_schema = str(first.get("result_schema") or "")
        capability_version = str(first.get("capability_version") or "")
        executor_fingerprint = str(first.get("executor_fingerprint") or "")
    else:
        result_schema = str(plan.get("result_schema") or "")
        capability_version = str(executor.get("capability_version") or "")
        executor_fingerprint = str(executor.get("implementation_fingerprint") or "")
    adapter_method = str(executor.get("adapter_method") or "")
    asset_id = str(scope.get("asset_id") or "")
    asset_version = str(scope.get("asset_version") or "")
    filters_key = _canonical_json(
        scope.get("filters") if isinstance(scope.get("filters"), dict) else {}
    )
    return (
        result_schema,
        capability_version,
        executor_fingerprint,
        adapter_method,
        asset_id,
        asset_version,
        filters_key,
    )


def _frozen_fact_tuple(
    sample_id: str,
    outcome: Mapping[str, Any],
    frozen_sample: Mapping[str, Any],
) -> tuple[str, str, str]:
    return (
        str(outcome.get("content_digest") or frozen_sample.get("content_digest") or ""),
        str(
            outcome.get("reference_label") or frozen_sample.get("reference_label") or ""
        ),
        str(outcome.get("source_revision") or frozen_sample.get("source_revision") or ""),
    )


def _facts_conflict(
    left: tuple[str, str, str], right: tuple[str, str, str]
) -> bool:
    for a, b in zip(left, right):
        if a and b and a != b:
            return True
    return False


def _merge_fact_tuple(
    left: tuple[str, str, str], right: tuple[str, str, str]
) -> tuple[str, str, str]:
    return tuple(a or b for a, b in zip(left, right))


def sample_outcome_from_result(
    result: Mapping[str, Any],
    *,
    run: Mapping[str, Any],
) -> dict[str, Any]:
    outcome = result.get("outcome")
    outcome_dict = outcome if isinstance(outcome, dict) else {}
    frozen = _scope_samples_by_id(run).get(str(result.get("sample_id") or ""), {})
    sample_id = str(result.get("sample_id") or "")
    status = str(result.get("status") or "failed")
    reason = str(result.get("reason") or outcome_dict.get("reason") or "")
    return {
        "sample_id": sample_id,
        "text": str(outcome_dict.get("text") or frozen.get("text") or ""),
        "reference_label": str(
            outcome_dict.get("reference_label") or frozen.get("reference_label") or ""
        ),
        "detected_label": str(outcome_dict.get("detected_label") or ""),
        "status": status,
        "reason": reason,
        "source": str(outcome_dict.get("source") or frozen.get("source") or ""),
        "content_digest": str(
            outcome_dict.get("content_digest") or frozen.get("content_digest") or ""
        ),
        "source_revision": str(
            outcome_dict.get("source_revision") or frozen.get("source_revision") or ""
        ),
        "run_id": str(result.get("run_id") or run.get("run_id") or ""),
        "capability_version": str(result.get("capability_version") or ""),
        "completed_at": str(result.get("completed_at") or ""),
    }


def _summary_from_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(str(item.get("status") or "") for item in samples)
    return {
        "consistent_count": counts.get("consistent", 0),
        "inconsistent_count": counts.get("inconsistent", 0),
        "failed_count": counts.get("failed", 0),
        "not_executed_count": counts.get("not_executed", 0),
    }


def merge_run_group(
    runs: Sequence[Mapping[str, Any]],
    *,
    sample_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Merge compatible runs within one compatibility key."""

    ordered_runs = list(runs)
    if not ordered_runs:
        return {
            "compatible": True,
            "reason": "",
            "samples": [],
            "summary": _summary_from_samples([]),
            "run_ids": [],
        }

    run_ids = [str(run.get("run_id") or "") for run in ordered_runs]
    facts_by_sample: dict[str, tuple[str, str, str]] = {}
    latest_by_sample: dict[str, dict[str, Any]] = {}
    conflict_sample_ids: list[str] = []

    for run in ordered_runs:
        scope_samples = _scope_samples_by_id(run)
        for result in run.get("sample_results") or []:
            sample_id = str(result.get("sample_id") or "")
            if not sample_id:
                continue
            outcome = result.get("outcome")
            outcome_dict = outcome if isinstance(outcome, dict) else {}
            fact = _frozen_fact_tuple(sample_id, outcome_dict, scope_samples.get(sample_id, {}))
            existing_fact = facts_by_sample.get(sample_id)
            if existing_fact is not None and _facts_conflict(existing_fact, fact):
                if sample_id not in conflict_sample_ids:
                    conflict_sample_ids.append(sample_id)
            else:
                facts_by_sample[sample_id] = _merge_fact_tuple(
                    existing_fact or ("", "", ""), fact
                )
            latest_by_sample[sample_id] = sample_outcome_from_result(result, run=run)

    if conflict_sample_ids:
        return {
            "compatible": False,
            "reason": (
                "样本冻结事实冲突，无法合并："
                + "、".join(sorted(conflict_sample_ids))
            ),
            "samples": [],
            "summary": _summary_from_samples([]),
            "run_ids": run_ids,
        }

    if sample_order:
        ordered_ids = [sample_id for sample_id in sample_order if sample_id in latest_by_sample]
        trailing = [
            sample_id
            for sample_id in sorted(latest_by_sample)
            if sample_id not in set(ordered_ids)
        ]
        merged_samples = [latest_by_sample[sample_id] for sample_id in ordered_ids + trailing]
    else:
        merged_samples = [
            latest_by_sample[sample_id] for sample_id in sorted(latest_by_sample)
        ]

    return {
        "compatible": True,
        "reason": "",
        "samples": merged_samples,
        "summary": _summary_from_samples(merged_samples),
        "run_ids": run_ids,
    }


def build_run_provenance(
    run: Mapping[str, Any], *, attempt: int
) -> dict[str, Any]:
    scope = _scope_dict(run)
    plan = _plan_dict(run)
    executor = scope.get("executor") if isinstance(scope.get("executor"), dict) else {}
    sample_results = run.get("sample_results") or []
    if sample_results:
        capability_version = str(sample_results[0].get("capability_version") or "")
        executor_fingerprint = str(sample_results[0].get("executor_fingerprint") or "")
        result_schema = str(sample_results[0].get("result_schema") or "")
    else:
        capability_version = str(executor.get("capability_version") or "")
        executor_fingerprint = str(executor.get("implementation_fingerprint") or "")
        result_schema = str(plan.get("result_schema") or "")

    return {
        "run_id": str(run.get("run_id") or ""),
        "attempt": attempt,
        "status": str(run.get("status") or ""),
        "capability_version": capability_version,
        "executor_fingerprint": executor_fingerprint,
        "scope_selection": "full",
        "parent_run_id": None,
        "result_schema": result_schema,
        "sample_count": len(sample_results),
        "started_at": str(run.get("confirmed_at") or run.get("created_at") or ""),
        "completed_at": run.get("finished_at"),
    }


def aggregate_task_run_groups(
    run_groups: Sequence[Mapping[str, Any]],
    *,
    sample_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build grouped merge view used by task-level aggregation."""

    if not run_groups:
        return {
            "groups": [],
            "primary_group": None,
            "run_provenance": [],
        }

    runs_by_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for run in run_groups:
        key = run_compatibility_key(run)
        runs_by_key.setdefault(key, []).append(dict(run))

    groups: list[dict[str, Any]] = []
    for key, runs in runs_by_key.items():
        merged = merge_run_group(runs, sample_order=sample_order)
        scope = _scope_dict(runs[0])
        executor = scope.get("executor") if isinstance(scope.get("executor"), dict) else {}
        filters = scope.get("filters") if isinstance(scope.get("filters"), dict) else {}
        finished_times = [
            str(run.get("finished_at") or "")
            for run in runs
            if run.get("finished_at")
        ]
        groups.append(
            {
                "compatible": merged["compatible"],
                "reason": merged["reason"],
                "executor_fingerprint": key[2],
                "result_schema": key[0],
                "capability_version": key[1],
                "sample_count": len(merged["samples"]),
                "method": key[3],
                "run_ids": merged["run_ids"],
                "samples": merged["samples"],
                "summary": merged["summary"],
                "asset_id": scope.get("asset_id"),
                "asset_name": scope.get("asset_name"),
                "filters": dict(filters),
                "completed_at": max(finished_times) if finished_times else None,
                "_attempt_rank": max(
                    index
                    for index, candidate in enumerate(run_groups)
                    if str(candidate.get("run_id") or "")
                    in {str(item.get("run_id") or "") for item in runs}
                ),
            }
        )

    compatible_groups = [group for group in groups if group["compatible"]]
    primary_group: dict[str, Any] | None = None
    if compatible_groups:
        primary_group = max(
            compatible_groups,
            key=lambda group: (
                len(group["samples"]),
                group["_attempt_rank"],
            ),
        )

    run_provenance = [
        build_run_provenance(run, attempt=index + 1)
        for index, run in enumerate(run_groups)
    ]

    for group in groups:
        group.pop("_attempt_rank", None)

    return {
        "groups": groups,
        "primary_group": primary_group,
        "run_provenance": run_provenance,
    }
