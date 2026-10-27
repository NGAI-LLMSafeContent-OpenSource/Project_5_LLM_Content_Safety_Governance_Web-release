/**
 * Public-contract smoke for the governance shell.
 *
 * Run with:
 *   node web/frontend/src/utils/__tests__/governance-shell.smoke.mjs
 */

import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  GOVERNANCE_DOMAINS,
  getGovernanceDomain,
  governanceSuggestionBinding,
  isExecutableRecommend,
  nextGovernanceDomain,
} from '../governance-domains.ts'
import {
  VALUE_KEY_DISPLAY_COUNT,
  formatMetricRate,
  formatValueKey,
  formatValueKeys,
} from '../governance-format.ts'
import {
  RISK_OVERVIEW_PROMPT,
  buildRiskFilterGroups,
  buildRiskFilterPrompt,
} from '../governance-risk-filters.ts'

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

assert(GOVERNANCE_DOMAINS.length === 2, 'governance shell must expose exactly two domains')
assert(
  GOVERNANCE_DOMAINS.map((domain) => domain.label).join('|') === '输入语料治理|输出内容治理',
  'governance domains must use the approved formal names',
)
assert(
  getGovernanceDomain('input').suggestions.length === 4,
  'input governance must append Topic 1 tool-status and CBRNE overview tasks',
)
const inputSuggestions = getGovernanceDomain('input').suggestions
assert(
  inputSuggestions.map((suggestion) => suggestion.id).join('|') ===
    'input-value-tier-compare|input-risk-corpus-rescan|input-topic1-corpus-tools|input-cbrne-overview',
  'input governance must preserve existing tasks and append Topic 1 + CBRNE recommendations',
)
assert(
  isExecutableRecommend(inputSuggestions[0]) &&
    inputSuggestions[0].capability === 'value_qa_search',
  'value-tier compare must be a bound executable capability recommendation',
)
assert(
  isExecutableRecommend(inputSuggestions[1]) &&
    inputSuggestions[1].kind === 'action' &&
    inputSuggestions[1].capability === 'risk_corpus_rescan' &&
    inputSuggestions[1].title === '输入风险语料在线二次检测' &&
    /课题二输入风险静态验证语料（400条）/.test(inputSuggestions[1].prompt) &&
    !inputSuggestions.some((suggestion) => suggestion.capability === 'dynbench400_eval'),
  'input governance must route new work to the risk_corpus_rescan v2 task, not an independent DynBench eval entry',
)
assert(
  isExecutableRecommend(inputSuggestions[2]) &&
    inputSuggestions[2].kind === 'action' &&
    inputSuggestions[2].capability === 'topic1_corpus_tool_catalog',
  'Topic 1 tool status must be a bound read-only capability recommendation',
)
assert(
  isExecutableRecommend(inputSuggestions[3]) &&
    inputSuggestions[3].kind === 'action' &&
    inputSuggestions[3].capability === 'cbrne_dataset_overview',
  'CBRNE overview must be a bound read-only capability recommendation',
)
assert(
  getGovernanceDomain('output').key === 'output',
  'getGovernanceDomain must resolve a known domain',
)
assert(
  getGovernanceDomain('unknown').key === 'input',
  'getGovernanceDomain must fall back to input governance',
)
const outputSuggestions = getGovernanceDomain('output').suggestions
assert(
  outputSuggestions.map((suggestion) => suggestion.id).join('|') ===
    'output-risk-system-record-search|output-cultural-system-record-search',
  'output governance welcome offers only the two system-record tasks',
)
assert(
  isExecutableRecommend(outputSuggestions[0]) &&
    outputSuggestions[0].capability === 'risk_system_record_search' &&
    outputSuggestions[0].prompt === '查看最近的风险安全评测系统预跑记录',
  'output risk starter must send the risk system-record task name',
)
assert(
  isExecutableRecommend(outputSuggestions[1]) &&
    outputSuggestions[1].capability === 'cultural_system_record_search' &&
    outputSuggestions[1].prompt === '查看最近的文化多样性系统预跑记录',
  'output cultural starter must send the cultural system-record task name',
)
assert(
  outputSuggestions.every(
    (suggestion) => suggestion.kind === 'action' && isExecutableRecommend(suggestion),
  ),
  'output welcome suggestions are executable record tasks',
)
assert(
  !outputSuggestions.some((suggestion) => suggestion.id.includes('filter')),
  'filter chips must not occupy the welcome grid',
)
assert(
  nextGovernanceDomain('input', 'ArrowRight') === 'output' &&
    nextGovernanceDomain('output', 'ArrowLeft') === 'input',
  'arrow keys must move between peer governance tabs',
)

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')
const routerSource = readFileSync(join(srcRoot, 'router/index.ts'), 'utf8')
const appSource = readFileSync(join(srcRoot, 'App.vue'), 'utf8')
const viewSource = readFileSync(join(srcRoot, 'views/GovernanceView.vue'), 'utf8')

