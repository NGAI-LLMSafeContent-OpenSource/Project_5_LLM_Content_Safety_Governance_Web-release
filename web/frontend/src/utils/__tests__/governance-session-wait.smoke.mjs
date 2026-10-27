/**
 * Create-session and append-turn wait longer than the planner,
 * and the uncertain-save sentence is only for a wait with no server response (#139).
 *
 * Run with:
 *   node web/frontend/src/utils/__tests__/governance-session-wait.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  GOVERNANCE_UNCERTAIN_SAVE_MESSAGE,
  governanceTurnFailureMessage,
} from '../governance-turn-failure.ts'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const apiSrc = readFileSync(join(srcRoot, 'api/governance.ts'), 'utf8')
const waitMatch = /export const GOVERNANCE_SESSION_WAIT_MS = (\d[\d_]*)/.exec(apiSrc)
assert(waitMatch, 'create/append must name a session wait')
assert(
  Number(waitMatch[1].replaceAll('_', '')) > 60000,
  'session wait must be greater than 60000 ms',
)

function functionSource(source, name, nextName) {
  const start = source.indexOf(`export function ${name}`)
  const end = source.indexOf(`export function ${nextName}`)
  assert(start >= 0 && end > start, `${name} must exist before ${nextName}`)
  return source.slice(start, end)
}

const createSrc = functionSource(apiSrc, 'createGovernanceSession', 'appendGovernanceTurn')
const appendSrc = functionSource(apiSrc, 'appendGovernanceTurn', 'deleteGovernanceSession')
assert(
  createSrc.includes('timeout: GOVERNANCE_SESSION_WAIT_MS'),
  'createGovernanceSession must wait GOVERNANCE_SESSION_WAIT_MS',
)
assert(
  appendSrc.includes('timeout: GOVERNANCE_SESSION_WAIT_MS'),
  'appendGovernanceTurn must wait GOVERNANCE_SESSION_WAIT_MS',
)
assert(
  apiSrc.includes('clarification_plan_id: clarificationPlan.planId') &&
    apiSrc.includes('clarification_plan_version: clarificationPlan.version'),
  'turn requests must carry the durable clarification plan id and concurrency version',
)

const requestSrc = readFileSync(join(srcRoot, 'api/request.ts'), 'utf8')
assert(/timeout:\s*15000/.test(requestSrc), 'global axios timeout stays 15000')
assert(
  !/timeout:\s*(?:6\d{4}|[7-9]\d{4}|\d{6,})/.test(requestSrc),
  'global axios timeout must not be lengthened',
)

const viewSrc = readFileSync(join(srcRoot, 'views/GovernanceView.vue'), 'utf8')
assert(
  viewSrc.includes('governanceTurnFailureMessage(error)'),
  'send failure must go through the no-response helper',
)
assert(
  !viewSrc.includes(GOVERNANCE_UNCERTAIN_SAVE_MESSAGE),
  'the uncertain-save sentence must not be assigned in the view',
)
assert(
  viewSrc.includes("activePlan?.status === 'awaiting_clarification'") &&
    viewSrc.includes('activeSession.value = await getGovernanceSession'),
  'the view must resume only the active plan and recover authoritative state after a failed send',
)
assert(
  viewSrc.includes(
    ':clarification-question="activeSession?.clarification_plan?.question || null"',
  ) &&
    viewSrc.includes('@submit="sendComposerPrompt"') &&
    viewSrc.includes('continueClarification = true'),
  'an awaiting plan must expose its question and route the single composer submit explicitly',
)

const composerSrc = readFileSync(
  join(srcRoot, 'components/governance/GovernanceComposer.vue'),
  'utf8',
)
assert(
  composerSrc.includes('正在回答：') &&
    composerSrc.includes('结束当前问题') &&
    composerSrc.includes('继续回答当前问题') &&
    composerSrc.includes("emit('submit', !props.canStartNewGoal || answeringClarification.value)"),
  'the composer must make clarification routing visible and reversible before one submit action',
)
assert(
  !composerSrc.includes('作为新目标发送') && !composerSrc.includes('submit-new-goal'),
  'the clarification protocol must not be exposed as a second send action',
)

const explained = Object.assign(new Error('没有匹配到已登记的治理技能，未回退到自由能力调用。'), {
  serverResponded: true,
})
assert(
  governanceTurnFailureMessage(explained) === explained.message,
  'a server explanation must be shown as-is',
)
assert(
  governanceTurnFailureMessage(
    Object.assign(new Error('timeout of 60000ms exceeded'), { serverResponded: false }),
  ) === GOVERNANCE_UNCERTAIN_SAVE_MESSAGE,
  'a timed-out request with no response uses the uncertain-save sentence',
)
assert(
  governanceTurnFailureMessage(new Error('Network Error')) === GOVERNANCE_UNCERTAIN_SAVE_MESSAGE,
  'an error without a server response uses the uncertain-save sentence',
)
const failureSrc = readFileSync(join(srcRoot, 'utils/governance-turn-failure.ts'), 'utf8')
assert(
  !failureSrc.includes('请求未完成，请查看返回说明后重试。'),
  'a missing server sentence must not be replaced with an invented one',
)
assert(
  governanceTurnFailureMessage(Object.assign(new Error('   '), { serverResponded: true })) === '',
  'a server response without text stays empty',
)

console.log('governance-session-wait.smoke.mjs: ok')
