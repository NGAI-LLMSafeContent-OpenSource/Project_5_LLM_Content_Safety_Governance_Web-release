"""Versioned governance-skill plan validation on top of the read-only registry.

Planner output is untrusted.  The registry resolves a reviewed Agent Skill
package; this module validates every branch, capability, version and parameter
against its machine contract, and freezes the execution scope before any plan is
eligible for confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.governance import (
    FrozenSampleFact,
    GovernanceExecutionScope,
    GovernanceSkillConfirmation,
    GovernanceSkillPlanProposal,
    GovernanceSkillStepProposal,
    GovernanceValidatedSkillPlan,
    GovernanceValidatedSkillStep,
)
from app.services.governance_capabilities import (
    CapabilityDef,
    resolve_capability,
    resolve_capability_by_key,
)
from app.services.governance_executor_identity import resolve_executor_identity
from app.services.governance_hashing import canonical_digest, canonical_hash
from app.services.governance_skill_registry import (
    ActivatedGovernanceSkill,
    SkillRegistryError,
    SkillStepContract,
    activate_registered_skill,
)
from app.services.data_input_corpus_catalog_service import (
    RISK_STATIC_MAX_RECORDS,
    list_risk_static_records,
)
from app.services.governance_risk_rescan_service import (
    derive_source_revision,
    resolve_rescan_scope,
    sample_content_digest,
)


class SkillContractError(ValueError):
    """A stable rejection raised when an untrusted plan violates its package."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def scope_fingerprint_data(scope: GovernanceExecutionScope | dict[str, Any]) -> dict[str, Any]:
    """Normalize scope dumps for fingerprinting (omit unset evaluation_object)."""
    data = scope.model_dump() if isinstance(scope, GovernanceExecutionScope) else dict(scope)
    if data.get("evaluation_object") is None:
        data.pop("evaluation_object", None)
    return data


def load_skill_package(skill_key: str, version: str) -> ActivatedGovernanceSkill:
    """Load one registered skill through the read-only registry.

    The registry is the single loader; the old ``skill.yaml`` path is gone and no
    production code keeps a second format.
    """

    try:
        return activate_registered_skill(skill_key, version)
    except SkillRegistryError as exc:
        raise SkillContractError(exc.code, str(exc)) from exc


def _validated_params(capability: CapabilityDef, parameters: Any) -> BaseModel:
    if parameters is None:
        raise SkillContractError("parameters_missing", "计划步骤缺少 parameters")
    try:
        return capability.params_model.model_validate(parameters)
    except ValidationError as exc:
        raise SkillContractError("parameters_invalid", "治理能力参数非法") from exc


def _validated_parameters(capability: CapabilityDef, parameters: Any) -> dict:
    return _validated_params(capability, parameters).model_dump()


def _assert_plan_shape(
    package: ActivatedGovernanceSkill,
    proposal: GovernanceSkillPlanProposal,
) -> None:
    contract = package.contract
    domain = package.descriptor.domain
    if proposal.entrypoint not in contract.entrypoints:
        raise SkillContractError("entrypoint_not_allowed", "治理技能入口未登记")
    if proposal.branch not in contract.branches:
        raise SkillContractError("branch_not_allowed", "治理技能分支未登记")
    if len(proposal.steps) != len(contract.steps):
        raise SkillContractError("plan_shape_invalid", "计划步骤数量与技能契约不一致")
    for proposed, expected in zip(proposal.steps, contract.steps, strict=True):
        identity = (
            proposed.step_id,
            proposed.capability,
            proposed.capability_version,
            proposed.action,
        )
        expected_identity = (
            expected.step_id,
            expected.capability,
            expected.capability_version,
            expected.action,
        )
        if identity == expected_identity:
            continue
        if resolve_capability(domain, proposed.capability) is None:
            raise SkillContractError(
                "capability_not_registered", f"未登记治理能力 {proposed.capability}"
            )
        raise SkillContractError(
            "plan_step_not_allowed", f"计划步骤 {proposed.step_id} 不符合技能契约"
        )


@dataclass(frozen=True)
class ContractCheckedStep:
    """One plan step that passed its machine-contract checks."""

    capability: CapabilityDef
    params: BaseModel

    @property
    def parameters(self) -> dict:
        return self.params.model_dump()