assert(
  /path:\s*['\"]\/['\"][\s\S]*?redirect:\s*['\"]\/governance['\"]/.test(routerSource),
  'root route must redirect to /governance',
)
assert(/path:\s*['\"]\/governance['\"]/.test(routerSource), 'router must expose /governance')
for (const legacyPath of ['/data-input', '/output', '/input-guardrail', '/output-guardrail']) {
  assert(
    routerSource.includes(`path: '${legacyPath}'`),
    `${legacyPath} must remain directly reachable`,
  )
}
assert(
  appSource.includes("route.name !== 'governance'"),
  'the legacy header must be hidden only on the governance route',
)
assert(viewSource.includes('role="tablist"'), 'governance domain switcher must expose a tablist')
assert(viewSource.includes('role="tabpanel"'), 'governance content must expose a tabpanel')
assert(
  !viewSource.includes('router.push') && !viewSource.includes('router.replace'),
  'switching governance domains must remain local page state',
)
const selectDomainSource = viewSource.match(
  /function selectDomain\(domain: GovernanceDomainKey\) \{[\s\S]*?\n\}/,
)?.[0]
assert(
  /if \(domain === activeDomainKey\.value\) return/.test(selectDomainSource || ''),
  'selecting the already-active governance domain must be a no-op',
)
assert(
  viewSource.includes('domainWorkspaces[activeDomainKey.value].session') &&
    viewSource.includes('domainWorkspaces[activeDomainKey.value].draft'),
  'each governance domain must retain its own active session and unsent draft',
)

const timelineSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceTimeline.vue'),
  'utf8',
)
for (const kind of ['risk_system_record_search', 'risk_system_record_detail']) {
  assert(
    timelineSource.includes(kind),
    `the timeline must dispatch the ${kind} system record result`,
  )
}
for (const kind of ['cultural_system_record_search', 'cultural_system_record_detail']) {
  assert(
    timelineSource.includes(kind),
    `the timeline must dispatch the ${kind} cultural record result`,
  )
}
assert(
  viewSource.includes('cultural_system_record_search'),
  'load-more must route a cultural record page to the cultural continuation prompt',
)
const listCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceSystemRecordListCard.vue'),
  'utf8',
)
const detailCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceSystemRecordDetailCard.vue'),
  'utf8',
)
assert(
  listCardSource.includes('系统预跑记录') && detailCardSource.includes('系统预跑记录'),
  'system record cards must be labelled as system prerun records',
)
assert(
  listCardSource.includes('非本次用户执行结果'),
  'the system record list must not be presented as the current user result',
)
assert(
  detailCardSource.includes("payload.source_status === 'missing'"),
  'the detail card must render an explicit missing-source state',
)
const culturalListCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCulturalRecordListCard.vue'),
  'utf8',
)
const culturalDetailCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCulturalRecordDetailCard.vue'),
  'utf8',
)
assert(
  culturalListCardSource.includes('系统预跑记录') &&
    culturalDetailCardSource.includes('系统预跑记录'),
  'cultural record cards must be labelled as system prerun records',
)
assert(
  culturalListCardSource.includes('非本次用户执行结果'),
  'the cultural record list must not be presented as the current user result',
)
assert(
  culturalDetailCardSource.includes("payload.source_status === 'missing'"),
  'the cultural detail card must render an explicit missing-source state',
)
assert(
  culturalListCardSource.includes('difficulty_levels') &&
    culturalListCardSource.includes('ethnic_groups'),
  'the cultural list must surface its business dimensions',
)
assert(
  culturalDetailCardSource.includes('difficulty_distribution') &&
    !culturalDetailCardSource.includes('safe_total'),
  'the cultural detail must show cultural metrics without risk-safety fields',
)

