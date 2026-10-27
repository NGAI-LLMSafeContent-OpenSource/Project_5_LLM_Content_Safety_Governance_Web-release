<template>
  <main class="governance-shell">
    <GovernanceSidebar
      :sessions="history"
      :total="historyTotal"
      :active-session-id="activeSession?.session_id || null"
      :loading="historyLoading"
      :loading-more="loadingMore"
      :deleting-session-id="deletingSessionId"
      @new-task="resetDraft"
      @open-session="openSession"
      @delete-session="deleteSession"
      @load-more="loadMoreHistory"
    />

    <section class="governance-main">
      <header class="governance-main__header">
        <div>
          <p>统一治理入口</p>
          <strong>{{ activeDomain.label }}</strong>
        </div>

        <div class="governance-tabs" role="tablist" aria-label="选择治理业务域">
          <button
            v-for="(domain, index) in GOVERNANCE_DOMAINS"
            :id="`governance-tab-${domain.key}`"
            ref="domainTabs"
            :key="domain.key"
            class="governance-tab"
            :class="{ 'is-active': activeDomainKey === domain.key }"
            type="button"
            role="tab"
            :aria-selected="activeDomainKey === domain.key"
            :aria-controls="`governance-panel-${domain.key}`"
            :tabindex="activeDomainKey === domain.key ? 0 : -1"
            @click="selectDomain(domain.key)"
            @keydown="handleTabKeydown(index, $event)"
          >
            {{ domain.label }}
          </button>
        </div>

        <span class="governance-main__status">
          <span aria-hidden="true"></span>
          {{ initialLoading ? '正在连接' : pageError ? '连接需复核' : '会话可恢复' }}
        </span>
      </header>

      <section
        :id="`governance-panel-${activeDomain.key}`"
        class="governance-workspace"
        role="tabpanel"
        :aria-labelledby="`governance-tab-${activeDomain.key}`"
        tabindex="0"
      >
        <div
          ref="workspaceBody"
          class="governance-workspace__body"
          :aria-busy="openingSession"
          @scroll.passive="handleWorkspaceScroll"
        >
          <div v-if="pageError" class="governance-page-error" role="alert">
            <span>{{ pageError }}</span>
            <button type="button" :disabled="initialLoading" @click="initialize">重试连接</button>
          </div>
          <GovernanceTimeline
            v-if="activeSession"
            :session="activeSession"
            :domain-label="activeDomain.label"
            :filter-busy="sending"
            @load-more="loadMoreRecords"
            @select-filter="applyRiskFilter"
            @request-overview="requestRiskOverview"
            @open-system-record="openSystemRecord"
            @select-suggestion="handleSuggestionSelect"
          />
          <GovernanceWelcome
            v-else
            :domain="activeDomain"
            @suggestion-select="handleRecommendSelect"
          />
        </div>
        <div v-if="openingSession" class="governance-workspace__restoring">
          <span class="governance-workspace__spinner" aria-hidden="true"></span>
          <p role="status">正在恢复治理会话…</p>
        </div>
        <GovernanceComposer
          v-model="draft"
          :domain-label="activeDomain.label"
          :placeholder="activeDomain.placeholder"
          :busy="sending"
          :blocked="!storageAvailable"
          :restoring="openingSession"
          :error="sendError"
          :can-start-new-goal="
            activeSession?.clarification_plan?.status === 'awaiting_clarification'
          "
          :clarification-plan-id="activeSession?.clarification_plan?.plan_id || null"
          :clarification-plan-version="activeSession?.clarification_plan?.version || null"
          :clarification-question="activeSession?.clarification_plan?.question || null"
          @submit="sendComposerPrompt"
        />
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, provide, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import type {
  GovernanceDomainKey,
  GovernanceResultProjectionData,
  GovernanceSessionDetail,
  GovernanceSessionMessage,
  GovernanceSessionSummary,
  GovernanceSuggestion,
  GovernanceSystemRecordOpenRequest,
  GovernanceTaskSuggestion,
} from '@/types'

