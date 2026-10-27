import request from './request'
import type { AssessmentRecord, Dataset, LineageEdge, LineageNode, PaginatedData } from '@/types'
import type { DataInputWorkflowPayload } from '@/utils/inputWorkflowPayload'
import type { Topic1CorpusToolCatalogResult } from '@/types/topic1CorpusTools'

export const TOPIC4_LINEAGE_BUILD_TIMEOUT_MS = 120000

export interface DataInputWorkflowSaveResult {
  workflowId: string
  status: 'draft' | 'submitted' | 'archived'
  savedAt: string
  title: string
}

export interface DataInputWorkflowSaveRequest {
  workflow_id?: string
  title?: string
  source?: 'wizard' | 'input_guardrail'
  payload: Record<string, unknown> | DataInputWorkflowPayload
  summary?: Record<string, unknown>
  asset_refs?: Record<string, unknown>
}

export interface DataInputWorkflowListItem {
  workflowId: string
  title: string
  status: 'draft' | 'submitted' | 'archived'
  source: string
  summary: Record<string, unknown>
  assetRefs: Record<string, unknown>
  createdAt: string
  updatedAt: string
  submittedAt: string | null
}

export interface DataInputWorkflowDetail extends DataInputWorkflowListItem {
  payload: Record<string, unknown>
}

export interface DataInputWorkflowListResult {
  items: DataInputWorkflowListItem[]
}

export interface IntegrationEndpoint {
  method: string
  path: string
  purpose: string
  ready: boolean
}

export interface Topic4LineageHealth {
  connected: boolean
  service: string
  base_url: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
}

export interface Topic4LineageNode {
  id: string
  type: string
  summary: string
  url: string
  docName: string
  docId: string
  topic: string
  pipeline: string
  isRisky: boolean
  riskLevel: string
  riskTypes: string[]
}

export interface Topic4LineageEdge {
  id: string
  source: string
  target: string
  type: string
}

export interface Topic4LineageSummary {
  totalNodes: number
  totalEdges: number
  metaCount: number
  chunkCount: number
  cleanedChunkCount: number
  questionCount: number
  answerCount: number
  riskyNodes: number
  cleanNodes: number
}

export interface Topic4WorkflowStage {
  key: string
  label: string
  status: string
  description: string
}

export interface Topic4LineageResult {
  connected: boolean
  service: string
  base_url: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  summary: Topic4LineageSummary
  nodes: Topic4LineageNode[]
  edges: Topic4LineageEdge[]
  workflowMode: string
  workflowStages: Topic4WorkflowStage[]
  annotations: Array<Record<string, unknown>>
  cleaningActions: Array<Record<string, unknown>>
  reportSummary: string
  selectedNodeId: string
}

export interface Topic4LineageBuildPayload {
  records?: Array<Record<string, unknown>>
  risk_annotations?: Array<Record<string, unknown>>
}

export interface Topic4LineageParseResult {
  records: Array<Record<string, unknown>>
  failures: Array<{ name: string; reason: string }>
  source: string
}

export interface Topic2FilterGuardHealth {
  connected: boolean
  service: string
  base_url: string
  message: string
  source: string
  mode: string
  method: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
}

export interface Topic2KeywordFinding {
  keyword: string
  evidence: string
  risk_type: string
}

export interface Topic2KeywordPrediction {
  id: string
  text: string
  source_index: number
  lineage_node_id: string
  lineage_node_label: string
  risk_category_l1: string
  risk_category_l2: string
  predicted_l1_id?: string
  detect_method?: string
  action?: string
  score: number
  threshold: number
  prediction: number
  is_abnormal: boolean
  status: string
  suggestion: string
  evidence_chain: string[]
  correction_contract_status: string
  findings: Topic2KeywordFinding[]
}

export interface Topic2KeywordResult {
  connected: boolean
  service: string
  base_url: string
  message: string
  source: string
  mode: string
  method: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  total: number
  abnormal_count: number
  normal_count: number
  predictions: Topic2KeywordPrediction[]
}

export interface Topic2RiskScanItem {
  text: string
  lineage_node_id?: string
  lineage_node_label?: string
  risk_category_l1?: string
  risk_category_l2?: string
}

export interface Topic2RiskScanTaskResult {
  task_id: string
  status: string
  progress: number
  message: string
  cancellable: boolean
  method?: string
  result: Topic2KeywordResult | null
}