// #59: value-key Chinese labels must cover the topic-1 taxonomy, keep the raw
// code, disambiguate duplicate Chinese labels and safely fall back.
assert(VALUE_KEY_DISPLAY_COUNT === 41, 'the value-key map must cover all 41 topic-1 keys (A/B/C/D)')
assert(
  formatValueKey('A.civility') === '文明（A.civility）' &&
    formatValueKey('A.integrity') === '诚信（A.integrity）',
  'known A-layer keys must render as 中文标签（原始代号）',
)
assert(
  formatValueKey('B.filial_piety') === '孝悌（B.filial_piety）' &&
    formatValueKey('C.privacy_protection') === '隐私保护（C.privacy_protection）' &&
    formatValueKey('D.medical.informed_consent') === '知情同意（D.medical.informed_consent）',
  'B/C/D-layer keys must render with the same rule',
)
assert(
  formatValueKey('A.integrity') !== formatValueKey('B.trustworthiness') &&
    formatValueKey('B.trustworthiness') === '诚信（B.trustworthiness）',
  'duplicate Chinese labels must stay distinguishable through the raw code',
)
assert(
  formatValueKey('Z.unknown') === 'Z.unknown' && formatValueKey('') === '',
  'unknown or empty value keys must fall back to the raw code without throwing',
)
assert(
  formatValueKeys(['A.civility', 'Z.unknown']) === '文明（A.civility）、Z.unknown',
  'value-key lists must join with the shared display rule',
)
const levelsSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceValueQaLevels.vue'),
  'utf8',
)
assert(
  levelsSource.includes('formatValueKeys'),
  'the value-basis list must use the shared value-key formatter',
)

// #60: clickable risk filter values must come from the latest risk overview
// payload and degrade explicitly when the session has none yet.
const riskSearchCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceRiskSearchCard.vue'),
  'utf8',
)
assert(
  riskSearchCardSource.includes('risk-filter-values') &&
    riskSearchCardSource.includes('select-filter'),
  'the risk search card must render clickable filter values and emit the selection',
)
assert(
  riskSearchCardSource.includes('risk-filter-values__empty') &&
    riskSearchCardSource.includes('request-overview'),
  'the risk search card must render the no-overview degradation action',
)
assert(
  timelineSource.includes('buildRiskFilterGroups') && timelineSource.includes('filter-groups'),
  'the timeline must derive filter values from the session risk overview',
)
assert(
  viewSource.includes('buildRiskFilterPrompt') && viewSource.includes('requestRiskOverview'),
  'the view must turn chip selections into the existing risk search prompt',
)
const overviewWithDistributions = {
  reference_label_distribution: { safe: 3, unsafe: 7 },
  source_distribution: { AILuminate: 2, PHTest: 1 },
  harm_category_L1_distribution: { 'L1-2 Explicit Harmful Injection': 4 },
  harm_category_L2_distribution: { 'Violence, Self-Harm, and Physical/Environmental Harm': 2 },
}
const filterGroups = buildRiskFilterGroups(overviewWithDistributions)
assert(
  filterGroups.map((group) => group.key).join('|') ===
    'source|harm_category_L1|harm_category_L2|reference_label',
  'filter values must group as 来源 / 一级分类 / 二级分类 / 参考标注',
)
assert(
  filterGroups
    .find((group) => group.key === 'reference_label')
    .options.map((option) => option.display)
    .join('|') === '安全|不安全',
  'reference-label filter values must render as 安全/不安全 while keeping raw safe/unsafe',
)
assert(
  filterGroups.find((group) => group.key === 'source').options[0].value === 'AILuminate',
  'source filter values must come from the overview distribution',
)
assert(
  buildRiskFilterGroups(null).length === 0 && buildRiskFilterGroups({}).length === 0,
  'a session without an overview payload must yield no filter groups',
)
assert(
  buildRiskFilterPrompt('source', 'AILuminate') === '筛选风险样本：source = AILuminate' &&
    RISK_OVERVIEW_PROMPT.includes('风险语料构成'),
  'chip selections must produce the deterministic risk search prompt',
)