import {
  appendGovernanceTurn,
  cancelGovernanceTask,
  confirmGovernanceTask,
  createCulturalPrerunReview,
  createGovernanceSession,
  createRiskPrerunReview,
  deleteGovernanceSession,
  getCulturalPrerunEvidencePack,
  getInputRiskRescanEvidencePack,
  getRiskPrerunEvidencePack,
  getGovernanceSession,
  getGovernanceTask,
  listGovernanceSessions,
  registerGovernanceClient,
  retryGovernanceTask,
  type GovernanceTurnBinding,
} from '@/api/governance'
import GovernanceComposer from '@/components/governance/GovernanceComposer.vue'
import GovernanceSidebar from '@/components/governance/GovernanceSidebar.vue'
import GovernanceTimeline from '@/components/governance/GovernanceTimeline.vue'
import GovernanceWelcome from '@/components/governance/GovernanceWelcome.vue'
import {
  GOVERNANCE_DOMAINS,
  getGovernanceDomain,
  governanceSuggestionBinding,
  isExecutableRecommend,
  isGovernanceTabNavigationKey,
  nextGovernanceDomain,
} from '@/utils/governance-domains'
import { governanceTurnFailureMessage } from '@/utils/governance-turn-failure'
import {
  loadGovernanceClientState,
  saveGovernanceClientState,
} from '@/utils/governance-client-state'
import {
  GOVERNANCE_RESCAN_ACTIONS,
  type GovernanceRescanActions,
} from '@/utils/governance-rescan-actions'
import {
  GOVERNANCE_CULTURAL_REVIEW_ACTIONS,
  type GovernanceCulturalReviewActions,
} from '@/utils/governance-cultural-review-actions'
import {
  GOVERNANCE_RISK_REVIEW_ACTIONS,
  type GovernanceRiskReviewActions,
} from '@/utils/governance-risk-review-actions'
import {
  RISK_OVERVIEW_PROMPT,
  buildRiskFilterPrompt,
  type RiskFilterKey,
} from '@/utils/governance-risk-filters'
import { createUuid } from '@/utils/uuid'

import '@/assets/styles/governance.css'

const browserState = loadGovernanceClientState()
const clientState = browserState.state
const clientId = clientState.clientId

interface GovernanceWorkspaceState {
  session: GovernanceSessionDetail | null
  draft: string
}

const activeDomainKey = ref<GovernanceDomainKey>(clientState.activeDomain)
const domainTabs = ref<HTMLButtonElement[]>([])
const domainWorkspaces = reactive<Record<GovernanceDomainKey, GovernanceWorkspaceState>>({
  input: { session: null, draft: '' },
  output: { session: null, draft: '' },
})
const activeSession = computed<GovernanceSessionDetail | null>({
  get: () => domainWorkspaces[activeDomainKey.value].session,
  set: (session) => {
    domainWorkspaces[activeDomainKey.value].session = session
  },
})
const draft = computed<string>({
  get: () => domainWorkspaces[activeDomainKey.value].draft,
  set: (value) => {
    domainWorkspaces[activeDomainKey.value].draft = value
  },
})
const history = ref<GovernanceSessionSummary[]>([])
const historyTotal = ref(0)
const historyLoading = ref(true)
const initialLoading = ref(true)
const loadingMore = ref(false)
const openingSession = ref(false)
const sending = ref(false)
const deletingSessionId = ref<string | null>(null)
const storageAvailable = ref(browserState.persistent)
const pageError = ref('')
const sendError = ref('')

// Provided to the rescan cards (two levels down) so the view stays the single
// owner of API calls and the timeline does not thread action props through.
const rescanActions = reactive<GovernanceRescanActions>({
  statuses: {},
  results: {},
  busyTaskId: null,
  busyAction: null,
  errorTaskId: null,
  error: '',
  exportBusyTaskId: null,
  exportErrorTaskId: null,
  exportError: '',
  confirm: (taskId) => void runRescanAction('confirm', taskId),
  cancel: (taskId) => void runRescanAction('cancel', taskId),
  retry: (taskId) => void runRescanAction('retry', taskId),
  downloadRiskRescanEvidencePack: (taskId) => void runRiskRescanEvidencePackDownload(taskId),
})
provide(GOVERNANCE_RESCAN_ACTIONS, rescanActions)

// #88: the cultural detail card creates review tasks through the dedicated API.
// Like the rescan contract, the view stays the single owner of the API call and
// provides this action so the card never sends a natural-language instruction.
const culturalReviewActions = reactive<GovernanceCulturalReviewActions>({
  busyRecordId: null,
  errorRecordId: null,
  error: '',
  create: (recordId, recordVersion) => void runCulturalReviewCreate(recordId, recordVersion),
  exportBusyTaskId: null,
  exportErrorTaskId: null,
  exportError: '',
  downloadEvidencePack: (taskId) => void runCulturalEvidencePackDownload(taskId),
})
provide(GOVERNANCE_CULTURAL_REVIEW_ACTIONS, culturalReviewActions)

