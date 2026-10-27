from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---- Risk Taxonomy ----

class SubcategoryItem(BaseModel):
    key: str
    label: str
    level: str = "MEDIUM"


class RiskCategory(BaseModel):
    key: str
    label: str
    category: str = "culture"
    level: str = "MEDIUM"
    selected: bool = True
    definition: str = ""
    subcategories: list[SubcategoryItem] = []


class ThresholdDefaults(BaseModel):
    high: float = 0.7
    medium: float = 0.4
    low: float = 0.2


class RiskTaxonomyOut(BaseModel):
    taxonomy_id: int
    taxonomy_name: str
    version: str = ""
    source_repo: str = "Project_3_Risk_Hierarchical_Classification_Benchmark"
    source: str = "benchmark"  # 'benchmark' | 'mock'
    categories: list[RiskCategory] = []
    threshold_defaults: ThresholdDefaults = Field(default_factory=ThresholdDefaults)


# ---- Eval Start ----

class SamplingConfigItem(BaseModel):
    dataset_id: str
    sampling_method: str = "full"
    sample_size: int = 0


class EvalRuntimeOptions(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    evaluator: str = "binary"
    include_severity: bool = True
    model_key: str = "bingoguard-local"
    display_scene: str = "output-risk"
    use_vllm: bool = False
    response_only: bool = False
    max_new_tokens: int = 32
    max_model_len: int = 4096


class EvalStartRequest(BaseModel):
    config_id: str = "risk-benchmark-v1"
    dataset_ids: list[str] = []
    taxonomy_id: int | None = None
    selected_dimensions: list[str] = []
    sampling_config: list[SamplingConfigItem] = []
    runtime_options: EvalRuntimeOptions = Field(default_factory=EvalRuntimeOptions)


class EvalStartResponse(BaseModel):
    task_id: str
    status: str = "pending"
    task_type: str = "output_risk_eval"
    created_at: str = ""


# ---- Single-Sample Dynamic Inference ----

class InferSampleRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    task: str = "binary"
    model_id: str = "qwen3.5-9b"
    prompt: str = ""
    response: str
    template_policy: str | None = None
    use_vllm: bool = True
    use_api: bool = False
    max_new_tokens: int = 64
    severity_max_new_tokens: int = 16
    evidence_max_new_tokens: int = 1536
    max_model_len: int = 32768


class InferStep(BaseModel):
    name: str
    status: str = "done"
    detail: dict | str | None = None


class InferSampleResponse(BaseModel):
    ok: bool = False
    source: str = "benchmark"  # 'benchmark' | 'mock'
    steps: list[InferStep] = []
    pred_safe_type: str | None = None
    pred_risk_level: str | None = None
    pred_category: str | None = None
    pred_category_code: str | None = None
    raw_response: str | None = None
    prompt_used: str | None = None
    cached: bool = False
    stderr: str | None = None
    stdout: str | None = None
    risk_evidence: list[dict] = []


# ---- Eval Task Status ----

class EvalLogEntry(BaseModel):
    time: str = ""
    level: str = "info"
    message: str = ""


class EvalTaskStatus(BaseModel):
    task_id: str
    task_type: str = "output_risk_eval"
    status: str = "pending"
    progress: float = 0.0
    stage: str = ""
    stage_label: str = ""
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    logs: list[EvalLogEntry] = []
    artifacts: dict[str, str] = {}
    source: str = "benchmark"


# ---- Eval Results ----

class DatasetSummary(BaseModel):
    sample_total: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    selected_dimension_count: int = 0


class EvalSampleOut(BaseModel):
    id: str
    text: str
    dimension_scores: dict[str, str] = {}
    overall_level: str = "LOW"
    overall_score: float = 0.0
    summary: str = ""
    dataset_id: str = ""
    dataset_name: str = ""
    gold_binary_label: int | None = None
    pred_binary_label: int | None = None
    gold_category: str = ""
    gold_category_code: str = ""
    pred_category: str = ""
    pred_category_code: str = ""
    gold_level: str = ""
    pred_level: str = ""
    is_correct: bool | None = None
    is_category_correct: bool | None = None


class EvalMetrics(BaseModel):
    binary_safe_acc: float = 0.0
    risk_class_acc: float = 0.0
    severity_acc: float = 0.0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    risk_recall: float = 0.0
    fpr: float = 0.0


class RadarSeriesData(BaseModel):
    name: str
    values: list[float]
    fill: str
    stroke: str


class RadarRiskData(BaseModel):
    dimensions: list[str] = []
    series: list[RadarSeriesData] = []


class DatasetMetricItem(BaseModel):
    dataset_id: str
    dataset_name: str
    sample_count: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    risk_class_acc: float = 0.0
    risk_recall: float = 0.0
    fpr: float = 0.0
    per_category: dict[str, dict[str, object]] = {}


class MultiDatasetRadarItem(BaseModel):
    dataset_id: str
    dataset_name: str
    values: list[float] = []
    color: str = ""


class RadarMultiDatasetData(BaseModel):
    dimensions: list[str] = []
    dimension_labels: dict[str, str] = {}
    selected_metric: str = "f1"
    series: list[MultiDatasetRadarItem] = []


class GroupedMetricItem(BaseModel):
    sample_count: int = 0
    accuracy: float = 0.0
    f1: float = 0.0
    risk_class_acc: float = 0.0
    risk_recall: float = 0.0


class GroupedMetricsData(BaseModel):
    dimension: str = ""
    groups: dict[str, GroupedMetricItem] = {}


class EvalResultSummary(BaseModel):
    task_id: str
    config_id: str = ""
    source: str = "benchmark"
    dataset_summary: DatasetSummary = Field(default_factory=DatasetSummary)
    radar_risk_data: RadarRiskData = Field(default_factory=RadarRiskData)
    radar_multi_dataset: RadarMultiDatasetData | None = None
    samples: list[EvalSampleOut] = []
    metrics: EvalMetrics = Field(default_factory=EvalMetrics)
    dataset_metrics: list[DatasetMetricItem] = []
    grouped_metrics: GroupedMetricsData | None = None
    artifacts: dict[str, str] = {}
    created_at: str = ""


# ---- Export ----

class ExportQuery(BaseModel):
    output_format: str = Field("csv", alias="format")
    level: str | None = None
    only_wrong: bool = False

    class Config:
        populate_by_name = True


# ---- Culture Diversity (Cultural Gen proxy) ----

class CultureScores(BaseModel):
    culture: int = 0
    semantic: int = 0
    integrity: int = 0
    total: int = 0


class CultureErrors(BaseModel):
    wrongExample: str = ""
    fixSuggestion: str = ""
    improveItems: list[str] = []


class CultureSampleOut(BaseModel):
    id: str
    fullQuestion: str
    bgType: str = ""
    cues: list[str] = []
    inferred: str = ""
    category: str = ""
    ethnic: str = ""
    expected: str = ""
    generated: str = ""
    knowledge: str = ""
    cultureScore: int = 0
    semanticScore: int = 0
    integrityScore: int = 0
    wrongExample: str = ""
    fixSuggestion: str = ""
    improveItems: list[str] = []


class CultureAnalyzeResultOut(BaseModel):
    text: str
    ethnic: str
    confidence: int = 0
    cues: list[str] = []
    category: str = ""
    reasoning: list[str] = []
    knowledge: str = ""
    top3: list[str] = []
    generated: str = ""
    scores: CultureScores = Field(default_factory=CultureScores)
    errors: CultureErrors = Field(default_factory=CultureErrors)


class Topic3RiskResultDisplay(BaseModel):
    """同版本指标展示。只把主评估器任务口径收成类型，其余指标字段保持原样。"""

    model_config = ConfigDict(extra="allow")

    task: str | None = None


class Topic3RiskPredictionRow(BaseModel):
    """主评估器规范化预测中的一条。没有该样本的行时不补空类别列表。"""

    sample_id: str
    prediction: dict[str, Any]
    pred_categories: list[str] | None = None


class Topic3RiskSameVersionOut(BaseModel):
    """课题三风险资产与同版本评测结果。版本、资产标识和内容哈希来自同一次解析。"""

    model_config = ConfigDict(extra="allow")

    series_id: str
    asset_id: str
    asset_version: str | None = None
    asset_sha256: str
    asset_status: str
    sample_count: int | None = None
    samples: dict[str, Any]
    sample_details: list[dict[str, Any]]
    evaluation: dict[str, Any]
    primary_evaluator: dict[str, Any]
    result_display: Topic3RiskResultDisplay
    predictions: list[Topic3RiskPredictionRow] = Field(default_factory=list)
    baseline: dict[str, Any]
    automatic_explanations: list[dict[str, Any]]
    versions: list[dict[str, Any]]


class CultureSummaryOut(BaseModel):
    source: str = ""  # 'real' | 'mock'
    total: int = 0
    explicit_count: int = 0
    implicit_count: int = 0
    ethnic_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    samples: list[CultureSampleOut] = []