def _checked_step(
    package: ActivatedGovernanceSkill,
    proposed: GovernanceSkillStepProposal,
    expected: SkillStepContract,
) -> ContractCheckedStep:
    capability = resolve_capability(package.descriptor.domain, proposed.capability)
    if capability is None:
        raise SkillContractError(
            "capability_not_registered", f"未登记治理能力 {proposed.capability}"
        )
    if capability.version != proposed.capability_version:
        raise SkillContractError(
            "capability_version_mismatch", "治理能力版本与登记版本不一致"
        )
    expected_parameters_schema = f"{capability.key}.params.{capability.version}"
    if expected.parameters_schema != expected_parameters_schema:
        raise SkillContractError(
            "parameters_schema_mismatch", "技能契约绑定的参数模型与登记能力不一致"
        )
    if expected.requires_confirmation and not capability.requires_confirmation:
        raise SkillContractError(
            "confirmation_policy_invalid", "远程执行步骤未绑定能力确认策略"
        )
    if expected.action == "execute" and (
        capability.result_schema != package.contract.result_schema
        or capability.result_model is None
    ):
        raise SkillContractError(
            "result_schema_not_registered", "技能结果 Schema 未绑定登记能力"
        )
    return ContractCheckedStep(
        capability=capability,
        params=_validated_params(capability, proposed.parameters),
    )


def _checked_steps(
    package: ActivatedGovernanceSkill,
    proposal: GovernanceSkillPlanProposal,
) -> list[ContractCheckedStep]:
    """Check every step against the contract; assumes the plan shape already matched."""

    checked = [
        _checked_step(package, proposed, expected)
        for proposed, expected in zip(proposal.steps, package.contract.steps, strict=True)
    ]
    parameter_sets = [step.parameters for step in checked]
    if any(parameters != parameter_sets[0] for parameters in parameter_sets[1:]):
        raise SkillContractError(
            "step_parameters_mismatch", "准备与执行步骤的参数必须完全一致"
        )
    return checked


def validate_plan_contract(
    proposal: GovernanceSkillPlanProposal,
) -> tuple[ContractCheckedStep, ...]:
    """Registry and machine-contract gate for a candidate plan.

    Runs before any governance task exists, so it checks only what the plan
    itself claims; the execution scope is frozen later by
    ``_validate_and_freeze_plan`` with the same step checks.
    """

    package = load_skill_package(proposal.skill_key, proposal.skill_version)
    _assert_plan_shape(package, proposal)
    return tuple(_checked_steps(package, proposal))


def _validate_and_freeze_plan(
    proposal: GovernanceSkillPlanProposal,
    scope: GovernanceExecutionScope,
) -> GovernanceValidatedSkillPlan:
    package = load_skill_package(proposal.skill_key, proposal.skill_version)
    contract = package.contract
    domain = package.descriptor.domain
    _assert_plan_shape(package, proposal)
    try:
        scope = GovernanceExecutionScope.model_validate(scope.model_dump())
    except ValidationError as exc:
        raise SkillContractError("scope_invalid", f"冻结执行范围非法：{exc}") from exc

    executor_capability = resolve_capability(domain, contract.executor_capability)
    if executor_capability is None:
        raise SkillContractError(
            "executor_contract_mismatch", "技能契约声明的执行器能力未登记"
        )
    if scope.executor.capability != contract.executor_capability:
        raise SkillContractError(
            "executor_contract_mismatch", "冻结执行器能力与技能契约不一致"
        )
    if scope.executor.capability_version != executor_capability.version:
        raise SkillContractError(
            "executor_version_mismatch", "冻结执行器能力版本与登记版本不一致"
        )

    steps = [
        GovernanceValidatedSkillStep(
            **expected.model_dump(exclude={"parameters_schema"}),
            parameters=checked.parameters,
        )
        for checked, expected in zip(
            _checked_steps(package, proposal), contract.steps, strict=True
        )
    ]
    parameter_sets = [step.parameters for step in steps]
    # DynBench ``evaluator`` is a run-identity param, not a sample filter (#93 T2);
    # ``export_requested`` is an initial delivery preference, not a filter (#167).
    expected_filters = {
        key: value
        for key, value in parameter_sets[0].items()
        if key not in ("limit", "sample_ids", "evaluator", "export_requested")
        and value is not None
    }
    if scope.filters != expected_filters:
        raise SkillContractError(
            "scope_parameters_mismatch", "冻结筛选条件与已校验计划参数不一致"
        )
    if scope.sample_count > parameter_sets[0]["limit"]:
        raise SkillContractError(
            "scope_limit_exceeded", "冻结样本数量超过已校验计划上限"
        )

    scope_data = scope_fingerprint_data(scope)
    actual_scope_fields = set(scope_data)
    if actual_scope_fields != set(contract.immutable_scope_fields):
        raise SkillContractError(
            "scope_contract_mismatch", "冻结执行范围字段与技能契约不一致"
        )
    scope_fingerprint = canonical_hash(scope_data)
    semantic_data = {
        "skill_key": package.descriptor.skill_key,
        "skill_version": package.descriptor.version,
        "skill_content_digest": package.descriptor.skill_content_digest,
        "contract_digest": package.descriptor.contract_digest,
        "branch": proposal.branch,
        "steps": [step.model_dump() for step in steps],
        "scope": scope_data,
        "result_schema": contract.result_schema,
    }
    semantic_fingerprint = canonical_hash(semantic_data)
    return GovernanceValidatedSkillPlan(
        plan_id=semantic_fingerprint,
        skill_key=package.descriptor.skill_key,
        skill_version=package.descriptor.version,
        skill_content_digest=package.descriptor.skill_content_digest,
        contract_digest=package.descriptor.contract_digest,
        title=package.descriptor.name,
        entrypoint=proposal.entrypoint,
        planner_provider=proposal.planner_provider,
        branch=proposal.branch,
        steps=steps,
        scope=scope,
        result_schema=contract.result_schema,
        confirmation_required=any(step.requires_confirmation for step in steps),
        scope_fingerprint=scope_fingerprint,
        semantic_fingerprint=semantic_fingerprint,
    )


