"""Governance assistant intent and capability result contracts.

The model only returns a GovernanceIntent; the orchestrator validates it against
the capability registry before executing anything. Capability results are fixed
Pydantic models so a model can never author its own result shape.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GovernanceDomainKey = Literal["input", "output"]

RISK_REFERENCE_LABELS = ("safe", "unsafe")
RISK_SEARCH_DEFAULT_LIMIT = 20
RISK_SEARCH_MAX_LIMIT = 50
VALUE_QA_SEARCH_DEFAULT_LIMIT = 20
VALUE_QA_SEARCH_MAX_LIMIT = 100


class CapabilityParams(BaseModel):
    """Base class for capability parameters.

    Unknown keys are rejected. A model that guesses a wrong field name (for
    example ``l1`` instead of ``harm_category_L1``) then fails loudly through the
    orchestrator's ValidationError boundary, instead of silently dropping the
    filter and returning an unfiltered result.
    """

    model_config = ConfigDict(extra="forbid")


class GovernanceIntent(BaseModel):
    kind: Literal["execute", "clarify", "boundary"]
    capability: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class GovernanceSkillStepProposal(BaseModel):
    """One untrusted planner step submitted for server-side validation."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    capability: str
    capability_version: str
    action: Literal["prepare", "execute"]
    parameters: dict[str, Any] | None


class GovernanceSkillPlanProposal(BaseModel):
    """Provider-independent plan proposal; never executable until validated."""

    model_config = ConfigDict(extra="forbid")

    skill_key: str
    skill_version: str
    entrypoint: Literal["natural_language", "skill_entry"]
    planner_provider: Literal["qwen", "deepseek", "deterministic"]
    branch: str
    steps: list[GovernanceSkillStepProposal]


class GovernanceSkillSelectionProposal(BaseModel):
    """Level-1 planner output: which registered skill (if any) to activate.

    The model only proposes; the server registry decides whether the skill is
    usable. A failed selection is an explicit result, never a fallback to a free
    capability call.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "selected",
        "no_match",
        "ambiguous",
        "needs_clarification",
        "rejected",
    ]
    skill_key: str | None = None
    skill_version: str | None = None
    domain: str | None = None
    domain_changed: bool = False
    candidates: list[str] = Field(default_factory=list)
    code: str | None = None
    message: str | None = None


class GovernanceReadonlyCapabilitySelection(BaseModel):
    """Planner choice of one no-confirmation read-only capability.

    Sits beside a skill selection. Carries the resolved user goal, the capability
    id, and a parameter object. It has no skill id or version, and it does not
    enter the skill registry or the machine contract.
    """

    model_config = ConfigDict(extra="forbid")

    user_goal: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExecutorIdentity(BaseModel):
    """The actual executor behind one capability call.

    A URL or a capability version alone never replaces this identity. Upstreams
    that expose stable service/build/model/taxonomy versions yield ``verified``;
    otherwise a ``provisional`` fingerprint is frozen from method, normalized
    base URL, available upstream info and semantically relevant local config.
    Secrets, auth headers and proxy credentials never enter this object.
    """

    model_config = ConfigDict(extra="forbid")

    capability: str
    capability_version: str
    adapter_method: str
    api_contract_version: str
    implementation_fingerprint: str
    version_assurance: Literal["verified", "provisional"]
    observed_metadata: dict[str, str] = Field(default_factory=dict)


class FrozenSampleFact(BaseModel):
    """One server-produced sample fact frozen before confirmation.

    ``content_digest`` is computed on the server-normalized text, so the raw
    sample text never has to be copied into task events. ``source_revision`` is
    the asset's own stable revision when available, otherwise a secret-free
    digest of the source identifier and record content.
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1)
    content_digest: str = Field(min_length=1)
    reference_label: str = ""
    source_revision: str = Field(min_length=1)


class GovernanceExecutionScope(BaseModel):
    """Facts frozen before a side-effecting governance step is confirmed."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    asset_version: str = Field(min_length=1)
    samples: list[FrozenSampleFact]
    filters: dict[str, Any] = Field(default_factory=dict)
    sample_count: int = Field(gt=0)
    executor: ExecutorIdentity
    estimated_cost_units: int = Field(ge=0)
    estimated_seconds: int = Field(ge=0)
    # Optional freezable evaluation-object metadata (#92 DynBench). Absent for
    # risk-corpus-rescan so existing immutable_scope_fields contracts stay exact.
    evaluation_object: dict[str, Any] | None = None

    @field_validator("samples")
    @classmethod
    def _require_unique_ordered_samples(
        cls, value: list[FrozenSampleFact]
    ) -> list[FrozenSampleFact]:
        if not value:
            raise ValueError("执行范围必须包含至少一个样本")
        sample_ids = [sample.sample_id for sample in value]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("执行范围中的样本 ID 不得重复")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.sample_count != len(self.samples):
            raise ValueError("sample_count 必须与冻结的有序样本数量一致")


class GovernanceValidatedSkillStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    capability: str
    capability_version: str
    action: Literal["prepare", "execute"]
    parameters: dict[str, Any]
    automatic: bool
    requires_confirmation: bool
    completion_condition: str


class GovernanceValidatedSkillPlan(BaseModel):
    """Canonical plan safe to display and persist, but not yet execute."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    skill_key: str
    skill_version: str
    skill_content_digest: str
    contract_digest: str
    title: str
    entrypoint: Literal["natural_language", "skill_entry"]
    planner_provider: Literal["qwen", "deepseek", "deterministic"]
    branch: str
    steps: list[GovernanceValidatedSkillStep]
    scope: GovernanceExecutionScope
    result_schema: str
    confirmation_required: bool
    scope_fingerprint: str
    semantic_fingerprint: str


class GovernanceSkillConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_fingerprint: str


class ValueCorpusOverviewParams(CapabilityParams):
    asset_id: str | None = None


class AssetSourceRef(BaseModel):
    ref_type: str = "value_qa_asset"
    ref_id: str
    name: str
    source_repo: str = ""
    source_commit: str = ""


class Topic1CorpusToolCatalogParams(CapabilityParams):
    """The tool catalog is read-only and intentionally takes no parameters."""

    pass


class ValueCorpusOverviewResult(BaseModel):
    capability: Literal["value_corpus_overview"] = "value_corpus_overview"
    source: str
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    sample_count: int = 0
    group_count: int = 0
    quality_level_distribution: dict[str, int] = Field(default_factory=dict)
    primary_dimension_distribution: dict[str, int] = Field(default_factory=dict)
    secondary_dimension_distribution: dict[str, int] = Field(default_factory=dict)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前尚未导入可用的价值语料资产，无法展示语料构成。"
        lines = [
            f"价值语料概览（{self.asset_name or 'value_qa 资产'}）",
            f"样本总数：{self.sample_count}",
            f"价值三联组：{self.group_count}",
        ]
        return "\n".join(lines)


