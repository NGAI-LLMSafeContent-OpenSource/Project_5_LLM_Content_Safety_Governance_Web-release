import request from './request'
import type {
  Dataset,
  EvalConfig,
  EvalResult,
  Attribution,
  AttributionNode,
  Strategy,
  PaginatedData,
} from '@/types'

// ---- 风险 Taxonomy ----

export interface RiskSubcategory {
  key: string
  label: string
  level?: string
}

export interface RiskCategoryItem {
  key: string
  label: string
  category: 'ai4sci' | 'culture'
  level: 'HIGH' | 'MEDIUM' | 'LOW'
  selected: boolean
  definition: string
  subcategories: RiskSubcategory[]
}

export interface RiskTaxonomyData {
  taxonomy_id: number
  taxonomy_name: string
  version: string
  source_repo: string
  source: string // 'benchmark' | 'mock'
  categories: RiskCategoryItem[]
  threshold_defaults: {
    high: number
    medium: number
    low: number
  }
}

/** 获取当前启用的风险分类体系 */
export function fetchRiskTaxonomies() {
  return request.get<RiskTaxonomyData>('/output/risk-taxonomies/active')
}

/** 获取可用评测数据集 */
export function fetchOutputDatasets() {
  return request.get<Dataset[]>('/output/datasets')
}

// ---- 评测任务 ----

export interface EvalStartResult {
  task_id: string
  status: string
  task_type: string
  created_at: string
}

export interface EvalStartDTO {
  config_id?: string
  dataset_ids: string[]
  taxonomy_id?: number
  selected_dimensions: string[]
  sampling_config?: Array<{
    dataset_id: string
    sampling_method: string
    sample_size: number
  }>
  runtime_options?: Record<string, unknown>
}

/** 启动输出风险评测任务 */
export function startEvalTask(dto: EvalStartDTO) {
  return request.post<EvalStartResult>('/output/eval-tasks', dto)
}

// ---- 任务状态 ----

export interface EvalLogEntry {
  time: string
  level: string
  message: string
}

export interface EvalTaskStatusData {
  task_id: string
  task_type: string
  status: 'pending' | 'running' | 'finished' | 'error'
  progress: number
  stage: string
  stage_label: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  logs: EvalLogEntry[]
  artifacts: Record<string, string>
  source: string
}

/** 查询评测任务状态与日志 */
export function getEvalTaskStatus(taskId: string) {
  return request.get<EvalTaskStatusData>(`/output/eval-tasks/${taskId}`)
}

// ---- 评测结果 ----

export interface EvalSampleData {
  id: string
  text: string
  dimension_scores: Record<string, string>
  overall_level: string
  overall_score: number
  summary: string
  dataset_id?: string
  dataset_name?: string
  gold_binary_label?: 0 | 1
  pred_binary_label?: 0 | 1
  gold_category?: string
  gold_category_code?: string
  pred_category?: string
  pred_category_code?: string
  gold_level?: string
  pred_level?: string
  is_correct?: boolean
  is_category_correct?: boolean
}

export interface EvalMetricsData {
  binary_safe_acc: number
  risk_class_acc: number
  severity_acc: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  risk_recall: number
  fpr: number
}

export interface DatasetSummaryData {
  sample_total: number
  high_count: number
  medium_count: number
  low_count: number
  selected_dimension_count: number
}

export interface RadarSeriesItem {
  name: string
  values: number[]
  fill: string
  stroke: string
}

export interface RadarRiskChartData {
  dimensions: string[]
  series: RadarSeriesItem[]
}

export interface DatasetMetricItem {
  dataset_id: string
  dataset_name: string
  sample_count: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  risk_class_acc: number
  risk_recall: number
  fpr: number
  per_category: Record<string, { accuracy: number; f1: number; count: number }>
}

export interface GroupedMetricItem {
  sample_count: number
  accuracy: number
  f1: number
  risk_class_acc: number
  risk_recall: number
}

export interface GroupedMetricsData {
  dimension: string
  groups: Record<string, GroupedMetricItem>
}

export interface MultiDatasetRadarItem {
  dataset_id: string
  dataset_name: string
  values: number[]
  color?: string
}