def validate_and_freeze_plan(
    proposal: GovernanceSkillPlanProposal,
) -> GovernanceValidatedSkillPlan:
    """Resolve server-owned asset and detector facts, then freeze a valid plan."""

    package = load_skill_package(proposal.skill_key, proposal.skill_version)
    _assert_plan_shape(package, proposal)
    first_step = proposal.steps[0]
    capability = resolve_capability(package.descriptor.domain, first_step.capability)
    if capability is None:
        raise SkillContractError(
            "capability_not_registered", f"未登记治理能力 {first_step.capability}"
        )
    parameters = _validated_parameters(capability, first_step.parameters)
    validated_params = capability.params_model.model_validate(parameters)
    resolved = resolve_rescan_scope(validated_params)
    if not resolved.get("available") or not resolved.get("samples"):
        raise SkillContractError("execution_scope_unavailable", "没有可冻结的风险样本")

    asset_records = list_risk_static_records(limit=RISK_STATIC_MAX_RECORDS, offset=0)
    if not asset_records.get("available"):
        raise SkillContractError("execution_scope_unavailable", "风险语料资产不可用")
    version_payload: dict[str, Any] = {
        "asset_id": resolved.get("asset_id"),
        "records": asset_records.get("records") or [],
    }
    asset_version = canonical_digest(version_payload)
    executor_capability = resolve_capability(
        package.descriptor.domain, package.contract.executor_capability
    )
    if executor_capability is None:
        raise SkillContractError(
            "executor_contract_mismatch", "技能契约声明的执行器能力未登记"
        )
    estimate = package.contract.execution_estimate
    samples = resolved.get("samples") or []
    sample_count = len(samples)
    try:
        frozen_samples = [
            FrozenSampleFact(
                sample_id=str(sample.get("sample_id") or ""),
                content_digest=str(sample.get("content_digest") or ""),
                reference_label=str(sample.get("reference_label") or ""),
                source_revision=str(sample.get("source_revision") or ""),
            )
            for sample in samples
        ]
    except ValidationError as exc:
        raise SkillContractError(
            "sample_fact_invalid", "样本事实缺少可用于冻结的文本或来源信息"
        ) from exc
    # The frozen scope intentionally omits the evaluation object: the runtime
    # scope dict resolved by ``resolve_rescan_scope`` carries it (and is what the
    # report builder reads), so adding it here would change the frozen-scope
    # fingerprint of every in-flight confirmation without changing the payload.
    try:
        scope = GovernanceExecutionScope(
            asset_id=str(resolved.get("asset_id") or ""),
            asset_version=asset_version,
            samples=frozen_samples,
            filters=resolved.get("filters") or {},
            sample_count=sample_count,
            executor=resolve_executor_identity(executor_capability, parameters),
            estimated_cost_units=estimate.cost_units_per_sample * sample_count,
            estimated_seconds=estimate.estimated_seconds_per_sample * sample_count,
            evaluation_object=None,
        )
    except ValidationError as exc:
        raise SkillContractError("sample_fact_invalid", "样本事实无法冻结为执行范围") from exc
    return _validate_and_freeze_plan(proposal, scope)


def capability_scope_fingerprint(scope: GovernanceExecutionScope) -> str:
    """Fingerprint a directly frozen capability scope (no skill package)."""

    return canonical_hash(scope_fingerprint_data(scope))


