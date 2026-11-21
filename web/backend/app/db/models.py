from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Topic1CorpusToolJob(Base):
    __tablename__ = "topic1_corpus_tool_jobs"
    __table_args__ = (UniqueConstraint("client_id", "request_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(36), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(32))
    operation: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(200))
    input_json: Mapped[str] = mapped_column(Text)
    parameters_json: Mapped[str] = mapped_column(Text)
    endpoint_hash: Mapped[str] = mapped_column(String(64))
    upstream_id: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="submitting")
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Topic1CorpusArchive(Base):
    __tablename__ = "topic1_corpus_archives"
    __table_args__ = (UniqueConstraint("job_id", "asset_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("topic1_corpus_tool_jobs.id"), index=True)
    asset_key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GovernanceClient(Base):
    __tablename__ = "governance_clients"

    client_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GovernanceSession(Base):
    __tablename__ = "governance_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("governance_clients.client_id"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(28), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GovernanceMessage(Base):
    __tablename__ = "governance_messages"
    __table_args__ = (
        Index(
            "uq_governance_messages_client_request",
            "client_id",
            "request_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("governance_sessions.session_id"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("governance_clients.client_id"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GovernanceClarificationPlan(Base):
    """Durable, pre-task goal context for one governance conversation."""

    __tablename__ = "governance_clarification_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting_clarification', 'resolved', 'abandoned', 'invalidated')",
            name="ck_governance_clarification_plans_status",
        ),
        Index(
            "uq_governance_clarification_plans_active_session",
            "session_id",
            unique=True,
            sqlite_where=text("status = 'awaiting_clarification'"),
            postgresql_where=text("status = 'awaiting_clarification'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("governance_sessions.session_id"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("governance_clients.client_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="awaiting_clarification"
    )
    source_message_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    system_clarifications_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    settled_boundaries_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    goal_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    bound_skill_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bound_skill_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    skill_content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contract_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GovernanceTask(Base):
    __tablename__ = "governance_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("governance_clients.client_id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("governance_sessions.session_id"), nullable=False, index=True
    )
    capability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GovernanceSkillRun(Base):
    """One immutable attempt of a versioned skill within a governance task."""

    __tablename__ = "governance_skill_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    skill_key: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(32), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(32), nullable=False)
    planner_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planning")
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[str] = mapped_column(Text, nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmation_scope_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scope_selection: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    revision_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    executor_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    result_schema: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GovernanceRunSampleResult(Base):
    """Immutable outcome for one frozen sample in one skill-run attempt."""

    __tablename__ = "governance_run_sample_results"
    __table_args__ = (
        Index(
            "uq_governance_run_sample_results_run_sample",
            "run_id",
            "sample_id",
            unique=True,
        ),
        CheckConstraint(
            "status IN ('consistent', 'inconsistent', 'failed', 'not_executed')",
            name="ck_governance_run_sample_results_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("governance_skill_runs.run_id"), nullable=False, index=True
    )
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_version: Mapped[str] = mapped_column(String(32), nullable=False)
    result_schema: Mapped[str] = mapped_column(String(128), nullable=False)
    executor_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now
    )


class GovernanceCapabilityStep(Base):
    """A validated atomic capability call belonging to one skill run."""

    __tablename__ = "governance_capability_steps"
    __table_args__ = (
        Index(
            "uq_governance_capability_steps_run_position",
            "run_id",
            "position",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("governance_skill_runs.run_id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    branch: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_schema: Mapped[str] = mapped_column(String(128), nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GovernanceCapabilityRun(Base):
    """One first-class execution attempt of a governance capability (#164 T2).

    A governance task either contains a direct capability run (``skill_run_id``
    is NULL) or a skill run that contains capability runs. The run owns the
    capability key/version, the frozen execution scope, the confirmation state,
    the resolved executor identity, its status/events result reference, its
    error facts and its retry lineage. A retry always creates a new run and
    never overwrites the previous one.
    """

    __tablename__ = "governance_capability_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    # NULL means this run was launched directly by the task rather than by a
    # skill run; kept nullable so skill-contained runs stay representable.
    skill_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("governance_skill_runs.run_id"), nullable=True, index=True
    )
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    confirmation_scope_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    scope_selection: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="awaiting_confirmation"
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    root_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revision_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    executor_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    executor_metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_schema: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    result_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GovernanceTaskLease(Base):
    """Exclusive, expiring database claim held by an independent worker."""

    __tablename__ = "governance_task_leases"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), primary_key=True
    )
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_token: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    leased_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class GovernanceTaskEvent(Base):
    """Stable, sanitized business event persisted before SSE delivery."""

    __tablename__ = "governance_task_events"
    __table_args__ = (
        Index(
            "uq_governance_task_events_task_sequence",
            "task_id",
            "sequence",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    counts_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    resource_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class GovernanceCompletionRecord(Base):
    __tablename__ = "governance_completion_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    completion_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("governance_sessions.session_id"), nullable=False, index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("governance_messages.id"), nullable=True
    )
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    result_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GovernanceTaskShare(Base):
    """Time-limited, revocable anonymous review share for one governance task."""

    __tablename__ = "governance_task_shares"
    __table_args__ = (
        Index("uq_governance_task_shares_token_hash", "token_hash", unique=True),
    )

    share_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("governance_tasks.task_id"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("governance_clients.client_id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    show_sample_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class GovernanceShareAccessEvent(Base):
    """Append-only audit row for anonymous review-share access attempts."""

    __tablename__ = "governance_share_access_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('ok', 'expired', 'revoked', 'not_found')",
            name="ck_governance_share_access_events_result",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    share_id: Mapped[str | None] = mapped_column(
        ForeignKey("governance_task_shares.share_id"), nullable=True, index=True
    )
    accessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    viewer_meta: Mapped[str | None] = mapped_column(Text, nullable=True)


class GovernanceProductEvent(Base):
    """Append-only anonymized product-funnel event (#67 / #83).

    ``session_id`` / ``task_id`` are never stored plaintext — only SHA-256 hashes.
    ``attributes_json`` must contain whitelist scalars only (no sample text).
    """

    __tablename__ = "governance_product_events"
    __table_args__ = (
        Index("ix_governance_product_events_event_name", "event_name"),
        Index("ix_governance_product_events_occurred_at", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    session_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MiningInput(Base):
    __tablename__ = "mining_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    definition_type: Mapped[str] = mapped_column(String(40), default="value")
    policy_text: Mapped[str] = mapped_column(Text, default="")
    sample_text: Mapped[str] = mapped_column(Text, default="")
    web_links_json: Mapped[str] = mapped_column(Text, default="[]")
    lookup_names_json: Mapped[str] = mapped_column(Text, default="[]")
    uploaded_document_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    mining_demand: Mapped[str] = mapped_column(String(40), default="level3")
    level1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MiningTask(Base):
    __tablename__ = "mining_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    input_id: Mapped[int] = mapped_column(ForeignKey("mining_inputs.id"), nullable=False)
    definition_type: Mapped[str] = mapped_column(String(40), default="value")
    definition_scope: Mapped[str] = mapped_column(String(40), default="input-value")
    task_type: Mapped[str] = mapped_column(String(60), default="rule_based_first_phase")
    subject_area: Mapped[str] = mapped_column(String(40), default="platform")
    parent_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    runtime_options_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    agent_runtime_json: Mapped[str] = mapped_column(Text, default="{}")
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Explicit user archive — runtime tasks always persist; only saved ones appear in history UI.
    saved_to_history: Mapped[bool] = mapped_column(default=False)
    history_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    history_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")


class OutputGuardrailLiveJob(Base):
    """输出护栏 live-batch 任务 — 小批量检测 + 合规改写快照"""
    __tablename__ = "output_guardrail_live_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    pack_id: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    source: Mapped[str] = mapped_column(String(20), default="live")
    progress_json: Mapped[str] = mapped_column(Text, default="{}")
    samples_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OutputEvalTask(Base):
    """输出风险评测任务 — 持久化任务元数据与结果"""
    __tablename__ = "output_eval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    benchmark_job_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    dataset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    selected_dimensions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    source: Mapped[str] = mapped_column(String(20), default="mock")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    samples_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DataInputWorkflowDraft(Base):
    """输入护栏工作草稿 — 检测、证据和修正清单的本地可回看快照。"""

    __tablename__ = "data_input_workflow_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    source: Mapped[str] = mapped_column(String(40), default="wizard", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    asset_refs_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TaskArtifact(Base):
    __tablename__ = "task_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), index=True)
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CandidateIndicator(Base):
    __tablename__ = "candidate_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    definition_type: Mapped[str] = mapped_column(String(40), default="value")
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    level1: Mapped[str] = mapped_column(String(100), default="")
    level2: Mapped[str] = mapped_column(String(100), default="")
    level3: Mapped[str] = mapped_column(String(150), default="")
    definition: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    formula: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="pending_review")
    review_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CandidateReviewEvent(Base):
    __tablename__ = "candidate_review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BenchmarkTask(Base):
    """课题二 AutoBench 动态 Benchmark 平台任务。"""

    __tablename__ = "benchmark_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="live_run")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    upstream_base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_contract: Mapped[str] = mapped_column(
        String(64), default="topic2-autobench-v0.1"
    )
    source_repo: Mapped[str] = mapped_column(String(255), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_version: Mapped[str] = mapped_column(
        String(64), default="topic2-autobench-adapter-v0.1"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BenchmarkTaskLog(Base):
    """AutoBench SSE 事件转存日志。"""

    __tablename__ = "benchmark_task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BenchmarkAsset(Base):
    """AutoBench 真跑产物冻结索引。"""

    __tablename__ = "benchmark_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    source_mode: Mapped[str] = mapped_column(String(32), default="live_run")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    artifact_dir: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_zip_path: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    source_repo: Mapped[str] = mapped_column(String(255), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BenchmarkAssetSeries(Base):
    """Versioned Benchmark asset series with an explicit current-version pointer."""

    __tablename__ = "benchmark_asset_series"

    series_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    current_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class BenchmarkAssetVersion(Base):
    """Immutable evaluated-object version identity of one asset within a series."""

    __tablename__ = "benchmark_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "series_id", "asset_version", name="uq_benchmark_asset_versions_series_version"
        ),
        Index("ix_benchmark_asset_versions_series_id", "series_id"),
    )

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class BenchmarkDelivery(Base):
    """Benchmark delivery package received by the management import and its lifecycle."""

    __tablename__ = "benchmark_deliveries"
    __table_args__ = (Index("ix_benchmark_deliveries_status", "status"),)

    delivery_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    asset_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    asset_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    # Import attempt that owns an unsettled record; every state change is conditional on it.
    attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Extracted delivery content; only kept while the delivery is publishable.
    staging_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class BenchmarkSampleAccessEvent(Base):
    """Append-only audit row for explicit Benchmark sample full-text detail access."""

    __tablename__ = "benchmark_sample_access_events"
    __table_args__ = (
        Index("ix_benchmark_sample_access_events_asset_id", "asset_id"),
        Index("ix_benchmark_sample_access_events_sample_id", "sample_id"),
        Index("ix_benchmark_sample_access_events_accessed_at", "accessed_at"),
        Index(
            "uq_benchmark_sample_access_events_disclosure_request_id",
            "disclosure_request_id",
            unique=True,
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    definition_type: Mapped[str] = mapped_column(String(40), default="value")
    level1: Mapped[str] = mapped_column(String(100), default="")
    level2: Mapped[str] = mapped_column(String(100), default="")
    level3: Mapped[str] = mapped_column(String(150), default="")
    definition: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    formula: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    source_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adopted_from_candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
