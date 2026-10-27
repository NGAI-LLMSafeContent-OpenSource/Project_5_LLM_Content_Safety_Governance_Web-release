/**
 * Contract smoke for anomaly-rewrite standard-mode mapping.
 * Keep in sync with standardTaskPayload.ts / BenchmarkStandardWorkbench.vue
 * (Vitest not wired yet).
 *
 *   node web/frontend/src/utils/benchmark/__tests__/standardTaskPayload.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const payloadSrc = readFileSync(join(here, '../standardTaskPayload.ts'), 'utf8')
const workbenchSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkStandardWorkbench.vue'),
  'utf8',
)

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

function readNumericRecord(source, name) {
  const match = source.match(new RegExp(`const ${name}[\\s\\S]*?=\\s*\\{([^}]+)\\}`))
  if (!match) {
    throw new Error(`missing ${name}`)
  }
  const out = {}
  for (const line of match[1].split('\n')) {
    const pair = line.match(/(\w+):\s*(\d+)/)
    if (pair) {
      out[pair[1]] = Number(pair[2])
    }
  }
  return out
}

const budget = readNumericRecord(payloadSrc, 'TOPIC2_BUDGET_BY_SCALE')
assertEqual(budget.trial, 1, 'upstream budget trial')
assertEqual(budget.standard, 2, 'upstream budget standard')
assertEqual(budget.large, 4, 'upstream budget large')

const samples = readNumericRecord(payloadSrc, 'TOPIC2_SAMPLE_COUNT_BY_SCALE')
assertEqual(samples.trial, 3, 'public sample count trial')
assertEqual(samples.standard, 20, 'public sample count standard')
assertEqual(samples.large, 50, 'public sample count large')

if (!payloadSrc.includes('return TOPIC2_SAMPLE_COUNT_BY_SCALE[input.scale]')) {
  throw new Error('estimateStandardSampleCount must use TOPIC2_SAMPLE_COUNT_BY_SCALE')
}

const topic2Block = payloadSrc.slice(payloadSrc.lastIndexOf("const strength = input.rewriteStrength"))
if (!topic2Block.includes('scale,') && !topic2Block.includes('scale: scale')) {
  throw new Error('topic2 createTask payload must include scale for evalset meta')
}
if (!topic2Block.includes('rewrite_strength: strength')) {
  throw new Error('topic2 createTask payload must include rewrite_strength')
}

if (!workbenchSrc.includes('>简单</el-radio-button>')) {
  throw new Error('Workbench must label light as 简单')
}
if (!workbenchSrc.includes('>困难</el-radio-button>')) {
  throw new Error('Workbench must label strong as 困难')
}
if (workbenchSrc.includes('>轻度</el-radio-button>') || workbenchSrc.includes('>强度</el-radio-button>')) {
  throw new Error('Workbench must not use 轻度/强度 radio labels')
}

const topic1Groups = readNumericRecord(payloadSrc, 'TOPIC1_GROUPS_BY_SCALE')
assertEqual(topic1Groups.trial, 1, 'topic1 groups trial')
assertEqual(topic1Groups.standard, 2, 'topic1 groups standard')
assertEqual(topic1Groups.large, 2, 'topic1 groups large')

if (!payloadSrc.includes('uniqueTopics(input.topics).length * 6')) {
  throw new Error('estimateStandardSampleCount must use selected topic count * 6 for large value_qa')
}

const valueQaBlock = payloadSrc.slice(
  payloadSrc.indexOf("if (direction === 'value_qa')"),
  payloadSrc.indexOf("if (direction === 'dynamic_difficulty')"),
)
if (!/groups_per_topic:\s*groups/.test(valueQaBlock) && !/groups_per_topic:\s*TOPIC1_GROUPS_BY_SCALE/.test(valueQaBlock)) {
  throw new Error('standard value_qa payload must set groups_per_topic from TOPIC1_GROUPS_BY_SCALE')
}
for (const [scale, groups] of Object.entries({ trial: 1, standard: 2, large: 2 })) {
  assertEqual(topic1Groups[scale], groups, `value_qa ${scale} groups_per_topic`)
}
if (!valueQaBlock.includes('大批量请至少选择 2 个主题')) {
  throw new Error('large value_qa must require at least 2 topics')
}
if (!valueQaBlock.includes('topics: selectedTopics')) {
  throw new Error('large value_qa payload must pass topics array')
}

const runnerSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkTaskRunner.vue'),
  'utf8',
)
if (runnerSrc.includes('总三档组数不能超过 2') || /topic1RequestedGroupCount\.value\s*>\s*2\b/.test(runnerSrc)) {
  throw new Error('expert Runner must align topic1 group ceiling with schema (<=10)')
}
if (!runnerSrc.includes('总三档组数不能超过 10') || !/topic1RequestedGroupCount\.value\s*>\s*10\b/.test(runnerSrc)) {
  throw new Error('expert Runner must reject topic1 total groups > 10')
}
if (valueQaBlock.includes('retrieval_mode') || valueQaBlock.includes('corpus_jsonl')) {
  throw new Error('standard value_qa payload must omit retrieval_mode and corpus_jsonl')
}
if (!valueQaBlock.includes('topic,')) {
  throw new Error('standard value_qa payload must pass topic')
}
if (workbenchSrc.includes('自定义主题需对应 corpus')) {
  throw new Error('Workbench must not tell users to prepare a local corpus')
}
if (!workbenchSrc.includes('allow-create')) {
  throw new Error('Workbench value_qa topic select must allow-create')
}
if (workbenchSrc.includes('el-option-group')) {
  throw new Error('Workbench value_qa topic select must be a flat list without dimension groups')
}
if (!workbenchSrc.includes('multiple')) {
  throw new Error('Workbench large value_qa topic select must allow multiple topics')
}
if (workbenchSrc.includes('最多 5') || workbenchSrc.includes('2–5')) {
  throw new Error('Workbench must not cap value_qa large topics at 5')
}
if (workbenchSrc.includes('clearable')) {
  throw new Error('Workbench value_qa topic select must not be clearable')
}
if (valueQaBlock.includes("|| '中秋节'") || valueQaBlock.includes('|| "中秋节"')) {
  throw new Error('standard value_qa payload must not silently default empty topic to 中秋节')
}
if (!workbenchSrc.includes('完整主题词表暂不可用')) {
  throw new Error('Workbench must show explicit empty-catalog message when topics unavailable')
}

const taskServicePath = join(
  here,
  '../../../../../backend/app/services/benchmark_task_service.py',
)
const taskServiceSrc = readFileSync(taskServicePath, 'utf8')
if (!taskServiceSrc.includes('build_topic2_autobench_payload')) {
  throw new Error('backend must whitelist topic2 upstream payload')
}
if (!taskServiceSrc.includes('TOPIC2_UPSTREAM_PARAMETER_KEYS')) {
  throw new Error('backend must define topic2 upstream parameter allowlist')
}

const evalPanelSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkEvaluationPanel.vue'),
  'utf8',
)
if (!evalPanelSrc.includes("asset.source_mode !== 'prerun_snapshot'")) {
  throw new Error('evaluation panel must exclude non-prerun topic3 risk assets')
}
if (!evalPanelSrc.includes('live_run_trial')) {
  throw new Error('evaluation panel must exclude live_run_trial release_kind')
}

if (!payloadSrc.includes('export function buildCulturalCorpusTaskPayload')) {
  throw new Error('standardTaskPayload must export buildCulturalCorpusTaskPayload')
}
if (!payloadSrc.includes("return buildCulturalCorpusTaskPayload({")) {
  throw new Error('standard cultural_diversity branch must reuse buildCulturalCorpusTaskPayload')
}

if (!runnerSrc.includes("value: 'topic3-cultural-corpus-generation'")) {
  throw new Error('expert Runner must include cultural corpus agent card')
}
if (!runnerSrc.includes('难度等级')) {
  throw new Error('expert Runner must expose structure_band as 难度等级')
}
if (
  runnerSrc.includes('背景结构') ||
  runnerSrc.includes('明示为主') ||
  runnerSrc.includes('偏隐式') ||
  runnerSrc.includes('强暗示') ||
  runnerSrc.includes('弱暗示')
) {
  throw new Error('expert Runner must not use 背景结构 / 明示 / 偏隐式 / 暗示 in user-facing copy')
}
if (
  !runnerSrc.includes('低难度为主') ||
  !runnerSrc.includes('中高难度') ||
  !runnerSrc.includes('试跑 3 条 / 低难度为主')
) {
  throw new Error('expert Runner cultural bands must use 低难度为主 / 混合 / 中高难度')
}
if (!runnerSrc.includes('buildTopic3CulturalPayload')) {
  throw new Error('expert Runner must submit cultural payload via buildTopic3CulturalPayload')
}
if (runnerSrc.includes('v-model="culturalForm.difficulty_counts') || runnerSrc.includes('culturalForm.difficultyCounts')) {
  throw new Error('expert Runner phase 1 must not expose custom L1/L2/L3 counts')
}
if (!runnerSrc.includes('ethnicGroups.length === 1')) {
  throw new Error('expert Runner must disable unchecking the last ethnic group')
}
if (!runnerSrc.includes('previousDefault')) {
  throw new Error('expert Runner must only auto-follow batchSize when it still matches the previous default')
}

const viewSrc = readFileSync(join(here, '../../../views/BenchmarkView.vue'), 'utf8')
if (!viewSrc.includes('>5</span>') || !viewSrc.includes('现场可跑链路')) {
  throw new Error('expert header must show 5 live-run links')
}
if (!viewSrc.includes('hydrateExpertFromQuery') || !viewSrc.includes('route.query.task')) {
  throw new Error('expert view must hydrate task_id from query')
}
if (!viewSrc.includes('alreadyHydrated') || !viewSrc.includes("hydratedExpertTaskId.value = ''")) {
  throw new Error('expert hydrate must skip only when same task is already polling and reset guard when task query is cleared')
}
if (!viewSrc.includes('polling.task.value = fetchedTask')) {
  throw new Error('expert hydrate must prefill polling.task when GET succeeds')
}

if (!workbenchSrc.includes("tab: 'tasks'") || !workbenchSrc.includes('task: feedbackTaskId.value')) {
  throw new Error('standard failure CTA must pass tab/agent/task into expert mode')
}

const viewModeSrc = readFileSync(
  join(here, '../../../composables/benchmark/useBenchmarkViewMode.ts'),
  'utf8',
)
if (!viewModeSrc.includes('payload?.task') || !viewModeSrc.includes("delete nextQuery.task")) {
  throw new Error('view mode must write and clear expert task query')
}
if (!viewModeSrc.includes('delete nextQuery.tab') || !viewModeSrc.includes('delete nextQuery.agent')) {
  throw new Error('goExpert must clear stale tab/agent/task before writing payload')
}

const overviewSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkOverview.vue'),
  'utf8',
)
if (!overviewSrc.includes("generation: 'live_run / 预跑可信资产'")) {
  throw new Error('overview cultural generation must include live_run')
}

// Keep in sync with culturalDifficultyCounts() in standardTaskPayload.ts (08-11 §3.1).
function culturalDifficultyCountsSmoke(scale, structureBand) {
  const totals = { trial: 3, standard: 9, large: 30 }
  const total = totals[scale]
  if (structureBand === 'explicit') {
    return { L1: total, L2: 0, L3: 0 }
  }
  if (structureBand === 'mixed') {
    const per = total / 3
    return { L1: per, L2: per, L3: per }
  }
  const l2 = Math.floor(total / 2)
  return { L1: 0, L2: l2, L3: total - l2 }
}

const culturalCountCases = [
  ['trial', 'explicit', { L1: 3, L2: 0, L3: 0 }],
  ['trial', 'mixed', { L1: 1, L2: 1, L3: 1 }],
  ['trial', 'implicit_heavy', { L1: 0, L2: 1, L3: 2 }],
  ['standard', 'explicit', { L1: 9, L2: 0, L3: 0 }],
  ['standard', 'mixed', { L1: 3, L2: 3, L3: 3 }],
  ['standard', 'implicit_heavy', { L1: 0, L2: 4, L3: 5 }],
  ['large', 'explicit', { L1: 30, L2: 0, L3: 0 }],
  ['large', 'mixed', { L1: 10, L2: 10, L3: 10 }],
  ['large', 'implicit_heavy', { L1: 0, L2: 15, L3: 15 }],
]
for (const [scale, band, expected] of culturalCountCases) {
  const actual = culturalDifficultyCountsSmoke(scale, band)
  assertEqual(actual.L1, expected.L1, `cultural ${scale}/${band} L1`)
  assertEqual(actual.L2, expected.L2, `cultural ${scale}/${band} L2`)
  assertEqual(actual.L3, expected.L3, `cultural ${scale}/${band} L3`)
}
if (!payloadSrc.includes("if (structureBand === 'explicit')") || !payloadSrc.includes('Math.floor(total / 2)')) {
  throw new Error('culturalDifficultyCounts must keep explicit/mixed/floor mapping')
}

if (!workbenchSrc.includes('生成有害/无害混合文本，用于合规编辑评测（结构层级 H1–H4）')) {
  throw new Error('Workbench dynamic_difficulty card must use Chinese-first H1–H4 copy')
}
if (!workbenchSrc.includes('生成多民族语境评测语料；按低/中/高难度（L1–L3）')) {
  throw new Error('Workbench cultural card must use 低/中/高难度 copy')
}
if (workbenchSrc.includes('基础混合（H1–H2）') || workbenchSrc.includes('高复杂（H3–H4）')) {
  throw new Error('Workbench must not expose H-structure bands after scheme B')
}
if (!workbenchSrc.includes('默认均衡覆盖 H1–H4')) {
  throw new Error('Workbench must say default balanced H1–H4 coverage')
}
if (!workbenchSrc.includes('抽样范围')) {
  throw new Error('Workbench must expose 17-class sampling range under more options')
}
if (!payloadSrc.includes('normalizeTopic3RiskCategories')) {
  throw new Error('payload helper must normalize 17-class sampling range')
}
if (!payloadSrc.includes('TOPIC3_DIFFICULTY_DURATION_HINT_BY_SCALE')) {
  throw new Error('payload must export topic3 duration hints 80/100/150s')
}
if (!payloadSrc.includes("risk_categories: normalizeTopic3RiskCategories(selected)")) {
  throw new Error('dynamic_difficulty payload must pass normalized risk_categories')
}
if (payloadSrc.includes('difficultyCountsForBand') || payloadSrc.includes('StandardDifficultyBand')) {
  throw new Error('scheme B must drop difficulty band mapping')
}
if (workbenchSrc.includes('简单（H1–H2）') || workbenchSrc.includes('困难（H3–H4）')) {
  throw new Error('Workbench must not use 简单/困难 for H-structure bands')
}
if (!workbenchSrc.includes('一段有害 + 一段无害，边界较清楚。测能不能把有害和无害分开看，别整段一刀切。')) {
  throw new Error('Workbench must always include H1 glossary sentence')
}
if (!workbenchSrc.includes('两段有害 + 一段无害。测多个风险点会不会漏掉。')) {
  throw new Error('Workbench must always include H2 glossary sentence')
}
if (!workbenchSrc.includes('一段有害 + 两段无害。测会不会把无害内容误判成风险。')) {
  throw new Error('Workbench must always include H3 glossary sentence')
}
if (!workbenchSrc.includes('有害和无害多段交错。当前结构最复杂，不能只靠关键词判断。')) {
  throw new Error('Workbench must always include H4 glossary sentence')
}
if (!workbenchSrc.includes('H2 和 H3 不是谁一定更难；H4 才是结构最复杂的一档。')) {
  throw new Error('Workbench must include H2/H3 non-monotonic note')
}
if (
  !workbenchSrc.includes('难度等级') ||
  !workbenchSrc.includes('低难度为主（L1）') ||
  !workbenchSrc.includes('混合（L1–L3）') ||
  !workbenchSrc.includes('中高难度（L2–L3）')
) {
  throw new Error('Workbench cultural bands must use 难度等级 + 低/中高难度 labels')
}
if (
  workbenchSrc.includes('背景结构') ||
  workbenchSrc.includes('明示为主') ||
  workbenchSrc.includes('偏隐式') ||
  workbenchSrc.includes('强暗示') ||
  workbenchSrc.includes('弱暗示')
) {
  throw new Error('Workbench must not use 背景结构 / 明示 / 偏隐式 / 暗示 in user-facing copy')
}
if (!workbenchSrc.includes('低/中/高难度是什么')) {
  throw new Error('Workbench must offer collapsible 低/中/高难度 glossary')
}
if (!workbenchSrc.includes('低难度：背景直接点名民族。测文化事实对不对。')) {
  throw new Error('Workbench must include L1 低难度 glossary sentence')
}
if (!workbenchSrc.includes('中难度：多个文化特征，较容易锁定民族。测不点名时会不会还答对。')) {
  throw new Error('Workbench must include L2 中难度 glossary sentence')
}
if (!workbenchSrc.includes('高难度：只有很隐蔽的一条线索。测最容易误判的语境。')) {
  throw new Error('Workbench must include L3 高难度 glossary sentence')
}
if (!payloadSrc.includes("explicit: '低难度为主'") || !payloadSrc.includes("implicit_heavy: '中高难度'")) {
  throw new Error('CULTURAL_STRUCTURE_BAND_LABELS must use 低难度为主 / 中高难度')
}
if (!workbenchSrc.includes('一次只选一档；表示改写强度（轮数上限），不是题目难度。')) {
  throw new Error('Workbench anomaly help must describe rewrite strength without H1–H4')
}
if (
  workbenchSrc.includes('不是动态难度的 H1–H4') ||
  workbenchSrc.includes('不是必须满跑 H1-H4')
) {
  throw new Error('Workbench anomaly help must not mention H1–H4')
}

if (workbenchSrc.includes('github.com')) {
  throw new Error('Workbench must not link the usage guide to GitHub')
}
if (!workbenchSrc.includes('BenchmarkStandardGuideDrawer')) {
  throw new Error('Workbench must open the in-app usage guide drawer')
}

const guideDrawerSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkStandardGuideDrawer.vue'),
  'utf8',
)
if (
  !guideDrawerSrc.includes('@repo-doc-guides/') ||
  !guideDrawerSrc.includes('使用说明.md?raw')
) {
  throw new Error('Guide drawer must import the usage guide markdown with ?raw')
}
if (!guideDrawerSrc.includes('size="min(520px, 92vw)"')) {
  throw new Error('Guide drawer width must be min(520px, 92vw)')
}

const liveRunDrawerSrc = readFileSync(
  join(here, '../../../components/benchmark/live-run-summary/BenchmarkLiveRunSummaryDrawer.vue'),
  'utf8',
)
if (!liveRunDrawerSrc.includes("benchmark_type === 'cultural_diversity_generation'")) {
  throw new Error('Live-run drawer must route cultural_diversity_generation to a dedicated body')
}
if (!liveRunDrawerSrc.includes('BenchmarkTopic3CulturalLiveRunSummaryBody')) {
  throw new Error('Live-run drawer must render BenchmarkTopic3CulturalLiveRunSummaryBody')
}
if (!liveRunDrawerSrc.includes('课题三文化多样性语料生成 live_run 运行摘要')) {
  throw new Error('Live-run drawer must use the cultural diversity title')
}
const culturalBranchIndex = liveRunDrawerSrc.indexOf('isTopic3CulturalSummary')
const autobenchBranchIndex = liveRunDrawerSrc.indexOf('BenchmarkAutoBenchLiveRunSummaryBody')
if (culturalBranchIndex < 0 || autobenchBranchIndex < 0 || culturalBranchIndex > autobenchBranchIndex) {
  throw new Error('Cultural live-run body must render before the AutoBench fallback')
}
if (liveRunDrawerSrc.includes("cultural_diversity_generation') {\n    return 'AutoBench")) {
  throw new Error('Cultural live-run title must not fall through to AutoBench')
}

const liveRunPanelSrc = readFileSync(
  join(here, '../../../components/benchmark/BenchmarkAssetPanel.vue'),
  'utf8',
)
if (!liveRunPanelSrc.includes('v-if="!isTopic3CulturalAsset(latestLiveAsset)"')) {
  throw new Error('Cultural live-run card must hide the Topic 2 console button')
}
if (!liveRunPanelSrc.includes("return '请求条数'")) {
  throw new Error('Cultural live-run card must relabel Budget as 请求条数')
}
if (!liveRunPanelSrc.includes("getLiveRunParameterLabel(asset, 'total_sample_count')")) {
  throw new Error('Cultural live-run card must read total_sample_count instead of budget')
}

const culturalBodySrc = readFileSync(
  join(
    here,
    '../../../components/benchmark/live-run-summary/BenchmarkTopic3CulturalLiveRunSummaryBody.vue',
  ),
  'utf8',
)
if (!culturalBodySrc.includes('.slice(0, 5)')) {
  throw new Error('Cultural live-run preview table must cap at 5 rows')
}

console.log('standardTaskPayload smoke: ok')
