import json
import re
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    GovernanceClient,
    GovernanceCapabilityStep,
    GovernanceClarificationPlan,
    GovernanceCompletionRecord,
    GovernanceMessage,
    GovernanceSession,
    GovernanceSkillRun,
    GovernanceTask,
    utc_now,
)
from app.schemas.governance import (
    SKILL_PLAN_MESSAGE_KIND,
    GovernanceIntent,
    GovernanceSkillConfirmation,
    GovernanceRetryRevision,
    GovernanceTaskRetryRequest,
    RISK_RESCAN_STATUS_AWAITING,
    RISK_RESCAN_STATUS_CANCELLED,
    RISK_RESCAN_STATUS_CANCELLING,
    RISK_RESCAN_STATUS_COMPLETED,
    RISK_RESCAN_STATUS_COMPLETED_PARTIAL,
    RISK_RESCAN_STATUS_FAILED,
    RISK_RESCAN_STATUS_QUEUED,
    RISK_RESCAN_STATUS_RUNNING,
    RISK_RESCAN_STATUS_TIMEOUT,
    GovernanceValidatedSkillPlan,
    RiskCorpusRescanPreviewResult,
)
from app.services.governance_assistant import (
    AssistantInterpretation,
    ambiguous_asset_version_clarification,
    ambiguous_asset_version_message,
    get_assistant_interpreter,
)
from app.services.governance_capabilities import (
    CapabilityContext,
    CapabilityDef,
    execute_capability,
    resolve_capability,
    resolve_capability_by_key,
)
from app.services.governance_cultural_review_service import (
    create_cultural_prerun_review as create_cultural_review_task,
)
from app.services.governance_risk_review_service import (
    create_risk_prerun_review as create_risk_review_task,
)
from app.services.governance_system_record_service import get_risk_system_record_asset
from app.services.governance_planner import (
    INVALID_CAPABILITY_PARAMETERS_MESSAGE,
    PlannedCapability,
    PlannedGovernanceTurn,
    get_governance_planner,
    plan_governance_turn,
)
from app.services.governance_skill_registry import (
    SkillRegistryError,
    activate_registered_skill,
    list_skill_descriptors,
)
from app.services.governance_plan_view import apply_plan_progress, build_plan_view
from app.services.governance_risk_report_service import (
    build_cancelling_payload,
    build_notice_payload,
)
from app.services.governance_risk_rescan_service import (
    capability_version_from_scope,
    derive_source_revision,
    sample_content_digest,
)
from app.services.governance_skills import (
    SkillContractError,
    capability_scope_fingerprint,
    freeze_capability_scope,
    validate_and_freeze_capability_plan,
    validate_and_freeze_capability_retry_plan,
    validate_execution,
)
from app.services.governance_capability_run_service import (
    active_capability_run,
    create_capability_run,
    list_capability_runs,
    mark_confirmed,
    mark_status,
    serialize_capability_run,
)
from app.services.governance_run_aggregation import (
    aggregated_has_executed_samples,
    build_task_aggregated_result,
)
from app.services.governance_run_results import summarize_task_results
from app.services.governance_product_metrics import (
    emit_product_event,
    match_suggestion_id,
)
from app.services.governance_suggestions import build_session_suggestions
from app.services.governance_task_runtime import append_task_event, list_task_events


class GovernanceTaskStateError(ValueError):
    """Raised when a task action is requested from a state that forbids it."""


