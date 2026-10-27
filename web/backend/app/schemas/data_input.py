from pydantic import BaseModel, Field


class IntegrationEndpoint(BaseModel):
    method: str
    path: str
    purpose: str
    ready: bool = True


class Topic4HealthResponse(BaseModel):
    connected: bool
    service: str = "Project 4 Input Workflow"
    base_url: str
    message: str
    source: str = "topic4_input_workflow"
    mode: str = "remote_service"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)


class Topic4LineageNode(BaseModel):
    id: str
    type: str
    summary: str
    url: str = ""
    docName: str = ""
    docId: str = ""
    topic: str = ""
    pipeline: str = "Project 4 Input Workflow /api/build_graph -> /api/graph/merge"
    isRisky: bool = False
    riskLevel: str = "none"
    riskTypes: list[str] = Field(default_factory=list)


class Topic4LineageEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "related"


class Topic4LineageSummary(BaseModel):
    totalNodes: int = 0
    totalEdges: int = 0
    metaCount: int = 0
    chunkCount: int = 0
    cleanedChunkCount: int = 0
    questionCount: int = 0
    answerCount: int = 0
    riskyNodes: int = 0
    cleanNodes: int = 0


class Topic4WorkflowStage(BaseModel):
    key: str
    label: str
    status: str = "completed"
    description: str = ""


class Topic4LineageResponse(BaseModel):
    connected: bool
    service: str = "Project 4 Input Workflow"
    base_url: str
    message: str
    source: str = "topic4_input_workflow"
    mode: str = "remote_service"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    summary: Topic4LineageSummary = Field(default_factory=Topic4LineageSummary)
    nodes: list[Topic4LineageNode] = Field(default_factory=list)
    edges: list[Topic4LineageEdge] = Field(default_factory=list)
    workflowMode: str = "topic4_full_v2"
    workflowStages: list[Topic4WorkflowStage] = Field(default_factory=list)
    annotations: list[dict] = Field(default_factory=list)
    cleaningActions: list[dict] = Field(default_factory=list)
    reportSummary: str = ""
    selectedNodeId: str = ""


class Topic4LineageBuildRequest(BaseModel):
    records: list[dict] = Field(default_factory=list)
    risk_annotations: list[dict] | None = None


class Topic4LineageParseFailure(BaseModel):
    name: str
    reason: str


class Topic4LineageParseResponse(BaseModel):
    records: list[dict] = Field(default_factory=list)
    failures: list[Topic4LineageParseFailure] = Field(default_factory=list)
    source: str = "project5_dataset_upload"


class Topic2HealthResponse(BaseModel):
    connected: bool
    service: str = "Project 2 FilterGuard"
    base_url: str
    message: str
    source: str = "topic2_filterguard"
    mode: str = "remote_service"
    method: str = "keyword"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)


class Topic2KeywordFinding(BaseModel):
    keyword: str
    evidence: str = ""
    risk_type: str = "keyword_hit"


class Topic2KeywordPrediction(BaseModel):
    id: str
    text: str
    source_index: int = 0
    lineage_node_id: str = ""
    lineage_node_label: str = ""
    risk_category_l1: str = ""
    risk_category_l2: str = ""
    predicted_l1_id: str = ""
    detect_method: str = ""
    action: str = ""
    score: float = 0
    threshold: float = 1
    prediction: int = 0
    is_abnormal: bool = False
    status: str = "安全"
    suggestion: str = ""
    evidence_chain: list[str] = Field(default_factory=list)
    correction_contract_status: str = "pending_topic2_contract"
    findings: list[Topic2KeywordFinding] = Field(default_factory=list)


class Topic2RiskScanItem(BaseModel):
    text: str
    lineage_node_id: str = ""
    lineage_node_label: str = ""
    risk_category_l1: str = ""
    risk_category_l2: str = ""


class Topic2KeywordPredictRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)
    method: str = ""


class Topic2KeywordPredictResponse(BaseModel):
    connected: bool
    service: str = "Project 2 FilterGuard"
    base_url: str
    message: str
    source: str = "topic2_filterguard"
    mode: str = "remote_service"
    method: str = "keyword"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    total: int = 0
    abnormal_count: int = 0
    normal_count: int = 0
    predictions: list[Topic2KeywordPrediction] = Field(default_factory=list)


class Topic2RiskScanTaskStartRequest(BaseModel):
    items: list[Topic2RiskScanItem] = Field(default_factory=list)
    method: str = ""


class Topic2RiskScanTaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    cancellable: bool = False
    method: str = ""
    result: Topic2KeywordPredictResponse | None = None


class Topic2PrerunSampleRow(BaseModel):
    id: str
    score: float = 0
    status: str = "安全"
    snippet: str
    suggestion: str = ""
    difficulty_level: str = ""
    pair_id: str = ""
    harm_category_l1: str = ""
    harm_category_l2: str = ""
    strategy_chain: list[str] = Field(default_factory=list)
    bypassed_moderators: list[str] = Field(default_factory=list)


class InputCorpusCatalogItem(BaseModel):
    asset_id: str
    name: str
    kind: str
    source_label: str
    sample_count: int = 0
    ready: bool = True
    description: str = ""
    track_hint: str = ""
    track: str = ""  # value | risk


class InputCorpusCatalogResponse(BaseModel):
    connected: bool
    message: str
    items: list[InputCorpusCatalogItem] = Field(default_factory=list)
    next_action: str = ""


