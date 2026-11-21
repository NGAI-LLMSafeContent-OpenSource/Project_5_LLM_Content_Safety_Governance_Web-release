// ============================================================
// 通用 API 响应格式
// ============================================================

/** 后端统一响应包裹 */
export interface ApiResponse<T = unknown> {
  code: number
  data: T
  msg: string
}

/** 分页数据结构 */
export interface PaginatedData<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

/** 分页查询参数 */
export interface PaginationQuery {
  page?: number
  pageSize?: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

// ============================================================
// 枚举常量
// ============================================================

/** 指标 Tab 枚举 */
export enum TabKeyEnum {
  INPUT_VALUE = 'input-value',
  INPUT_RISK = 'input-risk',
  OUTPUT_RISK = 'output-risk',
  OUTPUT_CULTURE = 'output-culture',
}

/** 风险评估等级 */
export enum RiskLevel {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

/** 数据集类别 */
export enum DatasetType {
  CULTURE = 'culture',
  SCIENCE = 'science',
}

/** 数据集子类型（输出页使用，由后端 /api/demo/options 的 group_name 动态决定） */
export type DatasetSubType = string

/** 评估轨道 */
export enum AssessmentTrack {
  VALUE = 'value',
  RISK = 'risk',
}

/** 输出页并行轨道 */
export enum OutputTrack {
  DIVERSITY = 'diversity',
  RISK = 'risk',
}

/** 多样性达成度档位 */
export enum DiversityLevel {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  NEEDS_IMPROVEMENT = 'needsImprovement',
}

/** 修正状态 */
export enum CorrectionStatus {
  PENDING = 'pending',
  ADOPTED = 'adopted',
  CLARIFY = 'clarify',
  SKIP = 'skip',
}

/** 采样方式 */
export enum SamplingMethod {
  FULL = 'full',
  RANDOM = 'random',
  RATIO = 'ratio',
}

/** 策略优先级 */
export enum StrategyPriority {
  P0 = 'P0',
  P1 = 'P1',
  P2 = 'P2',
}

/** 策略动作类型 */
export enum StrategyActionType {
  FIX = 'fix',
  ENHANCE = 'enhance',
  MONITOR = 'monitor',
}

/** 通用状态 */
export enum CommonStatus {
  PENDING = 'pending',
  ACCEPTED = 'accepted',
  REJECTED = 'rejected',
}

// ============================================================
// 业务错误码
// ============================================================

export const ErrorCodes = {
  SUCCESS: 0,
  UNKNOWN_ERROR: 10000,
  VALIDATION_ERROR: 10001,
  NOT_FOUND: 10002,

  INDICATOR_NOT_FOUND: 20101,
  INDICATOR_DUPLICATE: 20102,
  MINING_IN_PROGRESS: 20103,

  DATASET_NOT_FOUND: 30101,
  FILE_UPLOAD_FAILED: 30102,
  LINEAGE_BUILD_FAILED: 30103,

  EVAL_CONFIG_NOT_FOUND: 40101,
  EVAL_RUNNING: 40102,
  ATTRIBUTION_FAILED: 40103,
} as const

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes]

// ============================================================
// 治理标准体系相关类型
// ============================================================

export type TabKey = 'input-value' | 'input-risk' | 'output-risk' | 'output-culture'

export type IndicatorLevel = 1 | 2 | 3

export type MiningStatus = 'idle' | 'running' | 'done' | 'error'

/** 前端数据来源：Benchmark API / 本地 JSON 兜底 / 模拟数据 / 未加载 */
export type DataSource =
  | 'api'
  | 'local'
  | 'real'
  | 'benchmark'
  | 'benchmark_static'
  | 'backend_snapshot'
  | 'static'
  | 'corpus_static'
  | 'culture_assessment_static'
  | 'demo_fixture'
  | 'unavailable'
  | 'mock'
  | 'error'
  | ''

// ============================================================
// 动态 Benchmark / 多 Agent 接入相关类型
// ============================================================

export type BenchmarkTaskStatus =
  | 'pending'
  | 'validating'
  | 'running'
  | 'packaging'
  | 'completed'
  | 'failed'
  | 'rejected'

export type BenchmarkAgentId =
  | 'topic2-autobench'
  | 'topic3-difficulty-generation'
  | 'topic1-value-qa'
  | 'topic3-cultural-corpus-generation'
  | 'topic3-risk-benchmark-generation'

export type BenchmarkLanguage = 'zh' | 'en' | 'zh+en'

export interface BenchmarkViewAssetsPayload {
  focusAssetId?: string
  sourceTaskId?: string
  sourceAgentId?: BenchmarkAgentId
  from?: 'task_runner' | 'evaluation_panel'
}

export interface BenchmarkAssetFocusRequest {
  focusAssetId?: string
  requestedAt: number
  sourceTaskId?: string
  sourceAgentId?: BenchmarkAgentId
}

export interface Topic2BenchmarkTaskCreatePayload {
  agent_id: 'topic2-autobench'
  mode: 'live_run'
  parameters: {
    l1: string[]
    moderators: string[]
    language: BenchmarkLanguage
    budget: number
    sampling_seed: number
    model: string
    max_turns: number
    scale?: 'trial' | 'standard' | 'large'
    rewrite_strength?: 'light' | 'strong'
  }
}

export interface Topic3DifficultyTaskCreatePayload {
  agent_id: 'topic3-difficulty-generation'
  mode: 'live_run'
  parameters: {
    language: BenchmarkLanguage
    total_sample_count: number
    difficulty_preset: 'demo_small' | 'balanced_h1h4' | 'hard_h3h4' | 'custom'
    difficulty_counts: {
      H1: number
      H2: number
      H3: number
      H4: number
    }
    seed_dataset: string
    risk_categories: string[]
    generation_model: string
    guard_model: string
    scale?: 'trial' | 'standard' | 'large'
  }
}

export interface Topic1ValueQaTaskCreatePayload {
  agent_id: 'topic1-value-qa'
  mode: 'live_run'
  parameters: {
    generation_mode: 'topic' | 'dimension'
    topic?: string
    topics?: string[]
    dimension?: string
    n_topics: number
    groups_per_topic: number
    /** Omit in standard mode; backend silently resolves local corpus vs online. */
    retrieval_mode?: 'local_corpus' | 'online_baike'
    corpus_jsonl?: string
    language: 'zh' | 'zh-CN' | 'en' | 'zh+en'
    seed?: number
    model?: string
    run_qc: false
    run_trace: false
    /** Standard-mode workbench scale; stored for evalset meta, optional for expert. */
    scale?: 'trial' | 'standard' | 'large'
  }
}

export interface Topic3CulturalCorpusTaskCreatePayload {
  agent_id: 'topic3-cultural-corpus-generation'
  mode: 'live_run'
  parameters: {
    language: BenchmarkLanguage
    total_sample_count: number
    batch_size: number
    difficulty_counts: {
      L1: number
      L2: number
      L3: number
    }
    allowed_ethnic_groups: string[]
    allowed_dimensions: string[]
    random_seed: number
    scale?: 'trial' | 'standard' | 'large'
    structure_band?: 'explicit' | 'mixed' | 'implicit_heavy'
  }
}

export interface Topic3RiskTaskCreatePayload {
  agent_id: 'topic3-risk-benchmark-generation'
  mode: 'live_run'
  parameters: {
    scale: 'trial'
    target_per_kind: 5
    workers: number
  }
}

export type BenchmarkTaskCreatePayload =
  | Topic2BenchmarkTaskCreatePayload
  | Topic3DifficultyTaskCreatePayload
  | Topic1ValueQaTaskCreatePayload
  | Topic3CulturalCorpusTaskCreatePayload
  | Topic3RiskTaskCreatePayload

export interface BenchmarkTask {
  task_id: string
  agent_id: string
  mode: string
  status: BenchmarkTaskStatus
  parameters: Record<string, unknown>
  upstream_base_url?: string | null
  upstream_contract?: string | null
  source_repo?: string | null
  source_commit?: string | null
  adapter_version?: string | null
  error_message?: string | null
  asset_id?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface BenchmarkTaskLogItem {
  id: number
  task_id: string
  event_type: string
  stage?: string | null
  message?: string | null
  turn?: number | null
  raw_json: Record<string, unknown>
  created_at?: string | null
}

export interface BenchmarkTaskLogsResponse {
  task_id: string
  logs: BenchmarkTaskLogItem[]
}

export interface BenchmarkArtifactItem {
  asset_id: string
  task_id: string
  source_mode: string
  name: string
  manifest: Record<string, unknown>
  artifact_sha256: string
  created_at?: string | null
}

export interface BenchmarkArtifactsResponse {
  task_id: string
  artifacts: BenchmarkArtifactItem[]
}

export interface BenchmarkAssetRegistryResponse {
  assets: BenchmarkArtifactItem[]
}

export type BenchmarkTopic3RiskAssetStatus = 'current' | 'historical' | 'unregistered'

export interface BenchmarkTopic3RiskAssetIdentity {
  series_id: string
  asset_id: string
  asset_version: string | null
  asset_sha256: string
  asset_status: BenchmarkTopic3RiskAssetStatus
}

export interface BenchmarkTopic3RiskAssetVersion extends BenchmarkTopic3RiskAssetIdentity {
  series_name: string
  name: string
  sample_count: number | null
  safe_count: number | null
  risk_count: number | null
  risk_level_distribution: Record<string, number>
  language_distribution: Record<string, number>
  category_distribution: Record<string, number>
  evaluation_status: string
  registered_at?: string | null
}

export interface BenchmarkTopic3RiskAssetVersionsResponse {
  series_id: string
  series_name: string
  current_asset_id: string | null
  versions: BenchmarkTopic3RiskAssetVersion[]
}

export interface BenchmarkTopic3RiskComparisonSide {
  run_id: string | null
  model_id: string | null
  display_name: string | null
  primary_metrics: Record<string, number | null>
  supporting_metrics: Record<string, number | null>
}

export interface BenchmarkTopic3RiskComparison {
  available: boolean
  same_version: boolean
  primary: BenchmarkTopic3RiskComparisonSide | null
  baseline: BenchmarkTopic3RiskComparisonSide | null
  message: string
}

export interface BenchmarkTopic3RiskEvaluationMetricDef {
  key: string
  display_name: string
}

export interface BenchmarkTopic3RiskEvaluationResult {
  run_id: string
  model_id: string
  model_name: string
  model_version: string
  model_run_id: string
  role: string
  display_name: string
  eval_mode: string
  result_source: string
  evaluated_at: string
  predictions_count: number
  primary_metrics: Record<string, number | null>
  supporting_metrics: Record<string, number | null>
  per_category_metrics: Record<string, unknown>
}

export interface BenchmarkTopic3RiskEvaluationSummary {
  available: boolean
  asset_id: string
  asset_name: string
  eval_mode: string
  result_source: string
  status: string
  source_label: string
  primary_metrics: BenchmarkTopic3RiskEvaluationMetricDef[]
  results: BenchmarkTopic3RiskEvaluationResult[]
  comparison?: BenchmarkTopic3RiskComparison
  excluded_run_ids?: string[]
  live_eval: Record<string, unknown>
  series_id?: string
  asset_version?: string | null
  asset_sha256?: string
  asset_status?: BenchmarkTopic3RiskAssetStatus
}

export interface BenchmarkLiveRunMetricBucket {
  accuracy?: number | null
  precision?: number | null
  recall?: number | null
  f1?: number | null
  fpr?: number | null
  fnr?: number | null
  n_samples?: number | null
  n_errors?: number | null
}

export interface BenchmarkLiveRunModeratorSummary {
  name: string
  total_samples: number
  accuracy?: number | null
  precision?: number | null
  recall?: number | null
  f1?: number | null
  fpr?: number | null
  fnr?: number | null
  n_errors?: number | null
  avg_latency_ms?: number | null
  eval_time_seconds?: number | null
  per_vector: Record<string, BenchmarkLiveRunMetricBucket>
  per_category: Record<string, BenchmarkLiveRunMetricBucket>
}

export interface BenchmarkLiveRunResultSummary {
  available: boolean
  source: string
  setting?: string
  timestamp?: string
  moderators_tested?: number
  total_samples?: number
  moderators: BenchmarkLiveRunModeratorSummary[]
}

export interface BenchmarkLiveRunPreviewSample {
  id: string
  seedbank_id: string
  label: string
  harm_category_l1: string
  harm_category_l2: string
  attack_vector: string
  difficulty?: number | null
  language: string
  origin: string
  status: string
  test_count: number
  moderator_fooled: string[]
  query_preview: string
}

export interface BenchmarkLiveRunSamplePoolSummary {
  available: boolean
  total: number
  label_distribution: Record<string, number>
  l1_distribution: Record<string, number>
  l2_distribution: Record<string, number>
  attack_vector_distribution: Record<string, number>
  language_distribution: Record<string, number>
  origin_distribution: Record<string, number>
  fooled_count: number
  preview_samples: BenchmarkLiveRunPreviewSample[]
}

export interface BenchmarkLiveRunLifecycleSample {
  sample_id: string
  stage: string
  strategy: string
  difficulty?: number | null
  moderator_results: Record<string, unknown>
  query_preview: string
}

export interface BenchmarkLiveRunEventTimelineItem {
  id: number
  event_type: string
  stage?: string | null
  message?: string | null
  turn?: number | null
  tool_name: string
  created_at?: string | null
}

export interface BenchmarkLiveRunSummaryResponse {
  asset_id: string
  task_id: string
  agent_id: string
  source_mode: string
  name: string
  created_at?: string | null
  source_commit: string
  artifact_sha256: string
  parameters: Record<string, unknown>
  artifact_files: Record<string, boolean>
  event_counts: Record<string, number>
  tool_counts: Record<string, number>
  event_timeline: BenchmarkLiveRunEventTimelineItem[]
  result_summary: BenchmarkLiveRunResultSummary
  sample_pool_summary: BenchmarkLiveRunSamplePoolSummary
  lifecycle_samples: BenchmarkLiveRunLifecycleSample[]
  report: {
    available: boolean
    source: string
    markdown: string
  }
  warnings: string[]
  topic1_value_qa_summary?: BenchmarkTopic1ValueQaLiveRunSummary
  topic3_difficulty_summary?: BenchmarkTopic3DifficultyLiveRunSummary
  topic3_cultural_summary?: BenchmarkTopic3CulturalLiveRunSummary
}

export interface BenchmarkTopic1ValueQaLevelPreview {
  sample_id: string
  question: string
  answer: string
}

export interface BenchmarkTopic1ValueQaGroupPreview {
  group_id: string
  topic: string
  primary_dimension: string
  secondary_dimension: string
  levels: Record<'high' | 'medium' | 'low', BenchmarkTopic1ValueQaLevelPreview>
}

export interface BenchmarkTopic1ValueQaLiveRunSummary {
  available: boolean
  sample_limit: number
  generation_mode: string
  topic: string
  dimension: string
  selected_topics: string[]
  requested_group_count: number
  generated_group_count: number
  sample_count: number
  quality_level_distribution: Record<string, number>
  retrieval_mode: string
  corpus_jsonl: string
  language: string
  model: string
  llm_api_base?: string
  seed: number
  validation: Record<string, unknown>
  artifact_files: Record<string, boolean>
  sample_groups: BenchmarkTopic1ValueQaGroupPreview[]
  worker_log: string
  readiness: string
  readiness_note: string
}

export interface BenchmarkTopic3DifficultySpan {
  text: string
  start: number
  end: number
}

export interface BenchmarkTopic3DifficultySourceTrace {
  id: string
  safety_label: string
  risk_category: string
  risk_level: string
  source_trace: string
}

export interface BenchmarkTopic3DifficultySample {
  sample_id: string
  difficulty_level: string
  difficulty_strategy: string
  harmful_count: number
  harmless_count: number
  interleaving: boolean
  risk_category: string
  risk_category_key: string
  risk_level: string
  bridge_review_label: string
  bridge_review_reason: string
  coherence_label: string
  coherence_reason: string
  final_guard_label: string
  final_guard_categories: string[]
  harmful_spans: BenchmarkTopic3DifficultySpan[]
  harmless_spans: BenchmarkTopic3DifficultySpan[]
  edited_input: string
  edited_input_preview: string
  bridge_texts: string[]
  source_boundary_edits: unknown[]
  source_trace: BenchmarkTopic3DifficultySourceTrace[]
}

export interface BenchmarkTopic3DifficultyLiveRunSummary {
  available: boolean
  total: number
  sample_limit: number
  status: string
  generated: number
  requested: number
  batch_size: number
  random_seed: number
  sample_mode: string
  metric_targets: string[]
  difficulty_counts: Record<string, number>
  configured_difficulty_counts: Record<string, unknown>
  bridge_review_counts: Record<string, number>
  final_guard_counts: Record<string, number>
  risk_category_counts: Record<string, number>
  risk_level_counts: Record<string, number>
  discard_counts: Record<string, number>
  seed_pool_counts: Record<string, number>
  quality_reports: Record<string, unknown>[]
  worker_log: string
  samples: BenchmarkTopic3DifficultySample[]
  readiness: string
  readiness_note: string
  manifest_summary: Record<string, string>
}

export interface BenchmarkTopic3CulturalSamplePreview {
  sample_id: string
  ethnic_group: string
  difficulty_level: string
  background_type: string
  persona: string
  query_type: string
  prompt_preview: string
}

export interface BenchmarkTopic3CulturalLiveRunSummary {
  available: boolean
  sample_limit: number
  requested: number
  generated: number
  sample_count: number
  scale: string
  structure_band: string
  language: string
  batch_size: number
  random_seed: number
  difficulty_counts: Record<string, number>
  allowed_ethnic_groups: string[]
  difficulty_distribution: Record<string, number>
  ethnic_distribution: Record<string, number>
  background_type_distribution: Record<string, number>
  persona_distribution: Record<string, number>
  query_type_distribution: Record<string, number>
  review_passed_count: number
  review_passed_rate: number
  artifact_files: Record<string, boolean>
  sample_previews: BenchmarkTopic3CulturalSamplePreview[]
  readiness: string
  readiness_note: string
}

export interface BenchmarkPrerunImportPayload {
  archive_path: string
}

export interface BenchmarkPrerunImportResponse {
  asset: BenchmarkArtifactItem
}

export interface BenchmarkDatasetSnapshotImportPayload {
  archive_path: string
}

export interface BenchmarkDatasetSnapshotImportResponse {
  asset: BenchmarkArtifactItem
  idempotent: boolean
}

export interface BenchmarkCbrneSampleResourceRef {
  kind: string
  asset_id: string
  sample_id: string
}

export interface BenchmarkCbrneQueryFilters {
  label?: string
  cbrne_category?: string
  source?: string
  exposure_tier?: string
  difficulty_min?: number
  difficulty_max?: number
}

export interface BenchmarkCbrneSampleSummaryItem {
  sample_id: string
  label: string
  cbrne_category: string
  source: string
  exposure_tier: string
  evaluator_relative_difficulty: number
  text_excerpt: string
  resource_ref: BenchmarkCbrneSampleResourceRef
}

export interface BenchmarkCbrneSamplesQueryResponse {
  asset_id: string
  asset_version: string
  record_version: string
  query: BenchmarkCbrneQueryFilters
  total: number
  limit: number
  offset: number
  distributions: Record<string, unknown>
  samples: BenchmarkCbrneSampleSummaryItem[]
}

export interface BenchmarkCbrneSampleAccessEvent {
  event_id: string
  asset_id: string
  asset_version: string
  sample_id: string
  action_type: string
  accessed_at: string
  disclosure_request_id: string | null
}

export interface BenchmarkCbrneSampleRefItem {
  sample_id: string
  label: string
  cbrne_category: string
  source: string
  exposure_tier: string
  evaluator_relative_difficulty: number
  text_preview: string
}

export interface BenchmarkCbrneSampleRefsResponse {
  asset_id: string
  asset_version: string
  total: number
  limit: number
  offset: number
  items: BenchmarkCbrneSampleRefItem[]
}

/**
 * Exact masked sample identity for `/benchmark/assets/{asset}/samples/{sample}`.
 * Deliberately excludes full text, raw fields, and access events.
 */
export interface BenchmarkCbrneSampleRefResponse extends BenchmarkCbrneSampleRefItem {
  asset_id: string
  asset_version: string
}

export interface BenchmarkCbrneSampleDetail {
  asset_id: string
  asset_version: string
  sample_id: string
  full_text: string
  raw: Record<string, unknown>
  platform_normalized: Record<string, unknown>
  access_event: BenchmarkCbrneSampleAccessEvent
}

export interface BenchmarkCbrneSampleDisclosureRequest {
  disclosureRequestId: string
}

export type BenchmarkCbrneSampleDisclosure = BenchmarkCbrneSampleDetail

export interface BenchmarkTopic2ModeratorResult {
  label?: string | null
  confidence?: number | null
  strength?: number | null
}

export interface BenchmarkTopic2RewriteQa {
  passed: boolean
  semantic_ok: boolean
  format_ok: boolean
  reason?: string | null
  source?: string | null
}

export interface BenchmarkTopic2PrerunSampleItem {
  sample_id: string
  difficulty_level: string
  query_preview: string
  query: string
  rewrite_rounds?: number | null
  strategy?: string | null
  strategy_chain: string[]
  attack_vector?: string | null
  language?: string | null
  label?: string | null
  rewrite_qa: BenchmarkTopic2RewriteQa
  moderator_results: Record<string, BenchmarkTopic2ModeratorResult>
}

export interface BenchmarkTopic2PrerunPairItem {
  pair_id: string
  seedbank_id?: string | null
  root_seed_id?: string | null
  source_row_id?: string | null
  harm_category_l1?: string | null
  harm_category_l2?: string | null
  simple?: BenchmarkTopic2PrerunSampleItem | null
  hard?: BenchmarkTopic2PrerunSampleItem | null
}

export interface BenchmarkTopic2PrerunPairsResponse {
  asset_id: string
  total: number
  limit: number
  offset: number
  moderators: string[]
  pairs: BenchmarkTopic2PrerunPairItem[]
}

export interface BenchmarkTopic1ValueQaLevelPreview {
  sample_id: string
  question_preview: string
  answer_preview: string
  qc_status: string
}

export interface BenchmarkTopic1ValueQaTraceIssue {
  scope?: string | null
  span?: string | null
  type?: string | null
  issue_type?: string | null
  reason?: string | null
  rationale?: string | null
  [key: string]: unknown
}

export interface BenchmarkTopic1ValueQaLevelDetail {
  sample_id: string
  question: string
  answer: string
  quality_level: 'high' | 'medium' | 'low'
  source_reference: Record<string, unknown>
  missing_annotation_count: number
  prompt_snapshot: string
  manual_marked_at?: string | null
  qc_status: string
  trace_predicted_level?: string | null
  trace_true_label?: string | null
  trace_is_consistent?: boolean | null
  trace_match_status?: string | null
  trace_issue_count?: number | null
  trace_low_issue_spans: BenchmarkTopic1ValueQaTraceIssue[]
}

export interface BenchmarkTopic1ValueQaGroupItem {
  group_id: string
  asset_id: string
  topic: string
  primary_dimension: string
  secondary_dimension: string
  qc_status: string
  levels: Record<'high' | 'medium' | 'low', BenchmarkTopic1ValueQaLevelPreview>
}

export interface BenchmarkTopic1ValueQaGroupsResponse {
  asset_id: string
  total: number
  limit: number
  offset: number
  groups: BenchmarkTopic1ValueQaGroupItem[]
}

export interface BenchmarkTopic1ValueQaGroupDetail {
  group_id: string
  asset_id: string
  topic: string
  primary_dimension: string
  secondary_dimension: string
  qc_status: string
  levels: Record<'high' | 'medium' | 'low', BenchmarkTopic1ValueQaLevelDetail>
}

export interface BenchmarkTopic1ValueQaRecheckSummary {
  status: string
  scope: string
  sample_count: number
  prediction_count: number
  coverage_ratio: number
  correct_count: number
  mismatch_count: number
  accuracy: number
  gold_distribution: Record<string, number>
  true_label_distribution: Record<string, number>
  predicted_label_distribution: Record<string, number>
  low_issue_sample_count: number
  issue_count: number
  issue_type_distribution: Record<string, number>
  run_metadata?: Record<string, unknown>
  source_schema?: string | null
  source_file?: string | null
  is_formal_model_eval: boolean
}

export interface BenchmarkTopic3RiskSampleItem {
  sample_id: string
  asset_id: string
  index: number | string
  culture: string
  language: string
  prompt_preview: string
  response_preview: string
  response_safetype: string
  risk_category: string
  risk_category_code: string
  risk_sub_category: string
  risk_level_id: string
  safe_type: string
  safe_mode: string
  label_reason_preview: string
  response_text_source: string
  source_index: number | string
}

export interface BenchmarkTopic3RiskSamplesResponse {
  series_id?: string
  asset_id: string
  asset_version?: string | null
  asset_sha256?: string
  asset_status?: BenchmarkTopic3RiskAssetStatus
  total: number
  limit: number
  offset: number
  samples: BenchmarkTopic3RiskSampleItem[]
}

export interface BenchmarkRiskCategory {
  code: string
  name: string
}

export interface BenchmarkTopic3RiskTaxonomyResponse {
  schema: string
  version: string
  source: string
  categories: BenchmarkRiskCategory[]
}

export interface BenchmarkTopic3RiskIntegrityWarning {
  code: string
  message: string
}

export interface BenchmarkTopic3RiskSampleDetail {
  sample_id: string
  asset_id: string
  index: number | string
  version: string
  culture: string
  language: string
  prompt: string
  response: string
  response_safetype: string
  risk_category: string
  risk_category_code: string
  risk_sub_category: string
  risk_level_id: string
  label_source: string
  response_text_original: string
  response_text_source: string
  source_index: number | string
  safe_type: string
  safe_mode: string
  label_reason: string
  label_reason_status?: string
  integrity_warnings?: BenchmarkTopic3RiskIntegrityWarning[]
  label_reason_usable_for_automatic_explanation?: boolean
  warning_note?: string | null
  asset_version?: string | null
  asset_sha256?: string
}

export interface BenchmarkTopic3CulturalSampleItem {
  sample_id: string
  ethnic_group: string
  difficulty_level: string
  background_type: string
  persona: string
  query_type: string
  review_passed: boolean
  prompt_preview: string
}

export interface BenchmarkTopic3CulturalSamplesResponse {
  asset_id: string
  total: number
  limit: number
  offset: number
  samples: BenchmarkTopic3CulturalSampleItem[]
}

export interface BenchmarkTopic3CulturalSampleDetail {
  sample_id: string
  prompt: string
  background: string
  user_query: string
  expected_answer: string
  ethnic_group: string
  difficulty_level: string
  background_type: string
  persona: string
  query_type: string
  cultural_knowledge_points: string[]
  rubric: {
    must_have: string[]
    penalty: string[]
  }
  review: {
    overall_passed: boolean
    cultural_accuracy?: number | null
    reason?: string
    consistency?: string
  }
  run_id: string
  batch_id: string
}

export interface BenchmarkTopic3CulturalSummary {
  asset_id: string
  sample_count: number
  difficulty_distribution: Record<string, number>
  ethnic_distribution: Record<string, number>
  background_type_distribution: Record<string, number>
  persona_distribution: Record<string, number>
  query_type_distribution: Record<string, number>
  review_passed_count: number
  review_passed_rate: number
  model_eval_status: string
}

export type Topic2ProxySource = 'upstream' | 'fallback'

export interface Topic2OptionsResponse {
  source: Topic2ProxySource
  upstream_base_url?: string
  languages: string[]
  moderators: unknown[]
  agent_models?: unknown[]
  attack_vectors?: unknown[]
  capabilities?: unknown[]
}

export interface Topic1ValueQaTopicGroup {
  dimension: string
  primary_dimension: string
  topics: string[]
}

export interface Topic1ValueQaTopicsResponse {
  version: string
  topic_count: number
  default_topic: string
  groups: Topic1ValueQaTopicGroup[]
  topics: string[]
  source: 'keywords_5001' | 'project1_yaml' | 'unavailable'
}

export interface Topic2SeedbankStatsResponse {
  source: Topic2ProxySource
  static_total: number
  dynbench_total: number
  by_l1: unknown[] | Record<string, unknown>
  by_l2: unknown[] | Record<string, unknown>
  seed_types: unknown[] | Record<string, unknown>
}

export interface Topic1RuntimeResponse {
  runtime_ready: boolean
  runtime_source: 'project1_env' | 'missing'
  project_root: string
  llm_runtime: {
    provider: string
    model: string
    api_base: string
    api_base_origin: string
  }
  llm_status: {
    status: 'reachable' | 'not_configured' | 'unreachable'
    status_code?: number
    message?: string
  }
}

export interface Topic2AgentRuntimeSummary {
  submitted_model_id: string
  provider: string
  provider_label: string
  credential_policy: string
  uses_deepseek_fallback: boolean
  anthropic_compatible: boolean
  base_url_origin: string
}

export interface Topic2RuntimeResponse {
  upstream_ready: boolean
  upstream_base_url: string
  upstream_health: {
    service: string
    status: string
    version: string
  }
  agent_runtime?: Topic2AgentRuntimeSummary | null
  options_source: Topic2ProxySource
  seedbank_stats_source: Topic2ProxySource
  capabilities: Record<string, string>
  limits: {
    budget_min: number
    budget_max: number
    max_turns_max: number
  }
}

/** 单样本推理步骤 */
export interface InferProgressStep {
  name: string
  status: 'pending' | 'running' | 'done' | 'error'
  detail?: string
}

export interface Indicator {
  id: string
  tab: TabKey
  level: IndicatorLevel
  parentId: string | null
  name: string
  description: string
  weight: number
  status: 'draft' | 'reviewed' | 'published'
  createdAt: string
  updatedAt: string
}

// ============================================================
// 输入语料治理相关类型
// ============================================================

export interface Dataset {
  id: string
  name: string
  type: 'culture' | 'science'
  subType?: DatasetSubType
  description: string
  recordCount: number
  language?: string
  riskLevel: 'HIGH' | 'MEDIUM' | 'LOW'
  createdAt: string
  updatedAt: string
}

// ============================================================
// Step 1 — 数据资产三态模型
// ============================================================

/** 数据资产就绪状态 */
export type AssetState = 'evaluable' | 'mapped' | 'import'

/** 数据资产统一接口（可直接评测 / 待映射 / 待导入） */
export interface DataAsset {
  id: string
  name: string
  assetState: AssetState
  /** 数据场景：AI4Sci / 文化多样性内容 / 风险内容 / 通用安全基线 */
  scenario: string
  /** 数据来源标签 */
  source: string
  /** 数据资产进入的输出治理轨道 */
  track?: OutputTrack
  /** 已具备对应轨道的数据读取能力，可在 Step 1 选择 */
  selectable?: boolean
  description: string
  /** 仅 evaluable 有值 */
  datasetId?: string
  task?: string
  modelId?: string
  sampleCount?: number
  resultVersion?: string
  runName?: string
  language?: string
  hasStaticResult?: boolean
  canDynamicEval?: boolean
  /** 待映射/待导入资产的详情 */
  detailBlocks?: AssetDetailBlock[]
  existingFields?: string[]
  gaps?: string[]
  suggestedMapping?: Record<string, string>
  suggestedAction?: string
}

/** 资产详情信息块 */
export interface AssetDetailBlock {
  title: string
  kv?: [string, string][]
  tags?: string[]
  gaps?: string[]
}

export interface LineageNode {
  id: string
  datasetId: string
  label: string
  type: 'source' | 'transform' | 'output'
  metadata: Record<string, unknown>
}

export interface LineageEdge {
  id: string
  sourceNodeId: string
  targetNodeId: string
  relationType: string
}

export interface AssessmentRecord {
  id: string
  datasetId: string
  track: 'value' | 'risk'
  indicatorId: string
  score: number
  detail: Record<string, unknown>
  createdAt: string
}

// ============================================================
// 输出内容治理相关类型
// ============================================================

export interface EvalConfig {
  id: string
  name: string
  modelName: string
  promptTemplate: string
  parameters: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface EvalResult {
  id: string
  configId: string
  datasetId: string
  score: number
  dimensionScores: Record<string, number>
  detail: Record<string, unknown>
  createdAt: string
}

export interface Attribution {
  id: string
  evalResultId: string
  riskType: string
  rootCause: string
  evidence: string
  suggestion: string
}

export interface Strategy {
  id: string
  attributionId: string
  actionType: 'fix' | 'enhance' | 'monitor'
  description: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  status: 'pending' | 'accepted' | 'rejected'
}

// ============================================================
// 输出内容治理 — 页面专属 UI 类型
// ============================================================

/** 已选数据集（含采样配置） */
export interface SelectedDataset {
  datasetId: string
  name: string
  recordCount: number
  riskLevel: RiskLevel
  subType: string
  language: string
  track: OutputTrack
  dataSource?: DataSource
  resultVersion?: string
  runName?: string
  cultureCorpusFilters?: CultureCorpusFilters
  samplingMethod: SamplingMethod
  sampleSize: number
}

export interface CultureCorpusFilters {
  runIds: string[]
  ethnicGroups: string[]
  difficultyLevels: string[]
}

/** 维度筛选条目（多样性） */
export interface DiversityDimension {
  key: string
  label: string
  category: 'ai4sci' | 'culture'
  selected: boolean
}

/** 维度筛选条目（风险） */
export interface RiskDimension {
  key: string
  label: string
  code?: string
  category: 'ai4sci' | 'culture'
  level: RiskLevel
  selected: boolean
  definition?: string
  subcategories?: Array<{
    key: string
    label: string
    level?: string
  }>
}

/** 自定义规则 */
export interface CustomRule {
  id: string
  text: string
}

/** 雷达图数据 */
export interface RadarChartData {
  dimensions: string[]
  series: RadarSeriesData[]
}

export interface RadarSeriesData {
  name: string
  values: number[]
  fill: string
  stroke: string
}

/** 评估样例 */
export interface EvalSample {
  id: string
  text: string
  dimensionScores: Record<string, DiversityLevel | RiskLevel>
  overallLevel: DiversityLevel | RiskLevel
  overallScore: number
  summary: string
  /** 多样性样本口径：生成质量评分或参考答案审核 */
  evaluationKind?: 'generation_scores' | 'reference_review'
  /** 文化语料标注：民族/文化群体 */
  ethnic?: string
  /** 文化语料标注：主题或分类 */
  category?: string
  /** 文化语料标注：难度 */
  difficultyLevel?: string
  /** 文化语料预跑批次 ID */
  runId?: string
  /** 参考答案 */
  expectedAnswer?: string
  /** Cultural Gen 生成回答 */
  generatedAnswer?: string
  /** 文化知识依据 */
  knowledge?: string
  /** 背景类型：显式/隐式文化语境 */
  bgType?: 'explicit' | 'implicit'
  /** 文化线索 */
  cues?: string[]
  /** 三维原始分：文化适配 */
  cultureScore?: number
  /** 三维原始分：语义质量 */
  semanticScore?: number
  /** 三维原始分：完整度 */
  integrityScore?: number
  /** 反例或错误示例 */
  wrongExample?: string
  /** 修正建议 */
  fixSuggestion?: string
  /** 改进项 */
  improveItems?: string[]
  /** 评分规则：必须覆盖要点 */
  mustHave?: string[]
  /** 评分规则：扣分项 */
  penalty?: string[]
  /** 文化准确性审核分 */
  reviewAccuracy?: number | null
  /** 所属数据集 ID */
  datasetId?: string
  /** 所属数据集名称 */
  datasetName?: string
  /** Gold 标注：有害/安全 (1/0) */
  goldBinaryLabel?: 0 | 1
  /** 模型预测：有害/安全 (1/0) */
  predBinaryLabel?: 0 | 1
  /** Gold 标注：风险类别名称 */
  goldCategory?: string
  /** Gold 标注：风险类别编码 (C01-C17) */
  goldCategoryCode?: string
  /** 模型预测：风险类别名称 */
  predCategory?: string
  /** 模型预测：风险类别编码 (C01-C17) */
  predCategoryCode?: string
  /** Gold 标注：风险等级 */
  goldLevel?: RiskLevel
  /** 模型预测：风险等级 */
  predLevel?: RiskLevel
  /** 预测是否正确（binary 标签匹配） */
  isCorrect?: boolean
  /** 风险类别预测是否正确 */
  isCategoryCorrect?: boolean
}

/** 单个数据集的评估指标 */
export interface DatasetEvalMetric {
  datasetId: string
  datasetName: string
  sampleCount: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  riskClassAcc: number
  riskRecall: number
  fpr: number
  perCategory: Record<string, { accuracy: number; f1: number; count: number }>
}

/** 分组聚合指标（按 culture/language/risk_category_code/risk_level_id 等维度） */
export interface GroupedMetrics {
  dimension: string
  groups: Record<string, GroupedMetricItem>
}

export interface GroupedMetricItem {
  sampleCount: number
  accuracy: number
  f1: number
  riskClassAcc: number
  riskRecall: number
}

/** 多数据集雷达图数据（ECharts 兼容） */
export interface MultiDatasetRadarData {
  dimensions: string[]
  dimensionLabels?: Record<string, string>
  selectedMetric: string
  series: MultiDatasetRadarSeries[]
}

export interface MultiDatasetRadarSeries {
  datasetId: string
  datasetName: string
  values: number[]
  color?: string
}

/** 合规编辑样本（useComplianceData 加载的 JSON 原始格式） */
export interface ComplianceSample {
  index: number
  language: string
  prompt: string
  text: string
  categories: string[]
  risk_category: string
  risk_category_id: string
  risk_level: string
  source_id: string
  source_index: number
  difficulty_level: string
  harmful_spans: Array<{ start: number; end: number }>
  harmless_spans: Array<{ start: number; end: number }>
  edited_text: string
  translated_input_zh: string
  edited_text_zh: string
  edits: Array<{
    original: string
    replacement: string
    reason: string
    start?: number
    end?: number
  }>
  quality: {
    pre_safety_label: string
    post_safety_label: string
    risk_reduced: boolean
    needs_manual_review: boolean
    unchanged_non_risk_ratio: number
  }
  disposition: string
  elapsed_seconds: number
}

/** 修正样例 */
export interface CorrectionSample {
  id: string
  originalText: string
  correctedText: string
  highlightedMarks: HighlightMark[]
  dimensionScores: Record<string, string>
  overallLevel: string
  tags: string[]
  status: CorrectionStatus
  operator: string
  operateTime: string
}

export interface HighlightMark {
  text: string
  level: 'high' | 'medium' | 'low'
}

/** 归因节点 */
export interface AttributionNode {
  id: string
  signals: Record<string, DiversityLevel | RiskLevel>
  chain: string
  reasonPath: string
  weight: number
  /** 预测文本（全文） */
  text?: string
  /** 分句列表 */
  sentences?: string[]
  /** 含风险关键词的句子索引 */
  riskSentenceIndices?: number[]
  /** 风险子类证据描述 */
  riskEvidence?: string[]
  /** 综合等级 */
  overall?: RiskLevel
  /** 真实标注类别 */
  goldCategories?: string[]
  /** 预测类别 */
  predCategories?: string[]
}

/** 策略建议 */
export interface StrategyRecommendation {
  id: string
  priority: StrategyPriority
  title: string
  description: string
  trainingMethod: string
  trainingDataCount: string
  expectedDuration: string
  targetMetric: string
}

/** 指标对比 */
export interface ComparisonMetric {
  label: string
  before: string | number
  after: string | number
  improvement: string
}

/** 训练历史记录 */
export interface TrainingHistory {
  time: string
  strategyType: string
  scene: string
  status: string
}

/** 评估历史记录 */
export interface EvalHistory {
  time: string
  scene: string
  riskDistribution: string
  score: string
}

/** 修正历史记录 */
export interface CorrectionHistory {
  time: string
  correctionType: string
  scene: string
  status: string
}

// ============================================================
// 前端专属 UI 类型
// ============================================================

export type GovernanceDomainKey = 'input' | 'output'

export type GovernanceMessageKind =
  | 'text'
  | 'clarify'
  | 'boundary'
  | 'value_corpus_overview'
  | 'value_qa_search'
  | 'value_qa_group_detail'
  | 'topic1_corpus_tool_catalog'
  | 'cbrne_dataset_discover'
  | 'cbrne_dataset_overview'
  | 'cbrne_dataset_search'
  | 'cbrne_dataset_full_text'
  | 'risk_corpus_overview'
  | 'risk_corpus_search'
  | 'risk_corpus_rescan'
  | 'governance_skill_plan'
  | 'risk_system_record_search'
  | 'risk_system_record_detail'
  | 'cultural_system_record_search'
  | 'cultural_system_record_detail'
  | 'cultural_prerun_review'
  | 'risk_prerun_review'

export type GovernanceRescanTaskStatus =
  | 'awaiting_confirmation'
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'completed'
  | 'completed_partial'
  | 'cancelled'
  | 'failed'
  | 'timeout'

/** Confirm enqueue ack (#63+); not a session detail. */
export interface GovernanceTaskConfirmAccepted {
  task_id: string
  run_id?: string
  status: 'queued' | string
}

export interface GovernanceSourceRef {
  ref_type: string
  ref_id: string
  name: string
  source_repo: string
  source_commit: string
}

export interface GovernanceValueQaLevel {
  sample_id: string
  question: string
  answer: string
  quality_level: string
  level_display: string
  level_score: string
  source_reference: Record<string, unknown>
  source_documents: Record<string, unknown>[]
  evidence: Record<string, unknown>[]
  value_annotations: Record<string, unknown>[]
  prompt_snapshot: string
}

export interface GovernanceValueQaGroupItem {
  group_id: string
  topic: string
  primary_dimension: string
  secondary_dimension: string
  levels: Record<string, GovernanceValueQaLevel>
}

export interface GovernanceValueQaSearchPayload {
  capability: 'value_qa_search'
  capability_version: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  total: number
  offset: number
  limit: number
  filters: Record<string, unknown>
  group_ids: string[]
  groups: GovernanceValueQaGroupItem[]
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceValueQaGroupDetailPayload {
  capability: 'value_qa_group_detail'
  capability_version: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  group_id: string
  topic: string
  primary_dimension: string
  secondary_dimension: string
  levels: Record<string, GovernanceValueQaLevel>
  groups: string[]
  group_index: number
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceValueCorpusOverviewPayload {
  capability: 'value_corpus_overview'
  capability_version: string
  source: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  sample_count: number
  group_count: number
  quality_level_distribution: Record<string, number>
  primary_dimension_distribution: Record<string, number>
  secondary_dimension_distribution: Record<string, number>
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceCbrneAssetItem {
  asset_id: string
  asset_name: string
  asset_version: string
  record_version: string
  is_current: boolean
  sample_count: number
  source_repo: string
  source_commit: string
  benchmark_href: string
  resource_ref: Record<string, unknown>
}

export interface GovernanceCbrneDiscoverPayload {
  capability: 'cbrne_dataset_discover'
  capability_version?: string
  available: boolean
  total: number
  records: GovernanceCbrneAssetItem[]
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceCbrneOverviewPayload {
  capability: 'cbrne_dataset_overview'
  capability_version?: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  asset_version: string
  record_version: string
  is_current: boolean
  sample_count: number
  label_counts: Record<string, number>
  cbrne_category_counts: Record<string, number>
  source_counts: Record<string, number>
  exposure_tier_counts: Record<string, number>
  evaluator_relative_difficulty_counts: Record<string, number>
  difficulty_definition?: string
  source_limitations?: string[]
  licence_notes?: string
  benchmark_href?: string | null
  resource_ref?: Record<string, unknown> | null
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceCbrneSampleSummary {
  sample_id: string
  label: string
  cbrne_category: string
  source: string
  exposure_tier: string
  evaluator_relative_difficulty: number
  text_excerpt: string
  resource_ref: Record<string, unknown>
  benchmark_href: string
}

export interface GovernanceCbrneSearchPayload {
  capability: 'cbrne_dataset_search'
  capability_version?: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  asset_version: string
  record_version: string
  query: Record<string, unknown>
  filters: Record<string, unknown>
  total: number
  limit: number
  offset: number
  distributions: Record<string, unknown>
  samples: GovernanceCbrneSampleSummary[]
  benchmark_href?: string | null
  resource_ref?: Record<string, unknown> | null
  source_refs: GovernanceSourceRef[]
  execute_actions?: unknown[]
}

export interface GovernanceCbrneFullTextPayload {
  capability: 'cbrne_dataset_full_text'
  capability_version?: string
  available: boolean
  disclosure: string
  asset_id?: string | null
  sample_id: string
  asset_version: string
  record_version: string
  benchmark_href?: string | null
  resource_ref?: Record<string, unknown> | null
  source_refs: GovernanceSourceRef[]
  full_text: string | null
}

export interface GovernanceRiskRecord {
  sample_id: string
  text: string
  reference_label: string
  original_label: string
  harm_category_L1: string
  harm_category_L2: string
  source: string
  is_risky: boolean
}

export interface GovernanceRiskCorpusOverviewPayload {
  capability: 'risk_corpus_overview'
  capability_version: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  sample_count: number
  reference_label_distribution: Record<string, number>
  harm_category_L1_distribution: Record<string, number>
  harm_category_L2_distribution: Record<string, number>
  source_distribution: Record<string, number>
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceRiskCorpusSearchPayload {
  capability: 'risk_corpus_search'
  capability_version: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  total: number
  offset: number
  limit: number
  filters: Record<string, unknown>
  records: GovernanceRiskRecord[]
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceRiskRescanSample {
  sample_id: string
  text: string
  reference_label: string
  harm_category_L1: string
  harm_category_L2: string
  source: string
}

export interface GovernanceRiskRescanPreviewPayload {
  capability: 'risk_corpus_rescan'
  capability_version: string
  phase: 'preview'
  task_id: string
  parent_task_id?: string | null
  status: GovernanceRescanTaskStatus
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  total_matched: number
  sample_count: number
  capped: boolean
  filters: Record<string, unknown>
  samples: GovernanceRiskRescanSample[]
  source_refs: GovernanceSourceRef[]
  /** #167: frozen asset identity + hash carried from the preview scope. */
  evaluation_object?: RiskRescanEvaluationObject
  /** #167: resolved evaluator (server default when the request omitted it). */
  evaluator?: string
  /** #167: initial export preference; a completed result then exposes a download. */
  export_requested?: boolean
}

export type GovernanceRiskRescanOutcomeStatus =
  | 'consistent'
  | 'inconsistent'
  | 'failed'
  | 'not_executed'

export interface GovernanceRiskRescanSampleOutcome {
  sample_id: string
  text: string
  reference_label: string
  detected_label: string
  status: GovernanceRiskRescanOutcomeStatus
  reason: string
  source?: string
  run_id?: string
  capability_version?: string
  completed_at?: string
}

export interface GovernanceRiskRescanSummary {
  consistent_count: number
  inconsistent_count: number
  failed_count: number
  not_executed_count?: number
}

/** #167: executor identity that produced the persisted predictions. */
export interface GovernanceRiskRescanExecutorIdentity {
  agent_id?: string
  source_commit?: string
  reproduce_command?: string
  [key: string]: unknown
}

/** #167: execution progress only — never an accuracy-style metric. */
export interface GovernanceRiskRescanExecutionSummary {
  executed_count: number
  failed_count: number
  not_executed_count: number
}

export interface GovernanceRiskRescanRunPayload {
  capability: 'risk_corpus_rescan'
  capability_version: string
  phase: 'result'
  task_id: string
  status: GovernanceRescanTaskStatus
  method: string
  available: boolean
  asset_id?: string | null
  asset_name?: string | null
  filters: Record<string, unknown>
  sample_count: number
  /** #167: progress-only tally; accuracy-style metrics are forbidden. */
  execution_summary: GovernanceRiskRescanExecutionSummary
  /** #167: frozen, ordered sample identities covered by this result. */
  ordered_sample_ids: string[]
  /** #167: the two problem views (risk hits / reference-label disagreements). */
  issue_lists: RiskRescanIssueLists
  /** #167: evaluator identity resolved for this run. */
  evaluator: string
  /** #167: frozen asset identity + hash. */
  evaluation_object?: RiskRescanEvaluationObject
  /** #167: executor identity that produced these predictions. */
  executor_identity?: GovernanceRiskRescanExecutorIdentity
  /** #167: evidence-pack download contract. */
  export_requested?: boolean
  export_available?: boolean
  export_path?: string
  disclosure_limits?: string[]
  integrity_facts?: string[]
  envelope?: GovernanceReportEnvelope
  failure_diagnostics?: RiskRescanFailureDiagnostics | null
  samples: GovernanceRiskRescanSampleOutcome[]
  source_refs: GovernanceSourceRef[]
  completed_at: string
  // #64 聚合来源：任务级结果（get_task）会带 runs/partial；消息载荷可能为空列表。
  partial?: boolean
  runs?: GovernanceRunProvenance[]
}

export interface GovernanceRiskRescanNoticePayload {
  capability: 'risk_corpus_rescan'
  capability_version: string
  phase: 'failed' | 'cancelled'
  task_id: string
  status: GovernanceRescanTaskStatus
  reason: string
}

/** #93 T2: mutually exclusive detection methods; never silently merged. */
export type RiskRescanEvaluator = 'activation_probe' | 'keyword'

export type RiskRescanFailurePhase =
  | 'preflight'
  | 'sample_detection'
  | 'transport_abort'
  | 'cancelled'
  | 'timeout'
  | 'unknown'

/** #92 评测对象披露（internal_validation；来源/许可可缺失）。 */
export interface RiskRescanEvaluationObject {
  asset_id?: string
  name?: string
  filename?: string
  content_sha256?: string
  disclosure_level?: string
  source_missing?: boolean
  licence_missing?: boolean
  source_message?: string
  licence_message?: string
  sample_count?: number
  [key: string]: unknown
}

/** #93 T1: failure / partial diagnostics carried on notices and incomplete reports. */
export interface RiskRescanFailureDiagnostics {
  failure_phase: RiskRescanFailurePhase | string
  diagnosis: string
  completed_sample_ids: string[]
  failed_sample_ids: string[]
  not_executed_sample_ids: string[]
  evaluator_identity: Record<string, unknown>
  frozen_scope_snapshot: Record<string, unknown>
}

/** #92: frozen sample finding. No owner / assignment / closure. */
export interface RiskRescanIssue {
  issue_id: string
  list_kind: 'risk_hit' | 'reference_label_disagreement'
  category: string
  sample_id: string
  judgment: string
  reference_label: string
  detected_label: string
  evidence: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
}

export interface RiskRescanIssueLists {
  risk_hit: RiskRescanIssue[]
  reference_label_disagreement: RiskRescanIssue[]
}

/** #167: four-file pack projected from the persisted `risk_corpus_rescan` v2 result. */
export interface InputRiskRescanEvidencePack {
  task_id: string
  capability: 'risk_corpus_rescan'
  report_type: 'input_risk_rescan'
  artifacts: {
    'report.html': string
    'issues.csv': string
    'issues.json': string
    'manifest.json': string
  }
  manifest: Record<string, unknown>
}

export interface GovernanceTaskDetail {
  task_id: string
  session_id: string
  capability: string | null
  status: GovernanceRescanTaskStatus | string
  error_message?: string | null
  parent_task_id?: string | null
  created_at: string
  finished_at?: string | null
  result?: Record<string, unknown> | null
  capability_version?: string
  completed_at?: string
  plan?: GovernanceSkillPlanPayload | null
}

export interface GovernanceSessionMessage {
  id: number
  role: 'user' | 'assistant'
  kind: GovernanceMessageKind
  content: string
  payload?: Record<string, unknown>
  created_at: string
}

export interface GovernanceSystemRecordItem {
  record_id: string
  record_type: string
  record_type_label: string
  name: string
  status: string
  status_label: string
  source_repo: string
  source_commit: string
  record_version: string
  asset_version?: string | null
  asset_status?: 'current' | 'historical' | 'unregistered'
  asset_sha256?: string | null
  sample_count: number
  model_names: string[]
  has_evaluation: boolean
  evaluated_at: string | null
  completed_at: string
  created_at: string
}

export interface GovernanceSystemRecordSearchPayload {
  capability: 'risk_system_record_search'
  capability_version: string
  available: boolean
  record_type: string
  record_type_label: string
  total: number
  offset: number
  limit: number
  filters: Record<string, unknown>
  records: GovernanceSystemRecordItem[]
  source_refs: GovernanceSourceRef[]
}

/**
 * A list card's deterministic "open detail" action. The capability key and
 * record id travel as a bound turn, so the server never re-derives them from
 * free text.
 */
export interface GovernanceSystemRecordOpenRequest {
  capability: 'risk_system_record_detail' | 'cultural_system_record_detail'
  recordId: string
}

export interface GovernanceSystemRecordModelResult {
  model_id: string
  model_name: string
  display_name: string
  model_version: string
  role: string
  run_id: string
  evaluated_at: string
  predictions_count: number
  primary_metrics: Record<string, unknown>
  supporting_metrics: Record<string, unknown>
  per_category_metrics: Record<string, unknown>
}

export interface GovernanceSystemRecordDataset {
  sample_count: number
  safe_total: number
  risk_total: number
  taxonomy_schema: string
  category_distribution: Record<string, number>
  language_distribution: Record<string, number>
  culture_distribution: Record<string, number>
  risk_level_distribution: Record<string, number>
}

export interface GovernanceSystemRecordDetailPayload {
  capability: 'risk_system_record_detail'
  capability_version: string
  available: boolean
  source_status: 'ok' | 'changed' | 'missing'
  record_id: string
  record_type: string
  record_type_label: string
  name: string
  status: string
  status_label: string
  record_version: string
  asset_version?: string | null
  asset_status?: 'current' | 'historical' | 'unregistered'
  source_repo: string
  source_commit: string
  asset_sha256: string
  dataset: GovernanceSystemRecordDataset
  models: GovernanceSystemRecordModelResult[]
  primary_metrics: { key: string; display_name: string }[]
  sample_summary: string
  live_eval_enabled: boolean
  source_refs: GovernanceSourceRef[]
  review_supported?: boolean
  review_unavailable_reason?: string
}

export interface GovernanceCulturalRecordItem {
  record_id: string
  record_type: string
  record_type_label: string
  name: string
  status: string
  status_label: string
  source_repo: string
  source_commit: string
  record_version: string
  sample_count: number
  difficulty_levels: string[]
  ethnic_groups: string[]
  background_types: string[]
  query_types: string[]
  review_passed_count: number
  review_passed_rate: number
  quality_gate_overall: string
  has_evaluation: boolean
  completed_at: string
  created_at: string
}

export interface GovernanceCulturalRecordSearchPayload {
  capability: 'cultural_system_record_search'
  capability_version: string
  available: boolean
  record_type: string
  record_type_label: string
  total: number
  offset: number
  limit: number
  filters: Record<string, unknown>
  records: GovernanceCulturalRecordItem[]
  source_refs: GovernanceSourceRef[]
}

export interface GovernanceCulturalRecordDataset {
  sample_count: number
  review_passed_count: number
  review_passed_rate: number
  quality_gate_overall: string
  difficulty_distribution: Record<string, number>
  ethnic_distribution: Record<string, number>
  background_type_distribution: Record<string, number>
  persona_distribution: Record<string, number>
  query_type_distribution: Record<string, number>
  discard_counts: Record<string, number>
}

export interface GovernanceCulturalRecordSample {
  sample_id: string
  ethnic_group: string
  difficulty_level: string
  background_type: string
  persona: string
  query_type: string
  prompt_preview: string
}

export interface GovernanceCulturalRecordDetailPayload {
  capability: 'cultural_system_record_detail'
  capability_version: string
  available: boolean
  source_status: 'ok' | 'changed' | 'missing'
  record_id: string
  record_type: string
  record_type_label: string
  name: string
  status: string
  status_label: string
  record_version: string
  source_repo: string
  source_commit: string
  asset_sha256: string
  dataset: GovernanceCulturalRecordDataset
  samples: GovernanceCulturalRecordSample[]
  sample_summary: string
  source_refs: GovernanceSourceRef[]
  review_supported: boolean
  review_view_id?: string | null
  review_unavailable_reason?: string
}

// ============================================================
// #88 文化预跑审阅任务（冻结报告快照）
// ============================================================

/** 通用报告状态（评测运行 / 完整性 / 交付就绪 / 审阅任务，四者相互独立）。 */
export interface GovernanceReportStatus {
  code: string
  label: string
  detail: string
}

/**
 * Backend `GovernanceReportEnvelope` — shared by cultural / risk reports.
 * Domain cards may narrow `evaluated_object` / `run_identity`; the shell accepts dict facts.
 */
export interface GovernanceReportEnvelope {
  evaluated_object: Record<string, unknown>
  source_identity: Record<string, unknown>
  run_identity: Record<string, unknown>
  evaluation_run_status: GovernanceReportStatus
  integrity_status: GovernanceReportStatus
  delivery_readiness: GovernanceReportStatus
  review_task_status: GovernanceReportStatus
  claim_boundaries: string[]
  limitations: string[]
}

export interface CulturalPrerunEvidenceFile {
  role: string
  path: string
  sha256: string
}

export interface CulturalPrerunEvaluatedObject {
  record_id: string
  record_name: string
  record_version: string
  dataset_id?: string | null
  dataset_label?: string | null
  sample_count: number
}

export interface CulturalPrerunSourceIdentity {
  source_repo: string
  source_commit: string
  asset_sha256: string
  static_view_id?: string | null
  evidence_files: CulturalPrerunEvidenceFile[]
}

export interface CulturalPrerunRunIdentityDirect {
  run_id: string
  method: string
  model: string
}

export interface CulturalPrerunRunIdentityThreeAgent {
  run_id: string
  method: string
  pipeline: string
}

export interface CulturalPrerunRunIdentityJudge {
  ethnic_recognition_model: string
  cultural_specificity_model: string
  scope: string[]
}

export interface CulturalPrerunRunIdentity {
  direct: CulturalPrerunRunIdentityDirect
  three_agent: CulturalPrerunRunIdentityThreeAgent
  judge: CulturalPrerunRunIdentityJudge
}

export interface CulturalPrerunReviewEnvelope {
  evaluated_object: CulturalPrerunEvaluatedObject
  source_identity: CulturalPrerunSourceIdentity
  run_identity: CulturalPrerunRunIdentity
  evaluation_run_status: GovernanceReportStatus
  integrity_status: GovernanceReportStatus
  delivery_readiness: GovernanceReportStatus
  review_task_status: GovernanceReportStatus
  claim_boundaries: string[]
  limitations: string[]
}

export type CulturalPrerunReviewMethod = 'direct' | 'three_agent'

export interface CulturalPrerunSourceMetric {
  method: CulturalPrerunReviewMethod
  label: string
  ethnic_recognition_rate: number
  cultural_specificity_rate: number
  composite_pass_rate: number
  /** 上游综合通过率百分比（23.33 / 73.33），原样展示，前端不得重算。 */
  composite_percentage: number
  composite_pass_count: number
  total_samples: number
}

export interface CulturalPrerunThreeAgentStage {
  key: string
  label: string
  description: string
}

export interface CulturalPrerunIntegrityWarning {
  code: string
  message: string
  population?: string
  count?: number
  expected?: number
  actual?: number
  sample_ids?: string[]
  missing?: string[]
  extra?: string[]
  method?: string
  sample_id?: string
  dimension?: string
  score?: number | string | null
}

export interface CulturalPrerunJudgeVerdict {
  score?: number | string | null
  mentioned_ethnic_group?: string
  reason?: string
}

export interface CulturalPrerunEvidenceBinding {
  sample_id: string
  corpus_sha256: string
  direct_output_sha256: string
  three_agent_output_sha256: string
  judge: {
    direct: {
      ethnic_recognition: CulturalPrerunJudgeVerdict
      cultural_specificity: CulturalPrerunJudgeVerdict
    }
    three_agent: {
      ethnic_recognition: CulturalPrerunJudgeVerdict
      cultural_specificity: CulturalPrerunJudgeVerdict
    }
  }
}

export interface CulturalPrerunFrozenEvidence {
  sample_count: number
  sample_ids: string[]
  bindings: CulturalPrerunEvidenceBinding[]
  evidence_files: CulturalPrerunEvidenceFile[]
}

/** #89: frozen sample finding. No owner / assignment / closure fields. */
export interface CulturalReviewIssue {
  issue_id: string
  list_kind: 'content' | 'integrity'
  category: string
  sample_id: string
  method?: string | null
  dimension?: string | null
  judgment: string
  evidence: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
}

export interface CulturalReviewIssueLists {
  content: CulturalReviewIssue[]
  integrity: CulturalReviewIssue[]
}

export interface CulturalPrerunEvidencePack {
  task_id: string
  capability: 'cultural_prerun_review'
  artifacts: {
    'report.html': string
    'issues.csv': string
    'issues.json': string
    'manifest.json': string
  }
  manifest: Record<string, unknown>
}

export interface CulturalPrerunReviewReport {
  capability: 'cultural_prerun_review'
  capability_version: string
  task_id: string
  report_type: 'cultural_generation_method_comparison'
  envelope: CulturalPrerunReviewEnvelope
  source_metrics: CulturalPrerunSourceMetric[]
  /** 文化识别 / 知识检索 / 回答生成三个协作阶段，不是三个评估器。 */
  three_agent_stages: CulturalPrerunThreeAgentStage[]
  integrity_warnings: CulturalPrerunIntegrityWarning[]
  /** #89: content vs integrity issue views over the same freeze. */
  issue_lists: CulturalReviewIssueLists
  frozen_evidence: CulturalPrerunFrozenEvidence
  source_refs: GovernanceSourceRef[]
  completed_at: string
}

// ============================================================
// #90 风险预跑审阅任务（V7 正式摘要 + Base 基线对照）
// ============================================================

export type RiskPrerunEvaluatorRole = 'primary' | 'baseline'

export interface RiskPrerunRunIdentitySide {
  role: RiskPrerunEvaluatorRole
  model_id: string
  model_version: string
  display_name: string
  run_id: string
  evaluated_at: string
}

export interface RiskPrerunRunIdentity {
  benchmark_version: string
  primary: RiskPrerunRunIdentitySide
  baseline: RiskPrerunRunIdentitySide
}

export interface RiskPrerunEvaluatedObject {
  record_id: string
  record_name: string
  record_version: string
  dataset_id?: string
  dataset_label?: string
  sample_count: number
  benchmark_version?: string
  taxonomy_schema?: string
}

export interface RiskPrerunSourceIdentity {
  source_repo: string
  source_commit: string
  asset_sha256: string
  benchmark_version?: string
  evidence_files: CulturalPrerunEvidenceFile[]
}

export interface RiskPrerunReviewEnvelope {
  evaluated_object: RiskPrerunEvaluatedObject
  source_identity: RiskPrerunSourceIdentity
  run_identity: RiskPrerunRunIdentity
  evaluation_run_status: GovernanceReportStatus
  integrity_status: GovernanceReportStatus
  delivery_readiness: GovernanceReportStatus
  review_task_status: GovernanceReportStatus
  claim_boundaries: string[]
  limitations: string[]
}

export interface RiskEvaluatorMetrics {
  role: RiskPrerunEvaluatorRole
  model_id: string
  model_version: string
  display_name: string
  run_id: string
  evaluated_at: string
  predictions_count: number
  binary_metrics: Record<string, unknown>
  level_metrics: Record<string, unknown>
  multilabel_metrics: Record<string, unknown>
  primary_metrics: Record<string, unknown>
  supporting_metrics: Record<string, unknown>
  per_category_metrics: Record<string, unknown>
}

export interface RiskPrerunDimensionSummary {
  key: string
  label: string
  description: string
}

export interface RiskPrerunIntegrityWarning {
  code: string
  message: string
  [key: string]: unknown
}

/** #91: problem evidence state — not resolution / assignee workflow. */
export type RiskEvidenceState = 'confirmed-difference' | 'pending-human-confirmation'

export interface RiskReviewIssue {
  issue_id: string
  list_kind: 'recognition' | 'integrity'
  category: string
  sample_id: string
  evidence_state?: RiskEvidenceState | null
  judgment: string
  ref_labels: Record<string, unknown>
  v7_prediction: Record<string, unknown>
  excerpt_masked: string
  evidence: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
}

export interface RiskReviewIssueLists {
  recognition: RiskReviewIssue[]
  integrity: RiskReviewIssue[]
}

export interface RiskPrerunEvidencePack {
  task_id: string
  capability: 'risk_prerun_review'
  artifacts: {
    'report.html': string
    'issues.csv': string
    'issues.json': string
    'manifest.json': string
  }
  manifest: Record<string, unknown>
}

export interface RiskPrerunReviewReport {
  capability: 'risk_prerun_review'
  capability_version: string
  task_id: string
  report_type: 'risk_classifier_cross_check'
  envelope: RiskPrerunReviewEnvelope
  primary_evaluator: RiskEvaluatorMetrics
  baseline_evaluator: RiskEvaluatorMetrics | null
  dimension_summaries: RiskPrerunDimensionSummary[]
  integrity_warnings: RiskPrerunIntegrityWarning[]
  /** #91: recognition differences vs asset integrity problems. */
  issue_lists: RiskReviewIssueLists
  frozen_evidence: Record<string, unknown>
  source_refs: GovernanceSourceRef[]
  completed_at: string
}

export interface GovernanceSessionSummary {
  session_id: string
  domain: GovernanceDomainKey
  title: string
  created_at: string
  updated_at: string
}

export interface GovernanceClarificationPlan {
  plan_id: string
  status: 'awaiting_clarification' | 'resolved' | 'abandoned' | 'invalidated'
  version: number
  question: string
  missing_items: string[]
  goal_draft?: string | null
  resolved_goal?: string | null
  bound_skill_key?: string | null
  bound_skill_version?: string | null
  created_at: string
  updated_at: string
}

export interface GovernanceSessionDetail extends GovernanceSessionSummary {
  messages: GovernanceSessionMessage[]
  suggestions?: GovernanceTaskSuggestion[]
  clarification_plan?: GovernanceClarificationPlan | null
}

export interface GovernanceHistoryPage {
  items: GovernanceSessionSummary[]
  total: number
}

export type GovernanceTabNavigationKey = 'ArrowLeft' | 'ArrowRight' | 'Home' | 'End'

/** Empty-session 推荐任务：action 可点发送；explanation 为治理能力说明（无执行控件）。 */
export type GovernanceRecommendKind = 'action' | 'explanation'

export interface GovernanceSuggestion {
  id: string
  title: string
  prompt: string
  kind?: GovernanceRecommendKind
  capability?: string | null
  skill_key?: string | null
  reason?: string
}

export interface GovernanceDomain {
  key: GovernanceDomainKey
  label: string
  heading: string
  description: string
  placeholder: string
  suggestions: GovernanceSuggestion[]
}

// ============================================================
// #65 持续可见技能入口 / 计划投影 / 依据化建议
// ============================================================

export type GovernanceSkillAction = 'prepare' | 'execute'

export type GovernanceSkillEntrypoint = 'natural_language' | 'skill_entry'

export interface GovernanceSkillBoundaryStep {
  step_id: string
  capability: string
  capability_version: string
  action: GovernanceSkillAction
  automatic: boolean
  requires_confirmation: boolean
  completion_condition: string
}

export interface GovernanceSkillBoundary {
  branches: string[]
  entrypoints: GovernanceSkillEntrypoint[]
  executor_capability: string
  result_schema: string
  immutable_scope_fields: string[]
  cost_units_per_sample: number
  estimated_seconds_per_sample: number
  confirmation_required: boolean
  steps: GovernanceSkillBoundaryStep[]
}

export interface GovernanceSkillEntry {
  skill_key: string
  version: string
  name: string
  description: string
  domain: string
  skill_content_digest: string
  contract_digest: string
  boundary: GovernanceSkillBoundary
}

export interface GovernanceSkillCatalogResult {
  domain: string
  domains: string[]
  skills: GovernanceSkillEntry[]
}

export interface GovernanceSkillPlanStepView {
  step_id: string
  capability: string
  capability_version: string
  action: GovernanceSkillAction
  automatic: boolean
  requires_confirmation: boolean
  completion_condition: string
  status: string
}

export interface GovernanceSkillPlanScopeView {
  asset_id: string
  asset_name?: string | null
  asset_version: string
  filters: Record<string, unknown>
  sample_count: number
  immutable_scope_fields: string[]
  estimated_cost_units: number
  estimated_seconds: number
}

export interface GovernanceSkillPlanPayload {
  capability: 'skill_plan'
  phase: 'plan'
  message_kind: 'governance_skill_plan'
  plan_id: string
  task_id: string
  skill_key: string
  skill_version: string
  title: string
  entrypoint: GovernanceSkillEntrypoint
  branch: string
  status: string
  confirmation_required: boolean
  steps: GovernanceSkillPlanStepView[]
  scope: GovernanceSkillPlanScopeView
  executor?: ExecutorIdentityView | null
  scope_fingerprint: string
  notes: string[]
}

export interface ExecutorIdentityView {
  capability: string
  capability_version: string
  adapter_method: string
  api_contract_version: string
  implementation_fingerprint: string
  version_assurance: 'verified' | 'provisional'
  observed_metadata: Record<string, string>
}

export type GovernanceSuggestionHandling = 'direct' | 'plan'

export interface GovernanceTaskSuggestion {
  id: string
  title: string
  prompt: string
  handling: GovernanceSuggestionHandling
  capability?: string | null
  skill_key?: string | null
  parameters?: Record<string, unknown>
  reason: string
  origin: 'deterministic' | 'model'
}

export interface GovernanceTaskSuggestionResult {
  task_id?: string | null
  session_id: string
  has_candidates: boolean
  suggestions: GovernanceTaskSuggestion[]
}

// ---- 只读结果投影（#65 定义，#66 复用）----

export interface GovernanceRunProvenance {
  run_id: string
  attempt: number
  status: string
  capability_version: string
  executor_fingerprint: string
  scope_selection: string
  parent_run_id?: string | null
  result_schema: string
  sample_count: number
  started_at: string
  completed_at?: string | null
}

export interface GovernanceResultSample {
  sample_id: string
  text: string
  reference_label: string
  detected_label: string
  status: 'consistent' | 'inconsistent' | 'failed' | 'not_executed' | string
  reason: string
  source: string
  run_id: string
  capability_version: string
  completed_at: string
}

export interface GovernanceResultSummary {
  consistent_count: number
  inconsistent_count: number
  failed_count: number
  not_executed_count: number
}

export interface GovernanceResultProjectionData {
  task_id: string
  status: string
  method: string
  asset_id?: string | null
  asset_name?: string | null
  filters: Record<string, unknown>
  sample_count: number
  summary: GovernanceResultSummary
  samples: GovernanceResultSample[]
  completed_at: string
  capability_version: string
  partial: boolean
  runs: GovernanceRunProvenance[]
  source_refs?: GovernanceSourceRef[]
}

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastMessage {
  id: string
  type: ToastType
  title: string
  message: string
  duration: number
}

export interface StepItem {
  id: number
  label: string
  icon?: string
  disabled?: boolean
  /** DefinitionView 兼容：步骤标识（可替代 id 作为 key） */
  key?: number
  /** DefinitionView 兼容：展示序号（可替代 icon） */
  number?: number
}

export interface UploadFile {
  id: string
  name: string
  size: number
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress: number
}

// ============================================================
// 文化多样性生成 — 数据集与推理类型
// ============================================================

/** 文化多样性数据集样本 */
export interface CultureSample {
  id: string
  fullQuestion: string
  bgType: 'explicit' | 'implicit'
  cues: string[]
  inferred: string
  category: string
  ethnic: string
  expected: string
  generated: string
  knowledge: string
  cultureScore: number
  semanticScore: number
  integrityScore: number
  wrongExample: string
  fixSuggestion: string
  improveItems: string[]
}

/** 文化推理结果 */
export interface CultureAnalyzeResult {
  text: string
  ethnic: string
  confidence: number
  cues: string[]
  category: string
  reasoning: string[]
  knowledge: string
  top3: string[]
  generated: string
  scores: {
    culture: number
    semantic: number
    integrity: number
    total: number
  }
  errors: {
    wrongExample: string
    fixSuggestion: string
    improveItems: string[]
  }
}

/** 文化数据集统计 */
export interface CultureDatasetStats {
  total: number
  explicitCount: number
  implicitCount: number
  ethnicCounts: Record<string, number>
  categoryCounts: Record<string, number>
}

// ============================================================
// Governance Share* — Issue #66 / #78 匿名评审分享（独立区块，勿与 #65 投影类型混写）
// ============================================================

/** POST /governance/tasks/{task_id}/shares 请求体 */
export interface CreateGovernanceShareRequest {
  ttl_days?: number
  show_sample_text?: boolean
}

/** 创建分享响应（明文 token 仅此一次） */
export interface GovernanceShareCreated {
  share_id: string
  task_id: string
  token: string
  expires_at: string
  show_sample_text: boolean
  review_path: string
}

/**
 * 匿名 GET /governance/review/{share_token} 载荷。
 * `task` 与 get_task 同源结构，经服务端披露过滤。
 */
export interface GovernanceShareReviewPayload {
  share_id: string
  task_id: string
  expires_at: string
  show_sample_text: boolean
  task: GovernanceShareReviewTask
}

/** 评审页消费的任务事实（字段与 get_task 对齐；未投影部分保持宽松） */
export interface GovernanceShareReviewTask {
  task_id: string
  session_id?: string
  capability?: string | null
  status?: string
  error_message?: string | null
  parent_task_id?: string | null
  created_at?: string
  finished_at?: string | null
  capability_version?: string
  completed_at?: string
  result?: GovernanceShareReviewResult | Record<string, unknown> | null
  [key: string]: unknown
}

/** 风险二次检测结果中评审页可读的聚合字段 */
export interface GovernanceShareReviewResult {
  capability?: string
  phase?: string
  task_id?: string
  status?: string
  method?: string
  sample_count?: number
  filters?: Record<string, unknown>
  summary?: {
    consistent_count?: number
    inconsistent_count?: number
    failed_count?: number
    not_executed_count?: number
  }
  samples?: Array<{
    sample_id?: string
    text?: string
    reference_label?: string
    detected_label?: string
    status?: string
    reason?: string
    content_digest?: string
    run_id?: string
    capability_version?: string
    completed_at?: string
  }>
  source_refs?: Array<{
    ref_type?: string
    ref_id?: string
    name?: string
    source_repo?: string
    source_commit?: string
    kind?: string
    ref?: string
    label?: string
    [key: string]: unknown
  }>
  runs?: Array<Record<string, unknown>>
  groups?: Array<Record<string, unknown>>
  partial?: boolean
  [key: string]: unknown
}
