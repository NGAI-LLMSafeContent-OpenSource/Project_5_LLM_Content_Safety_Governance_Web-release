from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings

BENCHMARK_TASK_STATUSES = frozenset(
    {
        "pending",
        "validating",
        "running",
        "packaging",
        "completed",
        "failed",
        "rejected",
    }
)

BENCHMARK_LANGUAGES = frozenset({"zh", "en", "zh+en"})
BENCHMARK_AGENT_IDS = frozenset(
    {
        "topic2-autobench",
        "topic3-difficulty-generation",
        "topic1-value-qa",
        "topic3-cultural-corpus-generation",
        "topic3-risk-benchmark-generation",
    }
)
TOPIC1_VALUE_QA_LANGUAGES = frozenset({"zh", "zh-CN", "en", "zh+en"})
TOPIC3_DIFFICULTY_LEVELS = ("H1", "H2", "H3", "H4")
TOPIC3_RISK_CATEGORY_CODES = tuple(f"C{index:02d}" for index in range(1, 18))
TOPIC3_CULTURAL_DIFFICULTY_LEVELS = ("L1", "L2", "L3")


class BenchmarkTaskCreate(BaseModel):
    agent_id: Literal[
        "topic2-autobench",
        "topic3-difficulty-generation",
        "topic1-value-qa",
        "topic3-cultural-corpus-generation",
        "topic3-risk-benchmark-generation",
    ]
    mode: Literal["live_run"] = "live_run"
    parameters: dict[str, Any]

    @model_validator(mode="after")
    def validate_parameters_for_agent(self) -> "BenchmarkTaskCreate":
        if self.agent_id == "topic2-autobench":
            _validate_topic2_parameters(self.parameters)
        elif self.agent_id == "topic3-difficulty-generation":
            _validate_topic3_difficulty_parameters(self.parameters)
        elif self.agent_id == "topic1-value-qa":
            _validate_topic1_value_qa_parameters(self.parameters)
        elif self.agent_id == "topic3-cultural-corpus-generation":
            _validate_topic3_cultural_corpus_parameters(self.parameters)
        elif self.agent_id == "topic3-risk-benchmark-generation":
            _validate_topic3_risk_parameters(self.parameters)
        return self


def _validate_topic1_value_qa_parameters(value: dict[str, Any]) -> None:
    generation_mode = value.get("generation_mode", "topic")
    if generation_mode not in {"topic", "dimension"}:
        raise ValueError("generation_mode must be one of: topic, dimension")

    topic = value.get("topic")
    dimension = value.get("dimension")
    topic_text = topic.strip() if isinstance(topic, str) else ""
    dimension_text = dimension.strip() if isinstance(dimension, str) else ""
    if generation_mode == "topic":
        if not topic_text:
            raise ValueError("topic must be a non-empty string in topic mode")
        if dimension_text:
            raise ValueError("dimension must be empty in topic mode")
    if generation_mode == "dimension":
        if not dimension_text:
            raise ValueError("dimension must be a non-empty string in dimension mode")
        if topic_text:
            raise ValueError("topic must be empty in dimension mode")

    n_topics = value.get("n_topics", 1)
    if not isinstance(n_topics, int) or isinstance(n_topics, bool):
        raise ValueError("n_topics must be an integer")

    topics = _normalized_topic_list(value.get("topics"))
    if generation_mode == "dimension":
        if topics:
            raise ValueError("topics must not be set in dimension mode")
        if not 1 <= n_topics <= 2:
            raise ValueError("n_topics must be between 1 and 2")
    if generation_mode == "topic":
        if topics:
            if topic_text != topics[0]:
                raise ValueError("topic must equal the first topics item")
            if n_topics != len(topics):
                raise ValueError("n_topics must equal the number of topics")
        elif n_topics != 1:
            raise ValueError("n_topics must be 1 in topic mode when topics is omitted")
        if n_topics < 1:
            raise ValueError("n_topics must be >= 1")

    groups_per_topic = value.get("groups_per_topic")
    if not isinstance(groups_per_topic, int) or isinstance(groups_per_topic, bool):
        raise ValueError("groups_per_topic must be an integer")
    if not 1 <= groups_per_topic <= 10:
        raise ValueError("groups_per_topic must be between 1 and 10")
    if generation_mode == "dimension" and n_topics * groups_per_topic > 10:
        raise ValueError("total requested groups must be <= 10")

    retrieval_mode = value.get("retrieval_mode")
    if isinstance(retrieval_mode, str):
        retrieval_mode = retrieval_mode.strip() or None
    elif retrieval_mode is not None:
        raise ValueError("retrieval_mode must be one of: local_corpus, online_baike")
    if retrieval_mode is not None and retrieval_mode not in {
        "local_corpus",
        "online_baike",
    }:
        raise ValueError("retrieval_mode must be one of: local_corpus, online_baike")
    corpus_jsonl = value.get("corpus_jsonl")
    if retrieval_mode == "local_corpus" and (
        not isinstance(corpus_jsonl, str) or not corpus_jsonl.strip()
    ):
        raise ValueError("corpus_jsonl must be a non-empty string in local_corpus mode")

    language = value.get("language")
    if language not in TOPIC1_VALUE_QA_LANGUAGES:
        raise ValueError("language must be one of: zh, zh-CN, en, zh+en")

    seed = value.get("seed")
    if seed is not None and (
        not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
    ):
        raise ValueError("seed must be a non-negative integer")

    for key in ("run_qc", "run_trace"):
        flag = value.get(key, False)
        if not isinstance(flag, bool):
            raise ValueError(f"{key} must be a boolean")
        if flag:
            raise ValueError(f"{key}=true is not supported in the first live_run slice")


