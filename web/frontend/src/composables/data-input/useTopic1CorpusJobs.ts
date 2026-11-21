import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { ApiRequestError } from '@/api/request'
import { useInputStore } from '@/stores/input'
import { createUuid } from '@/utils/uuid'
import {
  archiveCorpusAsset,
  fingerprintCorpusRequest,
  downloadCorpusAsset,
  cancelCorpusJob,
  getCorpusJobResult,
  getCorpusModels,
  listCorpusJobs,
  refreshCorpusJob,
  startCorpusJob,
  type CorpusJob,
  type CorpusJobRequest,
  type CorpusJobResult,
} from '@/api/topic1CorpusJobs'

export const corpusOperations = [
  { key: 'refinemodel_clean', tool: 'refinement', label: '数据提质' },
  { key: 'preprocess', tool: 'detox', label: '文本预处理' },
  { key: 'detox', tool: 'detox', label: '数据去毒' },
  { key: 'evaluate', tool: 'detox', label: '毒性评估' },
  { key: 'score', tool: 'detection', label: '稀缺度评估' },
] as const

export const corpusJobStatus: Record<string, string> = {
  submitting: '正在提交',
  submission_unknown: '提交状态待确认',
  queued: '排队中',
  running: '处理中',
  cancelling: '正在取消',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

function taskError(reason: unknown, fallback: string): string {
  if (reason instanceof ApiRequestError) {
    if (reason.status === 422) return '语料或模型配置不符合要求，请检查后再提交。'
    if (reason.status === 404) return '当前任务不可用，请刷新任务列表。'
    if (reason.status === 409) return '任务状态或服务配置发生变化，请刷新后确认。'
    if (reason.status === 503) return '工具服务或模型尚未就绪，请联系管理员。'
    return `${fallback}，请确认平台及工具服务可用后重试。`
  }
  return fallback
}

export function useTopic1CorpusJobs() {
  const store = useInputStore()
  const source = ref<'value' | 'risk' | 'upload'>('value')
  const operation = ref('refinemodel_clean')
  const model = ref('')
  const models = ref<Array<{ alias: string; label: string }>>([])
  const jobs = ref<CorpusJob[]>([])
  const result = ref<CorpusJobResult | null>(null)
  const busy = ref(false)
  const error = ref('')
  const lastUpdated = ref('')
  const hasMore = ref(false)
  const search = ref('')
  const statusFilter = ref('')
  const filteredJobs = computed(() => {
    const query = search.value.trim().toLocaleLowerCase()
    return jobs.value.filter((job) => {
      const operationLabel =
        corpusOperations.find((item) => item.key === job.operation)?.label || ''
      return (
        (!statusFilter.value || job.status === statusFilter.value) &&
        (!query ||
          `${job.source_name} ${job.id} ${operationLabel}`.toLocaleLowerCase().includes(query))
      )
    })
  })
  let historyPages = 1
  let disposed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let polling = false
  let refreshQueued = false
  let consecutiveRefreshFailures = 0
  const active = (job: CorpusJob) =>
    ['submitting', 'queued', 'running', 'cancelling'].includes(job.status)
  const records = computed(() => {
    if (source.value === 'upload') {
      return store.parsedUploadRecords
        .map((row, index) => ({
          id: String(row.chunk_id || `upload-${index}`),
          text: typeof row.raw_chunk === 'string' ? row.raw_chunk : '',
        }))
        .filter((row) => row.text.trim())
    }
    return (source.value === 'value' ? store.valueCorpusRecords : store.riskCorpusRecords).map(
      ({ id, text }) => ({ id, text }),
    )
  })
  const sourceName = computed(() =>
    source.value === 'upload'
      ? '自定义上传语料'
      : (source.value === 'value'
          ? store.valueSelectedCorpus?.name
          : store.riskSelectedCorpus?.name) || '未选择语料',
  )

  function replace(job: CorpusJob) {
    jobs.value = jobs.value.map((item) => (item.id === job.id ? job : item))
  }

  async function refresh() {
    if (disposed) return
    if (polling) {
      refreshQueued = true
      return
    }
    polling = true
    try {
      const merged = new Map<string, CorpusJob>()
      for (let page = 0; page < historyPages; page += 1) {
        const response = await listCorpusJobs(page * 30)
        for (const job of [...response.items, ...response.active]) merged.set(job.id, job)
        hasMore.value = response.has_more
        if (!response.has_more) break
      }
      const listed = [...merged.values()].sort((a, b) => b.created_at.localeCompare(a.created_at))
      if (disposed) return
      jobs.value = listed
      let failed = 0
      for (const job of listed.filter(active)) {
        try {
          const updated = await refreshCorpusJob(job.id)
          if (disposed) return
          replace(updated)
        } catch {
          failed += 1
        }
      }
      consecutiveRefreshFailures = failed ? consecutiveRefreshFailures + 1 : 0
      error.value = failed ? `${failed} 个任务暂时无法更新，当前显示最近已知状态；可稍后刷新。` : ''
      lastUpdated.value = new Date().toLocaleTimeString()
    } catch (reason) {
      consecutiveRefreshFailures += 1
      error.value = taskError(reason, '任务状态刷新失败')
    } finally {
      polling = false
      if (timer) clearTimeout(timer)
      if (!disposed && refreshQueued) {
        refreshQueued = false
        timer = setTimeout(() => void refresh(), 0)
      } else if (!disposed && jobs.value.some(active) && consecutiveRefreshFailures < 3)
        timer = setTimeout(() => void refresh(), error.value ? 15000 : 4000)
    }
  }

  async function loadMore() {
    if (polling || !hasMore.value) return
    historyPages += 1
    await refresh()
  }

  async function submit() {
    if (busy.value || !records.value.length || records.value.length > 500) return
    const selected = corpusOperations.find((item) => item.key === operation.value)
    if (!selected) return
    const payload: CorpusJobRequest = {
      request_id: createUuid(),
      tool: selected.tool,
      operation: selected.key,
      source_name: sourceName.value,
      records: records.value.map((row) => ({ ...row })),
      model_alias: selected.tool === 'detection' ? model.value : '',
      confirmed: true,
    }
    busy.value = true
    try {
      await ElMessageBox.confirm(
        `将向已配置的课题一服务发送“${payload.source_name}”的 ${payload.records.length} 条文本，执行${selected.label}。原始语料不会被覆盖。`,
        '确认执行',
        { confirmButtonText: '执行', cancelButtonText: '取消', type: 'warning' },
      )
      error.value = ''
      result.value = null
      // Store only a digest and request identity, never the potentially sensitive text.
      const signature = await fingerprintCorpusRequest(payload)
      const key = `project5-topic1-pending-submit:${signature}`
      const saved = sessionStorage.getItem(key)
      const previous = saved ? (JSON.parse(saved) as { signature: string; id: string }) : null
      payload.request_id = previous?.signature === signature ? previous.id : payload.request_id
      sessionStorage.setItem(key, JSON.stringify({ signature, id: payload.request_id }))
      const job = await startCorpusJob(payload)
      // Unknown submissions may already be queued upstream: keep their identity.
      if (job.status !== 'submission_unknown' && job.status !== 'submitting')
        sessionStorage.removeItem(key)
      await refresh()
    } catch (reason) {
      if (reason !== 'cancel' && reason !== 'close')
        error.value = taskError(reason, '提交未完成，请先刷新任务列表确认状态')
    } finally {
      busy.value = false
    }
  }

  async function cancel(job: CorpusJob) {
    if (busy.value) return
    busy.value = true
    try {
      await ElMessageBox.confirm('确认取消此任务？上游停止执行可能需要一些时间。', '取消任务')
      replace(await cancelCorpusJob(job.id))
      await refresh()
    } catch (reason) {
      if (reason !== 'cancel' && reason !== 'close') error.value = taskError(reason, '取消请求失败')
    } finally {
      busy.value = false
    }
  }

  async function showResult(job: CorpusJob) {
    if (busy.value || disposed) return
    result.value = null
    error.value = ''
    busy.value = true
    try {
      const loaded = await getCorpusJobResult(job.id)
      if (!disposed) result.value = loaded
    } catch (reason) {
      if (!disposed) error.value = taskError(reason, '结果读取失败')
    } finally {
      busy.value = false
    }
  }

  async function download(key: string, name: string) {
    if (!result.value || busy.value) return
    busy.value = true
    error.value = ''
    try {
      await downloadCorpusAsset(result.value.job.id, key, name)
    } catch {
      error.value = '文件下载失败，请确认工具服务可用；超过16MB的文件请联系管理员导出。'
    } finally {
      busy.value = false
    }
  }

  async function archive(key: string, name: string) {
    if (!result.value || busy.value) return
    const jobId = result.value.job.id
    busy.value = true
    error.value = ''
    try {
      await ElMessageBox.confirm(
        `将完整结果文件“${name}”保存到平台，原始语料不会被覆盖。`,
        '保存结果',
        { confirmButtonText: '保存', cancelButtonText: '取消' },
      )
      await archiveCorpusAsset(jobId, key)
      result.value = await getCorpusJobResult(jobId)
    } catch (reason) {
      if (reason !== 'cancel' && reason !== 'close') error.value = taskError(reason, '保存结果失败')
    } finally {
      busy.value = false
    }
  }

  onMounted(async () => {
    try {
      models.value = await getCorpusModels()
    } catch (reason) {
      error.value = taskError(reason, '模型配置加载失败')
    }
    await refresh()
  })
  onBeforeUnmount(() => {
    disposed = true
    if (timer) clearTimeout(timer)
  })
  return {
    source,
    operation,
    model,
    models,
    jobs,
    search,
    statusFilter,
    filteredJobs,
    result,
    busy,
    error,
    lastUpdated,
    hasMore,
    loadMore,
    records,
    sourceName,
    refresh,
    submit,
    cancel,
    showResult,
    download,
    archive,
    active,
  }
}
