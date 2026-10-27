/**
 * Smoke coverage for CBRNE Benchmark query UI (#118 / Spec #116 T2).
 *
 *   node web/frontend/src/utils/benchmark/__tests__/cbrneQuery.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const utilSrc = readFileSync(join(here, '../cbrneQuery.ts'), 'utf8')
const panelSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkCbrneQueryPanel.vue'),
  'utf8',
)
const assetPanelSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkAssetPanel.vue'),
  'utf8',
)
const apiSrc = readFileSync(join(here, '../../../api/benchmark.ts'), 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(utilSrc.includes('export function buildCbrneQueryParams'), 'missing buildCbrneQueryParams')
assert(utilSrc.includes('export function isMaskedCbrneExcerpt'), 'missing isMaskedCbrneExcerpt')
assert(
  utilSrc.includes("excerpt.startsWith('[masked excerpt ·')"),
  'mask check must require masked excerpt prefix',
)
assert(
  utilSrc.includes('activation probe') && utilSrc.includes('execute_action'),
  'util must detect Activation Probe / execute_action',
)

assert(
  apiSrc.includes('/cbrne-anomaly/samples'),
  'api must expose cbrne-anomaly samples query',
)
assert(apiSrc.includes('export function queryCbrneAnomalySamples'), 'missing query API helper')

assert(utilSrc.includes('export const CBRNE_SOURCE_CHIP_LIMIT = 8'), 'source chips preview 8')
assert(utilSrc.includes('export function cbrneCountChips'), 'missing cbrneCountChips')
assert(
  utilSrc.includes(
    '.sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))',
  ),
  'chips sort by count desc, then name',
)
assert(utilSrc.includes('export function cbrneLabelCount'), 'missing cbrneLabelCount')

assert(assetPanelSrc.includes('<BenchmarkCbrneQueryPanel'), 'AssetPanel must mount query panel')
assert(assetPanelSrc.includes('cbrneCountChips'), 'AssetPanel must render count chips')
assert(assetPanelSrc.includes('来源种类数'), 'AssetPanel must show source kind count')
assert(assetPanelSrc.includes('data-testid="cbrne-source-toggle"'), 'source overflow toggles inline')
assert(assetPanelSrc.includes('还有 ${getCbrneHiddenSourceCount(asset)} 个来源'), 'collapsed label')
assert(assetPanelSrc.includes("? '收起'"), 'expanded label is 收起')
assert(
  assetPanelSrc.includes('return chips.slice(0, CBRNE_SOURCE_CHIP_LIMIT)'),
  'collapsed sources keep the first 8',
)
assert(/\.cbrne-chip\s*\{[^}]*white-space:\s*nowrap/.test(assetPanelSrc), 'chip text must not break')
assert(!assetPanelSrc.includes('getCbrneSourceDistribution'), 'joined source sentence must be gone')
assert(!assetPanelSrc.includes('safe / unsafe'), 'safe and unsafe are separate metrics')
assert(
  assetPanelSrc.includes("import BenchmarkCbrneQueryPanel from './BenchmarkCbrneQueryPanel.vue'"),
  'AssetPanel must import query panel',
)

assert(panelSrc.includes('data-testid="cbrne-filter-label"'), 'panel must expose label filter')
assert(
  panelSrc.includes('data-testid="cbrne-filter-category"'),
  'panel must expose category filter',
)
assert(panelSrc.includes('data-testid="cbrne-filter-source"'), 'panel must expose source filter')
assert(panelSrc.includes('data-testid="cbrne-filter-tier"'), 'panel must expose T1–T4 filter')
assert(
  panelSrc.includes('data-testid="cbrne-filter-difficulty-min"') &&
    panelSrc.includes('data-testid="cbrne-filter-difficulty-max"'),
  'panel must expose difficulty range filters',
)
assert(panelSrc.includes('data-testid="cbrne-query-hit"'), 'panel shows hit count only')
assert(panelSrc.includes('命中 {{ hasLoaded ? total : \'—\' }}'), 'hit line waits for the first response')
assert(!panelSrc.includes('cbrne-query__context'), 'panel must not repeat distribution cards')
assert(!panelSrc.includes('formatCountMap'), 'panel must not join distributions into one sentence')
assert(!panelSrc.includes('cbrneCountChips'), 'filter results must not redraw asset chips')
assert(panelSrc.includes('data-testid="cbrne-query-pagination"'), 'panel must expose pagination')
assert(panelSrc.includes('data-testid="cbrne-query-empty"'), 'panel must expose empty state')
assert(panelSrc.includes('handlePageChange'), 'panel must paginate via handlePageChange')
assert(panelSrc.includes('isMaskedCbrneExcerpt'), 'panel must enforce masked excerpt boundary')
assert(panelSrc.includes('queryCbrneAnomalySamples'), 'panel must call query API')
assert(
  panelSrc.includes('不提供 Activation Probe'),
  'panel copy must state no Activation Probe execute entry',
)
assert(
  !/ActivationProbe|startActivation|executeProbe|dynbench400_eval/.test(panelSrc),
  'query panel must not wire evaluator execute actions',
)
assert(!panelSrc.includes('@click="execute'), 'query results must not bind execute click handlers')

// Lightweight runtime checks for query helpers (inline reimplementation mirror).
function buildCbrneQueryParams(filters, offset, limit = 10) {
  return {
    label: filters.label || undefined,
    cbrne_category: filters.cbrne_category || undefined,
    source: filters.source || undefined,
    exposure_tier: filters.exposure_tier || undefined,
    difficulty_min:
      typeof filters.difficulty_min === 'number' ? filters.difficulty_min : undefined,
    difficulty_max:
      typeof filters.difficulty_max === 'number' ? filters.difficulty_max : undefined,
    limit,
    offset: Math.max(0, offset),
  }
}

function isMaskedCbrneExcerpt(excerpt) {
  return Boolean(excerpt?.startsWith('[masked excerpt ·') && excerpt.includes('chars]'))
}

const page1 = buildCbrneQueryParams(
  { label: 'unsafe', cbrne_category: 'Biological', difficulty_min: 2, difficulty_max: 4 },
  0,
  10,
)
assert(page1.label === 'unsafe', 'combined filter label')
assert(page1.cbrne_category === 'Biological', 'combined filter category')
assert(page1.difficulty_min === 2 && page1.difficulty_max === 4, 'difficulty range')
assert(page1.offset === 0 && page1.limit === 10, 'first page offset/limit')

const page2 = buildCbrneQueryParams({}, 10, 10)
assert(page2.offset === 10, 'second page offset')
assert(page2.label === undefined, 'cleared filters must leave label undefined')

assert(isMaskedCbrneExcerpt('[masked excerpt · 42 chars]'), 'accept masked excerpt')
assert(!isMaskedCbrneExcerpt('full sensitive prompt text'), 'reject full-text excerpt')
assert(!isMaskedCbrneExcerpt('sample one…'), 'reject truncated plaintext excerpt')

console.log('cbrneQuery.smoke.mjs: ok')