// #96: sidebar drops persistent skill catalog; welcome 推荐任务 send when bound;
// follow-up chips require capability/skill_key; plan/result projection stays.
const skillEntrySource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceSkillEntry.vue'),
  'utf8',
)
const skillPlanSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceSkillPlanCard.vue'),
  'utf8',
)
const suggestionListSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceTaskSuggestionList.vue'),
  'utf8',
)
const welcomeSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceWelcome.vue'),
  'utf8',
)
const sidebarSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceSidebar.vue'),
  'utf8',
)
const projectionSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceTaskResultProjection.vue'),
  'utf8',
)
const apiSource = readFileSync(join(srcRoot, 'api/governance.ts'), 'utf8')
const typesSource = readFileSync(join(srcRoot, 'types/index.ts'), 'utf8')

assert(
  apiSource.includes('getGovernanceSkillCatalog') && apiSource.includes('/governance/skills'),
  'the api layer must keep the read-only skill catalog endpoint for the control plane',
)
assert(
  apiSource.includes('getGovernanceTaskSuggestions') && apiSource.includes('/suggestions'),
  'the api layer must expose the client-scoped task suggestion endpoint',
)
assert(
  !sidebarSource.includes('GovernanceSkillEntry') && !viewSource.includes('GovernanceSkillEntry'),
  'the product shell must not host a persistent sidebar skill catalog',
)
assert(
  !viewSource.includes('getGovernanceSkillCatalog') && !viewSource.includes('fetchSkillCatalog'),
  'the shell view must not load the skill catalog for chrome display',
)
assert(
  welcomeSource.includes('推荐任务') && !welcomeSource.includes('受控治理能力'),
  'welcome must label starters as 推荐任务',
)
assert(
  welcomeSource.includes('治理能力说明') && welcomeSource.includes('isExecutableRecommend'),
  'welcome must separate explanation cards from bound executable recommendations',
)
assert(
  viewSource.includes('handleRecommendSelect') && viewSource.includes('isExecutableRecommend'),
  'the view must send bound 推荐任务 immediately and ignore explanation cards',
)
assert(
  viewSource.includes('governanceSuggestionBinding') &&
    readFileSync(join(srcRoot, 'api/governance.ts'), 'utf8').includes('requested_capability') &&
    readFileSync(join(srcRoot, 'api/governance.ts'), 'utf8').includes('requested_skill_key'),
  'a bound recommendation click must send its capability/skill key as a control-plane binding',
)
assert(
  viewSource.includes('select-suggestion') && viewSource.includes('handleSuggestionSelect'),
  'the view must handle follow-up suggestion selection through sendPrompt',
)
assert(
  readFileSync(join(srcRoot, 'utils/governance-domains.ts'), 'utf8').includes(
    'governanceSuggestionBinding',
  ) && viewSource.includes('governanceSuggestionBinding(suggestion)'),
  'follow-up selection must send the registered capability or skill binding, not a bare prompt',
)
assert(
  governanceSuggestionBinding({
    capability: 'value_qa_search',
    parameters: { continuation: true },
  })?.parameters?.continuation === true,
  'continuation suggestions must forward the server-authored parameters unchanged',
)
assert(
  timelineSource.includes('governance_skill_plan') &&
    timelineSource.includes('GovernanceSkillPlanCard'),
  'the timeline must dispatch the governance_skill_plan message to the plan card',
)
assert(
  timelineSource.includes('GovernanceTaskSuggestionList') && timelineSource.includes('suggestions'),
  'the timeline must render the session follow-up suggestions after the messages',
)
assert(
  suggestionListSource.includes('直接执行') &&
    suggestionListSource.includes('加入计划并确认') &&
    suggestionListSource.includes('visible.length >= 2') &&
    suggestionListSource.includes('capability || item.skill_key'),
  'the suggestion list must label direct/plan handling, skip fewer than two items, and drop unbound chips',
)
assert(
  skillPlanSource.includes('automatic') &&
    skillPlanSource.includes('requires_confirmation') &&
    skillPlanSource.includes('scope'),
  'the skill plan card must surface steps, confirmation flags and scope',
)
assert(
  skillEntrySource.includes('executor_capability') &&
    skillEntrySource.includes('requires_confirmation'),
  'GovernanceSkillEntry may remain as an unused advanced component with boundary fields',
)
assert(
  projectionSource.includes('showSampleText') &&
    projectionSource.includes('sampleTextVisible') &&
    projectionSource.includes("'review'"),
  'the result projection must gate sample text and keep the review mode independent',
)
assert(
  typesSource.includes('GovernanceRecommendKind') && typesSource.includes("'explanation'"),
  'types must distinguish action recommendations from 治理能力说明',
)
{
  const rescanStart = viewSource.indexOf('async function runRescanAction')
  const sendStart = viewSource.indexOf('async function sendPrompt')
  const rescanFn =
    rescanStart >= 0 && sendStart > rescanStart ? viewSource.slice(rescanStart, sendStart) : ''
  assert(
    viewSource.includes('reloadActiveSession') &&
      viewSource.includes('followRescanUntilSettled') &&
      rescanFn.includes('reloadActiveSession') &&
      !rescanFn.includes('activeSession.value = detail'),
    'rescan confirm must re-GET the session instead of assigning the enqueue ack to activeSession',
  )
}
assert(
  apiSource.includes('GovernanceTaskConfirmAccepted') &&
    typesSource.includes('GovernanceTaskConfirmAccepted'),
  'confirm API typing must use the enqueue ack, not GovernanceSessionDetail',
)

