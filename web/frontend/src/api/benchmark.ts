import axios from 'axios'
import http from './request'
import type {
  BenchmarkAssetRegistryResponse,
  BenchmarkArtifactItem,
  BenchmarkArtifactsResponse,
  BenchmarkLiveRunSummaryResponse,
  BenchmarkCbrneQueryFilters,
  BenchmarkCbrneSampleDetail,
  BenchmarkCbrneSampleDisclosure,
  BenchmarkCbrneSampleDisclosureRequest,
  BenchmarkCbrneSampleRefResponse,
  BenchmarkCbrneSampleRefsResponse,
  BenchmarkCbrneSamplesQueryResponse,
  BenchmarkDatasetSnapshotImportPayload,
  BenchmarkDatasetSnapshotImportResponse,
  BenchmarkPrerunImportPayload,
  BenchmarkPrerunImportResponse,
  BenchmarkTopic1ValueQaGroupsResponse,
  BenchmarkTopic1ValueQaGroupDetail,
  BenchmarkTopic1ValueQaRecheckSummary,
  BenchmarkTopic2PrerunPairsResponse,
  BenchmarkTopic3RiskAssetVersion,
  BenchmarkTopic3RiskAssetVersionsResponse,
  BenchmarkTopic3RiskEvaluationSummary,
  BenchmarkTopic3CulturalSampleDetail,
  BenchmarkTopic3CulturalSamplesResponse,
  BenchmarkTopic3CulturalSummary,
  BenchmarkTopic3RiskSampleDetail,
  BenchmarkTopic3RiskSamplesResponse,
  BenchmarkTopic3RiskTaxonomyResponse,
  BenchmarkTask,
  BenchmarkTaskCreatePayload,
  BenchmarkTaskLogsResponse,
  Topic2OptionsResponse,
  Topic2RuntimeResponse,
  Topic2SeedbankStatsResponse,
  Topic1RuntimeResponse,
  Topic1ValueQaTopicsResponse,
} from '@/types'

export function createBenchmarkTask(payload: BenchmarkTaskCreatePayload) {
  return http.post<BenchmarkTask>('/benchmark/tasks', payload)
}

export function getBenchmarkTask(taskId: string) {
  return http.get<BenchmarkTask>(`/benchmark/tasks/${taskId}`)
}

export function getBenchmarkTaskLogs(
  taskId: string,
  params?: { after_id?: number; limit?: number },
) {
  return http.get<BenchmarkTaskLogsResponse>(`/benchmark/tasks/${taskId}/logs`, { params })
}

export function getBenchmarkTaskArtifacts(taskId: string) {
  return http.get<BenchmarkArtifactsResponse>(`/benchmark/tasks/${taskId}/artifacts`)
}

/** Thin evalset zip (README + meta.json + samples.jsonl). Bypasses JSON envelope client. */
export async function downloadBenchmarkEvalset(taskId: string): Promise<Blob> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
  try {
    const response = await axios.get(
      `${baseURL}/benchmark/tasks/${encodeURIComponent(taskId)}/evalset`,
      {
        responseType: 'blob',
        timeout: 120000,
      },
    )
    const contentType = String(response.headers['content-type'] || '')
    if (contentType.includes('application/json')) {
      throw new Error(await readBlobErrorMessage(response.data as Blob))
    }
    return response.data as Blob
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      throw new Error(await readBlobErrorMessage(error.response.data))
    }
    if (error instanceof Error) {
      throw error
    }
    throw new Error('下载评测集失败')
  }
}

async function readBlobErrorMessage(blob: Blob): Promise<string> {
  try {
    const text = await blob.text()
    const payload = JSON.parse(text) as { detail?: unknown; msg?: unknown }
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
    if (typeof payload.msg === 'string' && payload.msg.trim()) {
      return payload.msg
    }
  } catch {
    // fall through
  }
  return '下载评测集失败'
}

