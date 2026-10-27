import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TabKey } from '@/types'
import {
  adoptCandidateIndicator,
  definitionTypeForTab,
  getMiningTask,
  getMiningTaskArtifacts,
  getMiningTaskHistoryResults,
  getMiningTaskLogs,
  getMiningTaskResults,
  listMiningTaskHistory,
  rejectCandidateIndicator,
  saveMiningTaskToHistory,
  startDefinitionMiningTask,
  updateCandidateIndicator,
  type CandidateUpdatePayload,
  type CandidateIndicator,
  type MiningTaskDetail,
  type MiningTaskStatus,
} from '@/api/definition'
import { useStandardStore } from '@/stores/standard'
import {
  buildDefinitionBranches,
  definitionTabConfigs,
  type DefinitionStepKey,
  type DefinitionStandard,
  type DefinitionStandardStatus,
  type DefinitionTabConfig,
} from '@/utils/definitionConfig'
import { buildDefinitionWorkflowPayload } from '@/utils/definitionWorkflowPayload'
import { scrollToPageTop } from '@/utils/scroll'
import type {
  DefinitionFormState,
  DefinitionHistoryViewerState,
  DefinitionMiningState,
} from '@/types/definition'

const pollingIntervalMs = 1000
const pollingWindowMs = 360_000
const maxPollingAttempts = Math.ceil(pollingWindowMs / pollingIntervalMs)
const runningProgressCap = 92
type InputSyncableTabKey = Extract<TabKey, 'input-value' | 'input-risk'>

function buildInitialFormState(config: DefinitionTabConfig): DefinitionFormState {
  void config
  return {
    uploadedDocuments: [],
    webLinksText: '',
    miningDemand: 'level3',
  }
}