def _normalized_topic_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("topics must be a list of strings")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("topics must be a list of strings")
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _validate_topic2_parameters(value: dict[str, Any]) -> None:
    settings = get_settings()
    budget = value.get("budget")
    if not isinstance(budget, int) or isinstance(budget, bool):
        raise ValueError("budget must be an integer")
    if not 1 <= budget <= settings.benchmark_demo_budget_max:
        raise ValueError(
            f"budget must be between 1 and {settings.benchmark_demo_budget_max}"
        )

    language = value.get("language")
    if language not in BENCHMARK_LANGUAGES:
        raise ValueError("language must be one of: zh, en, zh+en")

    l1 = value.get("l1")
    if isinstance(l1, str):
        if not l1.strip():
            raise ValueError("l1 must not be empty")
    elif isinstance(l1, list):
        if not l1 or not all(isinstance(item, str) and item.strip() for item in l1):
            raise ValueError("l1 must be a non-empty string list")
    else:
        raise ValueError("l1 must be a string or string list")

    moderators = value.get("moderators")
    if isinstance(moderators, str):
        if not moderators.strip():
            raise ValueError("moderators must not be empty")
    elif isinstance(moderators, list):
        if not moderators or not all(
            isinstance(item, str) and item.strip() for item in moderators
        ):
            raise ValueError("moderators must be a non-empty string list")
    else:
        raise ValueError("moderators must be a string or string list")

    max_turns = value.get("max_turns")
    if not isinstance(max_turns, int) or isinstance(max_turns, bool):
        raise ValueError("max_turns must be an integer")
    if not 1 <= max_turns <= 25:
        raise ValueError("max_turns must be between 1 and 25")