def freeze_capability_scope(
    capability: CapabilityDef, parameters: dict[str, Any]
) -> GovernanceExecutionScope:
    """Resolve server-owned asset and detector facts for a direct capability run.

    This is the skill-free counterpart of ``validate_and_freeze_plan``: a direct
    capability run still freezes the same immutable facts (asset version, ordered
    sample facts, executor identity) before confirmation, but does not require a
    versioned skill package. It never calls the online detector.
    """

    try:
        validated_params = capability.params_model.model_validate(parameters)
    except ValidationError as exc:
        raise SkillContractError("parameters_invalid", "治理能力参数非法") from exc
    params = validated_params.model_dump()
    resolved = resolve_rescan_scope(validated_params)
    if not resolved.get("available") or not resolved.get("samples"):
        raise SkillContractError("execution_scope_unavailable", "没有可冻结的风险样本")

    asset_records = list_risk_static_records(limit=RISK_STATIC_MAX_RECORDS, offset=0)
    if not asset_records.get("available"):
        raise SkillContractError("execution_scope_unavailable", "风险语料资产不可用")
    version_payload: dict[str, Any] = {
        "asset_id": resolved.get("asset_id"),
        "records": asset_records.get("records") or [],
    }
    asset_version = canonical_digest(version_payload)
    samples = resolved.get("samples") or []
    try:
        frozen_samples = [
            FrozenSampleFact(
                sample_id=str(sample.get("sample_id") or ""),
                content_digest=str(sample.get("content_digest") or ""),
                reference_label=str(sample.get("reference_label") or ""),
                source_revision=str(sample.get("source_revision") or ""),
            )
            for sample in samples
        ]
    except ValidationError as exc:
        raise SkillContractError(
            "sample_fact_invalid", "样本事实缺少可用于冻结的文本或来源信息"
        ) from exc
    try:
        return GovernanceExecutionScope(
            asset_id=str(resolved.get("asset_id") or ""),
            asset_version=asset_version,
            samples=frozen_samples,
            filters=resolved.get("filters") or {},
            sample_count=len(frozen_samples),
            executor=resolve_executor_identity(capability, params),
            estimated_cost_units=0,
            estimated_seconds=0,
            # See ``validate_and_freeze_plan``: the runtime scope dict carries the
            # evaluation object; freezing it here would shift every fingerprint.
            evaluation_object=None,
        )
    except ValidationError as exc:
        raise SkillContractError("sample_fact_invalid", "样本事实无法冻结为执行范围") from exc


# --- Direct capability runs (#164 T5) ---------------------------------------
#
# A governance task may contain a capability run without a skill run. Before
# #169 that run was planned through the single-capability ``risk-corpus-rescan``
# skill package; ADR-0012 retires such packages, so the same frozen-scope +
# confirmation contract is now built directly from the registered capability.
#
# The persisted plan keeps the ``GovernanceValidatedSkillPlan`` envelope so the
# worker, task API and retry lineage stay unchanged, but ``skill_key`` /
# ``skill_version`` carry the capability identity. ``resolve_capability_by_key``
# on that key is the unambiguous discriminator between the two plan owners.

CAPABILITY_PREPARE_STEP_ID = "prepare_scope"
CAPABILITY_EXECUTE_STEP_ID = "execute_detection"
CAPABILITY_PREPARE_COMPLETION = "execution_scope_frozen"
CAPABILITY_EXECUTE_COMPLETION = "registered_capability_result_valid"


def capability_scope_fields(
    scope: GovernanceExecutionScope | dict[str, Any],
) -> list[str]:
    """Immutable field names a capability run actually freezes, in order."""

    return list(scope_fingerprint_data(scope))


def capability_plan_steps(
    capability: CapabilityDef, parameters: dict[str, Any]
) -> list[GovernanceValidatedSkillStep]:
    """Deterministic ordered steps of one direct capability run.

    The prepare step freezes the scope without side effects; the execute step
    carries the capability's confirmation policy and only completes through the
    capability's registered result model.
    """

    shared = {
        "capability": capability.key,
        "capability_version": capability.version,
        "parameters": dict(parameters),
    }
    return [
        GovernanceValidatedSkillStep(
            step_id=CAPABILITY_PREPARE_STEP_ID,
            action="prepare",
            automatic=True,
            requires_confirmation=False,
            completion_condition=CAPABILITY_PREPARE_COMPLETION,
            **shared,
        ),
        GovernanceValidatedSkillStep(
            step_id=CAPABILITY_EXECUTE_STEP_ID,
            action="execute",
            automatic=False,
            requires_confirmation=capability.requires_confirmation,
            completion_condition=CAPABILITY_EXECUTE_COMPLETION,
            **shared,
        ),
    ]