// #90/#91: risk detail card creates review tasks; report card exports evidence packs.
const riskReviewActions = reactive<GovernanceRiskReviewActions>({
  busyRecordId: null,
  errorRecordId: null,
  error: '',
  create: (recordId, recordVersion) => void runRiskReviewCreate(recordId, recordVersion),
  exportBusyTaskId: null,
  exportErrorTaskId: null,
  exportError: '',
  downloadEvidencePack: (taskId) => void runRiskEvidencePackDownload(taskId),
})
provide(GOVERNANCE_RISK_REVIEW_ACTIONS, riskReviewActions)

// The session timeline scrolls inside `.governance-workspace__body`, not the
// window. Keeping that container mounted preserves its scroll position across
// refreshes, so the view only has to decide where to follow: stay put while the
// user reads above, follow new messages when already near the bottom, and land
// on the newest message when switching sessions (#70).
const workspaceBody = ref<HTMLElement | null>(null)
const followBottom = ref(true)

const NEAR_BOTTOM_THRESHOLD_PX = 80

function isNearWorkspaceBottom(element: HTMLElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= NEAR_BOTTOM_THRESHOLD_PX
}

function handleWorkspaceScroll() {
  const element = workspaceBody.value
  if (element) followBottom.value = isNearWorkspaceBottom(element)
}

function scrollWorkspaceToBottom() {
  const element = workspaceBody.value
  if (!element) return
  element.scrollTop = element.scrollHeight
  followBottom.value = true
}

watch(activeSession, async (session, previous) => {
  if (!session) {
    followBottom.value = true
    return
  }
  const switchedSession = session.session_id !== previous?.session_id
  await nextTick()
  if (switchedSession || followBottom.value) scrollWorkspaceToBottom()
})

interface PendingRequest {
  requestId: string
  domain: GovernanceDomainKey
  sessionId: string | null
  prompt: string
  binding?: GovernanceTurnBinding
  clarificationPlanId?: string
  clarificationPlanVersion?: number
}

let historyRevision = 0
let openRevision = 0
let pendingRequest: PendingRequest | null = null

const activeDomain = computed(() => getGovernanceDomain(activeDomainKey.value))

onMounted(() => void initialize())

function persistState() {
  clientState.activeDomain = activeDomainKey.value
  clientState.recentSessionId = activeSession.value?.session_id || null
  storageAvailable.value = saveGovernanceClientState(clientState)
}

async function initialize() {
  if (initialLoading.value && !historyLoading.value) return
  initialLoading.value = true
  pageError.value = ''
  try {
    await registerGovernanceClient(clientId)
    await refreshHistory()
    if (clientState.recentSessionId) await openSession(clientState.recentSessionId)
  } catch {
    pageError.value = '无法连接治理会话服务。请检查网络或服务状态后重试。'
    historyLoading.value = false
  } finally {
    initialLoading.value = false
  }
}

async function refreshHistory() {
  const revision = ++historyRevision
  historyLoading.value = true
  try {
    const page = await listGovernanceSessions(clientId)
    if (revision !== historyRevision) return
    history.value = page.items
    historyTotal.value = page.total
    pageError.value = ''
  } finally {
    if (revision === historyRevision) historyLoading.value = false
  }
}

async function loadMoreHistory() {
  if (loadingMore.value || history.value.length >= historyTotal.value) return
  const revision = historyRevision
  loadingMore.value = true
  try {
    const page = await listGovernanceSessions(clientId, history.value.length)
    if (revision !== historyRevision) return
    history.value = [...history.value, ...page.items]
    historyTotal.value = page.total
  } catch {
    pageError.value = '更多会话载入失败。请重试。'
  } finally {
    loadingMore.value = false
  }
}

async function openSession(sessionId: string) {
  const revision = ++openRevision
  openingSession.value = true
  pageError.value = ''
  try {
    const session = await getGovernanceSession(clientId, sessionId)
    if (revision !== openRevision) return
    activeDomainKey.value = session.domain
    activeSession.value = session
    draft.value = ''
    sendError.value = ''
    pendingRequest = null
    clearRescanAction()
    clearCulturalReviewAction()
    void refreshRescanTaskStatuses()
    persistState()
  } catch (error) {
    if (revision !== openRevision) return
    if (isNotFound(error)) {
      clientState.recentSessionId = null
      persistState()
      pageError.value = '该治理会话不存在或已从历史隐藏。请选择其他会话。'
    } else {
      pageError.value = '治理会话恢复失败。请检查连接后重试。'
    }
  } finally {
    if (revision === openRevision) openingSession.value = false
  }
}