def _validate_topic3_difficulty_parameters(value: dict[str, Any]) -> None:
    language = value.get("language")
    if language not in BENCHMARK_LANGUAGES:
        raise ValueError("language must be one of: zh, en, zh+en")

    total_sample_count = value.get("total_sample_count")
    if not isinstance(total_sample_count, int) or isinstance(total_sample_count, bool):
        raise ValueError("total_sample_count must be an integer")
    if not 1 <= total_sample_count <= 100:
        raise ValueError("total_sample_count must be between 1 and 100")

    difficulty_counts = value.get("difficulty_counts")
    if not isinstance(difficulty_counts, dict):
        raise ValueError("difficulty_counts must be an object")
    total = 0
    for level in TOPIC3_DIFFICULTY_LEVELS:
        count = difficulty_counts.get(level)
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError(f"difficulty_counts.{level} must be an integer")
        if count < 0:
            raise ValueError(f"difficulty_counts.{level} must be >= 0")
        total += count
    extra_levels = set(difficulty_counts) - set(TOPIC3_DIFFICULTY_LEVELS)
    if extra_levels:
        raise ValueError(
            f"difficulty_counts has unsupported levels: {', '.join(sorted(extra_levels))}"
        )
    if total != total_sample_count:
        raise ValueError("difficulty_counts total must equal total_sample_count")

    seed_dataset = value.get("seed_dataset")
    if not isinstance(seed_dataset, str) or not seed_dataset.strip():
        raise ValueError("seed_dataset must be a non-empty string")

    risk_categories = value.get("risk_categories", [])
    if not isinstance(risk_categories, list) or not all(
        isinstance(item, str) and item.strip() for item in risk_categories
    ):
        raise ValueError("risk_categories must be a string list")
    extra_categories = [
        item.strip()
        for item in risk_categories
        if item.strip() not in TOPIC3_RISK_CATEGORY_CODES
    ]
    if extra_categories:
        raise ValueError(
            "risk_categories must use C01–C17 codes; "
            f"unsupported: {', '.join(extra_categories)}"
        )

    for key in ("generation_model", "guard_model"):
        model = value.get(key)
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"{key} must be a non-empty string")


def _validate_topic3_cultural_corpus_parameters(value: dict[str, Any]) -> None:
    language = value.get("language", "zh")
    if language not in BENCHMARK_LANGUAGES:
        raise ValueError("language must be one of: zh, en, zh+en")

    total_sample_count = value.get("total_sample_count")
    if not isinstance(total_sample_count, int) or isinstance(total_sample_count, bool):
        raise ValueError("total_sample_count must be an integer")
    if not 1 <= total_sample_count <= 50:
        raise ValueError("total_sample_count must be between 1 and 50")

    difficulty_counts = value.get("difficulty_counts")
    if not isinstance(difficulty_counts, dict):
        raise ValueError("difficulty_counts must be an object")
    total = 0
    for level in TOPIC3_CULTURAL_DIFFICULTY_LEVELS:
        count = difficulty_counts.get(level)
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError(f"difficulty_counts.{level} must be an integer")
        if count < 0:
            raise ValueError(f"difficulty_counts.{level} must be >= 0")
        total += count
    extra_levels = set(difficulty_counts) - set(TOPIC3_CULTURAL_DIFFICULTY_LEVELS)
    if extra_levels:
        raise ValueError(
            f"difficulty_counts has unsupported levels: {', '.join(sorted(extra_levels))}"
        )
    if total != total_sample_count:
        raise ValueError("difficulty_counts total must equal total_sample_count")

    allowed_ethnic_groups = value.get("allowed_ethnic_groups")
    if not isinstance(allowed_ethnic_groups, list) or not allowed_ethnic_groups:
        raise ValueError("allowed_ethnic_groups must be a non-empty string list")
    if not all(
        isinstance(item, str) and item.strip() for item in allowed_ethnic_groups
    ):
        raise ValueError("allowed_ethnic_groups must be a non-empty string list")

    batch_size = value.get("batch_size")
    if batch_size is not None:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool):
            raise ValueError("batch_size must be an integer")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")

    random_seed = value.get("random_seed")
    if random_seed is not None and (
        not isinstance(random_seed, int)
        or isinstance(random_seed, bool)
        or random_seed < 0
    ):
        raise ValueError("random_seed must be a non-negative integer")

    allowed_dimensions = value.get("allowed_dimensions")
    if allowed_dimensions is not None:
        if not isinstance(allowed_dimensions, list) or not all(
            isinstance(item, str) and item.strip() for item in allowed_dimensions
        ):
            raise ValueError("allowed_dimensions must be a string list")


