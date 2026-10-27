"""Read-only plan projection for the governance timeline and review share (#65).

The projection is derived from a server-validated ``GovernanceValidatedSkillPlan``
but deliberately omits frozen sample digests/revisions and any sample text, so it
can be rendered in a read-only or anonymous review context (#66).
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from app.schemas.governance import (
    GovernanceSkillPlanScopeView,
    GovernanceSkillPlanStepView,
    GovernanceSkillPlanView,
    GovernanceValidatedSkillPlan,
)
from app.services.governance_skills import (
    SkillContractError,
    capability_scope_fields,
    load_skill_package,
)


DEFAULT_NOTE_PREPARE = "prepare 为自动只读步骤，不会调用在线服务。"
DEFAULT_NOTE_CONFIRM = "执行步骤需确认后才会调用在线服务。"


def _immutable_scope_fields(plan: GovernanceValidatedSkillPlan) -> list[str]:
    """Read the plan owner's immutable field names.

    A skill-orchestrated plan reads them from its contract; a direct capability
    run freezes exactly the fields present on its own scope, so the list stays
    derived from the plan rather than from a second source of truth.
    """

    try:
        package = load_skill_package(plan.skill_key, plan.skill_version)
    except SkillContractError:
        return capability_scope_fields(plan.scope)
    return list(package.contract.immutable_scope_fields)


def _step_status(action: str, completed: bool) -> str:
    # The prepare step is a read-only scope freeze; it is already done while the
    # task waits for confirmation. The execute step finishes only on completion.
    if action == "prepare":
        return "completed"
    return "completed" if completed else "pending"


_EXECUTE_STATUS_BY_TASK_STATUS: dict[str, str] = {
    "completed": "completed",
    "completed_partial": "completed",
    "running": "running",
    "cancelling": "cancelling",
    "failed": "failed",
    "timeout": "failed",
    "cancelled": "cancelled",
}


def apply_plan_progress(plan_view: Mapping[str, Any], task_status: str) -> dict:
    """Overlay the live task status on a frozen plan view's execute step.

    The plan view is persisted at plan time, when the execute step is always
    ``pending``; the task status advances afterwards. This returns a deep copy
    with only the execute step's status refreshed, so the stored dict is never
    mutated. ``prepare`` steps stay ``completed``, and statuses without a
    mapping (awaiting_confirmation/queued/unknown) leave the view unchanged.
    """

    projected = copy.deepcopy(dict(plan_view))
    mapped = _EXECUTE_STATUS_BY_TASK_STATUS.get(task_status)
    if mapped is None:
        return projected
    steps = projected.get("steps")
    if not isinstance(steps, list):
        return projected
    for step in steps:
        if isinstance(step, dict) and step.get("action") == "execute":
            step["status"] = mapped
    return projected


def build_plan_view(
    plan: GovernanceValidatedSkillPlan,
    *,
    task_id: str,
    status: str,
    asset_name: str | None = None,
    completed: bool = False,
    notes: list[str] | None = None,
) -> dict:
    """Project a validated plan into the safe, read-only view contract."""

    steps = [
        GovernanceSkillPlanStepView(
            step_id=step.step_id,
            capability=step.capability,
            capability_version=step.capability_version,
            action=step.action,
            automatic=step.automatic,
            requires_confirmation=step.requires_confirmation,
            completion_condition=step.completion_condition,
            status=_step_status(step.action, completed),
        )
        for step in plan.steps
    ]
    scope = GovernanceSkillPlanScopeView(
        asset_id=plan.scope.asset_id,
        asset_name=asset_name,
        asset_version=plan.scope.asset_version,
        filters=dict(plan.scope.filters),
        sample_count=plan.scope.sample_count,
        immutable_scope_fields=_immutable_scope_fields(plan),
        estimated_cost_units=plan.scope.estimated_cost_units,
        estimated_seconds=plan.scope.estimated_seconds,
    )
    if notes is None:
        notes = []
        if any(step.action == "prepare" for step in plan.steps):
            notes.append(DEFAULT_NOTE_PREPARE)
        if plan.confirmation_required and not completed:
            notes.append(DEFAULT_NOTE_CONFIRM)
    return GovernanceSkillPlanView(
        plan_id=plan.plan_id,
        task_id=task_id,
        skill_key=plan.skill_key,
        skill_version=plan.skill_version,
        title=plan.title,
        entrypoint=plan.entrypoint,
        branch=plan.branch,
        status=status,
        confirmation_required=plan.confirmation_required,
        steps=steps,
        scope=scope,
        executor=plan.scope.executor,
        scope_fingerprint=plan.scope_fingerprint,
        notes=list(notes),
    ).model_dump(mode="json")