def _capability_plan_digests(capability: CapabilityDef) -> tuple[str, str]:
    """Reviewed identity of the registered capability a plan froze.

    Mirrors the skill package's ``SKILL.md`` / ``contract.yaml`` digests so a
    plan stays tamper-evident after the package format was retired.
    """

    params_schema = capability.params_model.model_json_schema()
    contract_digest = canonical_digest(
        {
            "domain": capability.domain,
            "capability": capability.key,
            "capability_version": capability.version,
            "requires_confirmation": capability.requires_confirmation,
            "result_schema": capability.result_schema or "",
            "params_schema": params_schema,
        }
    )
    return canonical_digest({"params_schema": params_schema}), contract_digest


def _validated_capability_params(
    capability: CapabilityDef, parameters: dict[str, Any]
) -> BaseModel:
    if parameters is None:
        raise SkillContractError("parameters_missing", "能力运行缺少参数")
    try:
        return capability.params_model.model_validate(parameters)
    except ValidationError as exc:
        raise SkillContractError("parameters_invalid", "治理能力参数非法") from exc


def _assemble_capability_plan(
    capability: CapabilityDef,
    parameters: dict[str, Any],
    scope: GovernanceExecutionScope,
    *,
    planner_provider: str = "deterministic",
    entrypoint: str = "natural_language",
    branch: str = "default",
) -> GovernanceValidatedSkillPlan:
    steps = capability_plan_steps(capability, parameters)
    content_digest, contract_digest = _capability_plan_digests(capability)
    scope_data = scope_fingerprint_data(scope)
    scope_fingerprint = capability_scope_fingerprint(scope)
    semantic_fingerprint = canonical_hash(
        {
            "capability": capability.key,
            "capability_version": capability.version,
            "contract_digest": contract_digest,
            "branch": branch,
            "steps": [step.model_dump() for step in steps],
            "scope": scope_data,
            "result_schema": capability.result_schema or "",
        }
    )
    return GovernanceValidatedSkillPlan(
        plan_id=semantic_fingerprint,
        skill_key=capability.key,
        skill_version=capability.version,
        skill_content_digest=content_digest,
        contract_digest=contract_digest,
        title=capability.label,
        entrypoint=entrypoint,  # type: ignore[arg-type]
        planner_provider=planner_provider,  # type: ignore[arg-type]
        branch=branch,
        steps=steps,
        scope=scope,
        result_schema=capability.result_schema or "",
        confirmation_required=any(step.requires_confirmation for step in steps),
        scope_fingerprint=scope_fingerprint,
        semantic_fingerprint=semantic_fingerprint,
    )


def validate_and_freeze_capability_plan(
    capability: CapabilityDef,
    parameters: dict[str, Any],
    *,
    planner_provider: str = "deterministic",
) -> GovernanceValidatedSkillPlan:
    """Freeze one direct capability run against current server-owned facts.

    This is the skill-free counterpart of ``validate_and_freeze_plan`` and the
    only plan builder the confirm, retry and worker paths now use.
    """

    if not capability.requires_confirmation:
        raise SkillContractError(
            "confirmation_policy_invalid",
            f"治理能力 {capability.key} 是只读能力，不需要确认的执行计划",
        )
    validated = _validated_capability_params(capability, parameters)
    scope = freeze_capability_scope(capability, validated.model_dump())
    return _assemble_capability_plan(
        capability,
        validated.model_dump(),
        scope,
        planner_provider=planner_provider,
    )


def _revalidate_capability_plan(
    plan: GovernanceValidatedSkillPlan,
) -> GovernanceValidatedSkillPlan:
    """Rebuild a direct capability plan from current facts and compare."""

    capability = resolve_capability_by_key(plan.skill_key)
    if capability is None:
        raise SkillContractError(
            "capability_not_registered", f"未登记治理能力 {plan.skill_key}"
        )
    canonical = _assemble_capability_plan(
        capability,
        plan.steps[0].parameters,
        plan.scope,
        planner_provider=plan.planner_provider,
        entrypoint=plan.entrypoint,
        branch=plan.branch,
    )
    if (
        canonical.semantic_fingerprint != plan.semantic_fingerprint
        or canonical.plan_id != plan.plan_id
        or canonical.result_schema != plan.result_schema
        or canonical.confirmation_required != plan.confirmation_required
    ):
        raise SkillContractError("validated_plan_tampered", "已校验计划内容已被修改")
    return canonical


def resolve_capability_plan_owner(
    plan: GovernanceValidatedSkillPlan,
) -> CapabilityDef | None:
    """The registered capability that owns a direct capability plan, if any."""

    return resolve_capability_by_key(plan.skill_key)


