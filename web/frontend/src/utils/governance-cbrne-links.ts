/** Stable Benchmark navigation helpers for CBRNE governance results (#120). */

import { benchmarkAssetPath, benchmarkSamplePath } from '@/utils/benchmark/benchmarkAssetRoute'

export function cbrneAssetBenchmarkHref(assetId: string): string {
  return benchmarkAssetPath(assetId)
}

export function cbrneSampleBenchmarkHref(assetId: string, sampleId: string): string {
  return benchmarkSamplePath(assetId, sampleId)
}

export function isMaskedCbrneGovernanceExcerpt(excerpt: string | undefined | null): boolean {
  if (!excerpt) return false
  return excerpt.startsWith('[masked excerpt ·') && excerpt.includes('chars]')
}

export function governanceCbrnePayloadLeaksFullText(
  payload: unknown,
  forbiddenSnippets: string[] = [],
): boolean {
  const blob = JSON.stringify(payload ?? {})
  if (blob.includes('"full_text":"') && !blob.includes('"full_text":null')) {
    // Allow explicit null full_text on disclosure results.
    const match = /"full_text"\s*:\s*"([^"]*)"/.exec(blob)
    if (match && match[1]) return true
  }
  if (/"prompt"\s*:/.test(blob)) return true
  return forbiddenSnippets.some((snippet) => snippet && blob.includes(snippet))
}