export interface RadarMultiDatasetData {
  dimensions: string[]
  dimension_labels?: Record<string, string>
  selected_metric: string
  series: MultiDatasetRadarItem[]
}

export interface EvalResultSummaryData {
  task_id: string
  config_id: string
  source: string
  dataset_summary: DatasetSummaryData
  radar_risk_data: RadarRiskChartData
  radar_multi_dataset?: RadarMultiDatasetData
  samples: EvalSampleData[]
  metrics: EvalMetricsData
  dataset_metrics?: DatasetMetricItem[]
  grouped_metrics?: GroupedMetricsData
  artifacts: Record<string, string>
  created_at: string
}

/** 获取评测结果聚合数据 */
export function getEvalResultSummary(taskId: string) {
  return request.get<EvalResultSummaryData>(`/output/eval-tasks/${taskId}/results`)
}

/** 导出评测结果（CSV 或 JSON） */
export function exportEvalResults(
  taskId: string,
  format: 'csv' | 'json' = 'csv',
  filters?: { level?: string; onlyWrong?: boolean },
) {
  return request.get<string>(`/output/eval-tasks/${taskId}/results/export`, {
    params: { format, ...filters },
  })
}

// ---- 单样本动态推理 ----

export interface InferSampleRequest {
  task?: string
  model_id?: string
  prompt?: string
  response: string
  template_policy?: string
  use_vllm?: boolean
  use_api?: boolean
  max_new_tokens?: number
  max_model_len?: number
  severity_max_new_tokens?: number
  evidence_max_new_tokens?: number
}

export interface InferStep {
  name: string
  status: string
  detail?: Record<string, unknown> | string
}

export interface RiskEvidenceItem {
  text: string
  level?: 'neutral' | 'context' | 'warning' | 'critical' | string
}

export interface InferSampleResponse {
  ok: boolean
  source?: string
  steps: InferStep[]
  pred_safe_type?: string
  pred_risk_level?: string
  pred_category?: string
  pred_category_code?: string
  raw_response?: string
  prompt_used?: string
  cached?: boolean
  stderr?: string
  stdout?: string
  safe_type?: string
  risk_level?: string | number
  risk_level_id?: string | number
  risk_category?: string
  risk_category_name?: string
  risk_evidence?: RiskEvidenceItem[]
  evidence?: { items?: RiskEvidenceItem[] }
  result?: Record<string, unknown>
}

export function inferSingleSample(dto: InferSampleRequest) {
  return request.post<InferSampleResponse>('/output/eval-samples/infer', dto, {
    timeout: 900000,
  })
}

export function inferRiskEvidenceWithCache(
  dto: InferSampleRequest,
  params: { datasetId?: string; sampleId?: string; forceRefresh?: boolean } = {},
) {
  return request.post<InferSampleResponse>('/output/attribution/risk/evidence', dto, {
    params: {
      dataset_id: params.datasetId || '',
      sample_id: params.sampleId || '',
      force_refresh: params.forceRefresh ? 'true' : 'false',
    },
    timeout: 900000,
  })
}

// ---- 静态评测结果（通过后端代理）----

export interface StaticEvalMeta {
  dataset_id: string
  model_id: string
  model_name?: string
  run_name: string
  task: string
  num_examples: number
  created_at?: string
  result_version?: string
}

export interface StaticEvalMetrics {
  num_examples: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  risk_class_acc: number
  risk_recall: number
  per_category?: Record<string, { acc: number; total: number; correct: number }>
  per_category_metrics?: Record<string, Record<string, number>>
  risk_class_detected?: number
  risk_class_total?: number
  risk_total?: number
}

export interface StaticEvalResult {
  source?: string
  selected: {
    metrics: StaticEvalMetrics
    dataset_id: string
    model_id: string
    model_name?: string
    run_name: string
    task: string
    created_at?: string
    result_version?: string
  } | null
  results: StaticEvalMeta[]
}

/** 通过后端代理获取静态评测结果列表和已选指标 */
export function fetchBenchmarkResults(
  datasetId: string,
  modelId = '',
  task = '',
  signal?: AbortSignal,
): Promise<StaticEvalResult> {
  return request.get('/output/static-results', {
    params: { task: task || '', dataset_id: datasetId || '', model_id: modelId || '' },
    signal, // 支持请求取消
  }) as unknown as Promise<StaticEvalResult>
}

