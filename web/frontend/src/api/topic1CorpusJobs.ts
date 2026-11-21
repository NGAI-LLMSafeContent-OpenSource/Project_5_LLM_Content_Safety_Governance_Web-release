import request from '@/api/request'
import axios from 'axios'
import { createUuid } from '@/utils/uuid'

export interface CorpusJob {
  id: string
  tool: string
  operation: string
  source_name: string
  sample_count: number
  status: string
  progress: number | null
  error_code: string
  created_at: string
  result_available: boolean
  result_sha256: string | null
}

export interface CorpusJobRequest {
  request_id: string
  tool: 'refinement' | 'detox' | 'detection'
  operation: string
  source_name: string
  records: Array<{ id: string; text: string }>
  model_alias: string
  confirmed: true
}

export interface CorpusJobResult {
  job: CorpusJob
  result: {
    samples: Array<Record<string, string | number | boolean | null>>
    scope: string
    assets?: Array<{
      key: string
      name: string
      size_bytes?: number
      sha256?: string
      archived?: boolean
    }>
  }
}

function config() {
  const storageKey = 'project5-input-tool-client'
  let id = localStorage.getItem(storageKey)
  if (!id) {
    id = createUuid()
    localStorage.setItem(storageKey, id)
  }
  return { headers: { 'X-Input-Client-Id': id }, timeout: 70000 }
}

const base = '/data-input/topic1/jobs'
export const listCorpusJobs = (offset = 0) =>
  request.get<{ items: CorpusJob[]; active: CorpusJob[]; has_more: boolean }>(base, {
    ...config(),
    params: { offset },
  })
export const fingerprintCorpusRequest = (payload: CorpusJobRequest) =>
  request.post<string>(`${base}/fingerprint`, payload, config())
export const getCorpusModels = () =>
  request.get<Array<{ alias: string; label: string }>>(`${base}/models`)
export const startCorpusJob = (payload: CorpusJobRequest) =>
  request.post<CorpusJob>(base, payload, config())
export const refreshCorpusJob = (id: string) =>
  request.post<CorpusJob>(`${base}/${encodeURIComponent(id)}/refresh`, {}, config())
export const cancelCorpusJob = (id: string) =>
  request.post<CorpusJob>(`${base}/${encodeURIComponent(id)}/cancel`, {}, config())
export const getCorpusJobResult = (id: string) =>
  request.get<CorpusJobResult>(`${base}/${encodeURIComponent(id)}/result`, config())

export const archiveCorpusAsset = (id: string, key: string) =>
  request.post(
    `${base}/${encodeURIComponent(id)}/assets/${encodeURIComponent(key)}/archive`,
    { confirmed: true },
    config(),
  )

export async function downloadCorpusAsset(id: string, key: string, filename: string) {
  const response = await axios.get(
    `${import.meta.env.VITE_API_BASE_URL || '/api'}${base}/${encodeURIComponent(id)}/assets/${encodeURIComponent(key)}`,
    { ...config(), responseType: 'blob' },
  )
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