// #88: explicit cultural prerun review creation + frozen report rendering.
const culturalPrerunCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceCulturalPrerunReviewCard.vue'),
  'utf8',
)
const reportEnvelopeSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceReportEnvelope.vue'),
  'utf8',
)
assert(
  timelineSource.includes("message.kind === 'cultural_prerun_review'") &&
    timelineSource.includes('GovernanceCulturalPrerunReviewCard'),
  'the timeline must dispatch the cultural_prerun_review report to its card',
)
assert(
  timelineSource.includes('文化预跑记录审阅任务'),
  'the timeline must label the cultural prerun review message',
)
assert(
  apiSource.includes('createCulturalPrerunReview') &&
    apiSource.includes('/cultural-prerun-reviews'),
  'the api layer must expose the explicit cultural review creation endpoint',
)
assert(
  viewSource.includes('GOVERNANCE_CULTURAL_REVIEW_ACTIONS') &&
    viewSource.includes('createCulturalPrerunReview') &&
    viewSource.includes('runCulturalReviewCreate'),
  'the view must own the cultural review creation call via provide/inject',
)
assert(
  culturalDetailCardSource.includes('创建审阅任务') &&
    culturalDetailCardSource.includes(
      "payload.source_status === 'ok' && payload.review_supported",
    ) &&
    culturalDetailCardSource.includes('GOVERNANCE_CULTURAL_REVIEW_ACTIONS'),
  'the cultural detail card must offer the explicit review button only for reviewable records',
)
assert(
  !culturalDetailCardSource.includes('sendPrompt'),
  'creating a review task must not send a natural-language instruction',
)
assert(
  culturalPrerunCardSource.includes('composite_percentage') &&
    culturalPrerunCardSource.includes('three_agent_stages') &&
    culturalPrerunCardSource.includes('integrity_warnings') &&
    culturalPrerunCardSource.includes('claim_boundaries') &&
    culturalPrerunCardSource.includes('limitations'),
  'the cultural report card must render verbatim metrics, stages, warnings and boundaries',
)
assert(
  culturalPrerunCardSource.includes('内容问题') &&
    culturalPrerunCardSource.includes('评测完整性问题') &&
    culturalPrerunCardSource.includes('issue_lists') &&
    culturalPrerunCardSource.includes('导出证据包') &&
    culturalPrerunCardSource.includes('downloadEvidencePack'),
  'the cultural report card must switch dual issue lists and export the evidence pack',
)
assert(
  apiSource.includes('getCulturalPrerunEvidencePack') &&
    apiSource.includes('/cultural-prerun-review/evidence-pack'),
  'the api layer must expose the frozen cultural evidence-pack endpoint',
)
assert(
  viewSource.includes('runCulturalEvidencePackDownload') &&
    viewSource.includes('getCulturalPrerunEvidencePack'),
  'the view must own cultural evidence-pack downloads via the inject contract',
)
assert(
  reportEnvelopeSource.includes('evaluation_run_status') &&
    reportEnvelopeSource.includes('integrity_status') &&
    reportEnvelopeSource.includes('delivery_readiness') &&
    reportEnvelopeSource.includes('review_task_status'),
  'the reusable report envelope must render the four independent statuses',
)
assert(
  typesSource.includes('CulturalPrerunReviewReport') &&
    typesSource.includes('cultural_prerun_review'),
  'the types must define the frozen cultural prerun review report payload',
)

