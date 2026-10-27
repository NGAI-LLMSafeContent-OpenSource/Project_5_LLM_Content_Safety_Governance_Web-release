import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const routerSource = readFileSync(join(srcRoot, 'router/index.ts'), 'utf8')
assert(
  routerSource.includes("path: '/benchmark/assets/:assetId'") &&
    routerSource.includes("name: 'benchmark-asset'"),
  'router must expose the canonical asset resource route',
)
assert(
  routerSource.includes("path: '/benchmark/assets/:assetId/samples/:sampleId'") &&
    routerSource.includes("name: 'benchmark-sample'"),
  'router must expose the canonical sample resource route scoped by asset',
)

const benchmarkViewSource = readFileSync(join(srcRoot, 'views/BenchmarkView.vue'), 'utf8')
assert(
  benchmarkViewSource.includes('canonicalizeLegacyBenchmarkAssetQuery') &&
    benchmarkViewSource.includes('router.replace') &&
    benchmarkViewSource.includes("name: 'benchmark-sample'") &&
    benchmarkViewSource.includes(':sample-id="sampleResourceId'),
  'legacy focusAsset/cbrneSample links must normalize to canonical resource routes',
)

const resourceSource = readFileSync(
  join(srcRoot, 'components/benchmark/BenchmarkAssetResourceView.vue'),
  'utf8',
)
for (const contract of [
  '返回全部资产',
  "state.status === 'loading'",
  "state.status === 'not-found'",
  "state.status === 'error'",
  '重新读取',
  'benchmark-asset-resource-facts',
  'state.asset.artifact_sha256',
  'JSON.stringify(state.asset.manifest, null, 2)',
  'error instanceof ApiRequestError && error.status === 404',
]) {
  assert(resourceSource.includes(contract), `resource view must preserve contract: ${contract}`)
}

assert(
  resourceSource.includes("name: 'benchmark', query: { view: 'expert', tab: 'assets' }"),
  'return action must target the complete asset list',
)

assert(
  resourceSource.includes('getCbrneSampleRef') &&
    !resourceSource.includes('discloseCbrneSample') &&
    resourceSource.includes('data-testid="benchmark-sample-resource-not-found"') &&
    resourceSource.includes('data-testid="benchmark-sample-resource-error"') &&
    resourceSource.includes('重新读取样本') &&
    resourceSource.includes(':focus-sample="sampleState.ref"') &&
    resourceSource.includes('@close-sample-resource="returnToAssetResource"') &&
    /router\.replace\(assetRoute\.value\)/.test(resourceSource),
  'sample resource view must read a masked ref, never disclose, and close back to the asset URL',
)

const apiSource = readFileSync(join(srcRoot, 'api/benchmark.ts'), 'utf8')
assert(
  apiSource.includes('getCbrneSampleRef') &&
    apiSource.includes('/cbrne/sample-refs/${encodeURIComponent(sampleId)}'),
  'benchmark API client must expose the exact masked sample-ref read',
)

const panelSource = readFileSync(
  join(srcRoot, 'components/benchmark/BenchmarkAssetPanel.vue'),
  'utf8',
)
assert(
  panelSource.includes('focusSample') &&
    panelSource.includes(':focus-sample="focusedCbrneSample"') &&
    panelSource.includes('close-sample-resource'),
  'asset panel must open the drawer from the deep-linked masked ref',
)

const drawerSource = readFileSync(
  join(srcRoot, 'components/benchmark/BenchmarkCbrneSampleDrawer.vue'),
  'utf8',
)
assert(
  drawerSource.includes('data-testid="cbrne-masked-ref"') &&
    drawerSource.includes('focusSample') &&
    drawerSource.includes('drawerSession.restore(') &&
    drawerSource.includes('drawerSession.selectSample('),
  'drawer must show the selected masked ref and restore it without disclosing',
)

const governanceLinksSource = readFileSync(join(srcRoot, 'utils/governance-cbrne-links.ts'), 'utf8')
assert(
  governanceLinksSource.includes('benchmarkSamplePath') &&
    !governanceLinksSource.includes('focusAsset') &&
    !governanceLinksSource.includes('URLSearchParams'),
  'governance sample links must use the canonical sample path',
)

const telemetrySource = readFileSync(
  join(srcRoot, 'utils/benchmark/benchmarkResourceTelemetry.ts'),
  'utf8',
)
assert(
  [
    'canonical-hit',
    'legacy-normalized',
    'asset-not-found',
    'sample-not-found',
    'service-failure',
  ].every((outcome) => telemetrySource.includes(outcome)) &&
    !telemetrySource.includes('full_text') &&
    benchmarkViewSource.includes("emitBenchmarkResourceResolution('legacy-normalized'") &&
    resourceSource.includes('emitBenchmarkResourceResolution'),
  'resource resolution outcomes must be observable without sensitive text',
)

console.log('benchmark-asset-resource.smoke.mjs: ok')