function isNotFound(error: unknown) {
  return error instanceof Error && error.message === '治理会话不存在'
}

function selectDomain(domain: GovernanceDomainKey) {
  if (domain === activeDomainKey.value) return
  ++openRevision
  openingSession.value = false
  activeDomainKey.value = domain
  sendError.value = ''
  pageError.value = ''
  pendingRequest = null
  clearRescanAction()
  clearCulturalReviewAction()
  if (activeSession.value) void refreshRescanTaskStatuses()
  persistState()
}

function resetDraft() {
  ++openRevision
  openingSession.value = false
  activeSession.value = null
  draft.value = ''
  sendError.value = ''
  pendingRequest = null
  clearRescanAction()
  clearCulturalReviewAction()
  persistState()
}

// #96: bound 推荐任务 send immediately; explanation cards never emit select.
function handleRecommendSelect(suggestion: GovernanceSuggestion) {
  if (sending.value || !isExecutableRecommend(suggestion)) return
  void sendPrompt(suggestion.prompt, governanceSuggestionBinding(suggestion))
}

// #65/#168: follow-up suggestions carry the same trusted binding as the welcome
// cards, so the bound capability/skill key reaches the planner verbatim.
function handleSuggestionSelect(suggestion: GovernanceTaskSuggestion) {
  if (sending.value) return
  const binding = governanceSuggestionBinding(suggestion)
  if (!binding) return
  void sendPrompt(suggestion.prompt, binding)
}

// Deterministic continuation prompts: the backend reuses the previous page
// scope and advances the offset, so the wording only has to be recognised as
// "next page" for the right record type by the assistant in the active domain.
const CONTINUATION_PROMPTS: Record<GovernanceDomainKey, string> = {
  input: '继续浏览下一页风险样本',
  output: '继续查看下一页风险安全系统预跑记录',
}

const CULTURAL_CONTINUATION_PROMPT = '继续查看下一页文化多样性系统预跑记录'
const CBRNE_CONTINUATION_PROMPT = '继续浏览下一页 CBRNE 样本摘要'

function lastPagedRecordKind(messages: GovernanceSessionMessage[]) {
  let kind: GovernanceSessionMessage['kind'] | null = null
  for (const message of messages) {
    if (
      message.kind === 'risk_system_record_search' ||
      message.kind === 'cultural_system_record_search' ||
      message.kind === 'cbrne_dataset_search' ||
      message.kind === 'risk_corpus_search'
    ) {
      kind = message.kind
    }
  }
  return kind
}

function loadMoreRecords() {
  if (activeDomainKey.value !== 'output') {
    const kind = lastPagedRecordKind(activeSession.value?.messages ?? [])
    void sendPrompt(
      kind === 'cbrne_dataset_search' ? CBRNE_CONTINUATION_PROMPT : CONTINUATION_PROMPTS.input,
    )
    return
  }
  const kind = lastPagedRecordKind(activeSession.value?.messages ?? [])
  void sendPrompt(
    kind === 'cultural_system_record_search'
      ? CULTURAL_CONTINUATION_PROMPT
      : CONTINUATION_PROMPTS.output,
  )
}

// Clickable risk filter values (#60) only make sense in the input risk domain;
// the prompt names the capability field verbatim so the assistant maps it onto
// the existing `risk_corpus_search` parameters without a new backend route.
function applyRiskFilter(payload: { key: RiskFilterKey; value: string }) {
  if (activeDomainKey.value !== 'input' || sending.value) return
  void sendPrompt(buildRiskFilterPrompt(payload.key, payload.value))
}

function requestRiskOverview() {
  if (activeDomainKey.value !== 'input' || sending.value) return
  void sendPrompt(RISK_OVERVIEW_PROMPT)
}

function clearRescanAction() {
  rescanActions.statuses = {}
  rescanActions.results = {}
  rescanActions.busyTaskId = null
  rescanActions.busyAction = null
  rescanActions.errorTaskId = null
  rescanActions.error = ''
}

function clearCulturalReviewAction() {
  culturalReviewActions.busyRecordId = null
  culturalReviewActions.errorRecordId = null
  culturalReviewActions.error = ''
}

// The task-level aggregated result (#64) is the only payload that carries run
// provenance; the result message payload does not. Narrow it without `any`.
function asProjectionResult(
  value: Record<string, unknown> | null | undefined,
): GovernanceResultProjectionData | null {
  if (!value || typeof value !== 'object') return null
  const summary = value.summary
  if (!summary || typeof summary !== 'object') return null
  return value as unknown as GovernanceResultProjectionData
}