def _validate_topic3_risk_parameters(value: dict[str, Any]) -> None:
    scale = value.get("scale", "trial")
    if scale != "trial":
        raise ValueError("topic3 risk live_run currently only supports scale=trial")

    target_per_kind = value.get("target_per_kind", 5)
    if not isinstance(target_per_kind, int) or isinstance(target_per_kind, bool):
        raise ValueError("target_per_kind must be an integer")
    if target_per_kind != 5:
        raise ValueError("target_per_kind must be 5 for the trial live_run")

    workers = value.get("workers", 1)
    if workers is None:
        return
    if not isinstance(workers, int) or isinstance(workers, bool):
        raise ValueError("workers must be an integer")
    if not 1 <= workers <= 4:
        raise ValueError("workers must be between 1 and 4")


class BenchmarkTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    agent_id: str
    mode: str
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    upstream_base_url: str | None = None
    upstream_contract: str | None = None
    source_repo: str | None = None
    source_commit: str | None = None
    adapter_version: str | None = None
    error_message: str | None = None
    asset_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_parameters(cls, data: Any) -> Any:
        if isinstance(data, dict) and "parameters" not in data:
            parameters_json = data.get("parameters_json")
            if isinstance(parameters_json, str):
                import json

                try:
                    data = dict(data)
                    data["parameters"] = json.loads(parameters_json or "{}")
                except json.JSONDecodeError:
                    data = dict(data)
                    data["parameters"] = {}
        return data


class BenchmarkTaskLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    event_type: str
    stage: str | None = None
    message: str | None = None
    turn: int | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_json(cls, data: Any) -> Any:
        if isinstance(data, dict) and "raw_json" in data and isinstance(
            data["raw_json"], str
        ):
            import json

            payload = dict(data)
            try:
                payload["raw_json"] = json.loads(data["raw_json"] or "{}")
            except json.JSONDecodeError:
                payload["raw_json"] = {}
            return payload
        return data


class BenchmarkTaskLogsResponse(BaseModel):
    task_id: str
    logs: list[BenchmarkTaskLogItem]


class BenchmarkArtifactItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: str
    task_id: str
    source_mode: str
    name: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    artifact_sha256: str
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_manifest(cls, data: Any) -> Any:
        if isinstance(data, dict) and "manifest" not in data:
            manifest_json = data.get("manifest_json")
            if isinstance(manifest_json, str):
                import json

                payload = dict(data)
                try:
                    payload["manifest"] = json.loads(manifest_json or "{}")
                except json.JSONDecodeError:
                    payload["manifest"] = {}
                return payload
        return data


class BenchmarkArtifactsResponse(BaseModel):
    task_id: str
    artifacts: list[BenchmarkArtifactItem]


class BenchmarkAssetRegistryResponse(BaseModel):
    assets: list[BenchmarkArtifactItem]


class BenchmarkPrerunImportRequest(BaseModel):
    archive_path: str


class BenchmarkPrerunImportResponse(BaseModel):
    asset: BenchmarkArtifactItem


class BenchmarkDatasetSnapshotImportRequest(BaseModel):
    archive_path: str


class BenchmarkDatasetSnapshotImportResponse(BaseModel):
    asset: BenchmarkArtifactItem
    idempotent: bool = False


class BenchmarkCbrneSampleResourceRef(BaseModel):
    kind: str
    asset_id: str
    sample_id: str


class BenchmarkCbrneQueryFilters(BaseModel):
    label: str | None = None
    cbrne_category: str | None = None
    source: str | None = None
    exposure_tier: str | None = None
    difficulty_min: int | None = None
    difficulty_max: int | None = None


class BenchmarkCbrneSampleSummaryItem(BaseModel):
    sample_id: str
    label: str
    cbrne_category: str
    source: str
    exposure_tier: str
    evaluator_relative_difficulty: int
    text_excerpt: str
    resource_ref: BenchmarkCbrneSampleResourceRef


class BenchmarkCbrneSamplesQueryResponse(BaseModel):
    asset_id: str
    asset_version: str
    record_version: str
    query: BenchmarkCbrneQueryFilters
    total: int
    limit: int
    offset: int
    distributions: dict[str, Any] = Field(default_factory=dict)
    samples: list[BenchmarkCbrneSampleSummaryItem]