class ValueQaSearchParams(CapabilityParams):
    keyword: str | None = None
    topic: str | None = None
    primary_dimension: str | None = None
    secondary_dimension: str | None = None
    limit: int = Field(
        default=VALUE_QA_SEARCH_DEFAULT_LIMIT, ge=1, le=VALUE_QA_SEARCH_MAX_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    continuation: bool = False


class ValueQaLevelDetail(BaseModel):
    sample_id: str = ""
    question: str = ""
    answer: str = ""
    quality_level: str
    level_display: str = ""
    level_score: str = ""
    source_reference: dict[str, Any] = Field(default_factory=dict)
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    value_annotations: list[dict[str, Any]] = Field(default_factory=list)
    prompt_snapshot: str = ""


class ValueQaGroupItem(BaseModel):
    group_id: str
    topic: str = ""
    primary_dimension: str = ""
    secondary_dimension: str = ""
    levels: dict[str, ValueQaLevelDetail] = Field(default_factory=dict)


class ValueQaSearchResult(BaseModel):
    capability: Literal["value_qa_search"] = "value_qa_search"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    total: int = 0
    offset: int = 0
    limit: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    group_ids: list[str] = Field(default_factory=list)
    groups: list[ValueQaGroupItem] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前尚未导入可用的价值语料资产，无法检索价值问题组。"
        if self.total == 0:
            return (
                "没有匹配的价值问题组。可尝试更换关键词、主题或价值维度，"
                "或先执行“查看价值语料构成”了解资产规模。"
            )
        if self.offset >= self.total:
            return f"已显示全部 {self.total} 个价值问题组，没有更多组。"
        return f"找到 {self.total} 个价值问题组，当前展示第 {self.offset + 1}–{self.offset + len(self.groups)} 组。"


class ValueQaGroupDetailParams(CapabilityParams):
    group_id: str = Field(..., min_length=1)


class ValueQaGroupDetailResult(BaseModel):
    capability: Literal["value_qa_group_detail"] = "value_qa_group_detail"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    group_id: str
    topic: str = ""
    primary_dimension: str = ""
    secondary_dimension: str = ""
    levels: dict[str, ValueQaLevelDetail] = Field(default_factory=dict)
    groups: list[str] = Field(default_factory=list)
    group_index: int = 0
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "未找到该价值问题组，可能已被移除或组 ID 有误。"
        return (
            f"价值问题组（{self.topic or '未标注主题'}）："
            f"高/中/低三档答疑对照，第 {self.group_index + 1} 组。"
        )


class RiskCorpusOverviewParams(CapabilityParams):
    pass


class RiskCorpusRecord(BaseModel):
    sample_id: str
    text: str
    reference_label: str = ""
    original_label: str = ""
    harm_category_L1: str = ""
    harm_category_L2: str = ""
    source: str = ""
    is_risky: bool = False


class RiskCorpusOverviewResult(BaseModel):
    capability: Literal["risk_corpus_overview"] = "risk_corpus_overview"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    sample_count: int = 0
    reference_label_distribution: dict[str, int] = Field(default_factory=dict)
    harm_category_L1_distribution: dict[str, int] = Field(default_factory=dict)
    harm_category_L2_distribution: dict[str, int] = Field(default_factory=dict)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前未找到课题二静态风险语料包，无法展示风险语料构成。"
        lines = [
            f"风险语料概览（{self.asset_name or RISK_STATIC_ASSET_DISPLAY_NAME}）",
            f"样本总数：{self.sample_count}",
        ]
        if self.reference_label_distribution:
            parts = "、".join(
                f"{label} {count}"
                for label, count in self.reference_label_distribution.items()
            )
            lines.append(f"参考标注分布：{parts}")
        return "\n".join(lines)


class RiskCorpusSearchParams(CapabilityParams):
    keyword: str | None = None
    reference_label: str | None = None
    source: str | None = None
    harm_category_L1: str | None = None
    harm_category_L2: str | None = None
    limit: int = Field(default=RISK_SEARCH_DEFAULT_LIMIT, ge=1, le=RISK_SEARCH_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)
    continuation: bool = False

    @field_validator("reference_label")
    @classmethod
    def _normalize_reference_label(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().lower()
        if normalized not in RISK_REFERENCE_LABELS:
            raise ValueError("reference_label 必须是 safe 或 unsafe")
        return normalized


class RiskCorpusSearchResult(BaseModel):
    capability: Literal["risk_corpus_search"] = "risk_corpus_search"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    total: int = 0
    offset: int = 0
    limit: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    records: list[RiskCorpusRecord] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前未找到课题二静态风险语料包，无法浏览或筛选风险样本。"
        if self.total == 0:
            return (
                "没有匹配的风险样本。可尝试放宽关键词、更换参考标注、来源或风险分类后重试。"
            )
        if self.offset >= self.total:
            return f"已显示全部 {self.total} 条匹配样本，没有更多记录。"
        return (
            f"找到 {self.total} 条风险样本，"
            f"当前展示第 {self.offset + 1}–{self.offset + len(self.records)} 条。"
        )


# ---------------------------------------------------------------------------
# Risk-corpus online re-detection (#55)
# ---------------------------------------------------------------------------
#
# Two-phase contract: the capability only resolves and freezes an explicit
# sample scope (data source, filters, exact ids and count) and never calls the
# online detector. Execution happens exclusively after the user confirms a
# task. Detection results are displayed side by side with the read-only
# reference label and are never written back to the corpus.


RISK_RESCAN_CAPABILITY = "risk_corpus_rescan"
RISK_RESCAN_CAPABILITY_VERSION = "v2"
RISK_RESCAN_RESULT_SCHEMA = "risk_corpus_rescan.result.v2"
RISK_RESCAN_REPORT_TYPE = "input_risk_rescan"
# Canonical, user-facing name of the shared 400-row static validation corpus.
RISK_STATIC_ASSET_DISPLAY_NAME = "课题二输入风险静态验证语料（400条）"

RISK_RESCAN_MAX_SAMPLES = 30

RISK_RESCAN_STATUS_AWAITING = "awaiting_confirmation"
RISK_RESCAN_STATUS_QUEUED = "queued"
RISK_RESCAN_STATUS_RUNNING = "running"
RISK_RESCAN_STATUS_CANCELLING = "cancelling"
RISK_RESCAN_STATUS_COMPLETED = "completed"
RISK_RESCAN_STATUS_COMPLETED_PARTIAL = "completed_partial"
RISK_RESCAN_STATUS_CANCELLED = "cancelled"
RISK_RESCAN_STATUS_FAILED = "failed"
RISK_RESCAN_STATUS_TIMEOUT = "timeout"

RISK_RESCAN_TERMINAL_STATUSES = frozenset(
    {
        RISK_RESCAN_STATUS_COMPLETED,
        RISK_RESCAN_STATUS_COMPLETED_PARTIAL,
        RISK_RESCAN_STATUS_CANCELLED,
        RISK_RESCAN_STATUS_FAILED,
        RISK_RESCAN_STATUS_TIMEOUT,
    }
)


class GovernanceTaskRetryRequest(CapabilityParams):
    """Server-constrained selection for another run of the same task.

    The client may narrow the retry, but it cannot introduce sample ids or
    statuses outside the task's immutable root scope and persisted outcomes.
    Non-empty ``sample_ids`` selects a custom subset (``scope_selection=custom``).
    DynBench may also pin ``evaluator``; changing it (or the sample scope)
    requires reconfirmation and never silently replaces the prior run.
    """

    scope: Literal["failed", "not_executed", "remaining", "all"] = "remaining"
    sample_ids: list[str] | None = None
    evaluator: Literal["activation_probe", "keyword"] | None = None

    @field_validator("sample_ids")
    @classmethod
    def _normalize_sample_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [str(sample_id).strip() for sample_id in value]
        if not normalized or any(not sample_id for sample_id in normalized):
            raise ValueError("sample_ids 不能为空")
        if len(normalized) != len(set(normalized)):
            raise ValueError("sample_ids 不得重复")
        return normalized


class GovernanceRetryRevision(CapabilityParams):
    """Structured revision plan produced when planning a same-task retry."""

    changed: bool = False
    scope_selection: str = "remaining"
    added_sample_ids: list[str] = Field(default_factory=list)
    removed_sample_ids: list[str] = Field(default_factory=list)
    detector_changed: bool = False
    schema_changed: bool = False
    previous_run_id: str | None = None
    previous_executor_fingerprint: str = ""
    new_executor_fingerprint: str = ""
    requires_reconfirmation: bool = True
    reason: str = ""


class RiskCorpusRescanParams(CapabilityParams):
    """v2 sample-scope parameters for the merged input-risk re-detection.

    ``evaluator`` selects the Topic-2 detection method for this run only. Omission
    resolves to the registered server default; an explicitly illegal value is
    rejected here by the server before any scope is frozen. ``export_requested``
    is an initial preference: a completed result then exposes a download entry.
    """

    keyword: str | None = None
    reference_label: str | None = None
    source: str | None = None
    harm_category_L1: str | None = None
    harm_category_L2: str | None = None
    limit: int = Field(
        default=RISK_RESCAN_MAX_SAMPLES, ge=1, le=RISK_RESCAN_MAX_SAMPLES
    )
    sample_ids: list[str] | None = None
    evaluator: Literal["activation_probe", "keyword"] | None = None
    export_requested: bool = False

    @field_validator("sample_ids")
    @classmethod
    def _normalize_internal_sample_ids(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        normalized = [str(sample_id).strip() for sample_id in value]
        if not normalized or any(not sample_id for sample_id in normalized):
            raise ValueError("sample_ids 不能为空")
        if len(normalized) != len(set(normalized)):
            raise ValueError("sample_ids 不得重复")
        return normalized

    @field_validator("reference_label")
    @classmethod
    def _normalize_reference_label(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().lower()
        if normalized not in RISK_REFERENCE_LABELS:
            raise ValueError("reference_label 必须是 safe 或 unsafe")
        return normalized


def _format_rescan_filters(filters: dict[str, Any]) -> str:
    if not filters:
        return "全部样本"
    return "、".join(f"{key}={value}" for key, value in filters.items())


class RiskRescanSamplePreview(BaseModel):
    sample_id: str
    text: str
    reference_label: str = ""
    harm_category_L1: str = ""
    harm_category_L2: str = ""
    source: str = ""
    # Server-owned sample facts frozen with the preview so confirm/worker can
    # bind execution to the same digests Agent Skills recorded in the plan.
    content_digest: str = ""
    source_revision: str = ""


class RiskCorpusRescanPreviewResult(BaseModel):
    capability: Literal["risk_corpus_rescan"] = "risk_corpus_rescan"
    capability_version: str = RISK_RESCAN_CAPABILITY_VERSION
    phase: Literal["preview"] = "preview"
    task_id: str = ""
    parent_task_id: str | None = None
    status: Literal["awaiting_confirmation"] = RISK_RESCAN_STATUS_AWAITING
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    total_matched: int = 0
    sample_count: int = 0
    capped: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)
    samples: list[RiskRescanSamplePreview] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    evaluation_object: dict[str, Any] = Field(default_factory=dict)
    evaluator: str = ""
    export_requested: bool = False

    def render_content(self) -> str:
        if not self.available:
            return "当前未找到课题二输入风险静态验证语料，无法发起在线二次检测。"
        evaluator_label = _evaluator_display_label(self.evaluator)
        lines = [
            f"输入风险语料在线二次检测待确认：数据来源「{self.asset_name or RISK_STATIC_ASSET_DISPLAY_NAME}」，"
            f"筛选范围 {_format_rescan_filters(self.filters)}，实际检测 {self.sample_count} 条，"
            f"评估器 {evaluator_label}。",
        ]
        sha = str((self.evaluation_object or {}).get("content_sha256") or "")
        if sha:
            lines.append(f"已冻结资产内容摘要 content_sha256={sha[:16]}…。")
        lines.append(
            "披露级别为 internal_validation：参考标注未经验证为 ground truth，"
            f"确认后才调用 {evaluator_label}；取消不会产生任何在线调用。"
        )
        if self.capped:
            lines.append(
                f"匹配到 {self.total_matched} 条，超过单次最多 {RISK_RESCAN_MAX_SAMPLES} 条的"
                f"服务端上限，已按前 {self.sample_count} 条冻结执行范围。"
            )
        if self.parent_task_id:
            lines.append(f"本任务为重试任务，原任务 {self.parent_task_id} 的状态与原因保持不变。")
        return "\n".join(lines)


def _evaluator_display_label(evaluator: str) -> str:
    if evaluator == "keyword":
        return "FilterGuard keyword"
    if evaluator == "activation_probe":
        return "Activation Probe"
    return evaluator or "Activation Probe"


class RiskRescanSampleOutcome(BaseModel):
    sample_id: str
    text: str
    reference_label: str = ""
    detected_label: str = ""
    status: Literal["consistent", "inconsistent", "failed", "not_executed"] = "failed"
    reason: str = ""
    # Non-sensitive attribution carried from the frozen scope so completion can
    # bind each sample to its source without copying raw text into events.
    source: str = ""
    content_digest: str = ""
    source_revision: str = ""
    run_id: str = ""
    capability_version: str = ""
    completed_at: str = ""


class RiskRescanSummary(BaseModel):
    consistent_count: int = 0
    inconsistent_count: int = 0
    failed_count: int = 0
    not_executed_count: int = 0


class RiskRescanRunProvenance(BaseModel):
    """One skill-run attempt attached to a task, for result aggregation UI."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    attempt: int = 1
    status: str = ""
    capability_version: str = ""
    executor_fingerprint: str = ""
    scope_selection: str = "full"
    parent_run_id: str | None = None
    result_schema: str = ""
    sample_count: int = 0
    started_at: str = ""
    completed_at: str | None = None


class GovernanceTaskResultGroup(BaseModel):
    """One compatibility bucket of runs and their merged or blocked samples."""

    model_config = ConfigDict(extra="forbid")

    compatible: bool = True
    reason: str = ""
    executor_fingerprint: str = ""
    result_schema: str = ""
    capability_version: str = ""
    sample_count: int = 0
    method: str = ""
    run_ids: list[str] = Field(default_factory=list)
    samples: list[RiskRescanSampleOutcome] = Field(default_factory=list)
    summary: RiskRescanSummary = Field(default_factory=RiskRescanSummary)
    asset_id: str | None = None
    asset_name: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    completed_at: str | None = None


class GovernanceTaskAggregatedResult(BaseModel):
    """Task-level flattened result with per-run provenance and group sidecars."""

    model_config = ConfigDict(extra="forbid")

    capability: str = "risk_corpus_rescan"
    phase: Literal["result"] = "result"
    task_id: str = ""
    status: str = ""
    method: str = ""
    asset_id: str | None = None
    asset_name: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    sample_count: int = 0
    summary: RiskRescanSummary = Field(default_factory=RiskRescanSummary)
    samples: list[RiskRescanSampleOutcome] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    completed_at: str = ""
    capability_version: str = ""
    partial: bool = False
    runs: list[RiskRescanRunProvenance] = Field(default_factory=list)
    groups: list[GovernanceTaskResultGroup] = Field(default_factory=list)


class RiskCorpusRescanNoticeResult(BaseModel):
    """Terminal notice for cancelled / failed / timed-out re-detection tasks.

    These tasks keep their status and reason but never produce a completion
    record, so a failed run can never masquerade as a successful result."""

    capability: Literal["risk_corpus_rescan"] = "risk_corpus_rescan"
    phase: Literal["failed", "cancelled", "cancelling"]
    task_id: str = ""
    status: Literal[
        "failed", "cancelled", "timeout", "cancelling"
    ] = RISK_RESCAN_STATUS_FAILED
    reason: str = ""
    evaluator: str = ""
    failure_diagnostics: Any = None

    def render_content(self) -> str:
        diagnostics = self.failure_diagnostics
        if not diagnostics:
            return self.reason
        lines = [self.reason] if self.reason else []
        completed = len(getattr(diagnostics, "completed_sample_ids", []) or [])
        failed = len(getattr(diagnostics, "failed_sample_ids", []) or [])
        not_executed = len(getattr(diagnostics, "not_executed_sample_ids", []) or [])
        lines.append(
            f"样本范围：已完成 {completed} 条，失败 {failed} 条，未执行 {not_executed} 条"
            f"（阶段 {getattr(diagnostics, 'failure_phase', 'unknown')}）。"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output-domain system prerun records
# ---------------------------------------------------------------------------
#
# System prerun records stay in the Benchmark asset registry. The governance
# layer only stores an asset reference plus a presentation snapshot: it never
# copies a system record into a user completion record, and never creates a
# user session for one.

SYSTEM_RECORD_TYPE_RISK = "risk_safety"
SYSTEM_RECORD_TYPE_LABEL = "风险安全系统预跑记录"
SYSTEM_RECORD_TYPE_CULTURAL = "cultural_diversity"
SYSTEM_RECORD_TYPE_CULTURAL_LABEL = "文化多样性系统预跑记录"
SYSTEM_RECORD_SEARCH_DEFAULT_LIMIT = 20
SYSTEM_RECORD_SEARCH_MAX_LIMIT = 50


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO date/datetime into an aware UTC datetime.

    Shared by the parameter validators here and the system-record service so
    ``Z`` suffixes, naive values and invalid input are handled once."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SystemRecordSearchParamsBase(CapabilityParams):
    """Shared filters and pagination for output-domain system prerun records.

    Risk safety (#56) and cultural diversity (#57) share source/status/completion
    time filters and deterministic pagination; each record type adds its own
    business-dimension filters on top instead of overloading the other's."""

    source: str | None = None
    status: str | None = None
    completed_after: str | None = None
    completed_before: str | None = None
    limit: int = Field(
        default=SYSTEM_RECORD_SEARCH_DEFAULT_LIMIT,
        ge=1,
        le=SYSTEM_RECORD_SEARCH_MAX_LIMIT,
    )
    offset: int = Field(default=0, ge=0)
    continuation: bool = False

    @field_validator("completed_after")
    @classmethod
    def _validate_completed_after(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        if parse_iso_datetime(value) is None:
            raise ValueError("completed_after 必须是 ISO 日期或日期时间")
        return str(value).strip()

    @field_validator("completed_before")
    @classmethod
    def _validate_completed_before(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        if parse_iso_datetime(value) is None:
            raise ValueError("completed_before 必须是 ISO 日期或日期时间")
        return str(value).strip()


class RiskSystemRecordSearchParams(SystemRecordSearchParamsBase):
    """Risk-safety record filters plus the Topic3 asset-version selector.

    ``asset_version`` selects an evaluated-object benchmark version (``v6``,
    ``v7``, ...). Omitted means the series current version; unregistered legacy
    assets remain readable and are not removed by the version selector.
    """

    asset_version: str | None = None

    @field_validator("asset_version")
    @classmethod
    def _validate_asset_version(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().lower()
        if not re.fullmatch(r"v[0-9][0-9a-z._-]*", normalized):
            raise ValueError("asset_version 必须以 v 开头，例如 v6 或 v7")
        return normalized


class CulturalSystemRecordSearchParams(SystemRecordSearchParamsBase):
    """Cultural-diversity record filters.

    Business dimensions come from what the cultural result already exposes in
    its manifest distributions (语境难度、民族、背景类型、问题类型); a value
    matches when the record's distribution contains that exact value."""

    difficulty_level: str | None = None
    ethnic_group: str | None = None
    background_type: str | None = None
    query_type: str | None = None


class RiskSystemRecordDetailParams(CapabilityParams):
    record_id: str = Field(..., min_length=1)


class CulturalSystemRecordDetailParams(CapabilityParams):
    record_id: str = Field(..., min_length=1)


class SystemRecordItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    record_id: str
    record_type: str = SYSTEM_RECORD_TYPE_RISK
    record_type_label: str = SYSTEM_RECORD_TYPE_LABEL
    name: str = ""
    status: str = ""
    status_label: str = ""
    source_repo: str = ""
    source_commit: str = ""
    record_version: str = ""
    asset_version: str | None = None
    asset_status: Literal["current", "historical", "unregistered"] = "unregistered"
    asset_sha256: str = ""
    sample_count: int = 0
    model_names: list[str] = Field(default_factory=list)
    has_evaluation: bool = False
    evaluated_at: str | None = None
    completed_at: str = ""
    created_at: str = ""


class RiskSystemRecordSearchResult(BaseModel):
    capability: Literal["risk_system_record_search"] = "risk_system_record_search"
    available: bool = True
    record_type: str = SYSTEM_RECORD_TYPE_RISK
    record_type_label: str = SYSTEM_RECORD_TYPE_LABEL
    total: int = 0
    offset: int = 0
    limit: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    records: list[SystemRecordItem] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前注册表没有可用的风险安全系统预跑记录。"
        if self.total == 0:
            return (
                "没有匹配的系统预跑记录。可放宽来源、状态或完成时间后重试；"
                "系统预跑记录来自既有评测资产，不是本次用户执行结果。"
            )
        if self.offset >= self.total:
            return f"系统预跑记录已全部显示，共 {self.total} 条，没有更多记录。"
        return (
            f"共找到 {self.total} 条系统预跑记录（非本次用户执行结果），"
            f"当前展示第 {self.offset + 1}–{self.offset + len(self.records)} 条。"
        )


class SystemRecordModelResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str = ""
    model_name: str = ""
    display_name: str = ""
    model_version: str = ""
    role: str = ""
    run_id: str = ""
    evaluated_at: str = ""
    predictions_count: int = 0
    primary_metrics: dict[str, Any] = Field(default_factory=dict)
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    per_category_metrics: dict[str, Any] = Field(default_factory=dict)


class SystemRecordDataset(BaseModel):
    sample_count: int = 0
    safe_total: int = 0
    risk_total: int = 0
    taxonomy_schema: str = ""
    category_distribution: dict[str, int] = Field(default_factory=dict)
    language_distribution: dict[str, int] = Field(default_factory=dict)
    culture_distribution: dict[str, int] = Field(default_factory=dict)
    risk_level_distribution: dict[str, int] = Field(default_factory=dict)


class RiskSystemRecordDetailResult(BaseModel):
    capability: Literal["risk_system_record_detail"] = "risk_system_record_detail"
    available: bool = True
    source_status: Literal["ok", "changed", "missing"] = "ok"
    record_id: str
    record_type: str = SYSTEM_RECORD_TYPE_RISK
    record_type_label: str = SYSTEM_RECORD_TYPE_LABEL
    name: str = ""
    status: str = ""
    status_label: str = ""
    record_version: str = ""
    asset_version: str | None = None
    asset_status: Literal["current", "historical", "unregistered"] = "unregistered"
    source_repo: str = ""
    source_commit: str = ""
    asset_sha256: str = ""
    dataset: SystemRecordDataset = Field(default_factory=SystemRecordDataset)
    models: list[SystemRecordModelResult] = Field(default_factory=list)
    primary_metrics: list[dict[str, str]] = Field(default_factory=list)
    sample_summary: str = ""
    live_eval_enabled: bool = False
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    review_supported: bool = False
    review_unavailable_reason: str = ""

    def render_content(self) -> str:
        if self.source_status == "missing":
            return (
                "该系统预跑记录已不在资产注册表中，可能已被移除或重建。"
                "治理助手不会补造缺失结果。"
            )
        if self.source_status == "changed":
            return (
                "该系统中记录的版本与本会话早前列表快照不一致，"
                "结果可能已更新。以下展示当前注册表版本，请以最新版本为准。"
            )
        if not self.available:
            return "未找到该风险安全系统预跑记录，无法展示结构化详情。"
        version = self.asset_version or "未登记"
        status = {
            "current": "当前版本",
            "historical": "历史版本",
            "unregistered": "未登记系列",
        }.get(self.asset_status, self.asset_status)
        return (
            f"系统预跑记录（非本次用户执行结果）：{self.name or self.record_id}，"
            f"资产版本 {version}（{status}），"
            f"样本 {self.dataset.sample_count} 条，模型结果 {len(self.models)} 项。"
        )


# ---------------------------------------------------------------------------
# Cultural-diversity system prerun records (#57)
# ---------------------------------------------------------------------------
#
# Same frame as risk safety: a benchmark asset reference plus a presentation
# snapshot, never a user completion record. The fields are cultural-specific
# (语境难度、民族、背景类型、审校通过率), not risk-safety metrics.


class CulturalSystemRecordItem(BaseModel):
    record_id: str
    record_type: str = SYSTEM_RECORD_TYPE_CULTURAL
    record_type_label: str = SYSTEM_RECORD_TYPE_CULTURAL_LABEL
    name: str = ""
    status: str = ""
    status_label: str = ""
    source_repo: str = ""
    source_commit: str = ""
    record_version: str = ""
    sample_count: int = 0
    difficulty_levels: list[str] = Field(default_factory=list)
    ethnic_groups: list[str] = Field(default_factory=list)
    background_types: list[str] = Field(default_factory=list)
    query_types: list[str] = Field(default_factory=list)
    review_passed_count: int = 0
    review_passed_rate: float = 0.0
    quality_gate_overall: str = ""
    has_evaluation: bool = False
    completed_at: str = ""
    created_at: str = ""


class CulturalSystemRecordSearchResult(BaseModel):
    capability: Literal["cultural_system_record_search"] = (
        "cultural_system_record_search"
    )
    available: bool = True
    record_type: str = SYSTEM_RECORD_TYPE_CULTURAL
    record_type_label: str = SYSTEM_RECORD_TYPE_CULTURAL_LABEL
    total: int = 0
    offset: int = 0
    limit: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    records: list[CulturalSystemRecordItem] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前注册表没有可用的文化多样性系统预跑记录。"
        if self.total == 0:
            return (
                "没有匹配的文化多样性系统预跑记录。可放宽来源、状态、完成时间或"
                "语境难度、民族、背景类型后重试；系统预跑记录来自既有评测资产，"
                "不是本次用户执行结果。"
            )
        if self.offset >= self.total:
            return f"文化多样性系统预跑记录已全部显示，共 {self.total} 条，没有更多记录。"
        return (
            f"共找到 {self.total} 条文化多样性系统预跑记录（非本次用户执行结果），"
            f"当前展示第 {self.offset + 1}–{self.offset + len(self.records)} 条。"
        )


class CulturalSystemRecordDataset(BaseModel):
    sample_count: int = 0
    review_passed_count: int = 0
    review_passed_rate: float = 0.0
    quality_gate_overall: str = ""
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    ethnic_distribution: dict[str, int] = Field(default_factory=dict)
    background_type_distribution: dict[str, int] = Field(default_factory=dict)
    persona_distribution: dict[str, int] = Field(default_factory=dict)
    query_type_distribution: dict[str, int] = Field(default_factory=dict)
    discard_counts: dict[str, int] = Field(default_factory=dict)


class CulturalSystemRecordSample(BaseModel):
    sample_id: str = ""
    ethnic_group: str = ""
    difficulty_level: str = ""
    background_type: str = ""
    persona: str = ""
    query_type: str = ""
    prompt_preview: str = ""


class CulturalSystemRecordDetailResult(BaseModel):
    capability: Literal["cultural_system_record_detail"] = (
        "cultural_system_record_detail"
    )
    available: bool = True
    source_status: Literal["ok", "changed", "missing"] = "ok"
    record_id: str
    record_type: str = SYSTEM_RECORD_TYPE_CULTURAL
    record_type_label: str = SYSTEM_RECORD_TYPE_CULTURAL_LABEL
    name: str = ""
    status: str = ""
    status_label: str = ""
    record_version: str = ""
    source_repo: str = ""
    source_commit: str = ""
    asset_sha256: str = ""
    dataset: CulturalSystemRecordDataset = Field(
        default_factory=CulturalSystemRecordDataset
    )
    samples: list[CulturalSystemRecordSample] = Field(default_factory=list)
    sample_summary: str = ""
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    review_supported: bool = False
    review_view_id: str | None = None
    review_unavailable_reason: str = ""

    def render_content(self) -> str:
        if self.source_status == "missing":
            return (
                "该文化多样性系统预跑记录已不在资产注册表中，可能已被移除或重建。"
                "治理助手不会补造缺失结果。"
            )
        if self.source_status == "changed":
            return (
                "该文化多样性系统预跑记录的版本与本会话早前列表快照不一致，"
                "结果可能已更新。以下展示当前注册表版本，请以最新版本为准。"
            )
        if not self.available:
            return "未找到该文化多样性系统预跑记录，无法展示结构化详情。"
        return (
            f"文化多样性系统预跑记录（非本次用户执行结果）："
            f"{self.name or self.record_id}，样本 {self.dataset.sample_count} 条，"
            f"审校通过 {self.dataset.review_passed_count} 条。"
        )


# ---------------------------------------------------------------------------
# Common frozen report envelope + cultural prerun review tracer bullet (#88)
# ---------------------------------------------------------------------------

CULTURAL_PRERUN_REVIEW_CAPABILITY = "cultural_prerun_review"
CULTURAL_PRERUN_REVIEW_MESSAGE_KIND = "cultural_prerun_review"


class CulturalPrerunReviewRequest(BaseModel):
    """Explicit UI action; never inferred from catalogue browsing."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(..., min_length=1)
    record_version: str = Field(..., min_length=1)


class GovernanceReportStatus(BaseModel):
    code: str
    label: str
    detail: str = ""


class GovernanceReportEnvelope(BaseModel):
    """Reusable report facts shared by future input/culture/risk reports."""

    evaluated_object: dict[str, Any] = Field(default_factory=dict)
    source_identity: dict[str, Any] = Field(default_factory=dict)
    run_identity: dict[str, Any] = Field(default_factory=dict)
    evaluation_run_status: GovernanceReportStatus
    integrity_status: GovernanceReportStatus
    delivery_readiness: GovernanceReportStatus
    review_task_status: GovernanceReportStatus
    claim_boundaries: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CulturalSourceMetric(BaseModel):
    method: Literal["direct", "three_agent"]
    label: str
    ethnic_recognition_rate: float
    cultural_specificity_rate: float
    composite_pass_rate: float
    composite_percentage: float
    composite_pass_count: int
    total_samples: int


class CulturalReviewIssue(BaseModel):
    """One frozen sample-level finding (#89). No owner / assignment / closure."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    list_kind: Literal["content", "integrity"]
    category: str
    sample_id: str = ""
    method: str | None = None
    dimension: str | None = None
    judgment: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class CulturalReviewIssueLists(BaseModel):
    content: list[CulturalReviewIssue] = Field(default_factory=list)
    integrity: list[CulturalReviewIssue] = Field(default_factory=list)


class CulturalPrerunReviewReport(BaseModel):
    capability: Literal["cultural_prerun_review"] = CULTURAL_PRERUN_REVIEW_CAPABILITY
    capability_version: str = "v1"
    task_id: str
    report_type: Literal["cultural_generation_method_comparison"] = (
        "cultural_generation_method_comparison"
    )
    envelope: GovernanceReportEnvelope
    source_metrics: list[CulturalSourceMetric]
    three_agent_stages: list[dict[str, str]] = Field(default_factory=list)
    integrity_warnings: list[dict[str, Any]] = Field(default_factory=list)
    issue_lists: CulturalReviewIssueLists = Field(
        default_factory=CulturalReviewIssueLists
    )
    frozen_evidence: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    completed_at: str

    def render_content(self) -> str:
        content_n = len(self.issue_lists.content)
        integrity_n = len(self.issue_lists.integrity)
        return (
            "文化生成方法对比预跑记录审阅任务已完成。"
            f"内容问题 {content_n} 条，评测完整性问题 {integrity_n} 条；"
            "报告保留上游来源指标并单独展示完整性告警；"
            "该结果不评价事实正确性、安全性或合规性。"
        )


# ---------------------------------------------------------------------------
# Risk prerun review tracer bullet (#90) — V7 formal + Base baseline only
# ---------------------------------------------------------------------------

RISK_PRERUN_REVIEW_CAPABILITY = "risk_prerun_review"
RISK_PRERUN_REVIEW_MESSAGE_KIND = "risk_prerun_review"


class RiskPrerunReviewRequest(BaseModel):
    """Explicit UI action; never inferred from catalogue browsing."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(..., min_length=1)
    record_version: str = Field(..., min_length=1)


class RiskEvaluatorMetrics(BaseModel):
    """One evaluator package (V7 primary or Base baseline); never merged."""

    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    role: Literal["primary", "baseline"]
    model_id: str
    model_version: str = ""
    display_name: str = ""
    run_id: str = ""
    evaluated_at: str = ""
    predictions_count: int = 0
    binary_metrics: dict[str, Any] = Field(default_factory=dict)
    level_metrics: dict[str, Any] = Field(default_factory=dict)
    multilabel_metrics: dict[str, Any] = Field(default_factory=dict)
    primary_metrics: dict[str, Any] = Field(default_factory=dict)
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    per_category_metrics: dict[str, Any] = Field(default_factory=dict)


class RiskReviewIssue(BaseModel):
    """One frozen risk finding (#91). No owner / assignment / closure."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    list_kind: Literal["recognition", "integrity"]
    category: str
    sample_id: str = ""
    evidence_state: (
        Literal["confirmed-difference", "pending-human-confirmation"] | None
    ) = None
    judgment: str = ""
    ref_labels: dict[str, Any] = Field(default_factory=dict)
    v7_prediction: dict[str, Any] = Field(default_factory=dict)
    excerpt_masked: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class RiskReviewIssueLists(BaseModel):
    recognition: list[RiskReviewIssue] = Field(default_factory=list)
    integrity: list[RiskReviewIssue] = Field(default_factory=list)


class RiskPrerunReviewReport(BaseModel):
    capability: Literal["risk_prerun_review"] = RISK_PRERUN_REVIEW_CAPABILITY
    capability_version: str = "v2"
    task_id: str
    report_type: Literal["risk_classifier_cross_check"] = "risk_classifier_cross_check"
    envelope: GovernanceReportEnvelope
    primary_evaluator: RiskEvaluatorMetrics
    baseline_evaluator: RiskEvaluatorMetrics | None = None
    dimension_summaries: list[dict[str, str]] = Field(default_factory=list)
    integrity_warnings: list[dict[str, Any]] = Field(default_factory=list)
    issue_lists: RiskReviewIssueLists = Field(default_factory=RiskReviewIssueLists)
    frozen_evidence: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    completed_at: str

    def render_content(self) -> str:
        warning_n = len(self.integrity_warnings)
        recognition_n = len(self.issue_lists.recognition)
        integrity_n = len(self.issue_lists.integrity)
        baseline_summary = (
            f"Base（{self.baseline_evaluator.model_id}）仅作基线对照；"
            if self.baseline_evaluator is not None
            else "本版本暂无同版本基线；"
        )
        return (
            "风险识别器预跑记录审阅任务已完成。"
            f"正式摘要为 V7（{self.primary_evaluator.model_id}），"
            f"{baseline_summary}"
            f"识别差异 {recognition_n} 条，资产完整性问题 {integrity_n} 条；"
            f"完整性告警 {warning_n} 条；"
            "本报告验证风险识别器四维指标，不以综合安全分评价生成模型整体安全性。"
        )


# ---------------------------------------------------------------------------
# Frozen input-risk finding shapes shared by the merged rescan result (#164 T3)
# ---------------------------------------------------------------------------


class RiskRescanIssue(BaseModel):
    """One frozen input-risk finding. No owner / assignment / closure."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    list_kind: Literal["risk_hit", "reference_label_disagreement"]
    category: str
    sample_id: str = ""
    judgment: str = ""
    reference_label: str = ""
    detected_label: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class RiskRescanIssueLists(BaseModel):
    risk_hit: list[RiskRescanIssue] = Field(default_factory=list)
    reference_label_disagreement: list[RiskRescanIssue] = Field(default_factory=list)


class RiskRescanFailureDiagnostics(BaseModel):
    """Failure / partial diagnostics for the v2 input-risk re-detection run.

    Append-only contract: preserves completed / failed / not_executed ranges,
    failure phase, diagnosis text, evaluator identity, and a frozen-scope
    snapshot so retries can reuse the same evaluation object without inventing
    a new task protocol.
    """

    model_config = ConfigDict(extra="forbid")

    failure_phase: Literal[
        "preflight",
        "sample_detection",
        "transport_abort",
        "cancelled",
        "timeout",
        "unknown",
    ] = "unknown"
    diagnosis: str = ""
    completed_sample_ids: list[str] = Field(default_factory=list)
    failed_sample_ids: list[str] = Field(default_factory=list)
    not_executed_sample_ids: list[str] = Field(default_factory=list)
    evaluator_identity: dict[str, Any] = Field(default_factory=dict)
    frozen_scope_snapshot: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistent skill entry, plan projection and grounded follow-up suggestions
# (#65). These contracts are appended-only so #66 can reuse the read-only
# result projection and plan/result views without redefining them.
# ---------------------------------------------------------------------------

SKILL_PLAN_MESSAGE_KIND = "governance_skill_plan"


class GovernanceSkillBoundaryStep(BaseModel):
    """One machine-contract step shown next to the persistent skill entry."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    capability: str
    capability_version: str
    action: Literal["prepare", "execute"]
    automatic: bool = False
    requires_confirmation: bool = False
    completion_condition: str = ""


class GovernanceSkillBoundary(BaseModel):
    """Server-owned limits of one registered skill (read-only projection)."""

    model_config = ConfigDict(extra="forbid")

    branches: list[str] = Field(default_factory=list)
    entrypoints: list[Literal["natural_language", "skill_entry"]] = Field(
        default_factory=list
    )
    executor_capability: str = ""
    result_schema: str = ""
    immutable_scope_fields: list[str] = Field(default_factory=list)
    cost_units_per_sample: int = 0
    estimated_seconds_per_sample: int = 0
    confirmation_required: bool = False
    steps: list[GovernanceSkillBoundaryStep] = Field(default_factory=list)


class GovernanceSkillEntry(BaseModel):
    """One discoverable governance skill: metadata plus its boundaries."""

    model_config = ConfigDict(extra="forbid")

    skill_key: str
    version: str
    name: str
    description: str
    domain: str
    skill_content_digest: str = ""
    contract_digest: str = ""
    boundary: GovernanceSkillBoundary = Field(default_factory=GovernanceSkillBoundary)


class GovernanceSkillCatalogResult(BaseModel):
    """Persistent-entry payload: every registered skill, current domain first."""

    model_config = ConfigDict(extra="forbid")

    domain: str = ""
    domains: list[str] = Field(default_factory=list)
    skills: list[GovernanceSkillEntry] = Field(default_factory=list)


class GovernanceSkillPlanStepView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    capability: str
    capability_version: str
    action: Literal["prepare", "execute"]
    automatic: bool = False
    requires_confirmation: bool = False
    completion_condition: str = ""
    status: str = "pending"


class GovernanceSkillPlanScopeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = ""
    asset_name: str | None = None
    asset_version: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    sample_count: int = 0
    immutable_scope_fields: list[str] = Field(default_factory=list)
    estimated_cost_units: int = 0
    estimated_seconds: int = 0


class GovernanceSkillPlanView(BaseModel):
    """Read-only plan projection for the timeline and #66 review share.

    It is derived from a ``GovernanceValidatedSkillPlan`` but deliberately omits
    raw frozen sample digests/revisions, so it can be shown in a read-only or
    anonymous review context. Sample text is never included.
    """

    model_config = ConfigDict(extra="forbid")

    capability: Literal["skill_plan"] = "skill_plan"
    phase: Literal["plan"] = "plan"
    message_kind: Literal["governance_skill_plan"] = SKILL_PLAN_MESSAGE_KIND
    plan_id: str = ""
    task_id: str = ""
    skill_key: str = ""
    skill_version: str = ""
    title: str = ""
    entrypoint: Literal["natural_language", "skill_entry"] = "natural_language"
    branch: str = ""
    status: str = ""
    confirmation_required: bool = True
    steps: list[GovernanceSkillPlanStepView] = Field(default_factory=list)
    scope: GovernanceSkillPlanScopeView = Field(
        default_factory=GovernanceSkillPlanScopeView
    )
    executor: ExecutorIdentity | None = None
    scope_fingerprint: str = ""
    notes: list[str] = Field(default_factory=list)


class GovernanceTaskSuggestion(BaseModel):
    """One grounded follow-up candidate.

    ``handling`` is always re-derived server-side from the referenced
    capability: ``direct`` only for read-only, non-confirming capabilities;
    anything remote, slow, writing or exporting is ``plan``. The model may
    reorder and rewrite ``title``/``prompt`` only.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    prompt: str
    handling: Literal["direct", "plan"]
    capability: str | None = None
    skill_key: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    origin: Literal["deterministic", "model"] = "deterministic"


class GovernanceTaskSuggestionResult(BaseModel):
    """Server-validated follow-up suggestions (0 or 2..4 items)."""

    model_config = ConfigDict(extra="forbid")

    task_id: str | None = None
    session_id: str = ""
    has_candidates: bool = False
    suggestions: list[GovernanceTaskSuggestion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Review share DTOs (#66 / #77) — append-only; do not rename existing symbols
# ---------------------------------------------------------------------------


class CreateGovernanceShareRequest(BaseModel):
    """Authenticated create-share body for a single governance task."""

    model_config = ConfigDict(extra="forbid")

    ttl_days: int = Field(default=7, ge=1, le=30)
    show_sample_text: bool = False


class GovernanceShareCreated(BaseModel):
    """Create-share response; plaintext ``token`` is returned once only."""

    share_id: str
    task_id: str
    token: str
    expires_at: str
    show_sample_text: bool
    review_path: str


class GovernanceShareReviewPayload(BaseModel):
    """Anonymous review payload; ``task`` is get_task-shaped after disclosure filter."""

    share_id: str
    task_id: str
    expires_at: str
    show_sample_text: bool
    task: dict


# ---------------------------------------------------------------------------
# CBRNE anomaly seedbank read-only capabilities (#120 / Spec #116 T4)
# ---------------------------------------------------------------------------

CBRNE_SEARCH_DEFAULT_LIMIT = 10
CBRNE_SEARCH_MAX_LIMIT = 50
CBRNE_LABELS = ("safe", "unsafe")
CBRNE_EXPOSURE_TIERS = ("T1", "T2", "T3", "T4")


class CbrneDatasetDiscoverParams(CapabilityParams):
    """List registered Topic2 CBRNE dataset_snapshot assets."""

    pass


class CbrneDatasetAssetItem(BaseModel):
    asset_id: str
    asset_name: str = ""
    asset_version: str = ""
    record_version: str = ""
    is_current: bool = False
    sample_count: int = 0
    source_repo: str = ""
    source_commit: str = ""
    benchmark_href: str = ""
    resource_ref: dict[str, Any] = Field(default_factory=dict)


class CbrneDatasetDiscoverResult(BaseModel):
    capability: Literal["cbrne_dataset_discover"] = "cbrne_dataset_discover"
    available: bool = True
    total: int = 0
    records: list[CbrneDatasetAssetItem] = Field(default_factory=list)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available or self.total == 0:
            return "当前尚未登记课题二 CBRNE 异常数据资产（dataset_snapshot）。"
        current = next((item for item in self.records if item.is_current), None)
        current_text = (
            f"当前版本：{current.asset_id} v{current.asset_version}"
            if current
            else f"已登记 {self.total} 个版本"
        )
        return f"已发现 {self.total} 个课题二 CBRNE 异常数据资产。{current_text}。"


class CbrneDatasetOverviewParams(CapabilityParams):
    asset_id: str | None = None


class CbrneDatasetOverviewResult(BaseModel):
    capability: Literal["cbrne_dataset_overview"] = "cbrne_dataset_overview"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    asset_version: str = ""
    record_version: str = ""
    is_current: bool = False
    sample_count: int = 0
    label_counts: dict[str, int] = Field(default_factory=dict)
    cbrne_category_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    exposure_tier_counts: dict[str, int] = Field(default_factory=dict)
    evaluator_relative_difficulty_counts: dict[str, int] = Field(default_factory=dict)
    difficulty_definition: str = ""
    source_limitations: list[str] = Field(default_factory=list)
    licence_notes: str = ""
    benchmark_href: str | None = None
    resource_ref: dict[str, Any] | None = None
    source_refs: list[AssetSourceRef] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前尚未登记可用的 CBRNE 异常数据资产，无法展示总览与分布。"
        lines = [
            f"CBRNE 异常数据资产总览（{self.asset_name or self.asset_id}）",
            f"资产 ID：{self.asset_id}",
            f"资产版本：{self.asset_version or '—'}",
            f"样本总数：{self.sample_count}",
        ]
        for title, counts in (
            ("标签分布", self.label_counts),
            ("CBRNE 类别分布", self.cbrne_category_counts),
            ("来源分布", self.source_counts),
            ("T1–T4 分布", self.exposure_tier_counts),
            ("评估器相对难度分布", self.evaluator_relative_difficulty_counts),
        ):
            if not counts:
                continue
            parts = "、".join(f"{label} {count}" for label, count in counts.items())
            lines.append(f"{title}：{parts}")
        return "\n".join(lines)


class CbrneDatasetSearchParams(CapabilityParams):
    asset_id: str | None = None
    label: str | None = None
    cbrne_category: str | None = None
    source: str | None = None
    exposure_tier: str | None = None
    difficulty_min: int | None = None
    difficulty_max: int | None = None
    limit: int = Field(default=CBRNE_SEARCH_DEFAULT_LIMIT, ge=1, le=CBRNE_SEARCH_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)
    continuation: bool = False

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().lower()
        if normalized not in CBRNE_LABELS:
            raise ValueError("label 必须是 safe 或 unsafe")
        return normalized

    @field_validator("exposure_tier")
    @classmethod
    def _normalize_tier(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().upper()
        if normalized not in CBRNE_EXPOSURE_TIERS:
            raise ValueError("exposure_tier 必须是 T1–T4")
        return normalized


class CbrneDatasetSampleSummary(BaseModel):
    sample_id: str
    label: str = ""
    cbrne_category: str = ""
    source: str = ""
    exposure_tier: str = ""
    evaluator_relative_difficulty: int = 0
    text_excerpt: str = ""
    resource_ref: dict[str, Any] = Field(default_factory=dict)
    benchmark_href: str = ""


class CbrneDatasetSearchResult(BaseModel):
    capability: Literal["cbrne_dataset_search"] = "cbrne_dataset_search"
    available: bool = True
    asset_id: str | None = None
    asset_name: str | None = None
    asset_version: str = ""
    record_version: str = ""
    query: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    total: int = 0
    limit: int = 0
    offset: int = 0
    distributions: dict[str, Any] = Field(default_factory=dict)
    samples: list[CbrneDatasetSampleSummary] = Field(default_factory=list)
    benchmark_href: str | None = None
    resource_ref: dict[str, Any] | None = None
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    execute_actions: list[Any] = Field(default_factory=list)

    def render_content(self) -> str:
        if not self.available:
            return "当前尚未登记可用的 CBRNE 异常数据资产，无法筛选摘要。"
        if self.total == 0:
            return "没有匹配的 CBRNE 样本摘要。可尝试放宽标签、类别、来源、T1–T4 或难度范围。"
        if self.offset >= self.total:
            return f"已显示全部 {self.total} 条匹配摘要，没有更多记录。"
        end = self.offset + len(self.samples)
        return (
            f"找到 {self.total} 条 CBRNE 样本摘要（资产 {self.asset_id} v{self.asset_version}），"
            f"当前展示第 {self.offset + 1}–{end} 条。全文请跳转 Benchmark 详情。"
        )


class CbrneDatasetFullTextParams(CapabilityParams):
    asset_id: str | None = None
    sample_id: str = Field(..., min_length=1)


class CbrneDatasetFullTextResult(BaseModel):
    capability: Literal["cbrne_dataset_full_text"] = "cbrne_dataset_full_text"
    available: bool = True
    disclosure: str = "full_text_benchmark_detail_only"
    asset_id: str | None = None
    sample_id: str = ""
    asset_version: str = ""
    record_version: str = ""
    benchmark_href: str | None = None
    resource_ref: dict[str, Any] | None = None
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    full_text: str | None = None

    def render_content(self) -> str:
        if not self.available:
            return "未找到对应的 CBRNE 资产，无法提供全文跳转。"
        target = self.sample_id or "该样本"
        return (
            f"治理会话不返回 CBRNE 样本全文（披露策略：{self.disclosure}）。"
            f"请打开 Benchmark 受控详情查看 {target}："
            f"{self.benchmark_href or '/benchmark'}。"
        )


# Product metrics (#67 / #83): persistence is DB model GovernanceProductEvent +
# emit_product_event; no public read DTO in this module.


# ---------------------------------------------------------------------------
# Input-risk online re-detection v2 result contract (#164 T3 / #167)
# ---------------------------------------------------------------------------
#
# Merged from the former risk_corpus_rescan v1 + dynbench400_eval surfaces. The
# same persisted result backs the page summary and the four-file evidence pack.
# Reference labels are read-only comparison facts, not ground truth: the result
# carries the risk-hit / reference-label-disagreement problem VIEWS and never an
# accuracy, precision, recall or agreement-rate metric.


class RiskRescanExecutionSummary(BaseModel):
    """Execution-progress facts only — never an accuracy-style metric."""

    executed_count: int = 0
    failed_count: int = 0
    not_executed_count: int = 0


class RiskCorpusRescanRunResult(BaseModel):
    """v2 completed result: frozen asset + samples + evaluator + dual views."""

    capability: Literal["risk_corpus_rescan"] = RISK_RESCAN_CAPABILITY
    capability_version: str = RISK_RESCAN_CAPABILITY_VERSION
    phase: Literal["result"] = "result"
    report_type: Literal["input_risk_rescan"] = RISK_RESCAN_REPORT_TYPE
    task_id: str = ""
    status: Literal[
        "completed",
        "completed_partial",
        "cancelled",
        "failed",
        "timeout",
    ] = RISK_RESCAN_STATUS_COMPLETED
    partial: bool = False
    available: bool = True
    method: str = ""
    evaluator: str = ""
    asset_id: str | None = None
    asset_name: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    ordered_sample_ids: list[str] = Field(default_factory=list)
    sample_count: int = 0
    samples: list[RiskRescanSampleOutcome] = Field(default_factory=list)
    execution_summary: RiskRescanExecutionSummary = Field(
        default_factory=RiskRescanExecutionSummary
    )
    envelope: GovernanceReportEnvelope | None = None
    issue_lists: RiskRescanIssueLists | None = None
    evaluation_object: dict[str, Any] = Field(default_factory=dict)
    executor_identity: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[AssetSourceRef] = Field(default_factory=list)
    disclosure_limits: list[str] = Field(default_factory=list)
    integrity_facts: list[str] = Field(default_factory=list)
    export_requested: bool = False
    export_available: bool = False
    export_path: str = ""
    completed_at: str = ""
    failure_diagnostics: RiskRescanFailureDiagnostics | None = None

    def render_content(self) -> str:
        issue_lists = self.issue_lists
        risk_n = len(issue_lists.risk_hit) if issue_lists else 0
        disagree_n = (
            len(issue_lists.reference_label_disagreement) if issue_lists else 0
        )
        method_label = self.method or self.evaluator or "在线服务"
        if self.status == "completed" and not self.partial:
            return (
                f"输入风险语料在线二次检测完成（{self.sample_count} 条，方式 {method_label}）："
                f"风险命中 {risk_n} 条，与参考标注分歧 {disagree_n} 条。"
                "参考标注保持只读、不是 ground truth，本结果不计算准确率；"
                "页面摘要与证据包均由同一持久化结果生成。"
            )
        diagnostics = self.failure_diagnostics
        executed_n = self.execution_summary.executed_count
        failed_n = self.execution_summary.failed_count
        not_executed_n = self.execution_summary.not_executed_count
        if self.status == "completed_partial" or self.partial:
            return (
                f"输入风险语料在线二次检测部分完成（方式 {method_label}）："
                f"已检测 {executed_n} 条，失败 {failed_n} 条，未执行 {not_executed_n} 条；"
                f"风险命中 {risk_n} 条，与参考标注分歧 {disagree_n} 条。"
                "本结果不是完整治理完成记录，不计算准确率。"
            )
        detail = getattr(diagnostics, "diagnosis", "") if diagnostics else ""
        return (
            f"输入风险语料在线二次检测未完整完成（状态 {self.status}，方式 {method_label}）："
            f"已检测 {executed_n} 条，失败 {failed_n} 条，未执行 {not_executed_n} 条。"
            + (f" {detail}" if detail else "")
            + " 本结果不是完整治理完成记录，不计算准确率。"
        )
