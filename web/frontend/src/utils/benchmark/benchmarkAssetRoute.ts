export type BenchmarkRouteQueryValue = string | null | undefined | (string | null)[]

export type LegacyBenchmarkAssetRedirect = {
  assetId: string
  sampleId?: string
  query: Record<string, BenchmarkRouteQueryValue>
}

export function benchmarkAssetPath(assetId: string): string {
  return `/benchmark/assets/${encodeURIComponent(assetId.trim())}`
}

export function benchmarkSamplePath(assetId: string, sampleId: string): string {
  return `${benchmarkAssetPath(assetId)}/samples/${encodeURIComponent(sampleId.trim())}`
}

export function canonicalizeLegacyBenchmarkAssetQuery(
  query: Record<string, BenchmarkRouteQueryValue>,
): LegacyBenchmarkAssetRedirect | null {
  const rawFocusAsset = query.focusAsset
  const candidate = Array.isArray(rawFocusAsset) ? rawFocusAsset[0] : rawFocusAsset
  const assetId = typeof candidate === 'string' ? candidate.trim() : ''
  if (!assetId) return null

  const rawSample = query.cbrneSample
  const sampleCandidate = Array.isArray(rawSample) ? rawSample[0] : rawSample
  const sampleId = typeof sampleCandidate === 'string' ? sampleCandidate.trim() : ''

  const normalizedQuery = Object.fromEntries(
    Object.entries(query).filter(([key]) => key !== 'focusAsset' && key !== 'cbrneSample'),
  ) as Record<string, BenchmarkRouteQueryValue>
  return {
    assetId,
    ...(sampleId ? { sampleId } : {}),
    query: normalizedQuery,
  }
}