class BenchmarkCbrneSampleAccessEvent(BaseModel):
    event_id: str
    asset_id: str
    asset_version: str
    sample_id: str
    action_type: str
    accessed_at: str
    disclosure_request_id: str | None = None


class BenchmarkCbrneSampleRefItem(BaseModel):
    sample_id: str
    label: str
    cbrne_category: str
    source: str
    exposure_tier: str
    evaluator_relative_difficulty: int
    text_preview: str


class BenchmarkCbrneSampleRefsResponse(BaseModel):
    asset_id: str
    asset_version: str
    total: int
    limit: int
    offset: int
    items: list[BenchmarkCbrneSampleRefItem]


class BenchmarkCbrneSampleRefResponse(BaseModel):
    """One exact masked sample identity for a stable resource deep link.

    Deliberately a fixed whitelist: no full text, raw object, normalized
    payload, or access event may be added here.
    """

    asset_id: str
    asset_version: str
    sample_id: str
    label: str
    cbrne_category: str
    source: str
    exposure_tier: str
    evaluator_relative_difficulty: int
    text_preview: str


class BenchmarkCbrneSampleDetailResponse(BaseModel):
    asset_id: str
    asset_version: str
    sample_id: str
    full_text: str
    raw: dict[str, Any]
    platform_normalized: dict[str, Any]
    access_event: BenchmarkCbrneSampleAccessEvent


class BenchmarkCbrneSampleDisclosureRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    disclosure_request_id: UUID = Field(alias="disclosureRequestId")


class BenchmarkCbrneSampleDisclosureResponse(BenchmarkCbrneSampleDetailResponse):
    pass


class BenchmarkTopic3RiskImportRequest(BaseModel):
    final_dir: str | None = None
    asset_id: str | None = None
    name: str | None = None


class BenchmarkTopic3RiskImportResponse(BaseModel):
    asset: BenchmarkArtifactItem


class BenchmarkTopic3RiskV6ImportRequest(BaseModel):
    csv_path: str
    asset_id: str | None = None
    name: str | None = None


class BenchmarkTopic3RiskV6ImportResponse(BaseModel):
    asset: BenchmarkArtifactItem


class BenchmarkTopic3RiskEvaluationImportRequest(BaseModel):
    result_dir: str


class BenchmarkTopic3RiskEvaluationImportResponse(BaseModel):
    summary: dict[str, Any]


class BenchmarkTopic3RiskAssetIdentity(BaseModel):
    """Selected asset of the versioned topic3 risk Benchmark series.

    Legacy per-asset endpoints may address assets outside the series; those
    report ``asset_status="unregistered"`` and no ``asset_version``.
    """

    series_id: str
    asset_id: str
    asset_version: str | None = None
    asset_sha256: str
    asset_status: Literal["current", "historical", "unregistered"]


class BenchmarkTopic3RiskAssetOverview(BenchmarkTopic3RiskAssetIdentity):
    series_name: str
    name: str
    sample_count: int | None = None
    safe_count: int | None = None
    risk_count: int | None = None
    risk_level_distribution: dict[str, int] = Field(default_factory=dict)
    language_distribution: dict[str, int] = Field(default_factory=dict)
    culture_distribution: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    evaluation_status: str
    registered_at: datetime | None = None


class BenchmarkTopic3RiskAssetVersionsResponse(BaseModel):
    series_id: str
    series_name: str
    current_asset_id: str | None = None
    versions: list[BenchmarkTopic3RiskAssetOverview] = Field(default_factory=list)


class BenchmarkTopic3RiskEvaluationSummaryResponse(BenchmarkTopic3RiskAssetIdentity):
    available: bool
    asset_name: str
    eval_mode: str
    result_source: str
    status: str
    source_label: str
    primary_metrics: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, Any] = Field(default_factory=dict)
    excluded_run_ids: list[str] = Field(default_factory=list)
    live_eval: dict[str, Any] = Field(default_factory=dict)


class BenchmarkEvaluationAppendRun(BaseModel):
    run_id: str
    status: str
    run_content_sha256: str
    model_id: str
    role: str