export function getBenchmarkAssets(params?: { source_mode?: string }) {
  return http.get<BenchmarkAssetRegistryResponse>('/benchmark/assets', { params })
}

export function getBenchmarkAsset(assetId: string) {
  return http.get<BenchmarkArtifactItem>(`/benchmark/assets/${encodeURIComponent(assetId)}`)
}

export function getBenchmarkLiveRunSummary(assetId: string, params?: { sample_limit?: number }) {
  return http.get<BenchmarkLiveRunSummaryResponse>(
    `/benchmark/assets/${assetId}/live-run/summary`,
    { params },
  )
}

export function importBenchmarkPrerunAsset(payload: BenchmarkPrerunImportPayload) {
  return http.post<BenchmarkPrerunImportResponse>('/benchmark/assets/prerun/import', payload)
}

export function importBenchmarkDatasetSnapshotAsset(
  payload: BenchmarkDatasetSnapshotImportPayload,
) {
  return http.post<BenchmarkDatasetSnapshotImportResponse>(
    '/benchmark/assets/dataset-snapshot/import',
    payload,
  )
}

export function queryCbrneAnomalySamples(
  assetId: string,
  params?: BenchmarkCbrneQueryFilters & {
    limit?: number
    offset?: number
  },
) {
  return http.get<BenchmarkCbrneSamplesQueryResponse>(
    `/benchmark/assets/${assetId}/cbrne-anomaly/samples`,
    { params },
  )
}

export function getCbrneSampleRefs(assetId: string, params?: { limit?: number; offset?: number }) {
  return http.get<BenchmarkCbrneSampleRefsResponse>(
    `/benchmark/assets/${assetId}/cbrne/sample-refs`,
    { params },
  )
}

export function getCbrneSampleRef(assetId: string, sampleId: string) {
  return http.get<BenchmarkCbrneSampleRefResponse>(
    `/benchmark/assets/${assetId}/cbrne/sample-refs/${encodeURIComponent(sampleId)}`,
  )
}

export function getCbrneSampleDetail(assetId: string, sampleId: string) {
  return http.get<BenchmarkCbrneSampleDetail>(
    `/benchmark/assets/${assetId}/cbrne/samples/${encodeURIComponent(sampleId)}`,
  )
}

export function discloseCbrneSample(
  assetId: string,
  sampleId: string,
  disclosureRequestId: string,
) {
  const payload: BenchmarkCbrneSampleDisclosureRequest = { disclosureRequestId }
  return http.post<BenchmarkCbrneSampleDisclosure>(
    `/benchmark/assets/${assetId}/cbrne/samples/${encodeURIComponent(sampleId)}/disclosures`,
    payload,
  )
}

export function getTopic2PrerunPairs(
  assetId: string,
  params?: {
    moderator?: string
    verdict?: 'blocked' | 'bypassed'
    difficulty?: 'simple' | 'hard'
    strategy?: string
    limit?: number
    offset?: number
  },
) {
  return http.get<BenchmarkTopic2PrerunPairsResponse>(
    `/benchmark/assets/${assetId}/topic2-prerun/samples`,
    { params },
  )
}

export function getTopic1ValueQaGroups(
  assetId: string,
  params?: {
    topic?: string
    primary_dimension?: string
    secondary_dimension?: string
    qc_status?: 'not_sampled' | 'qc_sampled'
    keyword?: string
    limit?: number
    offset?: number
  },
) {
  return http.get<BenchmarkTopic1ValueQaGroupsResponse>(
    `/benchmark/assets/${assetId}/topic1-value-qa/groups`,
    { params },
  )
}

export function getTopic1ValueQaGroupDetail(assetId: string, groupId: string) {
  return http.get<BenchmarkTopic1ValueQaGroupDetail>(
    `/benchmark/assets/${assetId}/topic1-value-qa/groups/${encodeURIComponent(groupId)}`,
  )
}