// Confirmation-required tasks need their current server status after a refresh
// or a session switch; the view owns the API call (11-code-patterns.md 模式 3)
// and provides the result to the rescan cards.
async function refreshRescanTaskStatuses() {
  const taskIds = [
    ...new Set(
      (activeSession.value?.messages ?? [])
        .filter((message) => message.kind === 'risk_corpus_rescan')
        .map((message) => message.payload?.task_id)
        .filter((taskId): taskId is string => typeof taskId === 'string' && !!taskId),
    ),
  ]
  if (taskIds.length === 0) {
    rescanActions.statuses = {}
    rescanActions.results = {}
    return
  }
  const entries = await Promise.all(
    taskIds.map(async (taskId) => {
      try {
        const detail = await getGovernanceTask(clientId, taskId)
        return [taskId, detail.status, asProjectionResult(detail.result)] as const
      } catch {
        return [taskId, 'unknown', null] as const
      }
    }),
  )
  rescanActions.statuses = Object.fromEntries(entries.map(([taskId, status]) => [taskId, status]))
  rescanActions.results = Object.fromEntries(entries.map(([taskId, , result]) => [taskId, result]))
}

// Confirm returns a 202 enqueue ack; cancel may return a task snapshot or
// session detail; retry returns session detail. Never assign the raw response
// to activeSession — always re-GET the session so the timeline stays intact.
const RESCAN_ACTIONS = {
  confirm: confirmGovernanceTask,
  cancel: cancelGovernanceTask,
  retry: retryGovernanceTask,
} as const

const TERMINAL_RESCAN_STATUSES = new Set([
  'completed',
  'completed_partial',
  'failed',
  'timeout',
  'cancelled',
])

const IN_FLIGHT_RESCAN_STATUSES = new Set(['queued', 'running', 'cancelling'])

function stillOnSession(sessionId: string | null, domain: GovernanceDomainKey) {
  return (
    sessionId !== null &&
    activeDomainKey.value === domain &&
    activeSession.value?.session_id === sessionId
  )
}

async function reloadActiveSession(sessionId: string) {
  const session = await getGovernanceSession(clientId, sessionId)
  activeSession.value = session
  await refreshRescanTaskStatuses()
}

/** Poll task snapshot until terminal (or give up); then refresh the session
 * so Worker-written result messages appear without a full page reload. */
async function followRescanUntilSettled(
  taskId: string,
  sessionId: string,
  domain: GovernanceDomainKey,
) {
  const deadline = Date.now() + 120_000
  while (Date.now() < deadline) {
    if (!stillOnSession(sessionId, domain)) return
    await new Promise((resolve) => setTimeout(resolve, 1500))
    if (!stillOnSession(sessionId, domain)) return
    try {
      const detail = await getGovernanceTask(clientId, taskId)
      rescanActions.statuses = { ...rescanActions.statuses, [taskId]: detail.status }
      if (detail.result) {
        rescanActions.results = {
          ...rescanActions.results,
          [taskId]: asProjectionResult(detail.result),
        }
      }
      if (TERMINAL_RESCAN_STATUSES.has(detail.status)) {
        if (stillOnSession(sessionId, domain)) await reloadActiveSession(sessionId)
        return
      }
      if (!IN_FLIGHT_RESCAN_STATUSES.has(detail.status)) {
        if (stillOnSession(sessionId, domain)) await reloadActiveSession(sessionId)
        return
      }
    } catch {
      // Keep the queued/running label; the user can refresh the session.
      return
    }
  }
}

async function runRescanAction(action: keyof typeof RESCAN_ACTIONS, taskId: string) {
  if (rescanActions.busyTaskId) return
  const sessionId = activeSession.value?.session_id || null
  const domain = activeDomainKey.value
  if (!sessionId) return
  rescanActions.busyTaskId = taskId
  rescanActions.busyAction = action
  rescanActions.errorTaskId = null
  rescanActions.error = ''
  pendingRequest = null
  try {
    await RESCAN_ACTIONS[action](clientId, taskId)
    if (!stillOnSession(sessionId, domain)) return
    await reloadActiveSession(sessionId)
    try {
      await refreshHistory()
    } catch {
      pageError.value = '操作已保存，但会话历史刷新失败。请重试连接。'
    }
    if (action === 'confirm' && stillOnSession(sessionId, domain)) {
      // Confirm is async; clear the button busy state while we follow the queue.
      rescanActions.busyTaskId = null
      rescanActions.busyAction = null
      await followRescanUntilSettled(taskId, sessionId, domain)
    }
  } catch (error) {
    rescanActions.errorTaskId = taskId
    rescanActions.error =
      error instanceof Error && error.message ? error.message : '操作未确认完成，请刷新会话后重试。'
  } finally {
    if (rescanActions.busyTaskId === taskId) {
      rescanActions.busyTaskId = null
      rescanActions.busyAction = null
    }
  }
}

