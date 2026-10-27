import request from './request'
import type { TabKey } from '@/types'

export type MiningTaskStatus = 'pending' | 'running' | 'completed' | 'failed'
export type CandidateReviewStatus = 'pending_review' | 'adopted' | 'rejected' | 'edited'

export interface MiningInputSave {
  definition_type: string
  policy_text?: string
  sample_text?: string
  uploaded_document_ids: number[]
  web_links: string[]
  lookup_names: string[]
  mining_demand: string
  level1?: string | null
  level2?: string | null
}

export interface UploadedDocumentParseResult {
  count: number
  files: ParsedSourceDocument[]
  failures?: ParsedSourceDocumentFailure[]
}

export interface ParsedSourceDocumentFailure {
  name: string
  reason: string
}

export interface ParsedSourceDocument {
  id: number
  name: string
  content: string
  source_type: string
  source_url: string | null
}

export interface MiningTaskStats {
  input_text_count?: number
  matched_path_count?: number
  candidate_count?: number
  dropped_duplicate_count?: number
  adapter_version?: string
  adapter_mode?: string
  [key: string]: number | string | undefined
}

export interface MiningTaskStartResult {
  task_id: string
  input_id: number
  task_type: string
  definition_scope: TabKey
  subject_area: string
  parent_task_id: string | null
  retry_count: number
  status: MiningTaskStatus
  failure_stage?: string
  stats: MiningTaskStats
  progress?: number
}

export interface MiningTaskDetail extends MiningTaskStartResult {
  definition_type: string
  failure_stage?: string
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string
  candidate_count?: number
  saved_to_history?: boolean
  history_title?: string | null
  saved_at?: string | null
}

export interface CandidateIndicator {
  id: number
  name: string
  definition_type: string
  level1: string
  level2: string
  level3: string
  definition: string
  source: string
  formula: string
  rationale: string
  evidence_text: string
  confidence: number
  status: CandidateReviewStatus
}

export interface MiningTaskResults extends MiningTaskDetail {
  candidate_indicators: CandidateIndicator[]
}

export interface MiningTaskLog {
  id: number
  task_id: string
  agent_name: string
  status: string
  message: string
  created_at: string
}

export interface MiningTaskArtifact {
  artifact_type: string
  content: unknown
}

export interface MiningTaskArtifacts {
  task_id: string
  artifacts: MiningTaskArtifact[]
}

export interface CandidateUpdatePayload {
  name: string
  level1: string
  level2: string
  level3: string
  definition: string
  source: string
  formula: string
  rationale: string
  evidence_text: string
}

export interface CandidateReviewResult {
  candidate_id: number
  candidate_status: CandidateReviewStatus
  indicator_id?: number
}

export function definitionTypeForTab(tab: TabKey) {
  const map: Record<TabKey, 'value' | 'risk' | 'culture' | 'scene'> = {
    'input-value': 'value',
    'input-risk': 'risk',
    'output-risk': 'risk',
    'output-culture': 'culture',
  }
  return map[tab]
}

export function miningTaskTypeForTab(tab: TabKey) {
  const map: Record<TabKey, 'topic1_indicator_mining' | 'rule_based_first_phase'> = {
    'input-value': 'topic1_indicator_mining',
    'input-risk': 'rule_based_first_phase',
    'output-risk': 'rule_based_first_phase',
    'output-culture': 'rule_based_first_phase',
  }
  return map[tab]
}

export function startDefinitionMiningTask(tab: TabKey, input: MiningInputSave) {
  return request.post<MiningTaskStartResult>(
    '/mining-tasks/start',
    {
      task_type: miningTaskTypeForTab(tab),
      definition_scope: tab,
      input,
    },
    { timeout: 120000 },
  ) as unknown as Promise<MiningTaskStartResult>
}

export function parseMiningInputFiles(files: File[]) {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return request.post<UploadedDocumentParseResult>(
    '/mining-inputs/parse-uploaded-files',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    },
  ) as unknown as Promise<UploadedDocumentParseResult>
}

export function getMiningTask(taskId: string) {
  return request.get<MiningTaskDetail>(
    `/mining-tasks/${taskId}`,
  ) as unknown as Promise<MiningTaskDetail>
}

export function getMiningTaskResults(taskId: string) {
  return request.get<MiningTaskResults>(
    `/mining-tasks/${taskId}/results`,
  ) as unknown as Promise<MiningTaskResults>
}

export function getMiningTaskLogs(taskId: string) {
  return request.get<MiningTaskLog[]>(`/mining-tasks/${taskId}/logs`) as unknown as Promise<
    MiningTaskLog[]
  >
}

export function getMiningTaskArtifacts(taskId: string) {
  return request.get<MiningTaskArtifacts>(
    `/mining-tasks/${taskId}/artifacts`,
  ) as unknown as Promise<MiningTaskArtifacts>
}

export interface MiningTaskSummary extends MiningTaskDetail {
  started_at?: string | null
  finished_at?: string | null
  created_at?: string
  candidate_count?: number
}

export function listMiningTaskHistory(definitionScope: TabKey, limit = 20) {
  return request.get<MiningTaskSummary[]>('/mining-tasks/history', {
    params: { definition_scope: definitionScope, limit },
  }) as unknown as Promise<MiningTaskSummary[]>
}

export function getMiningTaskHistoryResults(taskId: string, definitionScope: TabKey) {
  return request.get<MiningTaskResults>(`/mining-tasks/${taskId}/history-results`, {
    params: { definition_scope: definitionScope },
  }) as unknown as Promise<MiningTaskResults>
}

export function saveMiningTaskToHistory(taskId: string, title = '') {
  return request.post<MiningTaskSummary>(`/mining-tasks/${taskId}/save-history`, {
    title,
  }) as unknown as Promise<MiningTaskSummary>
}

export function adoptCandidateIndicator(candidateId: number, comment = '') {
  return request.post<CandidateReviewResult>(`/candidate-indicators/${candidateId}/adopt`, {
    comment,
  }) as unknown as Promise<CandidateReviewResult>
}

export function rejectCandidateIndicator(candidateId: number, comment = '') {
  return request.post<CandidateReviewResult>(`/candidate-indicators/${candidateId}/reject`, {
    comment,
  }) as unknown as Promise<CandidateReviewResult>
}

export function updateCandidateIndicator(candidateId: number, payload: CandidateUpdatePayload) {
  return request.put<CandidateReviewResult>(
    `/candidate-indicators/${candidateId}`,
    payload,
  ) as unknown as Promise<CandidateReviewResult>
}