class InputCorpusRecord(BaseModel):
    id: str
    text: str
    meta: dict = Field(default_factory=dict)


class InputCorpusSelectResponse(BaseModel):
    connected: bool
    message: str
    asset_id: str = ""
    asset_name: str = ""
    kind: str = ""
    source_label: str = ""
    total: int = 0
    records: list[InputCorpusRecord] = Field(default_factory=list)
    blocking_reason: str = ""
    next_action: str = ""


class Topic2PrerunSamplesResponse(BaseModel):
    connected: bool
    service: str = "课题二正式预跑评测资产"
    base_url: str = ""
    message: str
    source: str = "benchmark_prerun_snapshot"
    mode: str = "asset_registry"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    asset_id: str = ""
    asset_name: str = ""
    total: int = 0
    pair_count: int = 0
    moderators: list[str] = Field(default_factory=list)
    l1_labels: list[str] = Field(default_factory=list)
    rows: list[Topic2PrerunSampleRow] = Field(default_factory=list)


class InputGuardrailLiveRunItem(BaseModel):
    id: str = ""
    text: str
    track: str = "general"
    source_asset_id: str = ""
    source_file: str = ""
    source_sample_id: str = ""
    source_label: str = ""
    source_name: str = ""
    expected_issue: str = ""


class InputGuardrailLiveRunStartRequest(BaseModel):
    pack_id: str = "demo-mixed-10"
    items: list[InputGuardrailLiveRunItem] = Field(default_factory=list)
    max_samples: int | None = None


class AttributionIssueSpan(BaseModel):
    type: str = ""
    sentence: str = ""
    span: str = ""


class AttributionFinding(BaseModel):
    keyword: str = ""
    evidence: str = ""
    risk_type: str = "keyword_hit"
    label: str = ""


class AttributionStep(BaseModel):
    title: str
    detail: str = ""


class AttributionRow(BaseModel):
    id: str
    track: str
    source: str
    status: str
    score: str
    snippet: str
    suggestion: str = ""
    summary: str = ""
    evidence_chain: list[str] = Field(default_factory=list)
    attribution_steps: list[AttributionStep] = Field(default_factory=list)
    findings: list[AttributionFinding] = Field(default_factory=list)
    issue_spans: list[AttributionIssueSpan] = Field(default_factory=list)
    lineage_node_id: str = ""
    lineage_node_label: str = ""
    risk_category_l1: str = ""
    risk_category_l2: str = ""
    predicted_l1_id: str = ""
    detect_method: str = ""
    action: str = ""
    note: str = ""
    difficulty_level: str = ""
    strategy_chain: list[str] = Field(default_factory=list)
    dimension: str = ""
    topic: str = ""
    true_label: str = ""
    predicted_label: str = ""
    quality_level: str = ""
    group_id: str = ""


class AttributionStatItem(BaseModel):
    val: str
    label: str


class AttributionResponse(BaseModel):
    connected: bool
    track: str
    service: str
    message: str
    source: str
    mode: str = "attribution_module"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    asset_id: str = ""
    asset_name: str = ""
    total: int = 0
    stats: list[AttributionStatItem] = Field(default_factory=list)
    rows: list[AttributionRow] = Field(default_factory=list)


class RiskAttributionRequest(BaseModel):
    task_id: str | None = None
    predictions: list[Topic2KeywordPrediction] = Field(default_factory=list)
    use_prerun: bool = False
    asset_id: str | None = None
    limit: int = 20


class ValueQaDimensionItem(BaseModel):
    name: str
    kind: str
    count: int = 0


class ValueQaAssetStatusResponse(BaseModel):
    connected: bool
    service: str = "课题一 value_qa 价值评测语料"
    message: str
    source: str = "topic1_value_qa"
    mode: str = "asset_registry"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    asset_id: str = ""
    asset_name: str = ""
    total: int = 0
    group_count: int = 0
    qc_status: str = ""
    trace_status: str = ""
    quality_level_distribution: dict[str, int] = Field(default_factory=dict)
    primary_dimension_distribution: dict[str, int] = Field(default_factory=dict)
    secondary_dimension_distribution: dict[str, int] = Field(default_factory=dict)


class ValueQaDimensionsResponse(BaseModel):
    connected: bool
    service: str = "课题一 value_qa 维度筛选"
    message: str
    source: str = "topic1_value_qa"
    mode: str = "asset_registry"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    asset_id: str = ""
    asset_name: str = ""
    dimensions: list[ValueQaDimensionItem] = Field(default_factory=list)


class ValueAssessmentResponse(BaseModel):
    connected: bool
    service: str = "课题一 value_qa 价值评估"
    message: str
    source: str = "topic1_value_qa"
    mode: str = "asset_registry"
    fallback: bool = False
    blocking_reason: str = ""
    next_action: str = ""
    endpoints: list[IntegrationEndpoint] = Field(default_factory=list)
    asset_id: str = ""
    asset_name: str = ""
    total: int = 0
    group_count: int = 0
    stats: list[AttributionStatItem] = Field(default_factory=list)
    rows: list[AttributionRow] = Field(default_factory=list)
    fix_rows: list[AttributionRow] = Field(default_factory=list)
    radar_scores: dict[str, float] = Field(default_factory=dict)
    quality_level_distribution: dict[str, int] = Field(default_factory=dict)