def _resolve_completion_owner(
    plan: GovernanceValidatedSkillPlan, step_id: str
) -> tuple[GovernanceValidatedSkillPlan, CapabilityDef, GovernanceValidatedSkillStep]:
    """Canonical plan + registered capability + step behind a completion result."""

    capability = resolve_capability_plan_owner(plan)
    canonical = (
        _revalidate_capability_plan(plan)
        if capability is not None
        else _revalidate_plan(plan)
    )
    step = next((item for item in canonical.steps if item.step_id == step_id), None)
    if step is None:
        raise SkillContractError("step_not_registered", "完成结果对应的步骤未登记")
    if capability is None:
        package = load_skill_package(canonical.skill_key, canonical.skill_version)
        capability = resolve_capability(package.descriptor.domain, step.capability)
    if capability is None:
        raise SkillContractError(
            "capability_not_registered", f"未登记治理能力 {step.capability}"
        )
    return canonical, capability, step


def _narrow_retry_samples(
    root_scope: GovernanceExecutionScope,
    current_scope: GovernanceExecutionScope,
    sample_ids: list[str],
) -> list[FrozenSampleFact]:
    """The root-ordered samples a retry may re-run, after rejecting drift."""

    root_by_id = {sample.sample_id: sample for sample in root_scope.samples}
    current_by_id = {sample.sample_id: sample for sample in current_scope.samples}
    selected: list[FrozenSampleFact] = []
    for sample_id in sample_ids:
        root_fact = root_by_id.get(sample_id)
        if root_fact is None:
            raise SkillContractError(
                "retry_scope_invalid", "重试范围包含根冻结事实之外的样本"
            )
        if current_by_id.get(sample_id) != root_fact:
            raise SkillContractError(
                "retry_sample_drift", "重试样本摘要或来源事实已漂移，不能继续"
            )
        selected.append(root_fact)
    if not selected:
        raise SkillContractError("retry_scope_empty", "没有可重试的样本")
    return selected


def _retry_scope(
    root_scope: GovernanceExecutionScope,
    current_scope: GovernanceExecutionScope,
    selected: list[FrozenSampleFact],
    *,
    cost_units_per_sample: int,
    seconds_per_sample: int,
) -> GovernanceExecutionScope:
    """Root facts narrowed to the retry selection, with a refreshed executor."""

    return GovernanceExecutionScope.model_validate(
        {
            **root_scope.model_dump(),
            "samples": selected,
            "sample_count": len(selected),
            "executor": current_scope.executor,
            "estimated_cost_units": cost_units_per_sample * len(selected),
            "estimated_seconds": seconds_per_sample * len(selected),
        }
    )


def validate_and_freeze_retry_plan(
    proposal: GovernanceSkillPlanProposal,
    root_scope: GovernanceExecutionScope,
    sample_ids: list[str],
) -> GovernanceValidatedSkillPlan:
    """Freeze a retry plan from an immutable root scope and current executor.

    A retry may only narrow the original ordered sample facts. The current
    asset is resolved again solely to reject content/reference/source drift;
    execution still uses the root facts and text snapshot. The executor is
    deliberately refreshed so a detector change becomes a visible revised
    plan that requires confirmation.
    """

    current = validate_and_freeze_plan(proposal)
    selected = _narrow_retry_samples(root_scope, current.scope, sample_ids)
    estimate = load_skill_package(
        proposal.skill_key, proposal.skill_version
    ).contract.execution_estimate
    retry_scope = _retry_scope(
        root_scope,
        current.scope,
        selected,
        cost_units_per_sample=estimate.cost_units_per_sample,
        seconds_per_sample=estimate.estimated_seconds_per_sample,
    )
    retry_parameters = {
        **(proposal.steps[0].parameters or {}),
        "limit": len(selected),
        "sample_ids": sample_ids,
    }
    retry_proposal = GovernanceSkillPlanProposal(
        skill_key=proposal.skill_key,
        skill_version=proposal.skill_version,
        entrypoint=proposal.entrypoint,
        planner_provider=proposal.planner_provider,
        branch=proposal.branch,
        steps=[
            GovernanceSkillStepProposal(
                step_id=step.step_id,
                capability=step.capability,
                capability_version=step.capability_version,
                action=step.action,
                parameters=retry_parameters,
            )
            for step in proposal.steps
        ],
    )
    return _validate_and_freeze_plan(retry_proposal, retry_scope)


def validate_and_freeze_capability_retry_plan(
    capability: CapabilityDef,
    parameters: dict[str, Any],
    root_scope: GovernanceExecutionScope,
    sample_ids: list[str],
    *,
    planner_provider: str = "deterministic",
) -> GovernanceValidatedSkillPlan:
    """Freeze a direct capability retry plan from an immutable root scope.

    Skill-free counterpart of ``validate_and_freeze_retry_plan``: the current
    asset is resolved only to reject drift, and the same narrowing contract
    applies to the frozen capability scope.
    """

    validated = _validated_capability_params(capability, parameters)
    current = freeze_capability_scope(capability, validated.model_dump())
    selected = _narrow_retry_samples(root_scope, current, sample_ids)
    retry_scope = _retry_scope(
        root_scope,
        current,
        selected,
        cost_units_per_sample=0,
        seconds_per_sample=0,
    )
    retry_parameters = {
        **validated.model_dump(),
        "limit": len(selected),
        "sample_ids": sample_ids,
    }
    return _assemble_capability_plan(
        capability,
        retry_parameters,
        retry_scope,
        planner_provider=planner_provider,
    )