async function sendPrompt(
  promptOverride?: string,
  binding?: GovernanceTurnBinding,
  continueClarification = true,
) {
  const prompt = promptOverride ?? draft.value
  const capability = binding?.capability?.trim()
  const skillKey = binding?.skillKey?.trim()
  const turnBinding =
    capability || skillKey
      ? {
          ...(capability ? { capability } : {}),
          ...(capability && binding?.parameters ? { parameters: binding.parameters } : {}),
          ...(skillKey ? { skillKey } : {}),
        }
      : undefined
  if (!prompt.trim() || sending.value || !storageAvailable.value) return
  const domain = activeDomainKey.value
  const currentSessionId = activeSession.value?.session_id || null
  const activePlan = activeSession.value?.clarification_plan
  const clarificationPlan =
    currentSessionId &&
    continueClarification &&
    !turnBinding &&
    activePlan?.status === 'awaiting_clarification'
      ? { planId: activePlan.plan_id, version: activePlan.version }
      : undefined
  const requestId =
    pendingRequest &&
    pendingRequest.domain === domain &&
    pendingRequest.sessionId === currentSessionId &&
    pendingRequest.prompt === prompt &&
    pendingRequest.binding?.capability === turnBinding?.capability &&
    pendingRequest.binding?.skillKey === turnBinding?.skillKey &&
    JSON.stringify(pendingRequest.binding?.parameters ?? null) ===
      JSON.stringify(turnBinding?.parameters ?? null) &&
    pendingRequest.clarificationPlanId === clarificationPlan?.planId &&
    pendingRequest.clarificationPlanVersion === clarificationPlan?.version
      ? pendingRequest.requestId
      : createUuid()
  pendingRequest = {
    requestId,
    domain,
    sessionId: currentSessionId,
    prompt,
    binding: turnBinding,
    clarificationPlanId: clarificationPlan?.planId,
    clarificationPlanVersion: clarificationPlan?.version,
  }
  sending.value = true
  sendError.value = ''
  clearRescanAction()
  clearCulturalReviewAction()
  try {
    if (currentSessionId) {
      const detail = await appendGovernanceTurn(
        clientId,
        currentSessionId,
        domain,
        prompt,
        requestId,
        turnBinding,
        clarificationPlan,
      )
      if (
        activeDomainKey.value === domain &&
        activeSession.value?.session_id === currentSessionId
      ) {
        activeSession.value = detail
        if (promptOverride === undefined) draft.value = ''
        void refreshRescanTaskStatuses()
      }
    } else {
      const session = await createGovernanceSession(
        clientId,
        domain,
        prompt,
        requestId,
        turnBinding,
        clarificationPlan,
      )
      if (activeDomainKey.value === domain && !activeSession.value) {
        activeSession.value = session
        if (promptOverride === undefined) draft.value = ''
        void refreshRescanTaskStatuses()
        persistState()
      }
    }
    pendingRequest = null
    try {
      await refreshHistory()
    } catch {
      pageError.value = '请求已保存，但会话历史刷新失败。请重试连接。'
    }
  } catch (error) {
    sendError.value = governanceTurnFailureMessage(error)
    // A timeout, duplicate submission, or stale planning version can leave the
    // server ahead of this tab. Reload the authoritative plan so the next turn
    // resumes with its current stable id/version instead of guessing from chat.
    if (currentSessionId && activeSession.value?.session_id === currentSessionId) {
      try {
        activeSession.value = await getGovernanceSession(clientId, currentSessionId)
        persistState()
      } catch (recoveryError) {
        console.error('Failed to recover governance session after send error', recoveryError)
        ElMessage.error('请求失败，且会话状态刷新失败。请重新打开该会话后再继续。')
      }
    }
  } finally {
    sending.value = false
  }
}

function sendComposerPrompt(continueClarification: boolean) {
  void sendPrompt(undefined, undefined, continueClarification)
}