/** 通过后端代理获取预测记录（用于等级分布统计） */
export function fetchBenchmarkPredictions(
  datasetId: string,
  modelId = '',
  task = '',
  limit = 3000,
  signal?: AbortSignal,
): Promise<{
  source?: string
  rows: Array<{ pred_level?: string; pred_risk_level?: string; pred_safe_type?: string }>
}> {
  return request.get('/output/static-predictions', {
    params: {
      task: task || '',
      dataset_id: datasetId || '',
      model_id: modelId || '',
      limit: String(limit),
    },
    signal, // 支持请求取消
  }) as unknown as Promise<{
    source?: string
    rows: Array<{ pred_level?: string; pred_risk_level?: string; pred_safe_type?: string }>
  }>
}

export interface Topic3RiskAssetIdentity {
  series_id: string
  asset_id: string
  asset_version: string | null
  asset_sha256: string
  asset_status: 'current' | 'historical' | 'unregistered'
}

export interface Topic3RiskVersionOption extends Topic3RiskAssetIdentity {
  name: string
  sample_count: number | null
}

export interface Topic3RiskSampleDetail {
  sample_id: string
  asset_id: string
  asset_version: string | null
  asset_sha256: string
  index: string | number
  prompt: string
  response: string
  risk_category: string
  risk_level_id: string
  response_safetype: string
  label_reason: string
  label_reason_status: string
  integrity_warnings: Array<{ code: string; message: string }>
  label_reason_usable_for_automatic_explanation: boolean
}

export interface Topic3RiskPredictionRow {
  sample_id: string
  prediction: Record<string, unknown>
  pred_categories: string[] | null
}

export interface Topic3RiskSameVersion extends Topic3RiskAssetIdentity {
  name: string
  sample_count: number | null
  evaluation_status: string
  sample_details: Topic3RiskSampleDetail[]
  evaluation: {
    available: boolean
    asset_id: string
    asset_version: string | null
    asset_sha256: string
    results: Array<{ role?: string; model_id?: string; run_id?: string }>
  }
  primary_evaluator: {
    available: boolean
    model_id: string | null
    run_id: string | null
  }
  result_display: {
    available: boolean
    requires_baseline: boolean
    model_id: string | null
    run_id: string | null
    role: string | null
    task: string | null
    primary_metrics: Record<string, number | null>
    supporting_metrics: Record<string, number | null>
  }
  predictions: Topic3RiskPredictionRow[]
  baseline: {
    available: boolean
    same_version: boolean
    model_id: string | null
    message: string
  }
  automatic_explanations: Array<{
    sample_id: string
    asset_id: string
    asset_version: string | null
    asset_sha256: string
    text: string
  }>
  versions: Topic3RiskVersionOption[]
}

/** 读取课题三风险资产的样本和同版本评测结果。省略版本时为当前资产。 */
export function fetchTopic3RiskSameVersion(params?: {
  assetVersion?: string
  assetId?: string
}): Promise<Topic3RiskSameVersion> {
  return request.get('/output/topic3-risk/same-version', {
    params: {
      ...(params?.assetVersion ? { asset_version: params.assetVersion } : {}),
      ...(params?.assetId ? { asset_id: params.assetId } : {}),
    },
  })
}

// ---- 以下为旧接口占位，后续阶段再对接 ----

/** 获取评估配置列表 */
export function getEvalConfigs() {
  return request.get<EvalConfig[]>('/output/eval-configs')
}

/** 创建评估配置 */
export function createEvalConfig(dto: Partial<EvalConfig>) {
  return request.post<EvalConfig>('/output/eval-configs', dto)
}

/** 开始评估（旧接口，保留兼容） */
export function startEval(configId: string, datasetIds: string[]) {
  return request.post<{ taskId: string }>('/output/eval', { configId, datasetIds })
}

/** 获取评估结果（旧接口，保留兼容） */
export function getEvalResults(query?: { taskId?: string }) {
  return request.get<PaginatedData<EvalResult>>('/output/eval-results', { params: query })
}