class BenchmarkEvaluationAppendResponse(BenchmarkTopic3RiskAssetIdentity):
    """Admin view of an appended same-version evaluation run set (#153)."""

    name: str
    sample_count: int | None = None
    package_sha256: str
    runs: list[BenchmarkEvaluationAppendRun] = Field(default_factory=list)
    evaluation: dict[str, Any] = Field(default_factory=dict)


class BenchmarkDeliveryResponse(BaseModel):
    """Admin view of a Benchmark delivery (#151); the staging directory stays server-side."""

    delivery_id: str
    status: str
    provider: str
    series_id: str
    asset_id: str
    asset_version: str
    package_sha256: str
    package_size: int
    uploaded_by: str
    received_at: datetime
    validated_at: datetime | None = None
    updated_at: datetime
    report: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRiskCategory(BaseModel):
    code: str
    name: str


class BenchmarkTopic3RiskTaxonomyResponse(BaseModel):
    taxonomy_schema: str = Field(alias="schema")
    version: str
    source: str
    categories: list[BenchmarkRiskCategory]


class BenchmarkTopic2ModeratorResult(BaseModel):
    label: str | None = None
    confidence: float | None = None
    strength: float | None = None


class BenchmarkTopic2RewriteQa(BaseModel):
    passed: bool
    semantic_ok: bool
    format_ok: bool
    reason: str | None = None
    source: str | None = None


class BenchmarkTopic2PrerunSampleItem(BaseModel):
    sample_id: str
    difficulty_level: str
    query_preview: str
    query: str
    rewrite_rounds: float | None = None
    strategy: str | None = None
    strategy_chain: list[str] = Field(default_factory=list)
    attack_vector: str | None = None
    language: str | None = None
    label: str | None = None
    rewrite_qa: BenchmarkTopic2RewriteQa
    moderator_results: dict[str, BenchmarkTopic2ModeratorResult] = Field(
        default_factory=dict
    )


class BenchmarkTopic2PrerunPairItem(BaseModel):
    pair_id: str
    seedbank_id: str | None = None
    root_seed_id: str | None = None
    source_row_id: str | None = None
    harm_category_l1: str | None = None
    harm_category_l2: str | None = None
    simple: BenchmarkTopic2PrerunSampleItem | None = None
    hard: BenchmarkTopic2PrerunSampleItem | None = None


class BenchmarkTopic2PrerunPairsResponse(BaseModel):
    asset_id: str
    total: int
    limit: int
    offset: int
    moderators: list[str]
    pairs: list[BenchmarkTopic2PrerunPairItem]


class BenchmarkTopic1ValueQaImportRequest(BaseModel):
    samples_path: str | None = None
    marks_path: str | None = None
    qc_index_path: str | None = None
    qc_samples_path: str | None = None
    qc_scores_path: str | None = None
    qc_summary_path: str | None = None
    trace_predictions_path: str | None = None
    trace_low_issues_path: str | None = None
    asset_id: str | None = None
    name: str | None = None


class BenchmarkTopic1ValueQaImportResponse(BaseModel):
    asset: BenchmarkArtifactItem


class BenchmarkTopic1ValueQaLevelPreview(BaseModel):
    sample_id: str
    question_preview: str
    answer_preview: str
    qc_status: str


class BenchmarkTopic1ValueQaGroupItem(BaseModel):
    group_id: str
    asset_id: str
    topic: str
    primary_dimension: str
    secondary_dimension: str
    qc_status: str
    levels: dict[str, BenchmarkTopic1ValueQaLevelPreview]


class BenchmarkTopic1ValueQaGroupsResponse(BaseModel):
    asset_id: str
    total: int
    limit: int
    offset: int
    groups: list[BenchmarkTopic1ValueQaGroupItem]