// #90: explicit risk prerun review creation + frozen report rendering.
const riskPrerunCardSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceRiskPrerunReviewCard.vue'),
  'utf8',
)
assert(
  timelineSource.includes("message.kind === 'risk_prerun_review'") &&
    timelineSource.includes('GovernanceRiskPrerunReviewCard'),
  'the timeline must dispatch the risk_prerun_review report to its card',
)
assert(
  timelineSource.includes('风险预跑记录审阅任务'),
  'the timeline must label the risk prerun review message',
)
assert(
  apiSource.includes('createRiskPrerunReview') && apiSource.includes('/risk-prerun-reviews'),
  'the api layer must expose the explicit risk review creation endpoint',
)
assert(
  viewSource.includes('GOVERNANCE_RISK_REVIEW_ACTIONS') &&
    viewSource.includes('createRiskPrerunReview') &&
    viewSource.includes('runRiskReviewCreate'),
  'the view must own the risk review creation call via provide/inject',
)
assert(
  detailCardSource.includes('创建审阅任务') &&
    detailCardSource.includes("payload.source_status === 'ok' && payload.review_supported") &&
    detailCardSource.includes('GOVERNANCE_RISK_REVIEW_ACTIONS'),
  'the risk detail card must offer the explicit review button only for reviewable records',
)
assert(
  !detailCardSource.includes('sendPrompt'),
  'creating a risk review task must not send a natural-language instruction',
)
assert(
  riskPrerunCardSource.includes('风险识别差异') &&
    riskPrerunCardSource.includes('资产完整性问题') &&
    riskPrerunCardSource.includes('issue_lists') &&
    riskPrerunCardSource.includes('evidence_state') &&
    riskPrerunCardSource.includes('导出证据包') &&
    riskPrerunCardSource.includes('downloadEvidencePack'),
  'the risk report card must switch dual issue lists, show evidence states, and export the evidence pack',
)
assert(
  apiSource.includes('getRiskPrerunEvidencePack') &&
    apiSource.includes('/risk-prerun-review/evidence-pack'),
  'the api layer must expose the frozen risk evidence-pack endpoint',
)
assert(
  viewSource.includes('runRiskEvidencePackDownload') &&
    viewSource.includes('getRiskPrerunEvidencePack'),
  'the view must own risk evidence-pack downloads via the inject contract',
)
assert(
  riskPrerunCardSource.includes('primary_evaluator') &&
    riskPrerunCardSource.includes('baseline_evaluator') &&
    riskPrerunCardSource.includes('dimension_summaries') &&
    riskPrerunCardSource.includes('integrity_warnings') &&
    riskPrerunCardSource.includes('claim_boundaries'),
  'the risk report card must render V7/Base evaluators, dimensions, warnings and boundaries',
)
assert(
  typesSource.includes('RiskPrerunReviewReport') &&
    typesSource.includes('risk_prerun_review') &&
    typesSource.includes('RiskReviewIssueLists') &&
    typesSource.includes('RiskEvidenceState'),
  'the types must define the frozen risk prerun review report and #91 issue/evidence-state payload',
)

