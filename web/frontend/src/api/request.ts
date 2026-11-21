import axios, { type AxiosRequestConfig } from 'axios'

import type { ApiResponse } from '@/types'

import { markGovernanceTransportError } from '@/utils/governance-turn-failure'

export class ApiRequestError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

function isGovernanceSessionCreateOrAppend(config?: AxiosRequestConfig): boolean {
  if ((config?.method ?? '').toLowerCase() !== 'post') return false
  const path = (config?.url ?? '').split('?')[0].replace(/\/+$/, '')
  if (path === '/governance/sessions' || path.endsWith('/governance/sessions')) return true
  return /\/governance\/sessions\/[^/]+\/turns$/.test(path)
}

function rejectApiError(
  error: Error,
  serverResponded: boolean,
  config?: AxiosRequestConfig,
  status?: number,
): Promise<never> {
  const requestError = new ApiRequestError(error.message, status)
  if (!isGovernanceSessionCreateOrAppend(config)) return Promise.reject(requestError)
  return Promise.reject(markGovernanceTransportError(requestError, serverResponded))
}

interface RequestClient {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

// 请求拦截器：附加 Token 等
http.interceptors.request.use((config) => {
  // TODO: 从 auth store 获取 token 附加到 header
  return config
})

// 响应拦截器：统一解包 + 错误处理
http.interceptors.response.use(
  (res) => {
    const body: ApiResponse = res.data
    if (body.code !== 0) {
      // TODO: 触发全局 Toast 报错
      return rejectApiError(new Error(body.msg), true, res.config)
    }
    // Axios interceptor needs to unwrap heterogeneous API payloads for typed callers.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return body.data as any
  },
  (error: unknown) => {
    // TODO: 统一网络错误处理
    const axiosError = axios.isAxiosError<{ detail?: unknown; msg?: unknown }>(error)
      ? error
      : undefined
    const requestConfig = axiosError?.config
    const serverResponded = Boolean(axiosError?.response)
    const detail = axiosError?.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return rejectApiError(new Error(detail), true, requestConfig, axiosError?.response?.status)
    }

    const message =
      axiosError?.response?.data?.msg || (error instanceof Error ? error.message : undefined)
    if (typeof message === 'string' && message.trim()) {
      return rejectApiError(
        new Error(message),
        serverResponded,
        requestConfig,
        axiosError?.response?.status,
      )
    }

    if (error instanceof Error) {
      return rejectApiError(error, serverResponded, requestConfig, axiosError?.response?.status)
    }
    return Promise.reject(error)
  },
)

export default http as unknown as RequestClient
