import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')
const benchmarkRoot = join(srcRoot, 'components/benchmark')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function read(name) {
  return readFileSync(join(benchmarkRoot, name), 'utf8')
}

const sectionSource = read('BenchmarkTopic3RiskSection.vue')
const behaviorSource = readFileSync(
  join(srcRoot, 'composables/benchmark/useTopic3RiskAssetVersions.ts'),
  'utf8',
)
const assetPanelSource = read('BenchmarkAssetPanel.vue')
const drawerSource = read('BenchmarkRiskSampleDrawer.vue')
const overviewSource = read('BenchmarkOverview.vue')
const evaluationSource = read('BenchmarkEvaluationPanel.vue')

for (const contract of [
  'getTopic3RiskAssetVersions',
  'data.current_asset_id',
  'asset_version',
  'asset_sha256',
  'risk_level_distribution',
  'language_distribution',
  'identityMatches',
]) {
  assert(behaviorSource.includes(contract), `risk behavior must keep contract: ${contract}`)
}

for (const contract of ['查看历史版本', '普通页面不提供 raw 或完整交付包下载']) {
  assert(sectionSource.includes(contract), `risk section must keep contract: ${contract}`)
}
for (const contract of ['handleVersionChange', '暂无同版本基线']) {
  assert(behaviorSource.includes(contract), `risk behavior must keep contract: ${contract}`)
}

assert(
  behaviorSource.includes(
    'getTopic3RiskSameVersionEvaluationSummary({ asset_id: current.asset_id })',
  ),
  'risk section must load evaluation results for the selected asset identity',
)
assert(
  behaviorSource.includes('评测结果与所选资产标识或内容哈希不一致') &&
    behaviorSource.includes('已停止展示以避免跨版本拼接'),
  'risk section must refuse mismatched evaluation results',
)

assert(
  assetPanelSource.includes('<BenchmarkTopic3RiskSection') &&
    assetPanelSource.includes(
      "import BenchmarkTopic3RiskSection from './BenchmarkTopic3RiskSection.vue'",
    ) &&
    assetPanelSource.includes(':asset-id="resourceMode'),
  'asset panel must mount the server-driven risk section for lists and asset resources',
)
assert(!assetPanelSource.includes('v6'), 'asset panel must not hardcode the v6 label')
assert(
  !assetPanelSource.includes('1526') && !assetPanelSource.includes('1,526'),
  'asset panel must not hardcode the historical sample count',
)

for (const source of [overviewSource, evaluationSource]) {
  assert(!source.includes('v6'), 'benchmark summary copy must not hardcode the v6 label')
  assert(
    !source.includes('1526') && !source.includes('1,526'),
    'benchmark summary copy must not hardcode 1526 samples',
  )
}

for (const contract of [
  'assetId',
  'assetVersion',
  'assetSha256',
  'sampleCount',
  'riskLevelDistribution',
  '未提供标注理由',
  'integrity_warnings',
]) {
  assert(drawerSource.includes(contract), `sample drawer must keep contract: ${contract}`)
}
assert(
  drawerSource.includes('getTopic3RiskSamples(props.assetId'),
  'sample drawer must query the selected asset instead of a fixed asset id',
)
assert(!drawerSource.includes('raw_download'), 'sample drawer must not expose raw download actions')
for (const source of [sectionSource, drawerSource]) {
  assert(!source.includes('download='), 'risk views must not expose a file download attribute')
  assert(!source.includes('window.open'), 'risk views must not open external download targets')
  assert(!source.includes('<a '), 'risk views must not expose raw file links')
}

console.log('benchmark-topic3-risk-version.smoke.mjs: ok')