// #169 / T5: the standalone `dynbench400_eval` surface is retired. The v2
// `risk_corpus_rescan` cards are the only render path, so assert the absence of
// the legacy components, kinds and export entry rather than their presence.
for (const retired of [
  'components/governance/GovernanceDynbenchEvalConfirmCard.vue',
  'components/governance/GovernanceDynbenchEvalReportCard.vue',
  'components/governance/GovernanceDynbenchEvalDiagnostics.vue',
]) {
  assert(!existsSync(join(srcRoot, retired)), `${retired} must be deleted with the legacy surface`)
}
assert(
  !timelineSource.includes('dynbench400_eval') &&
    !timelineSource.includes('GovernanceDynbenchEval') &&
    !timelineSource.includes('DynBench400'),
  'the timeline must not dispatch or label the retired dynbench400_eval messages',
)
assert(
  !apiSource.includes('getDynbenchEvidencePack') &&
    !apiSource.includes('/dynbench400-eval/evidence-pack') &&
    !viewSource.includes('runDynbenchEvidencePackDownload') &&
    !viewSource.includes('reviseDynbenchEvaluator'),
  'the retired DynBench evidence-pack and evaluator-revision entries must be gone from the client',
)
assert(
  !viewSource.includes('dynbench400_eval') &&
    !viewSource.includes('message.kind === "dynbench400_eval"'),
  'refreshRescanTaskStatuses must only collect risk_corpus_rescan task ids',
)

// #88: upstream judge rates keep their source precision; rounding them to whole
// percent in the UI would silently restate a frozen source metric.
assert(
  formatMetricRate(0.9333) === '93.33%' &&
    formatMetricRate(0.7667) === '76.67%' &&
    formatMetricRate(0.4333) === '43.33%',
  'source rates must keep their two-decimal upstream precision',
)
assert(
  formatMetricRate(1) === '100%' && formatMetricRate(0) === '0%',
  'whole rates must render without padded or trailing zeros',
)
assert(
  formatMetricRate(null) === '—' && formatMetricRate(undefined) === '—',
  'a missing rate must degrade to a dash instead of NaN%',
)
assert(
  culturalPrerunCardSource.includes('formatMetricRate') &&
    culturalDetailCardSource.includes('formatMetricRate') &&
    !culturalPrerunCardSource.includes('Math.round'),
  'both cultural cards must render rates through the shared precision formatter',
)