export function getTopic1ValueQaRecheckSummary(assetId: string) {
  return http.get<BenchmarkTopic1ValueQaRecheckSummary>(
    `/benchmark/assets/${assetId}/topic1-value-qa/recheck-summary`,
  )
}

export function getTopic3RiskSamples(
  assetId: string,
  params?: {
    risk_level_id?: string
    category?: string
    keyword?: string
    limit?: number
    offset?: number
  },
) {
  return http.get<BenchmarkTopic3RiskSamplesResponse>(
    `/benchmark/assets/${assetId}/topic3-risk/samples`,
    { params },
  )
}

export function getTopic3RiskSampleDetail(assetId: string, sampleId: string) {
  return http.get<BenchmarkTopic3RiskSampleDetail>(
    `/benchmark/assets/${assetId}/topic3-risk/samples/${encodeURIComponent(sampleId)}`,
  )
}

export function getTopic3RiskEvaluationSummary(assetId: string) {
  return http.get<BenchmarkTopic3RiskEvaluationSummary>(
    `/benchmark/assets/${assetId}/topic3-risk/evaluations/summary`,
  )
}

export function getTopic3RiskTaxonomy() {
  return http.get<BenchmarkTopic3RiskTaxonomyResponse>('/benchmark/topic3-risk/taxonomy')
}

/** All registered versions of the topic3 risk Benchmark; the server picks the current one. */
export function getTopic3RiskAssetVersions() {
  return http.get<BenchmarkTopic3RiskAssetVersionsResponse>('/benchmark/topic3-risk/assets')
}

export function getResolvedTopic3RiskAsset(params: { asset_version?: string; asset_id?: string }) {
  return http.get<BenchmarkTopic3RiskAssetVersion>('/benchmark/topic3-risk/assets/resolve', {
    params,
  })
}

/** Same-version evaluator results; omit params to let the server resolve the current asset. */
export function getTopic3RiskSameVersionEvaluationSummary(params?: {
  asset_version?: string
  asset_id?: string
}) {
  return http.get<BenchmarkTopic3RiskEvaluationSummary>(
    '/benchmark/topic3-risk/evaluations/summary',
    { params },
  )
}

export function ensureTopic3CulturalAsset() {
  return http.post<BenchmarkPrerunImportResponse>('/benchmark/assets/topic3-cultural/ensure')
}

export function getTopic3CulturalSamples(
  assetId: string,
  params?: {
    ethnic_group?: string
    difficulty_level?: string
    keyword?: string
    limit?: number
    offset?: number
  },
) {
  return http.get<BenchmarkTopic3CulturalSamplesResponse>(
    `/benchmark/assets/${assetId}/topic3-cultural/samples`,
    { params },
  )
}

export function getTopic3CulturalSampleDetail(assetId: string, sampleId: string) {
  return http.get<BenchmarkTopic3CulturalSampleDetail>(
    `/benchmark/assets/${assetId}/topic3-cultural/samples/${encodeURIComponent(sampleId)}`,
  )
}

export function getTopic3CulturalSummary(assetId: string) {
  return http.get<BenchmarkTopic3CulturalSummary>(
    `/benchmark/assets/${assetId}/topic3-cultural/summary`,
  )
}

export function getTopic2Options() {
  return http.get<Topic2OptionsResponse>('/benchmark/topic2/options')
}

export function getTopic1ValueQaTopics() {
  return http.get<Topic1ValueQaTopicsResponse>('/benchmark/topic1/value-qa-topics')
}

export function getTopic1Runtime() {
  return http.get<Topic1RuntimeResponse>('/benchmark/topic1/runtime')
}

export function getTopic2SeedbankStats() {
  return http.get<Topic2SeedbankStatsResponse>('/benchmark/topic2/seedbank-stats')
}

export function getTopic2Runtime() {
  return http.get<Topic2RuntimeResponse>('/benchmark/topic2/runtime')
}