/**
 * A list card's "open detail" is a deterministic control-plane action: the
 * capability and record id travel as bound parameters, so the turn never
 * depends on the model mapping a displayed name back to its id. It also starts
 * a new goal instead of replaying an older clarification plan.
 */
function openSystemRecord(request: GovernanceSystemRecordOpenRequest) {
  const label =
    request.capability === 'cultural_system_record_detail'
      ? '打开文化多样性系统预跑记录详情'
      : '打开风险安全系统预跑记录详情'
  void sendPrompt(`${label}：${request.recordId}`, {
    capability: request.capability,
    parameters: { record_id: request.recordId },
  })
}

// #88: the dedicated endpoint returns the refreshed session detail carrying the
// frozen report message, so unlike the rescan flow the view can assign it
// directly to `activeSession` (no task polling, no upstream re-read). The report
// itself always renders from this persisted payload.
function saveTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function runRiskRescanEvidencePackDownload(taskId: string) {
  if (rescanActions.exportBusyTaskId) return
  rescanActions.exportBusyTaskId = taskId
  rescanActions.exportErrorTaskId = null
  rescanActions.exportError = ''
  try {
    const pack = await getInputRiskRescanEvidencePack(clientId, taskId)
    const prefix = `input-risk-rescan-${taskId}`
    saveTextFile(`${prefix}-report.html`, pack.artifacts['report.html'], 'text/html;charset=utf-8')
    saveTextFile(`${prefix}-issues.csv`, pack.artifacts['issues.csv'], 'text/csv;charset=utf-8')
    saveTextFile(
      `${prefix}-issues.json`,
      pack.artifacts['issues.json'],
      'application/json;charset=utf-8',
    )
    saveTextFile(
      `${prefix}-manifest.json`,
      pack.artifacts['manifest.json'],
      'application/json;charset=utf-8',
    )
  } catch (error) {
    rescanActions.exportErrorTaskId = taskId
    rescanActions.exportError =
      error instanceof Error && error.message ? error.message : '证据包导出失败，请刷新会话后重试。'
  } finally {
    if (rescanActions.exportBusyTaskId === taskId) {
      rescanActions.exportBusyTaskId = null
    }
  }
}

async function runCulturalEvidencePackDownload(taskId: string) {
  if (culturalReviewActions.exportBusyTaskId) return
  culturalReviewActions.exportBusyTaskId = taskId
  culturalReviewActions.exportErrorTaskId = null
  culturalReviewActions.exportError = ''
  try {
    const pack = await getCulturalPrerunEvidencePack(clientId, taskId)
    const prefix = `cultural-prerun-review-${taskId}`
    saveTextFile(`${prefix}-report.html`, pack.artifacts['report.html'], 'text/html;charset=utf-8')
    saveTextFile(`${prefix}-issues.csv`, pack.artifacts['issues.csv'], 'text/csv;charset=utf-8')
    saveTextFile(
      `${prefix}-issues.json`,
      pack.artifacts['issues.json'],
      'application/json;charset=utf-8',
    )
    saveTextFile(
      `${prefix}-manifest.json`,
      pack.artifacts['manifest.json'],
      'application/json;charset=utf-8',
    )
  } catch (error) {
    culturalReviewActions.exportErrorTaskId = taskId
    culturalReviewActions.exportError =
      error instanceof Error && error.message ? error.message : '证据包导出失败，请刷新会话后重试。'
  } finally {
    if (culturalReviewActions.exportBusyTaskId === taskId) {
      culturalReviewActions.exportBusyTaskId = null
    }
  }
}

async function runCulturalReviewCreate(recordId: string, recordVersion: string) {
  if (culturalReviewActions.busyRecordId) return
  const sessionId = activeSession.value?.session_id || null
  const domain = activeDomainKey.value
  if (!sessionId || domain !== 'output') return
  culturalReviewActions.busyRecordId = recordId
  culturalReviewActions.errorRecordId = null
  culturalReviewActions.error = ''
  pendingRequest = null
  try {
    const detail = await createCulturalPrerunReview(clientId, sessionId, recordId, recordVersion)
    if (!stillOnSession(sessionId, domain)) return
    activeSession.value = detail
    try {
      await refreshHistory()
    } catch {
      pageError.value = '审阅任务已创建，但会话历史刷新失败。请重试连接。'
    }
  } catch (error) {
    if (!stillOnSession(sessionId, domain)) return
    culturalReviewActions.errorRecordId = recordId
    culturalReviewActions.error =
      error instanceof Error && error.message
        ? error.message
        : '审阅任务创建未确认完成，请刷新会话后重试。'
  } finally {
    if (culturalReviewActions.busyRecordId === recordId) {
      culturalReviewActions.busyRecordId = null
    }
  }
}

