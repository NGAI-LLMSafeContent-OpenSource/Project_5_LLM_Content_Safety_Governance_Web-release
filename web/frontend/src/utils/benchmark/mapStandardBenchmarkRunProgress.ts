import type { BenchmarkTask, BenchmarkTaskLogItem, BenchmarkTaskStatus } from '@/types'
import type { StandardBenchmarkScale } from '@/utils/benchmark/standardTaskPayload'

export const STANDARD_RUN_STEP_TITLES = ['排队校验', '生成中', '打包冻结', '完成'] as const

export type StandardRunStepIndex = 0 | 1 | 2 | 3

const ACTIVITY_EVENT_TYPES = new Set([
  'thinking',
  'tool_call',
  'tool_result',
  'lifecycle',
  'status',
])

export function resolveStandardRunStepIndex(
  status: BenchmarkTaskStatus | string | null | undefined,
  options?: { isStarting?: boolean },
): StandardRunStepIndex {
  const isStarting = options?.isStarting ?? false
  if (isStarting && !status) {
    return 0
  }
  switch (status) {
    case 'pending':
    case 'validating':
      return 0
    case 'running':
      return 1
    case 'packaging':
      return 2
    case 'completed':
      return 3
    default:
      return isStarting ? 0 : 1
  }
}

/** Naive API datetimes (no Z / offset) are treated as UTC — matches mining `_utc_isoformat` / definition `parseLogTime`. */
export function parseBenchmarkApiDateMs(value: string): number {
  const trimmed = value.trim()
  if (!trimmed) {
    return Number.NaN
  }
  const hasExplicitOffset = /Z$|[+-]\d{2}:\d{2}$/.test(trimmed)
  const normalized = !hasExplicitOffset && trimmed.includes('T') ? `${trimmed}Z` : trimmed
  return Date.parse(normalized)
}

export function formatStandardRunElapsed(elapsedMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export function resolveStandardRunActivity(input: {
  status: BenchmarkTaskStatus | string | null | undefined
  logs: BenchmarkTaskLogItem[]
  isStarting?: boolean
}): string {
  const { status, logs, isStarting = false } = input

  if (isStarting && !status) {
    return '正在创建任务…'
  }
  if (status === 'pending' || status === 'validating') {
    return '正在校验任务…'
  }
  if (status === 'packaging') {
    return '正在打包冻结…'
  }
  if (status === 'completed') {
    return '生成完成'
  }
  if (status === 'failed' || status === 'rejected') {
    return '生成未完成'
  }

  // running or unknown in-flight
  const latestWithTurn = [...logs].reverse().find((item) => typeof item.turn === 'number')
  if (latestWithTurn && typeof latestWithTurn.turn === 'number') {
    return `第 ${latestWithTurn.turn + 1} 轮处理中`
  }

  const latest = logs.length > 0 ? logs[logs.length - 1] : null
  if (latest?.event_type === 'done') {
    return '即将打包…'
  }
  if (latest && ACTIVITY_EVENT_TYPES.has(latest.event_type)) {
    return '正在生成…'
  }
  return '正在生成…'
}

export function resolveStandardScaleHint(scale: StandardBenchmarkScale | null | undefined): string {
  if (scale === 'standard' || scale === 'large') {
    return '当前规模大于试跑，耗时可能更长，请耐心等待。'
  }
  return ''
}

export function resolveStandardRunElapsedMs(
  task: Pick<BenchmarkTask, 'started_at' | 'created_at'> | null | undefined,
  nowMs: number,
): number {
  const raw = task?.started_at || task?.created_at
  if (!raw) {
    return 0
  }
  const started = parseBenchmarkApiDateMs(raw)
  if (Number.isNaN(started)) {
    return 0
  }
  return Math.max(0, nowMs - started)
}