class BenchmarkTopic1ValueQaLevelDetail(BaseModel):
    sample_id: str
    question: str
    answer: str
    quality_level: str
    source_reference: dict[str, Any]
    missing_annotation_count: int
    prompt_snapshot: str
    manual_marked_at: str | None = None
    qc_status: str
    trace_predicted_level: str | None = None
    trace_true_label: str | None = None
    trace_is_consistent: bool | None = None
    trace_match_status: str | None = None
    trace_issue_count: int | None = None
    trace_low_issue_spans: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkTopic1ValueQaGroupDetailResponse(BaseModel):
    asset_id: str
    group_id: str
    topic: str
    primary_dimension: str
    secondary_dimension: str
    qc_status: str
    levels: dict[str, BenchmarkTopic1ValueQaLevelDetail]


class BenchmarkTopic1ValueQaRecheckSummaryResponse(BaseModel):
    status: str
    scope: str
    sample_count: int
    prediction_count: int
    coverage_ratio: float
    correct_count: int
    accuracy: float
    mismatch_count: int = 0
    true_label_distribution: dict[str, int] = Field(default_factory=dict)
    predicted_label_distribution: dict[str, int] = Field(default_factory=dict)
    gold_distribution: dict[str, int] = Field(default_factory=dict)
    low_issue_sample_count: int
    issue_count: int
    issue_type_distribution: dict[str, int] = Field(default_factory=dict)
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    source_schema: str = ""
    source_file: str | None = None
    is_formal_model_eval: bool = False


class BenchmarkTopic3RiskSampleItem(BaseModel):
    sample_id: str
    asset_id: str
    index: int | str
    culture: str
    language: str
    prompt_preview: str
    response_preview: str
    response_safetype: str
    risk_category: str
    risk_category_code: str
    risk_sub_category: str
    risk_level_id: str
    safe_type: str
    safe_mode: str
    label_reason_preview: str
    response_text_source: str
    source_index: int | str


class BenchmarkTopic3RiskSamplesResponse(BenchmarkTopic3RiskAssetIdentity):
    total: int
    limit: int
    offset: int
    samples: list[BenchmarkTopic3RiskSampleItem]


class BenchmarkTopic3RiskSampleDetailResponse(BenchmarkTopic3RiskAssetIdentity):
    sample_id: str
    index: int | str
    version: str
    culture: str
    language: str
    prompt: str
    response: str
    response_safetype: str
    risk_category: str
    risk_category_code: str
    risk_sub_category: str
    risk_level_id: str
    label_source: str
    response_text_original: str
    response_text_source: str
    source_index: int | str
    source_sample_id: str = ""
    locale: str = ""
    is_translation: str = ""
    safe_type: str
    safe_mode: str
    label_reason: str
    label_reason_status: str = ""
    integrity_warnings: list[dict[str, str]] = Field(default_factory=list)
    label_reason_usable_for_automatic_explanation: bool = True
    warning_note: str | None = None


class BenchmarkTopic3CulturalEnsureResponse(BaseModel):
    asset: BenchmarkArtifactItem


class BenchmarkTopic3CulturalSampleItem(BaseModel):
    sample_id: str
    ethnic_group: str
    difficulty_level: str
    background_type: str
    persona: str
    query_type: str
    review_passed: bool
    prompt_preview: str


class BenchmarkTopic3CulturalSamplesResponse(BaseModel):
    asset_id: str
    total: int
    limit: int
    offset: int
    samples: list[BenchmarkTopic3CulturalSampleItem]


class BenchmarkTopic3CulturalSampleDetailResponse(BaseModel):
    sample_id: str
    prompt: str
    background: str
    user_query: str
    expected_answer: str
    ethnic_group: str
    difficulty_level: str
    background_type: str
    persona: str
    query_type: str
    cultural_knowledge_points: list[str] = Field(default_factory=list)
    rubric: dict[str, list[str]] = Field(default_factory=dict)
    review: dict[str, Any] = Field(default_factory=dict)
    run_id: str
    batch_id: str


class BenchmarkTopic3CulturalSummaryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    asset_id: str
    sample_count: int
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    ethnic_distribution: dict[str, int] = Field(default_factory=dict)
    background_type_distribution: dict[str, int] = Field(default_factory=dict)
    persona_distribution: dict[str, int] = Field(default_factory=dict)
    query_type_distribution: dict[str, int] = Field(default_factory=dict)
    review_passed_count: int
    review_passed_rate: float
    model_eval_status: str