def _proposal_from_plan(
    plan: GovernanceValidatedSkillPlan,
) -> GovernanceSkillPlanProposal:
    return GovernanceSkillPlanProposal(
        skill_key=plan.skill_key,
        skill_version=plan.skill_version,
        entrypoint=plan.entrypoint,
        planner_provider=plan.planner_provider,
        branch=plan.branch,
        steps=[
            GovernanceSkillStepProposal(
                step_id=step.step_id,
                capability=step.capability,
                capability_version=step.capability_version,
                action=step.action,
                parameters=step.parameters,
            )
            for step in plan.steps
        ],
    )


def _revalidate_plan(
    plan: GovernanceValidatedSkillPlan,
) -> GovernanceValidatedSkillPlan:
    canonical = _validate_and_freeze_plan(_proposal_from_plan(plan), plan.scope)
    if (
        canonical.semantic_fingerprint != plan.semantic_fingerprint
        or canonical.plan_id != plan.plan_id
        or canonical.result_schema != plan.result_schema
        or canonical.confirmation_required != plan.confirmation_required
    ):
        raise SkillContractError("validated_plan_tampered", "已校验计划内容已被修改")
    return canonical


def _confirmation_is_current(
    plan: GovernanceValidatedSkillPlan,
    current: GovernanceValidatedSkillPlan,
    actual_scope_fingerprint: str,
) -> bool:
    """Is the plan's frozen scope still the current server-owned fact?

    A same-task retry freezes a subset of the root samples, so its scope is
    legitimately narrower than a fresh full freeze. It is only current when the
    asset content (asset_version), filters and executor are unchanged and every
    retry sample still matches the server-owned fact of the same id.
    """

    if current.scope_fingerprint == actual_scope_fingerprint:
        return True
    current_facts = {sample.sample_id: sample for sample in current.scope.samples}
    return (
        plan.scope.asset_id == current.scope.asset_id
        and plan.scope.asset_version == current.scope.asset_version
        and plan.scope.filters == current.scope.filters
        and plan.scope.executor == current.scope.executor
        and bool(plan.scope.samples)
        and all(
            current_facts.get(sample.sample_id) == sample
            for sample in plan.scope.samples
        )
    )


def validate_execution(
    plan: GovernanceValidatedSkillPlan,
    confirmation: GovernanceSkillConfirmation | None,
) -> None:
    """Recheck the frozen scope at the last server boundary before execution.

    Dispatches on the plan owner exactly like ``validate_step_completion``: a
    direct capability run is re-frozen from the registered capability, a
    skill-orchestrated plan from its skill package.
    """

    actual_scope_fingerprint = canonical_hash(scope_fingerprint_data(plan.scope))
    if actual_scope_fingerprint != plan.scope_fingerprint:
        raise SkillContractError(
            "confirmation_invalidated", "执行范围已变化，原确认失效"
        )
    capability = resolve_capability_plan_owner(plan)
    if capability is not None:
        _revalidate_capability_plan(plan)
        current = validate_and_freeze_capability_plan(
            capability,
            plan.steps[0].parameters,
            planner_provider=plan.planner_provider,
        )
    else:
        _revalidate_plan(plan)
        current = validate_and_freeze_plan(_proposal_from_plan(plan))
    if not _confirmation_is_current(plan, current, actual_scope_fingerprint):
        raise SkillContractError(
            "confirmation_invalidated", "服务端资产、样本或执行器事实已变化，原确认失效"
        )
    if plan.confirmation_required and confirmation is None:
        raise SkillContractError("confirmation_required", "远程执行步骤必须先确认")
    if confirmation and confirmation.scope_fingerprint != actual_scope_fingerprint:
        raise SkillContractError(
            "confirmation_invalidated", "确认对应的执行范围与当前范围不一致"
        )