export interface Topic2PrerunSampleRow {
  id: string
  score: number
  status: string
  snippet: string
  suggestion: string
  difficulty_level: string
  pair_id: string
  harm_category_l1: string
  harm_category_l2: string
  strategy_chain: string[]
  bypassed_moderators: string[]
}

export interface Topic2PrerunSamplesResult {
  connected: boolean
  service: string
  base_url: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  asset_id: string
  asset_name: string
  total: number
  pair_count: number
  moderators: string[]
  l1_labels: string[]
  rows: Topic2PrerunSampleRow[]
}

export interface InputGuardrailDemoPack {
  pack_id: string
  title: string
  language: string
  mode: string
  sample_count: number
  description: string
}

export interface InputGuardrailLiveRunItem {
  id?: string
  text: string
  demo_category?: string
  language?: string
  track?: 'value' | 'risk' | 'general' | string
  domain?: string
  source_asset_id?: string
  source_file?: string
  source_sample_id?: string
  source_label?: string
  source_name?: string
  ethnic_group?: string
  difficulty_level?: string
  background_type?: string
  cultural_knowledge_points?: string[]
  expected_issue?: string
  expected_disposition?: string
  demo_note?: string
}

export interface InputGuardrailLiveEvidence {
  type: string
  title: string
  detail: string
}

export interface InputGuardrailLiveSample {
  id: string
  text: string
  demo_category: string
  language: string
  track: 'value' | 'risk' | 'general' | string
  domain: string
  source_asset_id: string
  source_file: string
  source_sample_id: string
  source_label: string
  source_name: string
  ethnic_group: string
  difficulty_level: string
  background_type: string
  cultural_knowledge_points: string[]
  expected_issue: string
  expected_disposition: string
  demo_note: string
  value_dimension: { primary: string; secondary: string; quality_level: string } | null
  culture_dimension: {
    ethnic_group: string
    difficulty_level: string
    background_type: string
    dimensions: string[]
    knowledge_ids: string[]
  } | null
  detect_status: string
  value_result: Record<string, unknown>
  risk_result: Record<string, unknown>
  lineage_result: Record<string, unknown>
  evidence: InputGuardrailLiveEvidence[]
  fix_suggestion: string
  disposition: string
  error: string | null
}

export interface InputGuardrailLiveRun {
  job_id: string
  pack_id: string
  status: 'pending' | 'running' | 'finished' | 'partial' | 'error' | string
  source: string
  mode: string
  service_status: Record<string, unknown>
  progress: { detect_done: number; detect_total: number }
  samples: InputGuardrailLiveSample[]
  created_at: string
  finished_at: string | null
}

export interface InputGuardrailLiveRunStartResult {
  job_id: string
  pack_id: string
  status: string
  source: string
  mode: string
  sample_count: number
  created_at: string
}

export function fetchInputGuardrailDemoPacks() {
  return request.get('/data-input/guardrail/demo-packs') as unknown as Promise<
    InputGuardrailDemoPack[]
  >
}

export function startInputGuardrailLiveRun(payload: {
  pack_id?: string
  items?: InputGuardrailLiveRunItem[]
  max_samples?: number
}) {
  return request.post(
    '/data-input/guardrail/live-run',
    payload,
  ) as unknown as Promise<InputGuardrailLiveRunStartResult>
}

export function fetchInputGuardrailLiveRun(jobId: string) {
  return request.get(
    `/data-input/guardrail/live-run/${jobId}`,
  ) as unknown as Promise<InputGuardrailLiveRun>
}

export function getDatasets(query?: { type?: string; keyword?: string }) {
  return request.get<PaginatedData<Dataset>>('/data-input/datasets', { params: query })
}

export function uploadFile(formData: FormData) {
  return request.post<{ fileId: string }>('/data-input/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function buildLineage(datasetId: string) {
  return request.post<{ nodes: LineageNode[]; edges: LineageEdge[] }>('/data-input/lineage', {
    datasetId,
  })
}

export function getTopic4LineageHealth() {
  return request.get('/data-input/topic4/lineage/health') as unknown as Promise<Topic4LineageHealth>
}

export function getTopic4StaticLineage() {
  return request.get('/data-input/topic4/lineage/static') as unknown as Promise<Topic4LineageResult>
}

export function parseTopic4LineageRecords(formData: FormData) {
  return request.post('/data-input/topic4/lineage/parse-records', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  }) as unknown as Promise<Topic4LineageParseResult>
}

