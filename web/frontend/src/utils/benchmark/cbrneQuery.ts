import type {
  BenchmarkArtifactItem,
  BenchmarkCbrneQueryFilters,
  BenchmarkCbrneSamplesQueryResponse,
} from '@/types'

export const CBRNE_QUERY_PAGE_SIZE = 10

export const CBRNE_SOURCE_CHIP_LIMIT = 8

export interface CbrneCountChip {
  name: string
  count: number
}

export const CBRNE_LABEL_OPTIONS = [
  { label: 'safe', value: 'safe' },
  { label: 'unsafe', value: 'unsafe' },
] as const

export const CBRNE_EXPOSURE_TIER_OPTIONS = [
  { label: 'T1', value: 'T1' },
  { label: 'T2', value: 'T2' },
  { label: 'T3', value: 'T3' },
  { label: 'T4', value: 'T4' },
] as const

export function emptyCbrneQueryFilters(): BenchmarkCbrneQueryFilters {
  return {
    label: undefined,
    cbrne_category: undefined,
    source: undefined,
    exposure_tier: undefined,
    difficulty_min: undefined,
    difficulty_max: undefined,
  }
}

export function buildCbrneQueryParams(
  filters: BenchmarkCbrneQueryFilters,
  offset: number,
  limit: number = CBRNE_QUERY_PAGE_SIZE,
): BenchmarkCbrneQueryFilters & { limit: number; offset: number } {
  return {
    label: filters.label || undefined,
    cbrne_category: filters.cbrne_category || undefined,
    source: filters.source || undefined,
    exposure_tier: filters.exposure_tier || undefined,
    difficulty_min: typeof filters.difficulty_min === 'number' ? filters.difficulty_min : undefined,
    difficulty_max: typeof filters.difficulty_max === 'number' ? filters.difficulty_max : undefined,
    limit,
    offset: Math.max(0, offset),
  }
}

export function cbrneCountChips(counts: unknown): CbrneCountChip[] {
  if (!counts || typeof counts !== 'object' || Array.isArray(counts)) return []
  return Object.entries(counts as Record<string, unknown>)
    .flatMap(([name, count]) => (typeof count === 'number' ? [{ name, count }] : []))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
}

export function cbrneLabelCount(counts: unknown, label: string): number | null {
  if (!counts || typeof counts !== 'object' || Array.isArray(counts)) return null
  const value = (counts as Record<string, unknown>)[label]
  return typeof value === 'number' ? value : null
}

export function optionsFromCountMap(counts: unknown): Array<{ label: string; value: string }> {
  if (!counts || typeof counts !== 'object') return []
  return Object.keys(counts as Record<string, unknown>)
    .sort((a, b) => a.localeCompare(b))
    .map((key) => ({ label: key, value: key }))
}

export function cbrneDistributionContext(asset: BenchmarkArtifactItem): Record<string, unknown> {
  const stats = asset.manifest.platform_stats
  if (stats && typeof stats === 'object') {
    return stats as Record<string, unknown>
  }
  return {}
}

export function isMaskedCbrneExcerpt(excerpt: string | undefined | null): boolean {
  if (!excerpt) return false
  return excerpt.startsWith('[masked excerpt ·') && excerpt.includes('chars]')
}

export function queryResponseContainsFullTextLeak(
  payload: BenchmarkCbrneSamplesQueryResponse,
  forbiddenSnippets: string[],
): boolean {
  const blob = JSON.stringify(payload)
  if (blob.includes('"prompt"')) return true
  return forbiddenSnippets.some((snippet) => snippet && blob.includes(snippet))
}

export function queryResponseOffersExecuteAction(
  payload: BenchmarkCbrneSamplesQueryResponse,
): boolean {
  const blob = JSON.stringify(payload).toLowerCase()
  return (
    blob.includes('activation probe') ||
    blob.includes('execute_action') ||
    'execute' in (payload as unknown as Record<string, unknown>)
  )
}