def _validate_completed_result(
    canonical: GovernanceValidatedSkillPlan,
    capability: CapabilityDef,
    step: GovernanceValidatedSkillStep,
    payload: dict[str, Any],
    *,
    allow_partial: bool,
) -> Any:
    """Shared result gate for skill-orchestrated and direct capability runs.

    The only inputs are the canonical plan, the registered capability that owns
    the execute step, and the payload the worker produced; both plan kinds run
    the same frozen-scope, sample-fact and executor-identity assertions.
    """

    if step.completion_condition != "registered_capability_result_valid":
        raise SkillContractError(
            "completion_condition_not_applicable", "该步骤不接受能力结果作为完成条件"
        )
    if (
        capability.version != step.capability_version
        or capability.result_schema != canonical.result_schema
        or capability.result_model is None
    ):
        raise SkillContractError(
            "result_schema_not_registered", "完成结果未绑定登记能力及结果 Schema"
        )
    try:
        result = capability.result_model.model_validate(payload)
    except ValidationError as exc:
        raise SkillContractError("completion_result_invalid", f"能力结果非法：{exc}") from exc

    result_sample_ids = [sample.sample_id for sample in result.samples]
    frozen_samples = canonical.scope.samples
    frozen_sample_ids = [fact.sample_id for fact in frozen_samples]
    # Execution-progress tally derived from the per-sample outcomes; the v2
    # contract no longer carries an agreement-style summary.
    status_tally = {
        status: sum(1 for sample in result.samples if sample.status == status)
        for status in ("consistent", "inconsistent", "failed", "not_executed")
    }
    executed_total = (
        status_tally["consistent"] + status_tally["inconsistent"] + status_tally["failed"]
    )
    not_executed_total = status_tally["not_executed"]
    summary_total = executed_total + not_executed_total
    if result.method != canonical.scope.executor.adapter_method:
        raise SkillContractError(
            "completion_executor_mismatch", "能力结果执行方法与冻结执行器身份不一致"
        )
    if allow_partial:
        if (
            result.asset_id != canonical.scope.asset_id
            or result.filters != canonical.scope.filters
            or result.sample_count != len(result.samples)
            or len(result.samples) > canonical.scope.sample_count
            or summary_total != len(result.samples)
        ):
            raise SkillContractError(
                "completion_scope_mismatch", "能力结果与冻结执行范围不一致"
            )
        if result_sample_ids != frozen_sample_ids:
            raise SkillContractError(
                "completion_scope_mismatch", "能力结果与冻结执行范围不一致"
            )
    elif (
        result.asset_id != canonical.scope.asset_id
        or result.filters != canonical.scope.filters
        or result.sample_count != canonical.scope.sample_count
        or result_sample_ids != frozen_sample_ids
        or len(result.samples) != canonical.scope.sample_count
        or summary_total != canonical.scope.sample_count
        or not_executed_total != 0
        or any(sample.status == "not_executed" for sample in result.samples)
    ):
        raise SkillContractError(
            "completion_scope_mismatch", "能力结果与冻结执行范围不一致"
        )
    frozen_by_id = {fact.sample_id: fact for fact in frozen_samples}
    for sample in result.samples:
        if allow_partial and sample.status == "not_executed":
            fact = frozen_by_id[sample.sample_id]
            if sample.sample_id != fact.sample_id:
                raise SkillContractError(
                    "completion_scope_mismatch", "能力结果与冻结执行范围不一致"
                )
            continue
        fact = frozen_by_id[sample.sample_id]
        if sample.reference_label != fact.reference_label:
            raise SkillContractError(
                "completion_sample_fact_mismatch", "能力结果替换了样本参考标签"
            )
        if sample.content_digest != fact.content_digest:
            raise SkillContractError(
                "completion_sample_fact_mismatch", "能力结果替换了样本内容摘要"
            )
        if sample.text and sample_content_digest(sample.text) != fact.content_digest:
            raise SkillContractError(
                "completion_sample_fact_mismatch", "能力结果替换了样本文本"
            )
        if not sample.source:
            raise SkillContractError(
                "completion_sample_source_mismatch", "能力结果缺少样本来源信息"
            )
        if sample.source_revision and sample.source_revision != fact.source_revision:
            raise SkillContractError(
                "completion_sample_source_mismatch", "能力结果替换了样本来源版本"
            )
        if (
            derive_source_revision(
                sample.source, sample.sample_id, sample.content_digest
            )
            != fact.source_revision
        ):
            raise SkillContractError(
                "completion_sample_source_mismatch", "能力结果与冻结的样本来源版本不一致"
            )
    return result


def validate_step_completion(
    plan: GovernanceValidatedSkillPlan,
    step_id: str,
    payload: dict[str, Any],
    *,
    allow_partial: bool = False,
) -> Any:
    """Validate completion through the result model registered by the capability.

    Dispatches on the plan owner: a plan whose key is a registered capability is
    a direct capability run (#164 T5), otherwise it is skill-orchestrated.
    """

    canonical, capability, step = _resolve_completion_owner(plan, step_id)
    return _validate_completed_result(
        canonical, capability, step, payload, allow_partial=allow_partial
    )