export function buildTopic4Lineage(payload: Topic4LineageBuildPayload = {}) {
  return request.post('/data-input/topic4/lineage/build', payload, {
    timeout: TOPIC4_LINEAGE_BUILD_TIMEOUT_MS,
  }) as unknown as Promise<Topic4LineageResult>
}

export function getTopic2FilterGuardHealth(params?: { method?: string }) {
  return request.get('/data-input/topic2/filterguard/health', {
    params,
  }) as unknown as Promise<Topic2FilterGuardHealth>
}

export function runTopic2KeywordDetection(texts: string[]) {
  return request.post('/data-input/topic2/filterguard/predict', {
    texts,
  }) as unknown as Promise<Topic2KeywordResult>
}

export function startTopic2RiskScanTask(
  items: Topic2RiskScanItem[],
  options?: { method?: string },
) {
  return request.post('/data-input/topic2/risk-scan-tasks', {
    items,
    method: options?.method || '',
  }) as unknown as Promise<Topic2RiskScanTaskResult>
}

export function getTopic2RiskScanTask(taskId: string) {
  return request.get(
    `/data-input/topic2/risk-scan-tasks/${taskId}`,
  ) as unknown as Promise<Topic2RiskScanTaskResult>
}

export function cancelTopic2RiskScanTask(taskId: string) {
  return request.post(
    `/data-input/topic2/risk-scan-tasks/${taskId}/cancel`,
  ) as unknown as Promise<Topic2RiskScanTaskResult>
}

export function getTopic2PrerunSamples(params?: { asset_id?: string; limit?: number }) {
  return request.get('/data-input/topic2/prerun-samples', {
    params,
  }) as unknown as Promise<Topic2PrerunSamplesResult>
}

export type InputCorpusKind = 'value_qa' | 'topic2_prerun' | 'risk_static_dynbench'

export interface InputCorpusCatalogItem {
  asset_id: string
  name: string
  kind: InputCorpusKind | string
  source_label: string
  sample_count: number
  ready: boolean
  description: string
  track_hint: string
  track?: 'value' | 'risk' | string
}

export interface InputCorpusCatalogResult {
  connected: boolean
  message: string
  items: InputCorpusCatalogItem[]
  next_action: string
}

export interface InputCorpusRecord {
  id: string
  text: string
  meta: Record<string, string>
}

export interface InputCorpusSelectResult {
  connected: boolean
  message: string
  asset_id: string
  asset_name: string
  kind: InputCorpusKind | string
  source_label: string
  total: number
  records: InputCorpusRecord[]
  blocking_reason: string
  next_action: string
}

export function getInputCorpusCatalog() {
  return request.get('/data-input/corpus-catalog') as unknown as Promise<InputCorpusCatalogResult>
}

export function getTopic1CorpusToolCatalog() {
  return request.get(
    '/data-input/topic1/corpus-tools',
  ) as unknown as Promise<Topic1CorpusToolCatalogResult>
}

export function getInputCorpusRecords(params: { asset_id: string; kind?: string; limit?: number }) {
  return request.get(`/data-input/corpus/${encodeURIComponent(params.asset_id)}/records`, {
    params: {
      kind: params.kind,
      limit: params.limit,
    },
  }) as unknown as Promise<InputCorpusSelectResult>
}

export interface AttributionIssueSpan {
  type: string
  sentence: string
  span: string
}

export interface AttributionFinding {
  keyword: string
  evidence: string
  risk_type: string
  label: string
}

export interface AttributionStep {
  title: string
  detail: string
}

export interface AttributionRow {
  id: string
  track: 'value' | 'risk' | string
  source: string
  status: string
  score: string
  snippet: string
  suggestion: string
  summary: string
  evidence_chain: string[]
  attribution_steps?: AttributionStep[]
  findings: AttributionFinding[]
  issue_spans: AttributionIssueSpan[]
  lineage_node_id: string
  lineage_node_label: string
  risk_category_l1: string
  risk_category_l2: string
  predicted_l1_id?: string
  detect_method?: string
  action?: string
  note?: string
  difficulty_level: string
  strategy_chain: string[]
  dimension: string
  topic: string
  true_label: string
  predicted_label: string
  quality_level: string
  group_id: string
}