class GovernancePlanningContextError(ValueError):
    """A clarification plan cannot be continued safely."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _loads_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _loads_list(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def serialize_message(message: GovernanceMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "kind": message.kind,
        "content": message.content,
        "payload": _loads_json(message.payload_json),
        "created_at": message.created_at.isoformat() + "Z",
    }


def serialize_session(session: GovernanceSession) -> dict:
    return {
        "session_id": session.session_id,
        "domain": session.domain,
        "title": session.title,
        "created_at": session.created_at.isoformat() + "Z",
        "updated_at": session.updated_at.isoformat() + "Z",
    }


def serialize_clarification_plan(plan: GovernanceClarificationPlan) -> dict:
    clarifications = _loads_list(plan.system_clarifications_json)
    latest = clarifications[-1] if clarifications else {}
    return {
        "plan_id": plan.plan_id,
        "status": plan.status,
        "version": plan.version,
        "question": str(latest.get("question") or ""),
        "missing_items": list(latest.get("missing_items") or []),
        "goal_draft": plan.goal_draft,
        "resolved_goal": plan.resolved_goal,
        "bound_skill_key": plan.bound_skill_key,
        "bound_skill_version": plan.bound_skill_version,
        "created_at": plan.created_at.isoformat() + "Z",
        "updated_at": plan.updated_at.isoformat() + "Z",
    }


async def _latest_clarification_plan(
    db: AsyncSession, session_id: str
) -> GovernanceClarificationPlan | None:
    result = await db.execute(
        select(GovernanceClarificationPlan)
        .where(GovernanceClarificationPlan.session_id == session_id)
        .order_by(GovernanceClarificationPlan.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _message_for_request(
    db: AsyncSession, client_id: str, request_id: str
) -> GovernanceMessage | None:
    result = await db.execute(
        select(GovernanceMessage).where(
            GovernanceMessage.client_id == client_id,
            GovernanceMessage.request_id == request_id,
        )
    )
    return result.scalar_one_or_none()


async def _messages_for_session(db: AsyncSession, session_id: str) -> list[dict]:
    result = await db.execute(
        select(GovernanceMessage)
        .where(GovernanceMessage.session_id == session_id)
        .order_by(GovernanceMessage.id)
    )
    return [serialize_message(message) for message in result.scalars()]


async def _session_detail(db: AsyncSession, session: GovernanceSession) -> dict:
    plan = await _latest_clarification_plan(db, session.session_id)
    return {
        **serialize_session(session),
        "messages": await _messages_for_session(db, session.session_id),
        "suggestions": await build_session_suggestions(db, session),
        "clarification_plan": serialize_clarification_plan(plan) if plan else None,
    }


async def _ensure_client(db: AsyncSession, client_id: str) -> None:
    if await db.get(GovernanceClient, client_id) is not None:
        return
    db.add(GovernanceClient(client_id=client_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()


async def register_client(db: AsyncSession, client_id: str) -> dict:
    client = await db.get(GovernanceClient, client_id)
    if client is None:
        client = GovernanceClient(client_id=client_id)
        db.add(client)
        await db.flush()
        data = {"client_id": client_id, "created_at": client.created_at.isoformat() + "Z"}
        await db.commit()
        return data
    return {"client_id": client_id, "created_at": client.created_at.isoformat() + "Z"}


def _assistant_message(
    client_id: str,
    session_id: str,
    kind: str,
    content: str,
    created_at,
    payload: dict | None = None,
) -> GovernanceMessage:
    return GovernanceMessage(
        session_id=session_id,
        client_id=client_id,
        request_id=str(uuid4()),
        role="assistant",
        kind=kind,
        content=content,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        created_at=created_at,
    )


async def _reply(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    kind: str,
    content: str,
    now,
    payload: dict | None = None,
) -> list[GovernanceMessage]:
    message = _assistant_message(client_id, session_id, kind, content, now, payload)
    db.add(message)
    await db.flush()
    return [message]


def _plan_message_content(plan_view: dict, *, retry: bool = False) -> str:
    """Short, grounded one-liner for the plan message (details live in payload)."""

    steps = plan_view.get("steps") or []
    scope = plan_view.get("scope") or {}
    title = plan_view.get("title") or plan_view.get("skill_key") or "治理技能"
    sample_count = int(scope.get("sample_count") or 0)
    lines = [
        f"已生成治理技能计划「{title}」：共 {len(steps)} 个步骤，"
        f"覆盖 {sample_count} 条样本。"
    ]
    if retry:
        lines.append("这是同一任务的新一次运行计划，需重新确认后才会执行。")
    elif plan_view.get("confirmation_required"):
        lines.append("执行步骤需确认后才会调用在线服务。")
    return "\n".join(lines)


def build_clarification_plan_payload(
    prior_inputs: tuple[str, ...] | list[str],
    question: str,
    boundaries: dict | None = None,
) -> dict:
    """Shared open-plan payload. Keys stay stable for later merges."""

    return {
        "clarification_plan": True,
        "prior_inputs": list(prior_inputs),
        "question": question,
        "boundaries": dict(boundaries or {}),
    }


def _merge_clarification_boundaries(settled: dict, incoming: dict | None) -> dict:
    """Keep limits already settled. Keys on the new plan replace the same keys."""

    return {**dict(settled), **dict(incoming or {})}


def _capability_plan_with_boundaries(
    plan: PlannedCapability,
    boundaries: dict,
) -> PlannedCapability:
    """Fill parameters the new choice omitted, then let the params model re-check."""

    if not boundaries:
        return plan
    explicit = {
        key: value for key, value in plan.parameters.items() if value is not None
    }
    filled = {**boundaries, **explicit}
    if filled == plan.parameters:
        return plan
    return PlannedCapability(
        user_goal=plan.user_goal,
        capability_key=plan.capability_key,
        capability_version=plan.capability_version,
        parameters=filled,
        requires_confirmation=plan.requires_confirmation,
    )


async def _skill_runtime_fail_closed(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    now,
    *,
    kind: str,
    content: str,
    error_code: str,
    attributes: dict,
) -> list[GovernanceMessage]:
    """Reject a Skill Runtime turn without creating a governance task."""

    await emit_product_event(
        db,
        "unsupported_rejected",
        session_id=session_id,
        attributes={**attributes, "error_code": error_code},
        occurred_at=now,
    )
    return await _reply(
        db,
        client_id,
        session_id,
        kind,
        content,
        now,
        payload={"error_code": error_code},
    )


async def _execute_readonly_capability_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    domain: str,
    plan: PlannedCapability,
    boundaries: dict,
    now,
) -> list[GovernanceMessage]:
    """Run one accepted read-only capability and store only a session message.

    No governance task, skill run, or completion record is created.
    """

    plan = _capability_plan_with_boundaries(plan, boundaries)
    capability = resolve_capability(domain, plan.capability_key)
    if (
        capability is None
        or capability.requires_confirmation
    ):
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content="该只读能力不能执行。",
            error_code="capability_not_executable",
            attributes={"domain": domain, "capability": plan.capability_key},
        )
    try:
        params = capability.params_model.model_validate(plan.parameters)
    except ValidationError:
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content=INVALID_CAPABILITY_PARAMETERS_MESSAGE,
            error_code="capability_parameters_invalid",
            attributes={"domain": domain, "capability": capability.key},
        )

    outcome = await execute_capability(
        db,
        CapabilityContext(session_id=session_id, client_id=client_id),
        capability,
        params,
    )
    message = _assistant_message(
        client_id,
        session_id,
        capability.key,
        outcome.content,
        now,
        payload=outcome.payload,
    )
    db.add(message)
    await db.flush()
    return [message]


async def _planning_inputs(
    db: AsyncSession, plan: GovernanceClarificationPlan
) -> tuple[str, ...]:
    source_ids = [int(value) for value in _loads_list(plan.source_message_ids_json)]
    if not source_ids:
        raise GovernancePlanningContextError(
            "goal_context_missing", "待澄清规划缺少原始用户输入。"
        )
    result = await db.execute(
        select(GovernanceMessage)
        .where(
            GovernanceMessage.id.in_(source_ids),
            GovernanceMessage.session_id == plan.session_id,
            GovernanceMessage.client_id == plan.client_id,
            GovernanceMessage.role == "user",
        )
        .order_by(GovernanceMessage.id)
    )
    messages = list(result.scalars())
    if [message.id for message in messages] != source_ids:
        raise GovernancePlanningContextError(
            "goal_context_missing", "待澄清规划的原始输入已不可用。"
        )
    return tuple(message.content for message in messages)


# The planner only needs enough identities to resolve a name the user just saw.
_RECORD_CONTEXT_LIMIT = 20
_RECORD_NAME_MAX = 120


async def _session_record_context(
    db: AsyncSession, session_id: str, client_id: str
) -> tuple[dict, ...]:
    """Trusted record identities from this session's latest persisted list.

    Derived from the list message the server already wrote, never from the
    client. It gives the planner a ``name -> record_id`` fact source without
    letting either the model or the request body invent one.
    """

    result = await db.execute(
        select(GovernanceMessage)
        .where(
            GovernanceMessage.session_id == session_id,
            GovernanceMessage.client_id == client_id,
            GovernanceMessage.role == "assistant",
            GovernanceMessage.kind.in_(
                ("risk_system_record_search", "cultural_system_record_search")
            ),
        )
        .order_by(GovernanceMessage.id.desc())
        .limit(1)
    )
    message = result.scalars().first()
    if message is None:
        return ()
    records = _loads_json(message.payload_json).get("records")
    if not isinstance(records, list):
        return ()
    context: list[dict] = []
    for record in records[:_RECORD_CONTEXT_LIMIT]:
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("record_id") or "").strip()
        if not record_id:
            continue
        context.append(
            {
                "record_id": record_id[:160],
                "name": str(record.get("name") or "").strip()[:_RECORD_NAME_MAX],
                "source_repo": str(record.get("source_repo") or "").strip()[:200],
                "source_commit": str(record.get("source_commit") or "").strip()[:80],
                "asset_version": str(record.get("asset_version") or "").strip()[:40],
            }
        )
    return tuple(context)


def _last_clarification_missing_items(
    plan: GovernanceClarificationPlan,
) -> tuple[str, ...]:
    """Items the last question asked for; the newest input answers them."""

    records = _loads_list(plan.system_clarifications_json)
    if not records or not isinstance(records[-1], dict):
        return ()
    items = records[-1].get("missing_items")
    if not isinstance(items, list):
        return ()
    return tuple(str(item).strip() for item in items if str(item).strip())


async def _start_or_continue_clarification_plan(
    db: AsyncSession,
    *,
    session: GovernanceSession,
    user_message: GovernanceMessage,
    plan_id: str | None,
    plan_version: int | None,
    requested_skill_key: str | None,
    now,
) -> GovernanceClarificationPlan:
    """Claim one plan version and append the new immutable source message."""

    if not plan_id and plan_version is not None:
        raise GovernancePlanningContextError(
            "planning_context_stale", "待澄清规划版本必须与规划标识一起提交。"
        )
    if plan_id:
        result = await db.execute(
            select(GovernanceClarificationPlan).where(
                GovernanceClarificationPlan.plan_id == plan_id,
                GovernanceClarificationPlan.client_id == session.client_id,
                GovernanceClarificationPlan.session_id == session.session_id,
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划不存在或不属于当前会话。"
            )
        if plan.status != "awaiting_clarification":
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划已结束，不能继续追加输入。"
            )
        if plan_version is None or plan.version != plan_version:
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划版本已变化，请刷新会话后重试。"
            )
        source_ids = [int(value) for value in _loads_list(plan.source_message_ids_json)]
        claimed = await db.execute(
            update(GovernanceClarificationPlan)
            .where(
                GovernanceClarificationPlan.id == plan.id,
                GovernanceClarificationPlan.status == "awaiting_clarification",
                GovernanceClarificationPlan.version == plan_version,
            )
            .values(
                source_message_ids_json=json.dumps(
                    [*source_ids, user_message.id], ensure_ascii=False
                ),
                version=plan_version + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划已被其他请求更新，请刷新后重试。"
            )
        await db.refresh(plan)
        return plan

    await db.execute(
        update(GovernanceClarificationPlan)
        .where(
            GovernanceClarificationPlan.session_id == session.session_id,
            GovernanceClarificationPlan.client_id == session.client_id,
            GovernanceClarificationPlan.status == "awaiting_clarification",
        )
        .values(status="abandoned", abandoned_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    bound_skill_version = None
    skill_content_digest = None
    contract_digest = None
    if requested_skill_key:
        descriptor = next(
            (
                item
                for item in list_skill_descriptors()
                if item.skill_key == requested_skill_key
            ),
            None,
        )
        if descriptor is not None:
            bound_skill_version = descriptor.version
            skill_content_digest = descriptor.skill_content_digest
            contract_digest = descriptor.contract_digest
    plan = GovernanceClarificationPlan(
        plan_id=str(uuid4()),
        session_id=session.session_id,
        client_id=session.client_id,
        status="awaiting_clarification",
        source_message_ids_json=json.dumps([user_message.id]),
        system_clarifications_json="[]",
        settled_boundaries_json="{}",
        goal_draft=None,
        bound_skill_key=requested_skill_key,
        bound_skill_version=bound_skill_version,
        skill_content_digest=skill_content_digest,
        contract_digest=contract_digest,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    await db.flush()
    return plan


async def _prepare_clarification_context(
    db: AsyncSession,
    *,
    session: GovernanceSession,
    user_message: GovernanceMessage,
    plan_id: str | None,
    plan_version: int | None,
    requested_skill_key: str | None,
    now,
) -> GovernanceClarificationPlan | None:
    """Create or claim the durable planning context when Skill Runtime is on."""

    if get_settings().governance_skill_runtime_mode != "on":
        return None
    await db.flush()
    return await _start_or_continue_clarification_plan(
        db,
        session=session,
        user_message=user_message,
        plan_id=plan_id,
        plan_version=plan_version,
        requested_skill_key=requested_skill_key,
        now=now,
    )


async def _validate_plan_binding(
    plan: GovernanceClarificationPlan,
) -> str | None:
    if not plan.bound_skill_key or not plan.bound_skill_version:
        return plan.bound_skill_key
    try:
        activated = activate_registered_skill(
            plan.bound_skill_key, plan.bound_skill_version
        )
    except SkillRegistryError:
        return None
    descriptor = activated.descriptor
    if (
        descriptor.skill_content_digest != plan.skill_content_digest
        or descriptor.contract_digest != plan.contract_digest
    ):
        return None
    return plan.bound_skill_key


def _record_plan_clarification(
    plan: GovernanceClarificationPlan,
    message: GovernanceMessage,
    question: str,
    missing_items: tuple[str, ...],
    now,
) -> None:
    records = _loads_list(plan.system_clarifications_json)
    records.append(
        {
            "message_id": message.id,
            "question": question,
            "missing_items": list(missing_items),
            "created_at": now.isoformat() + "Z",
        }
    )
    plan.system_clarifications_json = json.dumps(records, ensure_ascii=False)
    plan.updated_at = now


def _resolve_plan(
    plan: GovernanceClarificationPlan, planned: PlannedGovernanceTurn, now
) -> None:
    plan.status = "resolved"
    plan.goal_draft = planned.user_goal
    plan.resolved_goal = planned.user_goal
    plan.updated_at = now
    plan.resolved_at = now
    if planned.skill is not None:
        descriptor = planned.skill.activated.descriptor
        plan.bound_skill_key = descriptor.skill_key
        plan.bound_skill_version = descriptor.version
        plan.skill_content_digest = descriptor.skill_content_digest
        plan.contract_digest = descriptor.contract_digest


def _invalidate_plan(plan: GovernanceClarificationPlan, now) -> None:
    plan.status = "invalidated"
    plan.updated_at = now
    plan.invalidated_at = now


def _skill_runtime_task(
    client_id: str,
    session_id: str,
    capability_key: str,
    now,
    task_provider: str,
    extra_parameters: dict,
) -> GovernanceTask:
    """One planner turn that produced durable work.

    The task is the durable user goal; the capability run it will own holds the
    real frozen scope, executor identity and result facts.
    """

    return GovernanceTask(
        task_id=str(uuid4()),
        client_id=client_id,
        session_id=session_id,
        capability=capability_key,
        parameters_json=json.dumps(
            {"skill_runtime": True, **extra_parameters}, ensure_ascii=False
        ),
        status="completed",
        provider=task_provider,
        model="skill-runtime",
        latency_ms=0,
        parse_status="ok",
        error_message=None,
        created_at=now,
        finished_at=now,
    )


async def _run_capability_selection_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    domain: str,
    turn: PlannedGovernanceTurn,
    plan: PlannedCapability,
    clarification_plan: GovernanceClarificationPlan,
    boundaries: dict,
    task_provider: str,
    requested_skill_key: str | None,
    now,
) -> list[GovernanceMessage]:
    """Land one accepted capability selection.

    A no-confirmation capability only produces a session message. A
    confirmation-required capability creates the durable task and its first
    capability run, then waits for confirmation; the evaluator is not called.
    """

    _resolve_plan(clarification_plan, turn, now)
    if not plan.requires_confirmation:
        return await _execute_readonly_capability_turn(
            db, client_id, session_id, domain, plan, boundaries, now
        )

    capability = resolve_capability(domain, plan.capability_key)
    if capability is None:
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content="该治理能力不在当前业务域范围内，无法执行。",
            error_code="capability_out_of_domain",
            attributes={"domain": domain, "capability": plan.capability_key},
        )
    try:
        params = capability.params_model.model_validate(plan.parameters)
    except ValidationError:
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content=INVALID_CAPABILITY_PARAMETERS_MESSAGE,
            error_code="capability_parameters_invalid",
            attributes={"domain": domain, "capability": capability.key},
        )

    task = _skill_runtime_task(
        client_id,
        session_id,
        capability.key,
        now,
        task_provider,
        {
            "selection_status": "selected",
            "capability": capability.key,
            "requested_skill_key": requested_skill_key,
        },
    )
    db.add(task)
    await emit_product_event(
        db,
        "goal_recognized",
        session_id=session_id,
        task_id=task.task_id,
        attributes={
            "domain": domain,
            "provider": task_provider,
            "capability": capability.key,
            "parse_status": "ok",
        },
        occurred_at=now,
    )
    return await _await_confirmation_turn(
        db, client_id, session_id, capability, params, task, now
    )


async def _run_skill_runtime_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    domain: str,
    prompt: str,
    now,
    *,
    requested_skill_key: str | None = None,
    requested_capability: str | None = None,
    requested_parameters: dict | None = None,
    clarification_plan: GovernanceClarificationPlan,
) -> list[GovernanceMessage]:
    """Planner path: at most one provider completion; never fall back.

    A governance task exists only once the planner returned an accepted
    capability or skill and server-side validation passed. A rejection or an
    unparseable reply is a fail-closed boundary; only ``turn.clarification``
    resumes, as an incomplete goal or a missing required parameter.
    """

    # Never let the planner guess whether a bare v7 means the evaluated asset
    # version or the evaluator model version. This guard runs before any model
    # completion, so it holds in both runtime modes.
    guard_message = ambiguous_asset_version_message(domain, prompt)
    if guard_message is not None:
        return await _reply(
            db,
            client_id,
            session_id,
            "clarify",
            guard_message,
            now,
            payload={"error_code": "asset_version_ambiguous"},
        )

    planner = get_governance_planner()
    try:
        turn_inputs = await _planning_inputs(db, clarification_plan)
    except GovernancePlanningContextError as error:
        _invalidate_plan(clarification_plan, now)
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content=str(error),
            error_code=error.code,
            attributes={"domain": domain, "status": "invalidated"},
        )
    boundaries = _loads_json(clarification_plan.settled_boundaries_json)
    missing_items = _last_clarification_missing_items(clarification_plan)
    record_context = await _session_record_context(db, session_id, client_id)
    if clarification_plan.version > 1:
        if (
            requested_skill_key
            and requested_skill_key != clarification_plan.bound_skill_key
        ):
            _invalidate_plan(clarification_plan, now)
            return await _skill_runtime_fail_closed(
                db,
                client_id,
                session_id,
                now,
                kind="boundary",
                content="续接请求不能更改已冻结的治理技能。",
                error_code="skill_binding_invalidated",
                attributes={"domain": domain, "status": "invalidated"},
            )
        bound_key = await _validate_plan_binding(clarification_plan)
        if clarification_plan.bound_skill_key and bound_key is None:
            _invalidate_plan(clarification_plan, now)
            return await _skill_runtime_fail_closed(
                db,
                client_id,
                session_id,
                now,
                kind="boundary",
                content="待澄清期间绑定的治理技能或契约已变化，请重新发起目标。",
                error_code="skill_binding_invalidated",
                attributes={"domain": domain, "status": "invalidated"},
            )
        requested_skill_key = bound_key or requested_skill_key
    turn = await plan_governance_turn(
        turn_inputs[-1],
        domain,
        planner,
        requested_capability=requested_capability,
        requested_skill_key=requested_skill_key,
        requested_parameters=requested_parameters,
        user_inputs=turn_inputs,
        missing_items=missing_items,
        settled_boundaries=boundaries,
        record_context=record_context,
    )
    if turn.clarification is not None:
        clarification_plan.goal_draft = turn.clarification.goal_draft
        question = turn.clarification.question
        merged_boundaries = _merge_clarification_boundaries(
            boundaries, turn.clarification.boundaries
        )
        replies = await _reply(
            db,
            client_id,
            session_id,
            "clarify",
            question,
            now,
            payload=build_clarification_plan_payload(
                turn_inputs, question, merged_boundaries
            ),
        )
        _record_plan_clarification(
            clarification_plan,
            replies[0],
            question,
            turn.clarification.missing_items,
            now,
        )
        clarification_plan.settled_boundaries_json = json.dumps(
            merged_boundaries, ensure_ascii=False
        )
        return replies
    provider_name = getattr(planner, "name", "deterministic")
    task_provider = (
        provider_name if provider_name in {"qwen", "deepseek", "stub"} else "deterministic"
    )

    if turn.rejection is not None:
        _invalidate_plan(clarification_plan, now)
        return await _skill_runtime_fail_closed(
            db,
            client_id,
            session_id,
            now,
            kind="boundary",
            content=turn.rejection.message,
            error_code=turn.rejection.code,
            attributes={
                "domain": domain,
                "provider": task_provider,
                "status": "rejected",
            },
        )

    if turn.capability is not None:
        return await _run_capability_selection_turn(
            db,
            client_id,
            session_id,
            domain,
            turn,
            turn.capability,
            clarification_plan,
            boundaries,
            task_provider,
            requested_skill_key,
            now,
        )

    skill = turn.skill
    proposal = skill.plan_proposal
    _resolve_plan(clarification_plan, turn, now)
    skill_domain = skill.activated.descriptor.domain
    prepare = skill.checked_steps[0]
    capability = prepare.capability
    params = prepare.params

    task = _skill_runtime_task(
        client_id,
        session_id,
        capability.key,
        now,
        task_provider,
        {
            "selection_status": "selected",
            "requested_skill_key": requested_skill_key,
        },
    )
    db.add(task)
    await emit_product_event(
        db,
        "goal_recognized",
        session_id=session_id,
        task_id=task.task_id,
        attributes={
            "domain": skill_domain,
            "provider": task_provider,
            "capability": capability.key,
            "skill_key": proposal.skill_key,
            "skill_version": proposal.skill_version,
            "parse_status": "ok",
        },
        occurred_at=now,
    )

    if capability.requires_confirmation:
        return await _await_confirmation_turn(
            db, client_id, session_id, capability, params, task, now
        )

    outcome = await execute_capability(
        db,
        CapabilityContext(session_id=session_id, client_id=client_id),
        capability,
        params,
    )
    message = _assistant_message(
        client_id,
        session_id,
        capability.key,
        outcome.content,
        now,
        payload=outcome.payload,
    )
    db.add(message)
    await db.flush()
    db.add(
        GovernanceCompletionRecord(
            completion_id=str(uuid4()),
            task_id=task.task_id,
            session_id=session_id,
            message_id=message.id,
            capability=capability.key,
            capability_version=outcome.payload.get("capability_version", capability.version),
            result_snapshot_json=json.dumps(outcome.payload, ensure_ascii=False),
            source_refs_json=json.dumps(
                outcome.payload.get("source_refs", []), ensure_ascii=False
            ),
            completed_at=now,
        )
    )
    await emit_product_event(
        db,
        "task_completed",
        session_id=session_id,
        task_id=task.task_id,
        attributes={
            "domain": skill_domain,
            "capability": capability.key,
            "skill_key": proposal.skill_key,
            "status": "completed",
            "provider": task_provider,
        },
        occurred_at=now,
    )
    return [message]


# ADR-0012 retires single-capability skill packages, so a request that still
# names one of their skill keys has no package left to bind to. Each entry maps
# the retired skill key to the capability that now does the work; this ledger is
# the whole reason the mapping survives the package deletion.
#
# The retired ``dynbench400_eval`` *capability* alias was dropped with the v015
# cleanup migration (#169, W6): once those task rows are gone there is nothing
# left to redirect, and a genuinely unknown capability must fail closed.
_RETIRED_SKILL_KEYS = {
    "dynbench400-eval": "risk_corpus_rescan",
    "risk-corpus-rescan": "risk_corpus_rescan",
}


def _resolve_requested_binding(
    domain: str,
    requested_skill_key: str | None,
    requested_capability: str | None,
) -> tuple[str | None, str | None]:
    """Normalize one turn's explicit recommendation binding.

    A retired single-capability skill key is routed to the capability that now
    performs the work, so a stored option or an older client still resolves
    instead of failing closed. Genuine cross-capability skills keep their skill
    binding, and an explicit capability always wins.
    """

    requested_capability = (requested_capability or "").strip() or None
    skill_key = (requested_skill_key or "").strip() or None
    if requested_capability or skill_key is None:
        return skill_key, requested_capability
    bridged = _RETIRED_SKILL_KEYS.get(skill_key)
    if bridged is None:
        return skill_key, requested_capability
    capability = resolve_capability(domain, bridged)
    if capability is None:
        return skill_key, requested_capability
    return None, capability.key


def _capability_binding(
    domain: str, requested_capability: str | None
) -> tuple[str, CapabilityDef | None]:
    """Classify an explicit recommendation binding.

    Read-only capabilities execute with empty parameters. Confirmation-required
    capabilities fall through so the prompt can still supply scope. An unknown
    key is rejected and never handed to the planner or the interpreter.
    """

    key = (requested_capability or "").strip()
    if not key:
        return "absent", None
    capability = resolve_capability(domain, key)
    if capability is None:
        return "unknown", None
    if capability.requires_confirmation:
        return "confirm", capability
    return "readonly", capability


def _binding_interpretation(intent: GovernanceIntent) -> AssistantInterpretation:
    return AssistantInterpretation(
        provider="capability_binding",
        model="bound-capability",
        latency_ms=0,
        parse_status="ok",
        intent=intent,
        raw=intent.model_dump(),
    )


_RECORD_DETAIL_MARKERS = re.compile(r"打开|详情|详细")
_RECORD_ID_CANDIDATE = re.compile(
    r"(?<![0-9A-Za-z._-])([0-9A-Za-z][0-9A-Za-z._-]{2,63})"
)


async def _bind_exact_risk_record_id(
    db: AsyncSession,
    domain: str,
    prompt: str,
    requested_skill_key: str | None,
    requested_capability: str | None,
) -> tuple[str | None, dict | None]:
    """Bind a registry-owned exact id before any model sees the prompt.

    The text itself is never trusted as an asset fact: every candidate must
    resolve through the risk system-record registry. Explicit client bindings
    and non-detail wording keep their existing paths.
    """

    if (
        domain != "output"
        or requested_skill_key
        or requested_capability
        or _RECORD_DETAIL_MARKERS.search(prompt) is None
    ):
        return requested_capability, None
    matched_record_ids = []
    for match in _RECORD_ID_CANDIDATE.finditer(prompt):
        record_id = match.group(1)
        if await get_risk_system_record_asset(db, record_id) is not None:
            matched_record_ids.append(record_id)
    if len(matched_record_ids) == 1:
        return "risk_system_record_detail", {"record_id": matched_record_ids[0]}
    return requested_capability, None


async def _run_assistant_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    domain: str,
    prompt: str,
    now,
    *,
    requested_skill_key: str | None = None,
    requested_capability: str | None = None,
    requested_parameters: dict | None = None,
    clarification_plan: GovernanceClarificationPlan | None = None,
) -> list[GovernanceMessage]:
    deterministic_capability, deterministic_parameters = await _bind_exact_risk_record_id(
        db,
        domain,
        prompt,
        requested_skill_key,
        requested_capability,
    )
    if deterministic_capability is not None and requested_capability is None:
        requested_capability = deterministic_capability
        requested_parameters = deterministic_parameters
    requested_skill_key, requested_capability = _resolve_requested_binding(
        domain, requested_skill_key, requested_capability
    )
    binding, capability = _capability_binding(domain, requested_capability)
    if binding == "readonly" and capability is not None:
        interpretation = _binding_interpretation(
            GovernanceIntent(
                kind="execute",
                capability=capability.key,
                parameters=dict(requested_parameters or {}),
            )
        )
    elif binding == "unknown":
        interpretation = _binding_interpretation(
            GovernanceIntent(
                kind="boundary",
                message="该治理能力不在当前业务域范围内，无法执行。",
            )
        )
    elif get_settings().governance_skill_runtime_mode == "on":
        if clarification_plan is None:
            raise GovernancePlanningContextError(
                "goal_context_missing", "缺少待澄清规划上下文。"
            )
        return await _run_skill_runtime_turn(
            db,
            client_id,
            session_id,
            domain,
            prompt,
            now,
            requested_skill_key=requested_skill_key,
            requested_capability=requested_capability,
            requested_parameters=requested_parameters,
            clarification_plan=clarification_plan,
        )
    else:
        interpreter = get_assistant_interpreter()
        interpretation = await interpreter.interpret(domain, prompt)
    intent = interpretation.intent
    guard_message = ambiguous_asset_version_clarification(domain, prompt, intent)
    if guard_message is not None:
        intent = GovernanceIntent(kind="clarify", message=guard_message)
    if clarification_plan is not None and binding == "readonly":
        clarification_plan.status = "resolved"
        clarification_plan.resolved_goal = prompt
        clarification_plan.resolved_at = now
        clarification_plan.updated_at = now
    elif clarification_plan is not None and binding == "unknown":
        _invalidate_plan(clarification_plan, now)

    task = GovernanceTask(
        task_id=str(uuid4()),
        client_id=client_id,
        session_id=session_id,
        capability=intent.capability if intent else None,
        parameters_json=json.dumps(intent.parameters if intent else {}, ensure_ascii=False),
        status="completed",
        provider=interpretation.provider,
        model=interpretation.model,
        latency_ms=interpretation.latency_ms,
        parse_status=interpretation.parse_status,
        error_message=interpretation.error,
        created_at=now,
        finished_at=now,
    )
    db.add(task)

    if intent is None:
        task.status = "failed"
        return await _reply(
            db, client_id, session_id, "clarify", "暂时无法理解该请求，请换一种说法或补充信息。", now
        )

    if intent.kind == "clarify":
        return await _reply(
            db, client_id, session_id, "clarify", intent.message or "请补充要执行的治理动作。", now
        )

    if intent.kind == "boundary":
        await emit_product_event(
            db,
            "unsupported_rejected",
            session_id=session_id,
            task_id=task.task_id,
            attributes={
                "domain": domain,
                "provider": interpretation.provider,
                "error_code": "boundary",
            },
            occurred_at=now,
        )
        return await _reply(
            db, client_id, session_id, "boundary", intent.message or "该请求不在当前治理能力范围内。", now
        )

    capability = resolve_capability(domain, intent.capability or "")
    if capability is None:
        await emit_product_event(
            db,
            "unsupported_rejected",
            session_id=session_id,
            task_id=task.task_id,
            attributes={
                "domain": domain,
                "provider": interpretation.provider,
                "error_code": "capability_out_of_domain",
                "capability": intent.capability or "",
            },
            occurred_at=now,
        )
        return await _reply(
            db, client_id, session_id, "boundary", "该治理能力不在当前业务域范围内，无法执行。", now
        )

    try:
        params = capability.params_model.model_validate(intent.parameters or {})
    except ValidationError:
        await emit_product_event(
            db,
            "unsupported_rejected",
            session_id=session_id,
            task_id=task.task_id,
            attributes={
                "domain": domain,
                "provider": interpretation.provider,
                "error_code": "invalid_params",
                "capability": capability.key,
            },
            occurred_at=now,
        )
        return await _reply(
            db, client_id, session_id, "boundary", "治理能力参数不合法，无法执行。", now
        )

    await emit_product_event(
        db,
        "goal_recognized",
        session_id=session_id,
        task_id=task.task_id,
        attributes={
            "domain": domain,
            "provider": interpretation.provider,
            "capability": capability.key,
            "latency_ms": interpretation.latency_ms,
            "parse_status": interpretation.parse_status,
        },
        occurred_at=now,
    )

    if capability.requires_confirmation:
        return await _await_confirmation_turn(
            db, client_id, session_id, capability, params, task, now
        )

    outcome = await execute_capability(
        db,
        CapabilityContext(session_id=session_id, client_id=client_id),
        capability,
        params,
    )
    message = _assistant_message(
        client_id,
        session_id,
        capability.key,
        outcome.content,
        now,
        payload=outcome.payload,
    )
    db.add(message)
    await db.flush()

    db.add(
        GovernanceCompletionRecord(
            completion_id=str(uuid4()),
            task_id=task.task_id,
            session_id=session_id,
            message_id=message.id,
            capability=capability.key,
            capability_version=outcome.payload.get("capability_version", capability.version),
            result_snapshot_json=json.dumps(outcome.payload, ensure_ascii=False),
            source_refs_json=json.dumps(
                outcome.payload.get("source_refs", []), ensure_ascii=False
            ),
            completed_at=now,
        )
    )
    await emit_product_event(
        db,
        "task_completed",
        session_id=session_id,
        task_id=task.task_id,
        attributes={
            "domain": domain,
            "capability": capability.key,
            "status": "completed",
            "provider": interpretation.provider,
        },
        occurred_at=now,
    )
    return [message]


async def _prepare_capability_run(
    db: AsyncSession,
    task: GovernanceTask,
    capability: CapabilityDef,
    params,
):
    """Freeze the scope of a confirmation-required capability as a first-class run.

    The frozen scope is resolved from server-owned asset facts; the evaluator is
    never called here. A scope that cannot be frozen raises ``SkillContractError``
    so the caller fails closed: a bound entry must never exist without the
    capability run that owns its frozen scope.
    """

    capability_parameters = params.model_dump()
    frozen_scope = freeze_capability_scope(capability, capability_parameters)
    return await create_capability_run(
        db,
        task,
        capability=capability,
        parameters=capability_parameters,
        scope=frozen_scope,
        status=RISK_RESCAN_STATUS_AWAITING,
    )


def _assert_capability_run_scope_current(capability_run) -> None:
    """Reject a confirmation whose frozen immutable scope facts have changed."""

    capability = resolve_capability_by_key(capability_run.capability_key)
    if capability is None:
        raise SkillContractError(
            "confirmation_invalidated", "执行能力已不在登记表中，原确认失效。"
        )
    current = freeze_capability_scope(
        capability, _loads_json(capability_run.parameters_json)
    )
    if capability_scope_fingerprint(current) != capability_run.scope_fingerprint:
        raise SkillContractError(
            "confirmation_invalidated", "执行范围已变化，原确认失效，需要重新确认。"
        )


async def _await_confirmation_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    capability,
    params,
    task: GovernanceTask,
    now,
) -> list[GovernanceMessage]:
    """Freeze the execution scope of a confirmation-required capability.

    The capability runner only resolves the scope — it never calls the online
    service. The task stays ``awaiting_confirmation`` until the user confirms
    or cancels it through the task endpoints."""
    outcome = await execute_capability(
        db,
        CapabilityContext(session_id=session_id, client_id=client_id),
        capability,
        params,
    )
    scope = dict(outcome.payload)
    scope["task_id"] = task.task_id

    if not scope.get("available"):
        task.status = RISK_RESCAN_STATUS_FAILED
        task.error_message = outcome.content
        return await _reply(db, client_id, session_id, capability.key, outcome.content, now)

    if not scope.get("samples"):
        content = "筛选范围内没有匹配的风险样本，无法发起二次检测；请调整筛选条件后重试。"
        task.status = RISK_RESCAN_STATUS_FAILED
        task.error_message = content
        return await _reply(db, client_id, session_id, capability.key, content, now)

    task.status = RISK_RESCAN_STATUS_AWAITING
    task.finished_at = None
    parameters: dict = {"root_frozen_scope": scope, "frozen_scope": scope}
    try:
        capability_run = await _prepare_capability_run(db, task, capability, params)
    except SkillContractError:
        content = "执行范围无法冻结，无法发起在线二次检测；请稍后重试。"
        task.status = RISK_RESCAN_STATUS_FAILED
        task.error_message = content
        return await _reply(db, client_id, session_id, capability.key, content, now)
    parameters["active_capability_run_id"] = capability_run.run_id
    plan_message = None
    # The plan projection is a read-only convenience: a planning failure must
    # never block the existing preview/confirmation flow.
    try:
        plan = validate_and_freeze_capability_plan(
            capability,
            params.model_dump(),
            planner_provider=_planner_provider_for(task),
        )
        plan_view = build_plan_view(
            plan,
            task_id=task.task_id,
            status=task.status,
            asset_name=scope.get("asset_name"),
        )
        parameters["plan_view"] = plan_view
        plan_message = _assistant_message(
            client_id,
            session_id,
            SKILL_PLAN_MESSAGE_KIND,
            _plan_message_content(plan_view),
            now,
            payload=plan_view,
        )
        await emit_product_event(
            db,
            "plan_first_pass_ok",
            session_id=session_id,
            task_id=task.task_id,
            attributes={
                "skill_key": plan.skill_key,
                "skill_version": plan.skill_version,
                "capability": capability.key,
                "first_pass": True,
                "status": task.status,
            },
            occurred_at=now,
        )
    except SkillContractError:
        plan_message = None
    task.parameters_json = json.dumps(parameters, ensure_ascii=False)
    if plan_message is not None:
        db.add(plan_message)
        await db.flush()
    message = _assistant_message(
        client_id,
        session_id,
        capability.key,
        outcome.content,
        now,
        payload=scope,
    )
    db.add(message)
    await db.flush()
    return [plan_message, message] if plan_message is not None else [message]


async def create_session(
    db: AsyncSession,
    client_id: str,
    domain: str,
    prompt: str,
    request_id: str | None = None,
    requested_skill_key: str | None = None,
    requested_capability: str | None = None,
    requested_parameters: dict | None = None,
    clarification_plan_id: str | None = None,
    clarification_plan_version: int | None = None,
) -> dict:
    request_id = request_id or str(uuid4())
    await _ensure_client(db, client_id)

    existing = await _existing_session_for_request(db, client_id, request_id)
    if existing is not None:
        return existing

    # A client that retained the stable planning id but lost the session id can
    # recover through the create endpoint. The plan remains owned by its
    # original session; creating a second session would split one goal context.
    if clarification_plan_id:
        plan_result = await db.execute(
            select(GovernanceClarificationPlan).where(
                GovernanceClarificationPlan.plan_id == clarification_plan_id,
                GovernanceClarificationPlan.client_id == client_id,
            )
        )
        existing_plan = plan_result.scalar_one_or_none()
        if existing_plan is None:
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划不存在或不属于当前客户端。"
            )
        continued = await append_turn(
            db,
            client_id,
            existing_plan.session_id,
            domain,
            prompt,
            request_id,
            requested_skill_key=requested_skill_key,
            requested_capability=requested_capability,
            requested_parameters=requested_parameters,
            clarification_plan_id=clarification_plan_id,
            clarification_plan_version=clarification_plan_version,
        )
        if continued is None:
            raise GovernancePlanningContextError(
                "planning_context_stale", "待澄清规划所属会话不可用。"
            )
        return continued

    now = utc_now()
    session = GovernanceSession(
        session_id=str(uuid4()),
        client_id=client_id,
        domain=domain,
        title=re.sub(r"\s+", " ", prompt).strip()[:28],
        created_at=now,
        updated_at=now,
    )
    message = GovernanceMessage(
        session_id=session.session_id,
        client_id=client_id,
        request_id=request_id,
        role="user",
        kind="text",
        content=prompt,
        created_at=now,
    )
    db.add(session)
    db.add(message)
    requested_skill_key, requested_capability = _resolve_requested_binding(
        domain, requested_skill_key, requested_capability
    )
    clarification_plan = await _prepare_clarification_context(
        db,
        session=session,
        user_message=message,
        plan_id=clarification_plan_id,
        plan_version=clarification_plan_version,
        requested_skill_key=requested_skill_key,
        now=now,
    )
    await _run_assistant_turn(
        db,
        client_id,
        session.session_id,
        domain,
        prompt,
        now,
        requested_skill_key=requested_skill_key,
        requested_capability=requested_capability,
        requested_parameters=requested_parameters,
        clarification_plan=clarification_plan,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _existing_session_for_request(db, client_id, request_id)
        if existing is None:
            raise ValueError("请求标识无法映射到已有会话") from None
        return existing
    return await _session_detail(db, session)


async def list_sessions(db: AsyncSession, client_id: str, limit: int, offset: int) -> dict:
    visible = (
        GovernanceSession.client_id == client_id,
        GovernanceSession.deleted_at.is_(None),
    )
    total = await db.scalar(select(func.count()).select_from(GovernanceSession).where(*visible))
    result = await db.execute(
        select(GovernanceSession)
        .where(*visible)
        .order_by(GovernanceSession.updated_at.desc(), GovernanceSession.session_id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [serialize_session(session) for session in result.scalars()],
        "total": total or 0,
    }


async def get_session(db: AsyncSession, client_id: str, session_id: str) -> dict | None:
    result = await db.execute(
        select(GovernanceSession).where(
            GovernanceSession.session_id == session_id,
            GovernanceSession.client_id == client_id,
            GovernanceSession.deleted_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    return await _session_detail(db, session)


async def create_cultural_prerun_review(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    record_id: str,
    record_version: str,
) -> dict | None:
    """Explicitly create one frozen cultural prerun review inside a session.

    Ownership is resolved here so a session that does not belong to the client
    is reported as missing (``None`` → 404), matching the other session
    endpoints. Domain/record/version/evidence conflicts propagate as the
    ``CulturalReview*`` errors so the route can map them to 409/404/400.
    """
    session = await _load_session(db, client_id, session_id)
    if session is None:
        return None
    await create_cultural_review_task(
        db,
        client_id=client_id,
        session=session,
        record_id=record_id,
        record_version=record_version,
    )
    return await _session_detail(db, session)


async def create_risk_prerun_review(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    record_id: str,
    record_version: str,
) -> dict | None:
    """Explicitly create one frozen risk prerun review inside a session (#90).

    Ownership is resolved here so a session that does not belong to the client
    is reported as missing (``None`` → 404). Domain/record/version/evidence
    conflicts propagate as ``RiskReview*`` errors for 409/404/400 mapping.
    """
    session = await _load_session(db, client_id, session_id)
    if session is None:
        return None
    await create_risk_review_task(
        db,
        client_id=client_id,
        session=session,
        record_id=record_id,
        record_version=record_version,
    )
    return await _session_detail(db, session)


async def _existing_session_for_request(
    db: AsyncSession, client_id: str, request_id: str
) -> dict | None:
    message = await _message_for_request(db, client_id, request_id)
    if message is None:
        return None
    result = await db.execute(
        select(GovernanceSession).where(
            GovernanceSession.session_id == message.session_id,
            GovernanceSession.client_id == client_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    return await _session_detail(db, session)


async def _load_session(
    db: AsyncSession, client_id: str, session_id: str
) -> GovernanceSession | None:
    result = await db.execute(
        select(GovernanceSession).where(
            GovernanceSession.session_id == session_id,
            GovernanceSession.client_id == client_id,
            GovernanceSession.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def append_turn(
    db: AsyncSession,
    client_id: str,
    session_id: str,
    domain: str,
    prompt: str,
    request_id: str | None = None,
    requested_skill_key: str | None = None,
    requested_capability: str | None = None,
    requested_parameters: dict | None = None,
    clarification_plan_id: str | None = None,
    clarification_plan_version: int | None = None,
) -> dict | None:
    request_id = request_id or str(uuid4())
    session = await _load_session(db, client_id, session_id)
    if session is None:
        return None
    if session.domain != domain:
        raise ValueError("治理会话的业务域不可更改")

    existing = await _existing_turn_message(db, client_id, session_id, request_id)
    if existing is not None:
        return await _session_detail(db, session)

    # Match against prior grounded suggestions before the new turn lands.
    prior_suggestions = await build_session_suggestions(db, session)
    continued_suggestion_id = match_suggestion_id(prompt, prior_suggestions)

    now = utc_now()
    message = GovernanceMessage(
        session_id=session_id,
        client_id=client_id,
        request_id=request_id,
        role="user",
        kind="text",
        content=prompt,
        created_at=now,
    )
    session.updated_at = now
    db.add(message)
    requested_skill_key, requested_capability = _resolve_requested_binding(
        domain, requested_skill_key, requested_capability
    )
    clarification_plan = await _prepare_clarification_context(
        db,
        session=session,
        user_message=message,
        plan_id=clarification_plan_id,
        plan_version=clarification_plan_version,
        requested_skill_key=requested_skill_key,
        now=now,
    )
    if continued_suggestion_id is not None:
        await emit_product_event(
            db,
            "suggestion_continued",
            session_id=session_id,
            attributes={
                "domain": domain,
                "suggestion_id": continued_suggestion_id,
            },
            occurred_at=now,
        )
    await _run_assistant_turn(
        db,
        client_id,
        session_id,
        domain,
        prompt,
        now,
        requested_skill_key=requested_skill_key,
        requested_capability=requested_capability,
        requested_parameters=requested_parameters,
        clarification_plan=clarification_plan,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _existing_turn_message(db, client_id, session_id, request_id)
        if existing is None:
            raise ValueError("请求标识已用于其他会话") from None
        return await _session_detail(db, session)
    return await _session_detail(db, session)


async def _existing_turn_message(
    db: AsyncSession, client_id: str, session_id: str, request_id: str
) -> GovernanceMessage | None:
    message = await _message_for_request(db, client_id, request_id)
    if message is None or message.session_id != session_id:
        return None
    session = await db.get(GovernanceSession, message.session_id)
    if session is None or session.client_id != client_id or session.deleted_at is not None:
        return None
    return message


async def soft_delete_session(
    db: AsyncSession, client_id: str, session_id: str
) -> dict | None:
    session = await _load_session(db, client_id, session_id)
    if session is None:
        return None
    session.deleted_at = utc_now()
    deleted_at = session.deleted_at.isoformat() + "Z"
    await db.commit()
    return {"session_id": session_id, "deleted_at": deleted_at}


# ---------------------------------------------------------------------------
# Governance task lifecycle: recovery, confirm, cancel, retry (#55)
# ---------------------------------------------------------------------------


def serialize_task(task: GovernanceTask) -> dict:
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "capability": task.capability,
        "status": task.status,
        "error_message": task.error_message,
        "parent_task_id": task.parent_task_id,
        "created_at": task.created_at.isoformat() + "Z",
        "finished_at": task.finished_at.isoformat() + "Z" if task.finished_at else None,
    }


async def _load_task(
    db: AsyncSession, client_id: str, task_id: str
) -> GovernanceTask | None:
    result = await db.execute(
        select(GovernanceTask).where(
            GovernanceTask.task_id == task_id,
            GovernanceTask.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def _latest_completion(
    db: AsyncSession, task_id: str
) -> GovernanceCompletionRecord | None:
    result = await db.execute(
        select(GovernanceCompletionRecord)
        .where(GovernanceCompletionRecord.task_id == task_id)
        .order_by(GovernanceCompletionRecord.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _frozen_sample_fact_tuple(sample: dict) -> tuple[str, str, str, str]:
    """Normalize preview/plan sample facts for confirmation binding.

    Older preview payloads may omit digests; derive them from the frozen text so
    confirm still compares the same server-owned facts as Agent Skills.
    """

    sample_id = str(sample.get("sample_id") or "")
    text = str(sample.get("text") or "")
    content_digest = str(sample.get("content_digest") or "") or sample_content_digest(
        text
    )
    source = str(sample.get("source") or "")
    source_revision = str(sample.get("source_revision") or "") or derive_source_revision(
        source, sample_id, content_digest
    )
    return (
        sample_id,
        content_digest,
        str(sample.get("reference_label") or ""),
        source_revision,
    )


def _frozen_scope(task: GovernanceTask) -> dict:
    scope = _loads_json(task.parameters_json).get("frozen_scope")
    return scope if isinstance(scope, dict) else {}


def _task_parameters(task: GovernanceTask) -> dict:
    return _loads_json(task.parameters_json)


def _root_frozen_scope(task: GovernanceTask) -> dict:
    parameters = _task_parameters(task)
    scope = parameters.get("root_frozen_scope") or parameters.get("frozen_scope")
    return scope if isinstance(scope, dict) else {}


def _planner_provider_for(task: GovernanceTask) -> str:
    """Planner provider recorded on a frozen plan, from the task's own provider."""

    return task.provider if task.provider in {"qwen", "deepseek"} else "deterministic"


def _capability_parameters_from_scope(scope: dict) -> dict:
    """Reconstruct a capability run's parameters from its frozen preview scope.

    Used only for a task that predates capability-run rows: the frozen scope is
    the same server-owned fact the run would have stored.
    """

    parameters: dict = dict(scope.get("filters") or {})
    sample_ids = [
        str(sample.get("sample_id") or "")
        for sample in scope.get("samples") or []
        if str(sample.get("sample_id") or "")
    ]
    if sample_ids:
        parameters["sample_ids"] = sample_ids
        parameters["limit"] = len(sample_ids)
    if scope.get("evaluator"):
        parameters["evaluator"] = scope["evaluator"]
    if scope.get("export_requested"):
        parameters["export_requested"] = True
    return parameters


def _frozen_capability_plan(
    task: GovernanceTask, capability_run
) -> GovernanceValidatedSkillPlan:
    """Freeze the confirm-bound plan of one direct capability run.

    The capability run owns the server-validated parameters of the run, so the
    plan is rebuilt from the task's own capability rather than from a skill
    package (retired in #169).
    """

    capability = resolve_capability_by_key(
        (
            capability_run.capability_key
            if capability_run is not None
            else task.capability
        )
        or ""
    )
    if capability is None:
        raise SkillContractError(
            "capability_not_registered",
            f"任务绑定的治理能力未登记：{task.capability or '（空）'}",
        )
    parameters = (
        _loads_json(capability_run.parameters_json)
        if capability_run is not None
        else _capability_parameters_from_scope(_frozen_scope(task))
    )
    return validate_and_freeze_capability_plan(
        capability, parameters, planner_provider=_planner_provider_for(task)
    )


_RESCAN_RETRY_PREVIEW_KEYS = (
    "available",
    "asset_id",
    "asset_name",
    "total_matched",
    "sample_count",
    "capped",
    "filters",
    "samples",
    "source_refs",
    "evaluation_object",
    "evaluator",
    "export_requested",
)


def _retry_preview_result(task: GovernanceTask, retry_scope: dict):
    """Shape retry preview from the frozen capability, not a rescan-only subset."""
    return RiskCorpusRescanPreviewResult(
        **{
            key: retry_scope[key]
            for key in _RESCAN_RETRY_PREVIEW_KEYS
            if key in retry_scope
        },
        task_id=task.task_id,
    )


async def _task_runs(
    db: AsyncSession, task_id: str
) -> list[GovernanceSkillRun]:
    result = await db.execute(
        select(GovernanceSkillRun)
        .where(GovernanceSkillRun.task_id == task_id)
        .order_by(GovernanceSkillRun.created_at, GovernanceSkillRun.id)
    )
    return list(result.scalars())


def _run_plan(run: GovernanceSkillRun) -> GovernanceValidatedSkillPlan:
    return GovernanceValidatedSkillPlan.model_validate_json(run.plan_json)


def _next_run_attempt(runs: list[GovernanceSkillRun]) -> int:
    if not runs:
        return 1
    return max(int(getattr(run, "attempt", 1) or 1) for run in runs) + 1


def _build_retry_revision(
    *,
    scope_selection: str,
    selected_ids: list[str],
    previous_ids: list[str],
    previous_run: GovernanceSkillRun | None,
    previous_plan: GovernanceValidatedSkillPlan | None,
    plan: GovernanceValidatedSkillPlan,
) -> GovernanceRetryRevision:
    previous_fingerprint = (
        previous_plan.scope.executor.implementation_fingerprint
        if previous_plan is not None
        else ""
    )
    new_fingerprint = plan.scope.executor.implementation_fingerprint
    previous_schema = previous_plan.result_schema if previous_plan is not None else ""
    new_schema = plan.result_schema
    added_sample_ids = [
        sample_id for sample_id in selected_ids if sample_id not in previous_ids
    ]
    removed_sample_ids = [
        sample_id for sample_id in previous_ids if sample_id not in selected_ids
    ]
    detector_changed = bool(
        previous_plan is not None and previous_fingerprint != new_fingerprint
    )
    schema_changed = bool(
        previous_plan is not None and previous_schema != new_schema
    )
    changed = (
        detector_changed
        or schema_changed
        or bool(added_sample_ids or removed_sample_ids)
    )
    reasons: list[str] = []
    if added_sample_ids or removed_sample_ids:
        reasons.append("重试样本范围相对上次运行已变化")
    if detector_changed:
        reasons.append("在线检测执行器指纹已变化")
    if schema_changed:
        reasons.append("结果 Schema 已变化")
    if not reasons:
        reasons.append("重试将产生新的技能运行，需重新确认")
    return GovernanceRetryRevision(
        changed=changed,
        scope_selection=scope_selection,
        added_sample_ids=added_sample_ids,
        removed_sample_ids=removed_sample_ids,
        detector_changed=detector_changed,
        schema_changed=schema_changed,
        previous_run_id=previous_run.run_id if previous_run is not None else None,
        previous_executor_fingerprint=previous_fingerprint,
        new_executor_fingerprint=new_fingerprint,
        requires_reconfirmation=True,
        reason="；".join(reasons),
    )


async def _persist_run(
    db: AsyncSession,
    task: GovernanceTask,
    plan: GovernanceValidatedSkillPlan,
    *,
    status: str,
    confirmed_at=None,
    attempt: int = 1,
    parent_run_id: str | None = None,
    scope_selection: str = "full",
    revision_json: str = "{}",
) -> GovernanceSkillRun:
    now = utc_now()
    run_id = str(uuid4())
    run = GovernanceSkillRun(
        run_id=run_id,
        task_id=task.task_id,
        skill_key=plan.skill_key,
        skill_version=plan.skill_version,
        entrypoint=plan.entrypoint,
        planner_provider=plan.planner_provider,
        status=status,
        plan_json=plan.model_dump_json(),
        scope_json=plan.scope.model_dump_json(),
        scope_fingerprint=plan.scope_fingerprint,
        semantic_fingerprint=plan.semantic_fingerprint,
        confirmation_scope_fingerprint=(
            plan.scope_fingerprint if confirmed_at is not None else None
        ),
        created_at=now,
        confirmed_at=confirmed_at,
        attempt=attempt,
        parent_run_id=parent_run_id,
        scope_selection=scope_selection,
        revision_json=revision_json,
        executor_fingerprint=plan.scope.executor.implementation_fingerprint,
        result_schema=plan.result_schema,
    )
    db.add(run)
    for position, step in enumerate(plan.steps):
        step_status = "completed" if step.action == "prepare" else status
        db.add(
            GovernanceCapabilityStep(
                step_id=str(uuid4()),
                run_id=run_id,
                position=position,
                branch=plan.branch,
                capability=step.capability,
                capability_version=step.capability_version,
                action=step.action,
                parameters_json=json.dumps(step.parameters, ensure_ascii=False),
                result_schema=plan.result_schema,
                requires_confirmation=step.requires_confirmation,
                status=step_status,
                created_at=now,
            )
        )
    await db.flush()
    return run


async def _session_for_task(
    db: AsyncSession, task: GovernanceTask, now
) -> GovernanceSession | None:
    session = await db.get(GovernanceSession, task.session_id)
    if session is not None:
        session.updated_at = now
    return session


async def _build_task_detail(db: AsyncSession, task: GovernanceTask) -> dict:
    """Assemble the get_task snapshot for an already-loaded task row."""
    completion = await _latest_completion(db, task.task_id)
    detail = serialize_task(task)
    aggregated = await build_task_aggregated_result(db, task)
    terminal_with_samples = task.status in {
        "completed",
        "completed_partial",
        "cancelled",
    }
    # The v2 input-risk contract (page summary + evidence pack from one persisted
    # result) must not be replaced by the legacy aggregated view.
    completion_is_v2 = completion is not None and str(
        completion.capability_version or ""
    ).startswith("v2")
    if (
        not completion_is_v2
        and aggregated is not None
        and aggregated_has_executed_samples(aggregated)
        and (completion is not None or terminal_with_samples)
    ):
        detail["result"] = aggregated
        detail["capability_version"] = aggregated.get("capability_version") or ""
        completed_at = aggregated.get("completed_at")
        detail["completed_at"] = completed_at if completed_at else None
    elif completion is not None:
        detail["result"] = _loads_json(completion.result_snapshot_json)
        detail["capability_version"] = completion.capability_version
        detail["completed_at"] = completion.completed_at.isoformat() + "Z"
    else:
        detail["result"] = None
        detail["capability_version"] = capability_version_from_scope(_frozen_scope(task))
    events = await list_task_events(db, task.task_id, after_sequence=0)
    latest_event = events[-1] if events else None
    detail["event_cursor"] = latest_event["sequence"] if latest_event else 0
    detail["progress"] = latest_event["counts"] if latest_event else {
        "completed": 0,
        "failed": 0,
        "total": len(_frozen_scope(task).get("samples") or []),
    }
    summary = await summarize_task_results(db, task.task_id)
    detail["runs"] = summary.get("run_groups", [])
    detail["aggregation"] = {
        "status_counts": summary.get("status_counts", {}),
        "compatibility_groups": summary.get("compatibility_groups", []),
    }
    detail["comparison"] = (
        summary.get("compatibility_groups", [])
        if len(summary.get("compatibility_groups", [])) > 1
        else []
    )
    parameters = _task_parameters(task)
    detail["active_run_id"] = parameters.get("active_run_id")
    detail["active_capability_run_id"] = parameters.get("active_capability_run_id")
    detail["capability_runs"] = [
        serialize_capability_run(run)
        for run in await list_capability_runs(db, task.task_id)
    ]
    detail["revised_plan"] = parameters.get("revised_plan")
    # The stored plan view is frozen at plan time, so its execute step stays
    # "pending"; overlay the live task status when the stored value is a dict
    # (a non-dict left by an older task is passed through untouched).
    stored_plan = parameters.get("plan_view")
    detail["plan"] = (
        apply_plan_progress(stored_plan, task.status)
        if isinstance(stored_plan, dict)
        else stored_plan
    )
    return detail


async def get_task(db: AsyncSession, client_id: str, task_id: str) -> dict | None:
    """Task snapshot for refresh recovery; scoped to the owning client only."""
    task = await _load_task(db, client_id, task_id)
    if task is None:
        return None
    return await _build_task_detail(db, task)


async def get_task_for_review(db: AsyncSession, task_id: str) -> dict | None:
    """Task snapshot by ``task_id`` only (no client ownership).

    Used by anonymous review shares after the share token has already been
    validated. Reuses the same aggregation path as ``get_task``.
    """
    result = await db.execute(
        select(GovernanceTask).where(GovernanceTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None
    return await _build_task_detail(db, task)


async def confirm_task(
    db: AsyncSession, client_id: str, task_id: str
) -> dict | None:
    """Persist confirmation and enqueue execution for an independent worker."""
    task = await _load_task(db, client_id, task_id)
    if task is None:
        return None

    scope = _frozen_scope(task)
    parameters = _task_parameters(task)
    capability_run = await active_capability_run(db, task)
    runs = await _task_runs(db, task.task_id)
    pending_run = next(
        (
            run
            for run in reversed(runs)
            if run.run_id == parameters.get("active_run_id")
            and run.status == RISK_RESCAN_STATUS_AWAITING
        ),
        None,
    )
    try:
        if (
            capability_run is not None
            and capability_run.status == RISK_RESCAN_STATUS_AWAITING
        ):
            _assert_capability_run_scope_current(capability_run)
        plan = (
            _run_plan(pending_run)
            if pending_run is not None
            else _frozen_capability_plan(task, capability_run)
        )
        preview_facts = [
            _frozen_sample_fact_tuple(sample) for sample in scope.get("samples") or []
        ]
        plan_facts = [
            (
                fact.sample_id,
                fact.content_digest,
                fact.reference_label,
                fact.source_revision,
            )
            for fact in plan.scope.samples
        ]
        if preview_facts != plan_facts:
            raise SkillContractError(
                "confirmation_invalidated", "执行样本事实已变化，原确认失效"
            )
        validate_execution(
            plan,
            GovernanceSkillConfirmation(scope_fingerprint=plan.scope_fingerprint),
        )
    except SkillContractError as error:
        raise GovernanceTaskStateError(str(error)) from error

    claimed = await db.execute(
        update(GovernanceTask)
        .where(
            GovernanceTask.task_id == task_id,
            GovernanceTask.client_id == client_id,
            GovernanceTask.status == RISK_RESCAN_STATUS_AWAITING,
        )
        .values(status="queued")
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        fresh = await _load_task(db, client_id, task_id)
        if fresh is None:
            return None
        raise GovernanceTaskStateError(f"任务当前状态为 {fresh.status}，不能确认执行。")

    now = utc_now()
    if pending_run is None:
        run = await _persist_run(
            db, task, plan, status=RISK_RESCAN_STATUS_QUEUED, confirmed_at=now
        )
    else:
        run = pending_run
        run.status = RISK_RESCAN_STATUS_QUEUED
        run.confirmed_at = now
        run.confirmation_scope_fingerprint = plan.scope_fingerprint
        await db.execute(
            update(GovernanceCapabilityStep)
            .where(
                GovernanceCapabilityStep.run_id == run.run_id,
                GovernanceCapabilityStep.action == "execute",
                GovernanceCapabilityStep.status == RISK_RESCAN_STATUS_AWAITING,
            )
            .values(status=RISK_RESCAN_STATUS_QUEUED)
            .execution_options(synchronize_session=False)
        )
    if capability_run is not None:
        mark_confirmed(capability_run, confirmed_at=now, skill_run_id=run.run_id)
    parameters.setdefault("root_frozen_scope", scope)
    parameters["active_run_id"] = run.run_id
    task.parameters_json = json.dumps(parameters, ensure_ascii=False)
    await append_task_event(
        db,
        task_id,
        event_type="stage",
        stage=RISK_RESCAN_STATUS_QUEUED,
        counts={"completed": 0, "failed": 0, "total": plan.scope.sample_count},
        resource_refs=[],
    )
    await db.commit()
    return {
        "task_id": task_id,
        "run_id": run.run_id,
        "status": RISK_RESCAN_STATUS_QUEUED,
    }


async def cancel_task(
    db: AsyncSession, client_id: str, task_id: str
) -> dict | None:
    """Cancel immediately before confirmation or request cooperative stop."""
    task = await _load_task(db, client_id, task_id)
    if task is None:
        return None

    capability_run = await active_capability_run(db, task)
    if task.status in {RISK_RESCAN_STATUS_QUEUED, RISK_RESCAN_STATUS_RUNNING}:
        changed = await db.execute(
            update(GovernanceTask)
            .where(
                GovernanceTask.task_id == task_id,
                GovernanceTask.client_id == client_id,
                GovernanceTask.status.in_(
                    (RISK_RESCAN_STATUS_QUEUED, RISK_RESCAN_STATUS_RUNNING)
                ),
            )
            .values(status=RISK_RESCAN_STATUS_CANCELLING)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            fresh = await _load_task(db, client_id, task_id)
            raise GovernanceTaskStateError(
                f"任务当前状态为 {fresh.status if fresh else 'unknown'}，不能取消。"
            )
        # Keep the in-session task instance in sync with the atomic update so the
        # refreshed snapshot below does not read a stale "queued" status.
        task.status = RISK_RESCAN_STATUS_CANCELLING
        if capability_run is not None and capability_run.status in {
            RISK_RESCAN_STATUS_QUEUED,
            RISK_RESCAN_STATUS_RUNNING,
        }:
            mark_status(capability_run, RISK_RESCAN_STATUS_CANCELLING, now=utc_now())
        parameters = _task_parameters(task)
        active_run_id = parameters.get("active_run_id")
        if active_run_id:
            await db.execute(
                update(GovernanceSkillRun)
                .where(
                    GovernanceSkillRun.run_id == active_run_id,
                    GovernanceSkillRun.task_id == task_id,
                    GovernanceSkillRun.status.in_(
                        (RISK_RESCAN_STATUS_QUEUED, RISK_RESCAN_STATUS_RUNNING)
                    ),
                )
                .values(status=RISK_RESCAN_STATUS_CANCELLING)
                .execution_options(synchronize_session=False)
            )
        await append_task_event(
            db,
            task_id,
            event_type="stage",
            stage=RISK_RESCAN_STATUS_CANCELLING,
            counts={
                "completed": 0,
                "failed": 0,
                "total": len(_frozen_scope(task).get("samples") or []),
            },
            resource_refs=[],
        )
        now = utc_now()
        session = await _session_for_task(db, task, now)
        frozen = _frozen_scope(task)
        payload, content = build_cancelling_payload(
            task_id,
            capability_version_from_scope(frozen),
        )
        if session is not None:
            db.add(
                _assistant_message(
                    client_id,
                    session.session_id,
                    task.capability or "risk_corpus_rescan",
                    content,
                    now,
                    payload=payload,
                )
            )
        await db.commit()
        return await get_task(db, client_id, task_id)

    if task.status != RISK_RESCAN_STATUS_AWAITING:
        raise GovernanceTaskStateError(
            f"任务当前状态为 {task.status}，不能取消。"
        )

    now = utc_now()
    session = await _session_for_task(db, task, now)
    task.status = RISK_RESCAN_STATUS_CANCELLED
    task.error_message = "用户在执行前取消，未调用在线二次检测服务。"
    task.finished_at = now
    if capability_run is not None and capability_run.status == RISK_RESCAN_STATUS_AWAITING:
        mark_status(
            capability_run,
            RISK_RESCAN_STATUS_CANCELLED,
            now=now,
            finished=True,
            error_message=task.error_message,
            failure_phase="cancelled",
        )
    parameters = _task_parameters(task)
    active_run_id = parameters.get("active_run_id")
    if active_run_id:
        await db.execute(
            update(GovernanceSkillRun)
            .where(
                GovernanceSkillRun.run_id == active_run_id,
                GovernanceSkillRun.task_id == task_id,
                GovernanceSkillRun.status == RISK_RESCAN_STATUS_AWAITING,
            )
            .values(status=RISK_RESCAN_STATUS_CANCELLED)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            update(GovernanceCapabilityStep)
            .where(
                GovernanceCapabilityStep.run_id == active_run_id,
                GovernanceCapabilityStep.action == "execute",
                GovernanceCapabilityStep.status == RISK_RESCAN_STATUS_AWAITING,
            )
            .values(status=RISK_RESCAN_STATUS_CANCELLED)
            .execution_options(synchronize_session=False)
        )

    await emit_product_event(
        db,
        "confirm_abandoned",
        session_id=task.session_id,
        task_id=task.task_id,
        attributes={
            "capability": task.capability or "",
            "status": RISK_RESCAN_STATUS_CANCELLED,
        },
        occurred_at=now,
    )

    cancel_reason = (
        "已取消本次输入风险语料在线二次检测：未产生任何在线检测调用，"
        "任务保留取消状态与原因；可重新发起检测。"
    )
    payload, content = build_notice_payload(
        task.task_id,
        RISK_RESCAN_STATUS_CANCELLED,
        cancel_reason,
        capability_version_from_scope(_frozen_scope(task)),
        scope=_frozen_scope(task),
        failure_phase="cancelled",
    )
    db.add(
        _assistant_message(
            client_id,
            task.session_id,
            task.capability or "risk_corpus_rescan",
            content,
            now,
            payload=payload,
        )
    )
    await db.commit()
    return await _session_detail(db, session) if session else None


async def retry_task(
    db: AsyncSession,
    client_id: str,
    task_id: str,
    request: GovernanceTaskRetryRequest | None = None,
) -> dict | None:
    """Plan another immutable run under the same governance task."""
    task = await _load_task(db, client_id, task_id)
    if task is None:
        return None
    retryable_statuses = (
        RISK_RESCAN_STATUS_FAILED,
        RISK_RESCAN_STATUS_CANCELLED,
        RISK_RESCAN_STATUS_TIMEOUT,
        RISK_RESCAN_STATUS_COMPLETED_PARTIAL,
    )
    if task.status not in retryable_statuses:
        raise GovernanceTaskStateError(
            f"任务当前状态为 {task.status}，仅失败、取消、超时或部分完成任务可以重试。"
        )
    request = request or GovernanceTaskRetryRequest()
    root_scope = _root_frozen_scope(task)
    root_samples = root_scope.get("samples") or []
    if not root_samples:
        raise GovernanceTaskStateError(
            "原任务缺少冻结样本范围，无法重试；请重新发起检测。"
        )

    runs = await _task_runs(db, task.task_id)
    summary = await summarize_task_results(db, task.task_id)
    run_groups = summary.get("run_groups", [])
    latest_status_by_sample: dict[str, str] = {}
    for group in run_groups:
        for result in group.get("sample_results", []):
            latest_status_by_sample[str(result.get("sample_id") or "")] = str(
                result.get("status") or ""
            )
    if not latest_status_by_sample and task.status == RISK_RESCAN_STATUS_CANCELLED:
        latest_status_by_sample = {
            str(sample.get("sample_id") or ""): "not_executed"
            for sample in root_samples
        }
    elif not latest_status_by_sample and task.status in {
        RISK_RESCAN_STATUS_FAILED,
        RISK_RESCAN_STATUS_TIMEOUT,
    }:
        # Legacy whole-run failures predate per-sample persistence. Treat their
        # root scope as failed so existing tasks remain recoverable; all new
        # runs persist explicit sample statuses through governance_run_results.
        latest_status_by_sample = {
            str(sample.get("sample_id") or ""): "failed" for sample in root_samples
        }

    root_ids = {str(sample.get("sample_id") or "") for sample in root_samples}
    if request.scope == "all":
        eligible_ids = set(root_ids)
    else:
        allowed_statuses = {
            "failed" if request.scope == "failed" else request.scope
        }
        if request.scope == "remaining":
            allowed_statuses = {"failed", "not_executed"}
        eligible_ids = {
            sample_id
            for sample_id, status in latest_status_by_sample.items()
            if status in allowed_statuses
        }
    if request.sample_ids is not None:
        requested_ids = set(request.sample_ids)
        invalid_ids = requested_ids - root_ids
        if invalid_ids:
            raise GovernanceTaskStateError(
                "重试范围只能选择根冻结事实中的样本："
                + "、".join(sorted(invalid_ids))
            )
        ineligible = requested_ids - eligible_ids
        if ineligible and request.scope != "all":
            raise GovernanceTaskStateError(
                "重试范围只能选择根冻结事实中失败或未执行的样本："
                + "、".join(sorted(ineligible))
            )
        eligible_ids = requested_ids
    if request.sample_ids is not None:
        samples_by_id = {
            str(sample.get("sample_id") or ""): sample for sample in root_samples
        }
        selected_samples = [
            samples_by_id[sample_id]
            for sample_id in request.sample_ids
            if sample_id in eligible_ids
        ]
    else:
        selected_samples = [
            sample
            for sample in root_samples
            if str(sample.get("sample_id") or "") in eligible_ids
        ]
    selected_ids = [str(sample.get("sample_id") or "") for sample in selected_samples]
    if not selected_ids:
        raise GovernanceTaskStateError("当前任务没有符合所选范围的可重试样本。")

    scope_selection = (
        "custom" if request.sample_ids is not None else request.scope
    )
    retry_evaluator = request.evaluator
    capability = resolve_capability_by_key(task.capability or "")
    if capability is None:
        raise GovernanceTaskStateError(
            f"任务绑定的治理能力未登记：{task.capability or '（空）'}"
        )
    planner_provider = _planner_provider_for(task)
    retry_parameters = _capability_parameters_from_scope(root_scope)
    retry_parameters["sample_ids"] = selected_ids
    retry_parameters["limit"] = len(selected_ids)
    if retry_evaluator:
        retry_parameters["evaluator"] = retry_evaluator
    try:
        if runs:
            root_plan = _run_plan(runs[0])
            if any(
                str(sample.get("content_digest") or "")
                and sample_content_digest(str(sample.get("text") or ""))
                != str(sample.get("content_digest") or "")
                for sample in root_samples
            ):
                raise SkillContractError(
                    "retry_sample_drift", "根冻结样本文本摘要已漂移，不能重试"
                )
            root_task_facts = [
                _frozen_sample_fact_tuple(sample) for sample in root_samples
            ]
            root_plan_facts = [
                (
                    fact.sample_id,
                    fact.content_digest,
                    fact.reference_label,
                    fact.source_revision,
                )
                for fact in root_plan.scope.samples
            ]
            if root_task_facts != root_plan_facts:
                raise SkillContractError(
                    "retry_sample_drift", "根冻结样本摘要或来源事实已漂移，不能重试"
                )
            plan = validate_and_freeze_capability_retry_plan(
                capability,
                retry_parameters,
                root_plan.scope,
                selected_ids,
                planner_provider=planner_provider,
            )
        else:
            full_plan = validate_and_freeze_capability_plan(
                capability, retry_parameters, planner_provider=planner_provider
            )
            plan = validate_and_freeze_capability_retry_plan(
                capability,
                retry_parameters,
                full_plan.scope,
                selected_ids,
                planner_provider=planner_provider,
            )
    except SkillContractError as error:
        raise GovernanceTaskStateError(str(error)) from error

    previous_run = runs[-1] if runs else None
    previous_plan = _run_plan(previous_run) if previous_run is not None else None
    previous_ids = (
        [sample.sample_id for sample in previous_plan.scope.samples]
        if previous_plan is not None
        else [str(sample.get("sample_id") or "") for sample in root_samples]
    )
    revision = _build_retry_revision(
        scope_selection=scope_selection,
        selected_ids=selected_ids,
        previous_ids=previous_ids,
        previous_run=previous_run,
        previous_plan=previous_plan,
        plan=plan,
    )
    retry_scope = dict(root_scope)
    retry_scope["samples"] = selected_samples
    retry_scope["sample_count"] = len(selected_samples)
    if retry_evaluator:
        retry_scope["evaluator"] = retry_evaluator

    claimed = await db.execute(
        update(GovernanceTask)
        .where(
            GovernanceTask.task_id == task_id,
            GovernanceTask.client_id == client_id,
            GovernanceTask.status.in_(retryable_statuses),
        )
        .values(
            status=RISK_RESCAN_STATUS_AWAITING,
            error_message=None,
            finished_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        fresh = await _load_task(db, client_id, task_id)
        raise GovernanceTaskStateError(
            f"任务当前状态为 {fresh.status if fresh else 'unknown'}，不能重试。"
        )
    capability = resolve_capability_by_key(task.capability or "")
    capability_scope = None
    if capability is not None:
        try:
            capability_scope = freeze_capability_scope(
                capability, plan.steps[0].parameters
            )
        except SkillContractError as error:
            # Fail closed before any retry state is persisted.
            raise GovernanceTaskStateError(str(error)) from error

    run = await _persist_run(
        db,
        task,
        plan,
        status=RISK_RESCAN_STATUS_AWAITING,
        attempt=_next_run_attempt(runs),
        parent_run_id=previous_run.run_id if previous_run is not None else None,
        scope_selection=scope_selection,
        revision_json=revision.model_dump_json(),
    )
    previous_capability_run = await active_capability_run(db, task)
    new_capability_run = None
    if capability is not None and capability_scope is not None:
        new_capability_run = await create_capability_run(
            db,
            task,
            capability=capability,
            parameters=plan.steps[0].parameters,
            scope=capability_scope,
            status=RISK_RESCAN_STATUS_AWAITING,
            attempt=run.attempt,
            parent_run_id=(
                previous_capability_run.run_id
                if previous_capability_run is not None
                else None
            ),
            root_run_id=(
                previous_capability_run.root_run_id
                or previous_capability_run.run_id
                if previous_capability_run is not None
                else None
            ),
            scope_selection=scope_selection,
            revision_json=revision.model_dump_json(),
        )
    parameters = _task_parameters(task)
    parameters["root_frozen_scope"] = root_scope
    parameters["frozen_scope"] = retry_scope
    parameters["active_run_id"] = run.run_id
    if new_capability_run is not None:
        parameters["active_capability_run_id"] = new_capability_run.run_id
    parameters["revised_plan"] = {
        **revision.model_dump(),
        "run_id": run.run_id,
        "retry_scope": request.scope,
        "sample_ids": selected_ids,
    }
    plan_view = build_plan_view(
        plan,
        task_id=task.task_id,
        status=RISK_RESCAN_STATUS_AWAITING,
        asset_name=retry_scope.get("asset_name"),
    )
    parameters["plan_view"] = plan_view
    task.parameters_json = json.dumps(parameters, ensure_ascii=False)
    now = utc_now()
    session = await _session_for_task(db, task, now)
    await emit_product_event(
        db,
        "retry_recovered",
        session_id=task.session_id,
        task_id=task.task_id,
        attributes={
            "capability": task.capability or "",
            "status": RISK_RESCAN_STATUS_AWAITING,
            "attempt": run.attempt,
            "scope_selection": scope_selection,
            "recovered": True,
            "skill_key": plan.skill_key,
            "skill_version": plan.skill_version,
        },
        occurred_at=now,
    )
    db.add(
        _assistant_message(
            client_id,
            task.session_id,
            SKILL_PLAN_MESSAGE_KIND,
            _plan_message_content(plan_view, retry=True),
            now,
            payload=plan_view,
        )
    )
    await db.flush()
    preview = _retry_preview_result(task, retry_scope)
    payload = dict(
        preview.model_dump(),
        run_id=run.run_id,
        retry_scope=request.scope,
        scope_selection=scope_selection,
        attempt=run.attempt,
        revision=revision.model_dump(),
        revised_plan=parameters["revised_plan"],
        plan=plan.model_dump(),
        capability_version=capability_version_from_scope(retry_scope),
    )
    db.add(
        _assistant_message(
            client_id,
            task.session_id,
            task.capability or "risk_corpus_rescan",
            (
                "已为同一治理任务生成重试计划；历史运行和样本来源保持不变。\n"
                + preview.render_content()
            ),
            now,
            payload=payload,
        )
    )
    await db.commit()
    return await _session_detail(db, session) if session else None