// #167: 把「DynBench400 输入评测」合并进「输入风险语料在线二次检测」— the
// risk_corpus_rescan v2 card is the single new-work surface, backed by the
// frozen v2 result and its own evidence-pack endpoint.
const riskRescanConfirmSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceRiskRescanConfirmCard.vue'),
  'utf8',
)
const riskRescanResultSource = readFileSync(
  join(srcRoot, 'components/governance/GovernanceRiskRescanResultCard.vue'),
  'utf8',
)
assert(
  riskRescanConfirmSource.includes('输入风险语料在线二次检测') &&
    riskRescanConfirmSource.includes('payload.asset_name') &&
    !riskRescanConfirmSource.includes('课题二输入风险静态验证语料（400条）') &&
    riskRescanConfirmSource.includes('evaluator') &&
    riskRescanConfirmSource.includes('export_requested'),
  'the risk rescan confirm card must use the approved copy, render the server-sent asset name (no duplicated literal), disclose the resolved evaluator, and surface the export preference',
)
assert(
  riskRescanResultSource.includes('输入风险语料在线二次检测') &&
    riskRescanResultSource.includes('风险命中') &&
    riskRescanResultSource.includes('参考标注分歧') &&
    riskRescanResultSource.includes('issue_lists') &&
    riskRescanResultSource.includes('execution_summary') &&
    riskRescanResultSource.includes('executor_identity') &&
    riskRescanResultSource.includes('disclosure_limits') &&
    riskRescanResultSource.includes('integrity_facts') &&
    riskRescanResultSource.includes('GovernanceReportEnvelope') &&
    !riskRescanResultSource.includes('consistent_count') &&
    !riskRescanResultSource.includes('inconsistent_count'),
  'the v2 result card must render envelope + dual issue views + identity/limits and no accuracy metrics',
)
assert(
  riskRescanResultSource.includes('导出证据包') &&
    riskRescanResultSource.includes('downloadRiskRescanEvidencePack') &&
    riskRescanResultSource.includes('export_available'),
  'the completed v2 result must expose the evidence-pack download only when the persisted export contract allows it',
)
assert(
  apiSource.includes('getInputRiskRescanEvidencePack') &&
    apiSource.includes('/input-risk-rescan/evidence-pack') &&
    viewSource.includes('runRiskRescanEvidencePackDownload') &&
    viewSource.includes('getInputRiskRescanEvidencePack'),
  'the api layer + view must own the v2 input-risk evidence-pack endpoint',
)
assert(
  typesSource.includes('InputRiskRescanEvidencePack') &&
    typesSource.includes('GovernanceRiskRescanExecutionSummary') &&
    typesSource.includes('ordered_sample_ids') &&
    typesSource.includes('export_requested') &&
    typesSource.includes('execution_summary'),
  'the types must define the v2 result contract and its evidence pack',
)
assert(
  timelineSource.includes('输入风险语料在线二次检测') &&
    timelineSource.includes('risk_corpus_rescan') &&
    timelineSource.includes('GovernanceRiskRescanConfirmCard') &&
    timelineSource.includes('GovernanceRiskRescanResultCard') &&
    !getGovernanceDomain('input').suggestions.some(
      (suggestion) => suggestion.capability === 'dynbench400_eval',
    ),
  'the timeline and welcome must use the merged product copy and drop the independent DynBench entry',
)
// The shared evaluator / issue / diagnostics vocabulary stays, but it must be
// named for the surviving v2 path rather than the retired DynBench one.
assert(
  typesSource.includes('RiskRescanEvaluator') &&
    typesSource.includes('RiskRescanIssue') &&
    typesSource.includes('RiskRescanEvaluationObject') &&
    typesSource.includes('RiskRescanFailureDiagnostics') &&
    !typesSource.includes('GovernanceDynbenchEval') &&
    !typesSource.includes('DynBenchEvalFailureDiagnostics') &&
    !typesSource.includes('DynBenchEvidencePack'),
  'the retired DynBench payload types must be gone and the shared vocabulary renamed for the v2 path',
)

// #186 ①: a list card's "open detail" is a deterministic bound turn. The card
// emits the displayed record id, the timeline relays it with the capability key,
// and the view sends it as requested_parameters instead of parsing free text.
for (const card of [listCardSource, culturalListCardSource]) {
  assert(
    card.includes('打开详情') && card.includes("$emit('open', record.record_id)"),
    'each system record list card must emit its record id from an explicit open action',
  )
  assert(
    card.includes('记录 ID') && card.includes('复制'),
    'each system record list item must label and copy the record id',
  )
}
assert(
  timelineSource.includes('open-system-record') &&
    timelineSource.includes("capability: 'risk_system_record_detail'") &&
    timelineSource.includes("capability: 'cultural_system_record_detail'"),
  'the timeline must relay record opens with their domain capability',
)
assert(
  viewSource.includes('openSystemRecord') &&
    viewSource.includes('@open-system-record="openSystemRecord"') &&
    viewSource.includes('parameters: { record_id: request.recordId }'),
  'the view must send a record open as bound requested_parameters',
)
assert(
  apiSource.includes('requested_parameters') &&
    typesSource.includes('GovernanceSystemRecordOpenRequest'),
  'the api and types must carry the bound parameter contract for record opens',
)
assert(
  viewSource.includes('!turnBinding') && viewSource.includes('continueClarification'),
  'a bound click must not replay an older awaiting-clarification plan',
)

console.log('governance-shell.smoke.mjs ok')