async function runRiskReviewCreate(recordId: string, recordVersion: string) {
  if (riskReviewActions.busyRecordId) return
  const sessionId = activeSession.value?.session_id || null
  const domain = activeDomainKey.value
  if (!sessionId || domain !== 'output') return
  riskReviewActions.busyRecordId = recordId
  riskReviewActions.errorRecordId = null
  riskReviewActions.error = ''
  pendingRequest = null
  try {
    const detail = await createRiskPrerunReview(clientId, sessionId, recordId, recordVersion)
    if (!stillOnSession(sessionId, domain)) return
    activeSession.value = detail
    try {
      await refreshHistory()
    } catch {
      pageError.value = '审阅任务已创建，但会话历史刷新失败。请重试连接。'
    }
  } catch (error) {
    if (!stillOnSession(sessionId, domain)) return
    riskReviewActions.errorRecordId = recordId
    riskReviewActions.error =
      error instanceof Error && error.message
        ? error.message
        : '审阅任务创建未确认完成，请刷新会话后重试。'
  } finally {
    if (riskReviewActions.busyRecordId === recordId) {
      riskReviewActions.busyRecordId = null
    }
  }
}

async function runRiskEvidencePackDownload(taskId: string) {
  if (riskReviewActions.exportBusyTaskId) return
  riskReviewActions.exportBusyTaskId = taskId
  riskReviewActions.exportErrorTaskId = null
  riskReviewActions.exportError = ''
  try {
    const pack = await getRiskPrerunEvidencePack(clientId, taskId)
    const prefix = `risk-prerun-review-${taskId}`
    saveTextFile(`${prefix}-report.html`, pack.artifacts['report.html'], 'text/html;charset=utf-8')
    saveTextFile(`${prefix}-issues.csv`, pack.artifacts['issues.csv'], 'text/csv;charset=utf-8')
    saveTextFile(
      `${prefix}-issues.json`,
      pack.artifacts['issues.json'],
      'application/json;charset=utf-8',
    )
    saveTextFile(
      `${prefix}-manifest.json`,
      pack.artifacts['manifest.json'],
      'application/json;charset=utf-8',
    )
  } catch (error) {
    riskReviewActions.exportErrorTaskId = taskId
    riskReviewActions.exportError =
      error instanceof Error && error.message ? error.message : '证据包导出失败，请刷新会话后重试。'
  } finally {
    if (riskReviewActions.exportBusyTaskId === taskId) {
      riskReviewActions.exportBusyTaskId = null
    }
  }
}

async function deleteSession(session: GovernanceSessionSummary) {
  if (deletingSessionId.value) return
  try {
    await ElMessageBox.confirm(
      `“${session.title}”将从普通历史中隐藏；服务端记录仍会保留。`,
      '删除治理会话',
      { confirmButtonText: '从历史隐藏', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  deletingSessionId.value = session.session_id
  try {
    await deleteGovernanceSession(clientId, session.session_id)
    history.value = history.value.filter((item) => item.session_id !== session.session_id)
    historyTotal.value = Math.max(0, historyTotal.value - 1)
    if (activeSession.value?.session_id === session.session_id) {
      resetDraft()
    } else {
      const workspace = Object.values(domainWorkspaces).find(
        (item) => item.session?.session_id === session.session_id,
      )
      if (workspace) workspace.session = null
    }
    if (clientState.recentSessionId === session.session_id) {
      clientState.recentSessionId = null
      persistState()
    }
    ElMessage.success('治理会话已从历史隐藏。')
  } catch {
    pageError.value = '删除未确认完成，会话仍显示在历史中。请重试。'
  } finally {
    deletingSessionId.value = null
  }
}

function handleTabKeydown(index: number, event: KeyboardEvent) {
  if (!isGovernanceTabNavigationKey(event.key)) return

  event.preventDefault()
  const domain = nextGovernanceDomain(activeDomainKey.value, event.key)
  selectDomain(domain)
  const targetIndex =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? GOVERNANCE_DOMAINS.length - 1
        : index + (event.key === 'ArrowRight' ? 1 : -1)
  const normalizedIndex = (targetIndex + GOVERNANCE_DOMAINS.length) % GOVERNANCE_DOMAINS.length
  void nextTick(() => domainTabs.value[normalizedIndex]?.focus())
}
</script>
