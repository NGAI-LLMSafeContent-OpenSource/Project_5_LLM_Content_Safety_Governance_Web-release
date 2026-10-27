import type {
  BenchmarkArtifactItem,
  BenchmarkArtifactsResponse,
  BenchmarkTask,
  BenchmarkTaskLogItem,
  BenchmarkTaskLogsResponse,
} from '../../types'

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'rejected'])

export interface BenchmarkPollingState {
  task: BenchmarkTask | null
  logs: BenchmarkTaskLogItem[]
  artifacts: BenchmarkArtifactItem[]
  isPolling: boolean
  errorMessage: string
  currentTaskId: string
}

export interface BenchmarkPollingControllerOptions {
  state: BenchmarkPollingState
  getTask: (taskId: string) => Promise<BenchmarkTask>
  getLogs: (
    taskId: string,
    params?: { after_id?: number; limit?: number },
  ) => Promise<BenchmarkTaskLogsResponse>
  getArtifacts: (taskId: string) => Promise<BenchmarkArtifactsResponse>
  setTimer?: (callback: () => void, delayMs: number) => number
  clearTimer?: (timerId: number) => void
  pollIntervalMs?: number
  maxPollFailures?: number
}

export interface BenchmarkPollingController {
  startPolling: (taskId: string) => void
  stopPolling: () => void
  resetPolling: () => void
  refreshArtifacts: (taskId?: string) => Promise<void>
}

export function createBenchmarkTaskPollingController(
  options: BenchmarkPollingControllerOptions,
): BenchmarkPollingController {
  const {
    state,
    getTask,
    getLogs,
    getArtifacts,
    setTimer = (callback, delayMs) => window.setTimeout(callback, delayMs),
    clearTimer = (timerId) => window.clearTimeout(timerId),
    pollIntervalMs = 1500,
    maxPollFailures = 3,
  } = options

  let timer: number | undefined
  let pollFailCount = 0
  let generation = 0

  function latestLogId() {
    return state.logs.reduce((max, item) => Math.max(max, item.id), 0)
  }

  function clearActiveTimer() {
    if (timer !== undefined) {
      clearTimer(timer)
      timer = undefined
    }
  }

  function isCurrent(taskId: string, tickGeneration: number) {
    return state.currentTaskId === taskId && generation === tickGeneration
  }

  function finishPolling() {
    clearActiveTimer()
    state.isPolling = false
    pollFailCount = 0
  }

  function stopPolling() {
    generation++
    finishPolling()
  }

  function resetPolling() {
    stopPolling()
    state.task = null
    state.logs = []
    state.artifacts = []
    state.errorMessage = ''
    state.currentTaskId = ''
  }

  async function refreshArtifacts(taskId = state.currentTaskId) {
    const tickGeneration = generation
    const response = await getArtifacts(taskId)
    if (!isCurrent(taskId, tickGeneration)) {
      return
    }
    state.artifacts = response.artifacts
  }

  async function refreshArtifactsForTerminalTask(taskId: string, tickGeneration: number) {
    try {
      const response = await getArtifacts(taskId)
      if (!isCurrent(taskId, tickGeneration)) {
        return
      }
      state.artifacts = response.artifacts
    } catch (error) {
      if (!isCurrent(taskId, tickGeneration)) {
        return
      }
      const message = error instanceof Error ? error.message : '未知错误'
      state.errorMessage = `任务已结束，但产物摘要拉取失败：${message}`
    }
  }

  async function refreshOnce(taskId: string, tickGeneration: number) {
    const nextTask = await getTask(taskId)
    if (!isCurrent(taskId, tickGeneration)) {
      return 'stale'
    }
    state.task = nextTask

    const nextLogs = await getLogs(taskId, {
      after_id: latestLogId() || undefined,
      limit: 200,
    })
    if (!isCurrent(taskId, tickGeneration)) {
      return 'stale'
    }
    if (nextLogs.logs.length > 0) {
      state.logs = [...state.logs, ...nextLogs.logs]
    }

    if (TERMINAL_STATUSES.has(nextTask.status)) {
      finishPolling()
      await refreshArtifactsForTerminalTask(taskId, tickGeneration)
      return 'terminal'
    }

    return 'active'
  }

  function schedulePoll(taskId: string, tickGeneration: number) {
    if (!state.isPolling || !isCurrent(taskId, tickGeneration)) {
      return
    }
    timer = setTimer(() => {
      void pollTick(taskId, tickGeneration)
    }, pollIntervalMs)
  }

  async function pollTick(taskId: string, tickGeneration: number) {
    if (!state.isPolling || !isCurrent(taskId, tickGeneration)) {
      return
    }
    try {
      const result = await refreshOnce(taskId, tickGeneration)
      if (!isCurrent(taskId, tickGeneration) || result !== 'active') {
        return
      }
      pollFailCount = 0
    } catch (error) {
      if (!isCurrent(taskId, tickGeneration)) {
        return
      }
      pollFailCount++
      if (pollFailCount >= maxPollFailures) {
        finishPolling()
        state.errorMessage =
          error instanceof Error
            ? error.message
            : '动态 Benchmark 任务查询失败（连接中断，请检查后重试）'
        return
      }
    }
    schedulePoll(taskId, tickGeneration)
  }

  function startPolling(taskId: string) {
    stopPolling()
    state.errorMessage = ''
    state.currentTaskId = taskId
    state.isPolling = true
    generation++
    void pollTick(taskId, generation)
  }

  return {
    startPolling,
    stopPolling,
    resetPolling,
    refreshArtifacts,
  }
}