export interface AttributionResult {
  connected: boolean
  track: string
  service: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  asset_id: string
  asset_name: string
  total: number
  stats: Array<{ val: string; label: string }>
  rows: AttributionRow[]
}

export function buildRiskAttribution(payload: {
  task_id?: string
  predictions?: Topic2KeywordPrediction[]
  use_prerun?: boolean
  asset_id?: string
  limit?: number
}) {
  return request.post(
    '/data-input/attribution/risk',
    payload,
  ) as unknown as Promise<AttributionResult>
}

export function getValueAttribution(params?: {
  asset_id?: string
  limit?: number
  prefer_low?: boolean
}) {
  return request.get('/data-input/attribution/value', {
    params,
  }) as unknown as Promise<AttributionResult>
}

export interface ValueQaDimensionItem {
  name: string
  kind: 'primary' | 'secondary' | string
  count: number
}

export interface ValueQaAssetStatusResult {
  connected: boolean
  service: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  asset_id: string
  asset_name: string
  total: number
  group_count: number
  qc_status: string
  trace_status: string
  quality_level_distribution: Record<string, number>
  primary_dimension_distribution: Record<string, number>
  secondary_dimension_distribution: Record<string, number>
}

export interface ValueQaDimensionsResult {
  connected: boolean
  service: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  asset_id: string
  asset_name: string
  dimensions: ValueQaDimensionItem[]
}

export interface ValueAssessmentResult {
  connected: boolean
  service: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blocking_reason: string
  next_action: string
  endpoints: IntegrationEndpoint[]
  asset_id: string
  asset_name: string
  total: number
  group_count: number
  stats: Array<{ val: string; label: string }>
  rows: AttributionRow[]
  fix_rows: AttributionRow[]
  radar_scores: Record<string, number>
  quality_level_distribution: Record<string, number>
}

export function getValueQaAssetStatus(params?: { asset_id?: string }) {
  return request.get('/data-input/value-qa/status', {
    params,
  }) as unknown as Promise<ValueQaAssetStatusResult>
}

export function getValueQaDimensions(params?: { asset_id?: string }) {
  return request.get('/data-input/value-qa/dimensions', {
    params,
  }) as unknown as Promise<ValueQaDimensionsResult>
}

export function getValueAssessment(params?: {
  asset_id?: string
  primary_dimension?: string[]
  secondary_dimension?: string[]
  limit?: number
}) {
  return request.get('/data-input/value-qa/assessment', {
    params,
  }) as unknown as Promise<ValueAssessmentResult>
}

export function getAssessments(datasetId: string, track: 'value' | 'risk') {
  return request.get<AssessmentRecord[]>('/data-input/assessments', {
    params: { datasetId, track },
  })
}

export function saveDataInputDraft(
  payload: DataInputWorkflowPayload,
  options?: Omit<DataInputWorkflowSaveRequest, 'payload'>,
) {
  return saveDataInputDraftRequest({
    ...options,
    payload,
    source: options?.source || 'wizard',
  })
}

export function submitDataInputWorkflow(
  payload: DataInputWorkflowPayload,
  options?: Omit<DataInputWorkflowSaveRequest, 'payload'>,
) {
  return submitDataInputWorkflowRequest({
    ...options,
    payload,
    source: options?.source || 'wizard',
  })
}

export function saveDataInputDraftRequest(payload: DataInputWorkflowSaveRequest) {
  return request.post<DataInputWorkflowSaveResult>('/data-input/workflows/draft', payload)
}

export function submitDataInputWorkflowRequest(payload: DataInputWorkflowSaveRequest) {
  return request.post<DataInputWorkflowSaveResult>('/data-input/workflows/submit', payload)
}

export function getDataInputWorkflow(workflowId: string) {
  return request.get<DataInputWorkflowDetail>(`/data-input/workflows/${workflowId}`)
}

export function listDataInputWorkflows(params?: {
  status?: 'draft' | 'submitted' | 'archived'
  source?: 'wizard' | 'input_guardrail'
  limit?: number
}) {
  return request.get<DataInputWorkflowListResult>('/data-input/workflows', { params })
}
