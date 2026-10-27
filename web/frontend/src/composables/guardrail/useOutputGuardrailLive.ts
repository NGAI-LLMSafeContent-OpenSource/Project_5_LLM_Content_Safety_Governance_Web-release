import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchGuardrailDemoPacks,
  fetchGuardrailLiveBatch,
  startGuardrailLiveBatch,
  type GuardrailDemoPack,
  type GuardrailLiveJob,
  type GuardrailLiveSample,
} from '@/api/output'

export const LIVE_DISPOSAL_NOTICE = '以下结果来自本次运行，不是预跑静态样例。'
export const CULTURE_IDLE_LABEL = '本批未跑'
export const DEFAULT_PACK_ID = 'demo-zh-8'

function isUnsafe(sample: GuardrailLiveSample): boolean {
  if (sample.detect_status !== 'done') return false
  return String(sample.pred_safe_type || '').toLowerCase() !== 'safe'
}

function formatEvidence(items: unknown[]): string[] {
  return items.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return String(record.text || record.span || record.detail || JSON.stringify(item))
    }
    return String(item)
  })
}

export function useOutputGuardrailLive() {
  const route = useRoute()
  const router = useRouter()
  const packs = ref<GuardrailDemoPack[]>([])
  const selectedPackId = ref(DEFAULT_PACK_ID)
  const packsLoading = ref(false)
  const packsError = ref('')
  const job = ref<GuardrailLiveJob | null>(null)
  const jobError = ref('')
  const running = ref(false)
  const selectedSampleId = ref('')
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const selectedPack = computed(
    () => packs.value.find((item) => item.pack_id === selectedPackId.value) || null,
  )
  const samples = computed(() => job.value?.samples || [])
  const selectedSample = computed(
    () => samples.value.find((item) => item.id === selectedSampleId.value) || null,
  )
  const detectCounts = computed(() => {
    const counts = { safe: 0, unsafe: 0, failed: 0, pending: 0 }
    for (const sample of samples.value) {
      if (sample.detect_status === 'error') counts.failed += 1
      else if (sample.detect_status !== 'done') counts.pending += 1
      else if (isUnsafe(sample)) counts.unsafe += 1
      else counts.safe += 1
    }
    return counts
  })
  const jobBusy = computed(
    () => running.value || job.value?.status === 'pending' || job.value?.status === 'running',
  )

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function pickDefaultSample(nextJob: GuardrailLiveJob) {
    const unsafe = nextJob.samples.find((sample) => isUnsafe(sample))
    const firstDone = nextJob.samples.find((sample) => sample.detect_status === 'done')
    selectedSampleId.value = unsafe?.id || firstDone?.id || nextJob.samples[0]?.id || ''
  }

  async function refreshJob(jobId: string) {
    try {
      const next = await fetchGuardrailLiveBatch(jobId)
      job.value = next
      jobError.value = ''
      if (
        !selectedSampleId.value ||
        !next.samples.some((sample) => sample.id === selectedSampleId.value)
      ) {
        pickDefaultSample(next)
      }
      if (next.status !== 'pending' && next.status !== 'running') {
        running.value = false
        stopPolling()
      }
    } catch (error) {
      jobError.value = error instanceof Error ? error.message : '任务不存在'
      running.value = false
      stopPolling()
    }
  }

  function startPolling(jobId: string) {
    stopPolling()
    pollTimer = setInterval(() => {
      void refreshJob(jobId)
    }, 1000)
  }

  async function loadPacks() {
    packsLoading.value = true
    packsError.value = ''
    try {
      const list = await fetchGuardrailDemoPacks()
      packs.value = list
      if (!list.some((item) => item.pack_id === selectedPackId.value)) {
        selectedPackId.value = list[0]?.pack_id || DEFAULT_PACK_ID
      }
    } catch (error) {
      packsError.value = error instanceof Error ? error.message : '预置包不可达'
    } finally {
      packsLoading.value = false
    }
  }

  async function restoreJobFromQuery() {
    const jobId = typeof route.query.job === 'string' ? route.query.job : ''
    if (!jobId) return
    running.value = true
    await refreshJob(jobId)
    if (job.value && (job.value.status === 'pending' || job.value.status === 'running')) {
      startPolling(job.value.job_id)
    } else {
      running.value = false
    }
  }

  async function runBatch() {
    if (!selectedPackId.value || jobBusy.value) return
    running.value = true
    jobError.value = ''
    selectedSampleId.value = ''
    try {
      const started = await startGuardrailLiveBatch({ pack_id: selectedPackId.value })
      await router.replace({ query: { ...route.query, job: started.job_id } })
      await refreshJob(started.job_id)
      startPolling(started.job_id)
    } catch (error) {
      running.value = false
      jobError.value = error instanceof Error ? error.message : '启动失败'
    }
  }

  function selectPack(packId: string) {
    selectedPackId.value = packId
  }

  function selectSample(sampleId: string) {
    selectedSampleId.value = sampleId
  }

  function showNextEvidence() {
    const unsafe = samples.value.filter((sample) => isUnsafe(sample))
    const pool = unsafe.length ? unsafe : samples.value
    if (!pool.length) return
    const current = pool.findIndex((sample) => sample.id === selectedSampleId.value)
    const next = pool[(current + 1) % pool.length]
    if (next) selectedSampleId.value = next.id
  }

  watch(
    () => job.value?.samples,
    (nextSamples) => {
      if (!nextSamples?.length) return
      if (!selectedSampleId.value) pickDefaultSample(job.value as GuardrailLiveJob)
    },
  )

  void loadPacks().then(() => restoreJobFromQuery())
  onUnmounted(stopPolling)

  return {
    packs,
    selectedPackId,
    selectedPack,
    packsLoading,
    packsError,
    job,
    jobError,
    running,
    jobBusy,
    samples,
    selectedSampleId,
    selectedSample,
    detectCounts,
    loadPacks,
    selectPack,
    runBatch,
    selectSample,
    showNextEvidence,
    formatEvidence,
  }
}
