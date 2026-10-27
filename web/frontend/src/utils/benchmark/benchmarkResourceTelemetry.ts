/**
 * Non-sensitive observability for Benchmark resource resolution (#175).
 *
 * Outcomes distinguish a canonical hit, legacy-query normalization, and the
 * three failure shapes. The payload is a fixed whitelist of resource identity
 * fields, so sample text can never reach logs, analytics, or URLs.
 */

export const BENCHMARK_RESOURCE_RESOLUTION_EVENT = 'benchmark-resource-resolution'

export type BenchmarkResourceOutcome =
  | 'canonical-hit'
  | 'legacy-normalized'
  | 'asset-not-found'
  | 'sample-not-found'
  | 'service-failure'

export interface BenchmarkResourceResolution {
  outcome: BenchmarkResourceOutcome
  assetId: string
  sampleId?: string
}

export function emitBenchmarkResourceResolution(
  outcome: BenchmarkResourceOutcome,
  identity: { assetId?: string | null; sampleId?: string | null },
): BenchmarkResourceResolution {
  const assetId = String(identity.assetId || '').trim()
  const sampleId = String(identity.sampleId || '').trim()
  const detail: BenchmarkResourceResolution = {
    outcome,
    assetId,
    ...(sampleId ? { sampleId } : {}),
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(BENCHMARK_RESOURCE_RESOLUTION_EVENT, { detail }))
  }
  return detail
}
