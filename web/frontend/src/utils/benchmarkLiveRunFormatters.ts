import type { BenchmarkLiveRunLifecycleSample, BenchmarkTopic3DifficultySpan } from '@/types'

export interface BenchmarkDistributionItem {
  key: string
  value: number
}

export interface BenchmarkMarkedSegment {
  kind: 'plain' | 'harmful' | 'harmless'
  text: string
  start: number
  end: number
}

export function valueLabel(value: unknown) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => String(item)).join(', ') : '-'
  }
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return '-'
}

export function numberLabel(value: unknown) {
  return typeof value === 'number' ? String(value) : '0'
}

export function difficultyCountLabel(value: Record<string, unknown>) {
  const levels = ['H1', 'H2', 'H3', 'H4']
  const parts = levels
    .map((level) => `${level} ${numberLabel(value[level])}`)
    .filter((part) => !part.endsWith(' 0'))
  return parts.length > 0 ? parts.join(' / ') : '-'
}

export function percentLabel(value?: number | null) {
  if (typeof value !== 'number') {
    return '-'
  }
  return `${(value * 100).toFixed(1)}%`
}

export function msLabel(value?: number | null) {
  if (typeof value !== 'number') {
    return '-'
  }
  return `${Math.round(value)} ms`
}

export function compactHash(value?: string | null) {
  if (!value) {
    return '-'
  }
  if (value.length <= 18) {
    return value
  }
  return `${value.slice(0, 10)}...${value.slice(-8)}`
}

export function recordValue(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

export function distributionItems(value?: Record<string, number>): BenchmarkDistributionItem[] {
  return Object.entries(value ?? {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 6)
    .map(([key, count]) => ({ key, value: count }))
}

export function formatModeratorResults(value: Record<string, unknown>) {
  const entries = Object.entries(value)
  if (entries.length === 0) {
    return ''
  }
  return entries
    .map(([name, result]) => {
      const record = recordValue(result)
      return `${name}=${String(record?.label ?? result)}`
    })
    .join(', ')
}

export function lifecycleMeta(item: BenchmarkLiveRunLifecycleSample) {
  const parts = [
    item.strategy ? `strategy=${item.strategy}` : '',
    typeof item.difficulty === 'number' ? `difficulty=${item.difficulty}` : '',
    formatModeratorResults(item.moderator_results),
  ].filter(Boolean)
  return parts.join(' / ') || '-'
}

export function markedSegments(
  text: string,
  spans: Array<BenchmarkTopic3DifficultySpan & { kind: 'harmful' | 'harmless' }>,
): BenchmarkMarkedSegment[] {
  const validSpans = spans
    .filter((span) => span.end > span.start && span.start >= 0 && span.end <= text.length)
    .sort((left, right) => left.start - right.start || right.end - left.end)
  const segments: BenchmarkMarkedSegment[] = []
  let cursor = 0
  for (const span of validSpans) {
    if (span.start < cursor) {
      continue
    }
    if (span.start > cursor) {
      segments.push({
        kind: 'plain',
        text: text.slice(cursor, span.start),
        start: cursor,
        end: span.start,
      })
    }
    segments.push({
      kind: span.kind,
      text: text.slice(span.start, span.end),
      start: span.start,
      end: span.end,
    })
    cursor = span.end
  }
  if (cursor < text.length) {
    segments.push({
      kind: 'plain',
      text: text.slice(cursor),
      start: cursor,
      end: text.length,
    })
  }
  return segments
}