function splitMultilineValue(value: string) {
  return value
    .split(/[\s,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function smoothRunningProgress(currentProgress: number, backendProgress: number, attempt: number) {
  const elapsedSeconds = Math.floor((attempt * pollingIntervalMs) / 1000)
  const estimatedProgress = Math.min(
    runningProgressCap,
    Math.max(backendProgress, 28) + Math.floor(elapsedSeconds / 3),
  )
  return Math.max(currentProgress, estimatedProgress)
}

function buildInitialStandardStatusByTab() {
  return Object.values(definitionTabConfigs).reduce(
    (acc, config) => {
      acc[config.key] = config.standards.reduce<Record<string, DefinitionStandardStatus>>(
        (states, item) => {
          states[item.id] = item.status
          return states
        },
        {},
      )
      return acc
    },
    {} as Record<TabKey, Record<string, DefinitionStandardStatus>>,
  )
}

function buildInitialMiningStateByTab() {
  return Object.values(definitionTabConfigs).reduce(
    (acc, config) => {
      acc[config.key] = {
        taskId: '',
        inputId: null,
        status: 'idle',
        loading: false,
        timedOut: false,
        error: '',
        stats: {},
        progress: 0,
        logs: [],
        artifacts: [],
        candidates: [],
        finishedAt: '',
        createdAt: '',
        savedToHistory: false,
        historyTitle: '',
        history: [],
        historyLoading: false,
        historyError: '',
      }
      return acc
    },
    {} as Record<TabKey, DefinitionMiningState>,
  )
}

function buildInitialStepByTab(step: DefinitionStepKey = 1) {
  return Object.values(definitionTabConfigs).reduce(
    (acc, config) => {
      acc[config.key] = step
      return acc
    },
    {} as Record<TabKey, DefinitionStepKey>,
  )
}

function formatMiningTimestamp(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function mapCandidateStatus(status: CandidateIndicator['status']): DefinitionStandardStatus {
  if (status === 'adopted') return 'adopted'
  if (status === 'rejected') return 'ignored'
  if (status === 'edited') return 'edited'
  return 'pending'
}

function candidateStandardId(candidateId: number) {
  return `candidate-${candidateId}`
}

/** 课题一口径更名：挖掘结果挂到预定一级树下 */
const VALUE_LEVEL1_ALIASES: Record<string, string> = {
  伦理敏感度: '伦理合规度',
  文化忠诚度: '文化忠实度',
}

function normalizeValueLevel1(level1: string) {
  return VALUE_LEVEL1_ALIASES[level1] ?? level1
}

function candidateToStandard(
  tab: TabKey,
  candidate: CandidateIndicator,
  baseStandards: DefinitionStandard[],
): DefinitionStandard {
  const status = mapCandidateStatus(candidate.status)
  const level1 = tab === 'input-value' ? normalizeValueLevel1(candidate.level1) : candidate.level1
  const matchedBaseStandard = baseStandards.find(
    (item) => item.level1 === level1 && item.level2 === candidate.level2,
  )
  return {
    id: candidateStandardId(candidate.id),
    candidateId: candidate.id,
    definitionType: tab,
    name: candidate.name || candidate.level3,
    definition: candidate.definition,
    source: candidate.source,
    formula: candidate.formula,
    rationale: candidate.rationale,
    evidenceText: candidate.evidence_text,
    category: matchedBaseStandard?.category ?? level1,
    level1,
    level2: candidate.level2,
    level3: candidate.level3,
    tag: candidate.confidence ? `置信度 ${Math.round(candidate.confidence * 100)}%` : '后端候选',
    defaultEnabled: status !== 'ignored',
    status,
  }
}

function buildCandidateUpdatePayload(candidate: CandidateIndicator) {
  return {
    name: candidate.name,
    level1: candidate.level1,
    level2: candidate.level2,
    level3: candidate.level3,
    definition: candidate.definition,
    source: candidate.source,
    formula: candidate.formula,
    rationale: candidate.rationale,
    evidence_text: candidate.evidence_text,
  }
}

function canSyncDefinitionStandardsToInput(tab: TabKey): tab is InputSyncableTabKey {
  return tab === 'input-value' || tab === 'input-risk'
}

function shouldSyncDefinitionStandardToInput(standard: DefinitionStandard) {
  return standard.status === 'adopted'
}

function topic1ConnectionFailureMessage() {
  return [
    '后端 API 请求失败，无法连接课题一主流价值评估体系服务 (127.0.0.1:6102)。',
    '当前不会展示本地预设或模拟数据，请先启动 Project_1_Construction_of_Evaluation_System/backend 后重试。',
    '如需临时查看课题五定义模块流程，可重启课题五后端并设置 TOPIC1_ALGORITHM_MODE=local_adapter。',
    '详见 Project_1_Construction_of_Evaluation_System/backend/main.py。',
  ].join('\n')
}

function isTopic1ConnectionFailure(message: string) {
  return (
    message.includes('Project1Adapter') ||
    message.includes('127.0.0.1:6102') ||
    message.includes('start-mining request failed')
  )
}

function definitionMiningFailureMessage(task: MiningTaskDetail) {
  const rawMessage = task.error_message || '后端挖掘任务执行失败'
  const failureStage = task.failure_stage || ''

  if (failureStage === 'Project1Adapter' || isTopic1ConnectionFailure(rawMessage)) {
    return topic1ConnectionFailureMessage()
  }

  return rawMessage
}

export function useDefinitionWorkflow() {
  const standardStore = useStandardStore()
  const activeTab = ref<TabKey>('input-value')
  const activeStep = ref<DefinitionStepKey>(1)
  const maxUnlockedStep = ref<DefinitionStepKey>(1)
  const stepByTab = reactive(buildInitialStepByTab(1))
  const maxUnlockedStepByTab = reactive(buildInitialStepByTab(1))
  const standardStatusByTab = ref<Record<TabKey, Record<string, DefinitionStandardStatus>>>(
    buildInitialStandardStatusByTab(),
  )
  const miningStateByTab = reactive(buildInitialMiningStateByTab())
  const definitionFormStateByTab = reactive(
    Object.values(definitionTabConfigs).reduce(
      (acc, config) => {
        acc[config.key] = buildInitialFormState(config)
        return acc
      },
      {} as Record<TabKey, DefinitionFormState>,
    ),
  )
  const historyViewer = reactive<DefinitionHistoryViewerState>({
    open: false,
    loading: false,
    error: '',
    taskId: '',
    title: '',
    subtitle: '',
    rootTitle: '',
    branches: [],
  })

  const activeTabConfig = computed(() => definitionTabConfigs[activeTab.value])
  const activeTabFormState = computed(() => definitionFormStateByTab[activeTab.value])
  const activeMiningState = computed(() => miningStateByTab[activeTab.value])
  const activeBackendStandards = computed(() =>
    activeMiningState.value.candidates.map((candidate) =>
      candidateToStandard(activeTab.value, candidate, activeTabConfig.value.standards),
    ),
  )
  const activeStandards = computed(() =>
    activeBackendStandards.value.map((item) => ({
      ...item,
      status: standardStatusByTab.value[activeTab.value][item.id] ?? item.status,
    })),
  )
  const activeBranches = computed(() =>
    buildDefinitionBranches([...activeTabConfig.value.standards, ...activeStandards.value]),
  )
  const definitionWorkflowPayload = computed(() =>
    buildDefinitionWorkflowPayload({
      activeTab: activeTab.value,
      canonicalTabConfigs: definitionTabConfigs,
      formStateByTab: definitionFormStateByTab,
      standardStatusByTab: standardStatusByTab.value,
    }),
  )
  function persistActiveTabStep() {
    const tab = activeTab.value
    stepByTab[tab] = activeStep.value
    maxUnlockedStepByTab[tab] = maxUnlockedStep.value
  }

  function applyTabStep(tab: TabKey) {
    activeStep.value = stepByTab[tab] || 1
    maxUnlockedStep.value = maxUnlockedStepByTab[tab] || 1
  }

  function unlockStepsForMiningStatus(tab: TabKey, status: MiningTaskStatus | 'idle') {
    if (status === 'completed' || status === 'failed') {
      maxUnlockedStepByTab[tab] = 3
      if (stepByTab[tab] < 2) stepByTab[tab] = 2
    } else if (status === 'running') {
      maxUnlockedStepByTab[tab] = Math.max(maxUnlockedStepByTab[tab], 2) as DefinitionStepKey
      if (stepByTab[tab] < 2) stepByTab[tab] = 2
    }
  }

  async function switchTab(key: TabKey) {
    if (key === activeTab.value) return
    persistActiveTabStep()
    activeTab.value = key
    applyTabStep(key)
    scrollToPageTop()
    if (!miningStateByTab[key].history.length) {
      await loadMiningHistoryForTab(key)
    }
  }

  function showBlockedStepHint(step: number) {
    const messages: Record<number, string> = {
      1: '请按流程从第 1 步开始完成定义模块。',
      2: '请先完成第 1 步后，再进入第 2 步。',
      3: '请先完成第 1、2 步后，再进入第 3 步。',
    }
    ElMessage.warning(messages[step] ?? '请按当前页面流程逐步查看。')
  }

  function isMiningTerminal(state = activeMiningState.value) {
    return state.status === 'completed' || state.status === 'failed'
  }

  function canEnterMindmapStep() {
    return isMiningTerminal()
  }

  function goToStep(step: DefinitionStepKey) {
    if (step === 1) {
      activeStep.value = 1
      persistActiveTabStep()
      scrollToPageTop()
      return
    }

    if (step === 3 && !canEnterMindmapStep()) {
      ElMessage.warning('挖掘任务完成或失败后，才能进入指标体系浏览。')
      return
    }

    if (step === activeStep.value + 1) {
      activeStep.value = step
      maxUnlockedStep.value = Math.max(maxUnlockedStep.value, step) as DefinitionStepKey
      persistActiveTabStep()
      scrollToPageTop()
      return
    }

    if (step <= maxUnlockedStep.value) {
      activeStep.value = step
      persistActiveTabStep()
      scrollToPageTop()
      return
    }

    showBlockedStepHint(step)
  }

  function handleStepIndicatorUpdate(step: number) {
    if (step < 1 || step > 3) return
    goToStep(step as DefinitionStepKey)
  }

  function updateActiveTabFormState(value: DefinitionFormState) {
    definitionFormStateByTab[activeTab.value] = value
  }

  async function refreshMiningTask(tab: TabKey, taskId: string) {
    const state = miningStateByTab[tab]
    const [results, logs, artifacts] = await Promise.all([
      getMiningTaskResults(taskId),
      getMiningTaskLogs(taskId),
      getMiningTaskArtifacts(taskId),
    ])

    state.status = results.status
    state.stats = results.stats ?? {}
    state.progress = results.progress ?? (results.status === 'completed' ? 100 : state.progress)
    state.logs = logs
    state.artifacts = artifacts.artifacts
    state.candidates = results.candidate_indicators ?? []
    state.candidates.forEach((candidate) => {
      standardStatusByTab.value[tab][candidateStandardId(candidate.id)] = mapCandidateStatus(
        candidate.status,
      )
    })
  }

  async function loadMiningTaskSnapshot(tab: TabKey, taskId: string) {
    const state = miningStateByTab[tab]
    const [task, logs] = await Promise.all([getMiningTask(taskId), getMiningTaskLogs(taskId)])

    state.status = task.status
    state.stats = task.stats ?? {}
    state.progress = Math.max(state.progress, task.progress ?? state.progress)
    state.logs = logs
    state.finishedAt = task.finished_at || state.finishedAt || ''
    state.createdAt = task.created_at || state.createdAt || ''
    state.savedToHistory = Boolean(task.saved_to_history)
    state.historyTitle = task.history_title || ''
    return task
  }

  async function pollMiningTask(tab: TabKey, taskId: string) {
    const state = miningStateByTab[tab]

    for (let attempt = 0; attempt < maxPollingAttempts; attempt += 1) {
      const task = await loadMiningTaskSnapshot(tab, taskId)

      if (task.status === 'completed' || task.status === 'failed') {
        if (task.status === 'failed') {
          const message = definitionMiningFailureMessage(task)
          state.error = message
          try {
            await refreshMiningTask(tab, taskId)
          } catch {
            state.status = 'failed'
          }
          throw new Error(message)
        }
        await refreshMiningTask(tab, taskId)
        state.progress = 100
        return
      }

      state.progress = smoothRunningProgress(
        state.progress,
        task.progress ?? state.progress,
        attempt,
      )
      await wait(pollingIntervalMs)
    }

    state.timedOut = true
    throw new Error('挖掘任务可能仍在后端执行，请稍后刷新查看任务结果。')
  }

  async function loadMiningHistoryForTab(tab: TabKey) {
    const state = miningStateByTab[tab]
    state.historyLoading = true
    state.historyError = ''
    try {
      state.history = await listMiningTaskHistory(tab, 20)
    } catch (error) {
      state.history = []
      state.historyError = error instanceof Error ? error.message : '历史记录加载失败'
    } finally {
      state.historyLoading = false
    }
  }

  async function refreshActiveMiningHistory() {
    await loadMiningHistoryForTab(activeTab.value)
  }

  function closeHistoryViewer() {
    historyViewer.open = false
    historyViewer.loading = false
    historyViewer.error = ''
    historyViewer.taskId = ''
    historyViewer.title = ''
    historyViewer.subtitle = ''
    historyViewer.rootTitle = ''
    historyViewer.branches = []
  }

  async function viewHistoryMiningTask(taskId: string) {
    if (!taskId) return
    const tab = activeTab.value
    const config = definitionTabConfigs[tab]
    const summary = miningStateByTab[tab].history.find((item) => item.task_id === taskId)
    historyViewer.open = true
    historyViewer.loading = true
    historyViewer.error = ''
    historyViewer.taskId = taskId
    historyViewer.title = summary?.history_title || `历史挖掘 ${taskId.slice(0, 8)}`
    historyViewer.subtitle = formatMiningTimestamp(
      summary?.saved_at || summary?.finished_at || summary?.created_at,
    )
    historyViewer.rootTitle = `${config.rootTitle}（历史存档）`
    historyViewer.branches = []
    try {
      const results = await getMiningTaskHistoryResults(taskId, tab)
      const candidates = results.candidate_indicators ?? []
      const minedStandards = candidates.map((candidate) =>
        candidateToStandard(tab, candidate, config.standards),
      )
      historyViewer.branches = buildDefinitionBranches([...config.standards, ...minedStandards])
      const count = candidates.length
      const adopted = candidates.filter((item) => item.status === 'adopted').length
      historyViewer.subtitle = [historyViewer.subtitle, `候选 ${count} 条`, `已采纳 ${adopted} 条`]
        .filter(Boolean)
        .join(' · ')
    } catch (error) {
      historyViewer.error = error instanceof Error ? error.message : '加载历史挖掘结果失败'
    } finally {
      historyViewer.loading = false
    }
  }

  async function saveCurrentMiningToHistory(options: { promptTitle?: boolean } = {}) {
    const tab = activeTab.value
    const state = miningStateByTab[tab]
    if (!state.taskId || state.status !== 'completed') {
      ElMessage.warning('仅已完成的挖掘结果可以保存到历史记录。')
      return false
    }
    if (state.savedToHistory) {
      ElMessage.info('本次结果已在历史记录中。')
      return true
    }

    let title = state.historyTitle || ''
    if (options.promptTitle !== false) {
      try {
        const { value } = await ElMessageBox.prompt(
          '为本次指标体系命名后写入历史记录。历史仅供查看，不会覆盖当前工作流。',
          '保存到历史记录',
          {
            confirmButtonText: '保存',
            cancelButtonText: '取消',
            inputPlaceholder: '例如：价值对齐-伦理合规度初版',
            inputValue: title,
          },
        )
        title = String(value || '').trim()
      } catch {
        return false
      }
    }

    state.loading = true
    try {
      const saved = await saveMiningTaskToHistory(state.taskId, title)
      state.savedToHistory = true
      state.historyTitle = saved.history_title || title
      await loadMiningHistoryForTab(tab)
      ElMessage.success('已保存到历史记录，可在第 1 步「历史记录」中查看。')
      return true
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '保存历史记录失败')
      return false
    } finally {
      state.loading = false
    }
  }

  async function refreshActiveMiningTask() {
    const tab = activeTab.value
    const state = miningStateByTab[tab]
    const taskId = state.taskId
    if (!taskId) {
      ElMessage.warning('当前没有可刷新的挖掘任务。')
      return
    }

    state.loading = true
    state.error = ''
    try {
      const task = await loadMiningTaskSnapshot(tab, taskId)
      if (task.status === 'completed') {
        await refreshMiningTask(tab, taskId)
        state.progress = 100
        state.timedOut = false
        ElMessage.success('已获取后端挖掘结果。')
        return
      }

      if (task.status === 'failed') {
        try {
          await refreshMiningTask(tab, taskId)
        } catch {
          state.status = 'failed'
        }
        state.timedOut = false
        state.error = definitionMiningFailureMessage(task)
        ElMessage.error(state.error)
        return
      }

      state.timedOut = true
      state.error = '挖掘任务仍在后端执行，可稍后再次刷新任务结果。'
      ElMessage.info('任务仍在执行中。')
    } catch (error) {
      state.error = error instanceof Error ? error.message : '刷新任务结果失败'
      ElMessage.error(state.error)
    } finally {
      state.loading = false
    }
  }

  async function startMiningForActiveTab() {
    const tab = activeTab.value
    const state = miningStateByTab[tab]
    const formState = activeTabFormState.value

    if (
      state.taskId &&
      (state.status === 'completed' || state.status === 'failed' || state.status === 'running')
    ) {
      try {
        await ElMessageBox.confirm(
          state.savedToHistory
            ? '将开始一次新的挖掘。已存档的历史记录不受影响，可稍后在历史列表中查看。'
            : '将开始一次新的挖掘。若当前结果尚未存档，刷新或离开后将无法从历史中找回（可先保存到历史）。',
          '开始新的指标挖掘？',
          {
            type: 'warning',
            confirmButtonText: '开始新挖掘',
            cancelButtonText: '取消',
          },
        )
      } catch {
        return
      }
    }

    state.loading = true
    state.timedOut = false
    state.error = ''
    state.taskId = ''
    state.inputId = null
    state.status = 'running'
    state.progress = 8
    state.logs = []
    state.candidates = []
    state.stats = {}
    state.artifacts = []
    state.finishedAt = ''
    state.createdAt = ''
    state.savedToHistory = false
    state.historyTitle = ''
    goToStep(2)

    try {
      const started = await startDefinitionMiningTask(tab, {
        definition_type: definitionTypeForTab(tab),
        uploaded_document_ids: formState.uploadedDocuments.map((doc) => doc.id),
        web_links: splitMultilineValue(formState.webLinksText),
        lookup_names: [],
        mining_demand: formState.miningDemand,
      })
      state.taskId = started.task_id
      state.inputId = started.input_id
      state.status = started.status
      state.stats = started.stats ?? {}
      state.progress = started.progress ?? 12
      state.createdAt = new Date().toISOString()
      await pollMiningTask(tab, started.task_id)
      unlockStepsForMiningStatus(tab, miningStateByTab[tab].status)
      applyTabStep(tab)
      ElMessage.success(
        '多智能体挖掘任务已完成，候选指标已返回。可进入指标体系浏览后保存到历史记录。',
      )
    } catch (error) {
      if (!state.timedOut) {
        state.status = 'failed'
      }
      state.error = error instanceof Error ? error.message : '后端挖掘任务启动失败'
      unlockStepsForMiningStatus(tab, state.status)
      applyTabStep(tab)
      ElMessage.error(state.error)
    } finally {
      state.loading = false
    }
  }

  function syncAdoptedStandardsToInputModule() {
    if (!canSyncDefinitionStandardsToInput(activeTab.value)) return

    standardStore.syncDefinitionStandards(
      activeTab.value,
      activeStandards.value.filter(shouldSyncDefinitionStandardToInput),
    )
  }

  async function adoptCandidate(candidateId: number, comment = '') {
    activeMiningState.value.loading = true
    try {
      await adoptCandidateIndicator(candidateId, comment || '采纳单条候选指标')
      try {
        await refreshMiningTask(activeTab.value, activeMiningState.value.taskId)
        syncAdoptedStandardsToInputModule()
      } catch {
        ElMessage.warning('采纳已提交，但候选指标列表刷新失败，请稍后手动刷新。')
        return
      }
      ElMessage.success('已采纳该候选指标，并同步到后续输入模块。')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '采纳候选指标失败，请稍后重试。')
    } finally {
      activeMiningState.value.loading = false
    }
  }

  async function rejectCandidate(candidateId: number, comment = '') {
    activeMiningState.value.loading = true
    try {
      await rejectCandidateIndicator(candidateId, comment || '忽略单条候选指标')
      try {
        await refreshMiningTask(activeTab.value, activeMiningState.value.taskId)
      } catch {
        ElMessage.warning('忽略已提交，但候选指标列表刷新失败，请稍后手动刷新。')
        return
      }
      ElMessage.warning('已忽略该候选指标。')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '忽略候选指标失败，请稍后重试。')
    } finally {
      activeMiningState.value.loading = false
    }
  }

  async function updateCandidate(candidateId: number, payload: Partial<CandidateUpdatePayload>) {
    activeMiningState.value.loading = true
    try {
      const sourceCandidate = activeMiningState.value.candidates.find(
        (candidate) => candidate.id === candidateId,
      )
      if (!sourceCandidate) throw new Error('未找到需要矫正的候选指标')

      await updateCandidateIndicator(candidateId, {
        ...buildCandidateUpdatePayload(sourceCandidate),
        ...payload,
      })
      try {
        await refreshMiningTask(activeTab.value, activeMiningState.value.taskId)
      } catch {
        ElMessage.warning('修改已提交，但候选指标列表刷新失败，请稍后手动刷新。')
        return
      }
      ElMessage.success('已保存该候选指标的矫正内容。')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '保存候选指标修改失败，请稍后重试。')
    } finally {
      activeMiningState.value.loading = false
    }
  }

  onMounted(() => {
    void loadMiningHistoryForTab(activeTab.value)
  })

  return {
    activeTab,
    activeStep,
    maxUnlockedStep,
    activeTabConfig,
    activeTabFormState,
    activeMiningState,
    activeStandards,
    activeBranches,
    historyViewer,
    definitionWorkflowPayload,
    switchTab,
    showBlockedStepHint,
    goToStep,
    handleStepIndicatorUpdate,
    updateActiveTabFormState,
    startMiningForActiveTab,
    refreshActiveMiningTask,
    viewHistoryMiningTask,
    refreshActiveMiningHistory,
    closeHistoryViewer,
    saveCurrentMiningToHistory,
    formatMiningTimestamp,
    adoptCandidate,
    rejectCandidate,
    updateCandidate,
  }
}
