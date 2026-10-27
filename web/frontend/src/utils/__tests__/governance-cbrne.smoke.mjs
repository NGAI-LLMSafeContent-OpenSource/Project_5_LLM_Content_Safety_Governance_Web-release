/**
 * Minimal frontend smoke for CBRNE governance summary / pagination / Benchmark links (#120).
 *
 * Run with:
 *   node web/frontend/src/utils/__tests__/governance-cbrne.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  cbrneAssetBenchmarkHref,
  cbrneSampleBenchmarkHref,
  governanceCbrnePayloadLeaksFullText,
  isMaskedCbrneGovernanceExcerpt,
} from '../governance-cbrne-links.ts'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(
  cbrneAssetBenchmarkHref('topic2_cbrne_v1') === '/benchmark/assets/topic2_cbrne_v1',
  'asset href must target the canonical Benchmark asset resource',
)
assert(
  cbrneAssetBenchmarkHref('topic2/cbrne v1') === '/benchmark/assets/topic2%2Fcbrne%20v1',
  'asset href must encode the resource identity as one path segment',
)
assert(
  cbrneSampleBenchmarkHref('topic2_cbrne_v1', 'cbrne-0001') ===
    '/benchmark/assets/topic2_cbrne_v1/samples/cbrne-0001',
  'sample href must target the canonical sample resource scoped by asset',
)
assert(
  cbrneSampleBenchmarkHref('topic2/cbrne v1', 'cbrne/0001') ===
    '/benchmark/assets/topic2%2Fcbrne%20v1/samples/cbrne%2F0001',
  'sample href must encode both identities as path segments',
)
assert(
  isMaskedCbrneGovernanceExcerpt('[masked excerpt · 42 chars]'),
  'masked excerpt helper must accept list-safe summaries',
)
assert(
  !governanceCbrnePayloadLeaksFullText({
    capability: 'cbrne_dataset_search',
    samples: [{ text_excerpt: '[masked excerpt · 12 chars]', full_text: null }],
  }),
  'masked search payload must not count as full-text leak',
)
assert(
  governanceCbrnePayloadLeaksFullText({
    samples: [{ prompt: 'secret full prompt text' }],
  }),
  'prompt field must be treated as a leak',
)

const timelineSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceTimeline.vue'),
  'utf8',
)
assert(
  timelineSrc.includes('cbrne_dataset_search') &&
    timelineSrc.includes('GovernanceCbrneSearchCard') &&
    timelineSrc.includes('GovernanceCbrneOverviewCard'),
  'timeline must render CBRNE governance cards',
)

const overviewCardSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCbrneOverviewCard.vue'),
  'utf8',
)
assert(
  overviewCardSrc.includes('在 Benchmark 查看资产') &&
    overviewCardSrc.includes('target="_blank"') &&
    overviewCardSrc.includes('rel="noopener noreferrer"'),
  'overview asset entry must open the canonical resource in an isolated new tab',
)
for (const heading of ['标签分布', 'CBRNE 类别分布', '来源', 'T1–T4', '评估器相对难度']) {
  assert(overviewCardSrc.includes(`<h4>${heading}</h4>`), `overview card must show ${heading}`)
}
for (const field of [
  'source_counts',
  'exposure_tier_counts',
  'evaluator_relative_difficulty_counts',
]) {
  assert(overviewCardSrc.includes(field), `overview card must read ${field}`)
}

const searchCardSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCbrneSearchCard.vue'),
  'utf8',
)

const discoverCardSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCbrneDiscoverCard.vue'),
  'utf8',
)
assert(
  discoverCardSrc.includes('在 Benchmark 查看资产') &&
    discoverCardSrc.includes('target="_blank"') &&
    discoverCardSrc.includes('rel="noopener noreferrer"'),
  'discovery asset entries must open independent tabs without an opener',
)
assert(
  searchCardSrc.includes('在 Benchmark 查看样本') &&
    searchCardSrc.includes('target="_blank"') &&
    searchCardSrc.includes('rel="noopener noreferrer"') &&
    !searchCardSrc.includes('cbrneSample=') &&
    searchCardSrc.includes('data-testid="cbrne-search-pagination"') &&
    searchCardSrc.includes('data-testid="cbrne-benchmark-sample-link"') &&
    searchCardSrc.includes('load-more'),
  'search card must expose pagination and isolated canonical sample links',
)
assert(
  !searchCardSrc.includes('Activation Probe') && !searchCardSrc.includes('execute_action'),
  'search card must not offer evaluator execute actions',
)

const fullTextCardSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCbrneFullTextCard.vue'),
  'utf8',
)
assert(
  fullTextCardSrc.includes('data-testid="cbrne-benchmark-sample-link"') &&
    fullTextCardSrc.includes('全文不进治理消息') &&
    fullTextCardSrc.includes('在 Benchmark 查看样本') &&
    fullTextCardSrc.includes('target="_blank"') &&
    fullTextCardSrc.includes('rel="noopener noreferrer"'),
  'full-text card must disclose and open the canonical sample in a new tab',
)

const viewSrc = readFileSync(join(srcRoot, 'views/GovernanceView.vue'), 'utf8')
assert(
  viewSrc.includes('CBRNE_CONTINUATION_PROMPT') && viewSrc.includes('cbrne_dataset_search'),
  'GovernanceView must continue CBRNE pagination',
)

const domainsSrc = readFileSync(join(srcRoot, 'utils/governance-domains.ts'), 'utf8')
assert(
  domainsSrc.includes("capability: 'cbrne_dataset_overview'"),
  'domains must expose bound CBRNE overview recommendation',
)

console.log('governance-cbrne.smoke.mjs: ok')