/** 获取归因分析 */
export function getAttribution(evalResultId: string) {
  return request.get<Attribution>(`/output/attribution/${evalResultId}`)
}

/** 获取风险归因节点列表（从 Benchmark 静态 predictions） */
export function fetchRiskAttribution(params?: { dataset_id?: string; limit?: number }) {
  return request.get<AttributionNode[]>('/output/attribution/risk', { params })
}

/** 获取策略建议 */
export function getStrategies(query?: { evalResultId?: string }) {
  return request.get<Strategy[]>('/output/strategies', { params: query })
}

// ============================================================
// 文化多样性生成 — BFF 代理到 Cultural Gen Backend (6322)
// ============================================================

export interface CultureSampleDTO {
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
  evaluationKind?: 'generation_scores' | 'reference_review'
  reviewAccuracy?: number | null
  reviewPassed?: boolean
  difficultyLevel?: string
  runId?: string
  rubric?: { must_have?: string[]; penalty?: string[] }
}

export interface CultureAnalyzeResultDTO {
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

export interface CultureSamplesResponse {
  source: string // 'real' | 'corpus_static' | 'demo_fixture' | 'unavailable'
  integration_mode?:
    | 'upstream_data_api'
    | 'legacy_backend_samples_api'
    | 'local_artifact_adapter'
    | string
  total: number
  explicit_count: number
  implicit_count: number
  ethnic_counts: Record<string, number>
  category_counts: Record<string, number>
  difficulty_counts?: Record<string, number>
  run_counts?: Record<string, number>
  samples: CultureSampleDTO[]
}

export interface CultureCorpusSamplesQuery {
  run_id?: string[]
  ethnic?: string[]
  difficulty?: string[]
  include_live_runs?: boolean
  limit?: number
}

export interface CultureCorpusGenerationRequest {
  run_id?: string
  output_dir?: string
  mode?: 'single' | 'batch'
  total_sample_count?: number
  batch_size?: number
  random_seed?: number
  language?: string
  sample_mode?: string
  skill_path?: string
  data_source_mode?: 'cultural_knowledge_library' | 'seed_input_json'
  cultural_knowledge_library_path?: string
  seed_sources?: string[]
  allowed_ethnic_groups?: string[]
  allowed_dimensions?: string[]
  difficulty_counts?: Partial<Record<'L1' | 'L2' | 'L3', number>>
  api_base?: string
  model?: string
  max_tokens?: number
  temperature?: number
  timeout?: number
  composer_concurrency?: number
  discard_retry_limit?: number
}

export interface CultureCorpusGenerationStatus {
  job_id: string
  status: string
  running: boolean
  pid?: number | null
  generated: number
  total: number
  progress: number
  difficulty_level_counts: Record<string, number>
  output_dir: string
  config_path: string
  samples_path: string
  manifest: Record<string, unknown>
  worker_state: Record<string, unknown>
  log_tail: string
  samples: CultureSampleDTO[]
  source: 'corpus_live'
  runner?: 'topic3_http_job_api' | 'local_subprocess_adapter' | string
  integration_mode?: 'upstream_service' | 'local_demo_adapter' | string
}

export interface CultureCorpusGenerationSamples {
  job_id: string
  source: 'corpus_live'
  runner?: 'topic3_http_job_api' | 'local_subprocess_adapter' | string
  integration_mode?: 'upstream_service' | 'local_demo_adapter' | string
  count: number
  samples: CultureSampleDTO[]
}

/** 通过 BFF 代理获取文化多样性样本 */
export async function fetchCultureSamples() {
  return request.get('/output/culture/samples') as unknown as Promise<CultureSamplesResponse>
}

/** 获取课题三预跑文化评测语料，不触发在线生成。 */
export async function fetchCultureCorpusSamples(params?: CultureCorpusSamplesQuery) {
  const query = new URLSearchParams()
  for (const runId of params?.run_id || []) query.append('run_id', runId)
  for (const ethnic of params?.ethnic || []) query.append('ethnic', ethnic)
  for (const difficulty of params?.difficulty || []) query.append('difficulty', difficulty)
  if (params?.include_live_runs !== undefined) {
    query.set('include_live_runs', String(params.include_live_runs))
  }
  if (params?.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  return request.get('/output/culture/corpus-samples', {
    params: query,
  }) as unknown as Promise<CultureSamplesResponse>
}

/** 启动课题三文化语料实时生成任务，API Key 只由后端环境变量读取。 */
export async function startCultureCorpusGenerationJob(payload: CultureCorpusGenerationRequest) {
  return request.post(
    '/output/culture/corpus-generation/jobs',
    payload,
  ) as unknown as Promise<CultureCorpusGenerationStatus>
}

/** 查询课题三文化语料实时生成任务状态。 */
export async function fetchCultureCorpusGenerationJob(jobId: string) {
  return request.get(
    `/output/culture/corpus-generation/jobs/${encodeURIComponent(jobId)}`,
  ) as unknown as Promise<CultureCorpusGenerationStatus>
}

/** 读取课题三文化语料实时生成任务已产出的样本。 */
export async function fetchCultureCorpusGenerationSamples(jobId: string, limit = 50) {
  return request.get(
    `/output/culture/corpus-generation/jobs/${encodeURIComponent(jobId)}/samples`,
    { params: { limit } },
  ) as unknown as Promise<CultureCorpusGenerationSamples>
}

/** 停止当前后端进程内启动的课题三文化语料实时生成任务。 */
export async function stopCultureCorpusGenerationJob(jobId: string) {
  return request.post(
    `/output/culture/corpus-generation/jobs/${encodeURIComponent(jobId)}/stop`,
  ) as unknown as Promise<CultureCorpusGenerationStatus>
}

/** 通过 BFF 代理调用 Cultural Gen 实时推理 */
export async function analyzeCultureText(text: string) {
  return request.post('/output/culture/analyze', {
    text,
  }) as unknown as Promise<CultureAnalyzeResultDTO>
}

// ============================================================
// 文化多样性评测 Benchmark — 静态资产读取
// ============================================================

export interface CultureAssessmentDatasetDTO {
  id: string
  label: string
  path: string
  sample_count: number
  description: string
  exists: boolean
  preview_sample_id?: string
  preview_ethnic_group?: string
  preview_difficulty_level?: string
  source: 'culture_assessment_static'
}

export interface CultureAssessmentStaticViewSummary {
  total_samples: number
  ethnic_group_metric_rate: number
  cultural_difference_rate: number
  composite_pass_count: number
  composite_pass_rate: number
  composite_percentage: number
  by_ethnic_group: Record<string, { count: number; pass_rate: number }>
  by_difficulty: Record<string, { count: number; pass_rate: number }>
}

export interface CultureAssessmentAnswerEval {
  answer_a: string
  answer_b: string
  ethnic_group_judge: { score?: number; mentioned_ethnic_group?: string; reason?: string }
  cultural_difference_judge: { score?: number; reason?: string }
  composite_score: number
}

export interface CultureAssessmentSamplePair {
  sample_id: string
  difficulty_level?: string
  expected_ethnic_group?: string
  original_question?: string
  neutralized_question?: string
  direct: CultureAssessmentAnswerEval
  agent: CultureAssessmentAnswerEval
  advantage_note: string
}

export interface CultureAssessmentReferenceSample {
  sample_id: string
  difficulty_level?: string
  expected_ethnic_group?: string
  original_question?: string
  neutralized_question?: string
  answer_a: string
  answer_b: string
  ethnic_group_judge: { score?: number; mentioned_ethnic_group?: string; reason?: string }
  cultural_difference_judge: { score?: number; reason?: string }
  composite_score: number
}

export interface CultureAssessmentStaticViewDTO {
  source: 'culture_assessment_static'
  view_id: string
  title: string
  dataset_id: string
  dataset_label: string
  highlights: string[]
  advantage_summary: string
  reference?: {
    label: string
    run_dir: string
    summary: CultureAssessmentStaticViewSummary
  }
  direct: {
    label: string
    run_dir: string
    summary: CultureAssessmentStaticViewSummary
  }
  agent: {
    label: string
    run_dir: string
    summary: CultureAssessmentStaticViewSummary
  }
  radar: {
    labels: string[]
    series: Array<{ name: string; values: number[]; color: string }>
  }
  sample_pairs: CultureAssessmentSamplePair[]
  reference_samples?: CultureAssessmentReferenceSample[]
}

export async function fetchCultureAssessmentDatasets() {
  return request.get('/output/culture-assessment/datasets') as unknown as Promise<{
    source: 'culture_assessment_static'
    repo_root: string
    datasets: CultureAssessmentDatasetDTO[]
  }>
}

export async function fetchCultureAssessmentStaticViews() {
  return request.get('/output/culture-assessment/static-views') as unknown as Promise<{
    source: 'culture_assessment_static'
    repo_root: string
    views: Array<{
      id: string
      title: string
      dataset_id: string
      dataset_label: string
      highlights?: string[]
      advantage_summary?: string
    }>
  }>
}

export async function fetchCultureAssessmentStaticView(viewId: string) {
  return request.get(
    `/output/culture-assessment/static-views/${encodeURIComponent(viewId)}`,
  ) as unknown as Promise<CultureAssessmentStaticViewDTO>
}

export interface CultureAssessmentConsoleDataset {
  id: string
  label: string
  sample_count: number
  description?: string
  preview_sample_id?: string
  preview_ethnic_group?: string
  preview_difficulty_level?: string
}

export interface CultureAssessmentConsoleJob {
  job_id: string
  status: string
  running?: boolean
  progress?: number
  completed?: number
  total?: number
  target_mode?: 'direct' | 'agent' | string
  dataset_id?: string
  dataset_label?: string
  output_dir?: string
  log_tail?: string[]
  error?: string
  cached?: boolean
  cache_key?: string
  cache_saved_at?: string
}

export interface CultureAssessmentConsoleJobResult {
  dataset_label?: string
  target_mode?: 'direct' | 'agent' | string
  summary?: CultureAssessmentStaticViewSummary
  radar?: CultureAssessmentStaticViewDTO['radar']
  sample_results?: Array<Record<string, unknown>>
  attribution?: Array<Record<string, unknown>>
  cached?: boolean
  cache_key?: string
  cache_saved_at?: string
}

export function fetchCultureAssessmentConsoleHealth() {
  return request.get('/output/culture-assessment/console/health') as unknown as Promise<{
    active_jobs?: number
    dataset_count?: number
    status?: string
  }>
}

export function fetchCultureAssessmentConsoleDatasets() {
  return request.get('/output/culture-assessment/console/datasets') as unknown as Promise<{
    datasets: CultureAssessmentConsoleDataset[]
  }>
}

export function fetchCultureAssessmentConsoleJobs() {
  return request.get('/output/culture-assessment/console/jobs') as unknown as Promise<{
    jobs: CultureAssessmentConsoleJob[]
  }>
}

export function startCultureAssessmentConsoleJob(payload: {
  dataset_id: string
  target_mode: 'reference' | 'direct' | 'agent'
  run_suffix?: string
  limit?: string
  offset?: string
}) {
  return request.post(
    '/output/culture-assessment/console/jobs',
    payload,
  ) as unknown as Promise<CultureAssessmentConsoleJob>
}

export function fetchCultureAssessmentConsoleJob(jobId: string) {
  return request.get(
    `/output/culture-assessment/console/jobs/${encodeURIComponent(jobId)}`,
  ) as unknown as Promise<CultureAssessmentConsoleJob>
}

export function fetchCultureAssessmentConsoleJobResults(jobId: string) {
  return request.get(
    `/output/culture-assessment/console/jobs/${encodeURIComponent(jobId)}/results`,
  ) as unknown as Promise<CultureAssessmentConsoleJobResult>
}

export function stopCultureAssessmentConsoleJob(jobId: string) {
  return request.post(
    `/output/culture-assessment/console/jobs/${encodeURIComponent(jobId)}/stop`,
  ) as unknown as Promise<CultureAssessmentConsoleJob>
}

export interface GuardrailDemoPack {
  pack_id: string
  title: string
  model_id: string
  language: string
  sample_count: number
}

export interface GuardrailLiveSample {
  id: string
  prompt: string
  response: string
  detect_status: 'pending' | 'running' | 'done' | 'error'
  pred_safe_type: string | null
  pred_risk_level: string | null
  pred_category: string | null
  pred_category_code: string | null
  risk_evidence: unknown[]
  rewrite_status: 'pending' | 'running' | 'done' | 'skipped' | 'error'
  disposition: string
  edited_text: string
  post_safety_label: string
  error: string | null
}

export interface GuardrailLiveJob {
  job_id: string
  pack_id: string
  status: 'pending' | 'running' | 'finished' | 'partial' | 'error'
  source: string
  progress: {
    detect_done: number
    detect_total: number
    rewrite_done: number
    rewrite_total: number
  }
  samples: GuardrailLiveSample[]
}

export interface GuardrailLiveStart {
  job_id: string
  status: string
  pack_id: string
  sample_count: number
}

export function fetchGuardrailDemoPacks() {
  return request.get<GuardrailDemoPack[]>('/output/guardrail/demo-packs')
}

export function startGuardrailLiveBatch(payload: { pack_id: string; max_samples?: number }) {
  return request.post<GuardrailLiveStart>('/output/guardrail/live-batch', payload)
}

export function fetchGuardrailLiveBatch(jobId: string) {
  return request.get<GuardrailLiveJob>(`/output/guardrail/live-batch/${encodeURIComponent(jobId)}`)
}

export interface CultureGuardrailBatchRequest {
  candidate_responses_path?: string
  limit?: number
  model_id?: string
  language?: string
  generate_neutral_candidate?: boolean
}

export interface GeneralRiskDetection {
  ok: boolean
  pred_safe_type?: string | null
  pred_risk_level?: string | number | null
  pred_category?: string | null
  pred_category_code?: string | null
  risk_evidence?: unknown[]
  error?: string | null
}

export interface CultureJudgeResult {
  score?: number
  mentioned_ethnic_group?: string
  reason?: string
}

export interface CultureAssessment {
  status?: string
  error?: string
  culture_dimension_recognition?: number
  cultural_substantive_response?: number
  culture_composite_pass?: boolean
  culture_risk_category?: string
  ethnic_mention_judge?: CultureJudgeResult
  cultural_difference_judge?: CultureJudgeResult
  neutralized_question?: string
  neutral_answer_source?: string
  neutral_answer?: string
}

export interface CulturalRewrite {
  status?: string
  reason?: string
  model_name?: string
  model_version?: string
  rewritten_response?: string
  rewrite_reason?: string
  fixed_issues?: string[]
  remaining_risk?: string
}

export interface CultureGuardrailScene {
  background?: string
  user_query?: string
  implied_ethnic_group?: string
  difficulty_level?: string
  background_type?: string
  cultural_knowledge_points?: string[] | string
  reference_answer?: string
  expected_neutral_answer?: string
}

export interface CultureGuardrailSample {
  batch_id: string
  index: number
  id: string
  source_scene_run_id?: string
  source_scene_sample_id?: string
  model_provider?: string
  model_name?: string
  model_version?: string
  prompt: string
  candidate_response: string
  pred_safe_type?: string | null
  pred_risk_level?: string | number | null
  pred_category?: string | null
  pred_category_code?: string | null
  risk_evidence?: unknown[]
  scene?: CultureGuardrailScene
  general_risk_detection?: GeneralRiskDetection
  culture_assessment?: CultureAssessment
  general_compliance_rewrite?: Record<string, unknown>
  cultural_rewrite?: CulturalRewrite
  recommendation?: string
  final_recommended_response?: string
  processed_at?: string
}

export interface CultureGuardrailSummary {
  total: number
  general_detect_ok: number
  general_detect_error: number
  culture_pass: number
  culture_fail: number
  general_rewrite_done: number
  cultural_rewrite_done: number
}

export interface CultureGuardrailBatchResponse {
  batch_id: string
  status: string
  sample_count: number
  output_dir: string
  results_path: string
  manifest_path: string
  summary: CultureGuardrailSummary
  samples: CultureGuardrailSample[]
}

export function runCultureGuardrailBatch(payload: CultureGuardrailBatchRequest) {
  return request.post<CultureGuardrailBatchResponse>('/output/guardrail/culture-batch', payload, {
    timeout: 900000,
  })
}
