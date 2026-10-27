import { computed, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchInputGuardrailDemoPacks,
  fetchInputGuardrailLiveRun,
  startInputGuardrailLiveRun,
  type InputGuardrailDemoPack,
  type InputGuardrailLiveRun,
  type InputGuardrailLiveSample,
} from '@/api/dataInput'
import {
  DISPOSITION_HELP,
  truncateText,
  type AbnormalSlice,
  type DemoCategorySummary,
  type DemoSampleRow,
  type DispositionCategoryRow,
  type FixItem,
  type InputGuardrailEvidenceView,
  type LineageSlice,
  type PoisonSlice,
  type RiskBasis,
  type RunDispositionSummary,
  type UnreleasedEvidenceDetail,
  type UnreleasedEvidenceRow,
  type ValueBasis,
} from './inputGuardrailDemoMap'

export const INPUT_LIVE_NOTICE = '以下结果来自本次输入数据治理运行，不是预跑静态拼接。'
export const DEFAULT_INPUT_PACK_ID = 'demo-mixed-10'

const CATEGORY_ORDER = [
  '中文正常语料',
  '英文正常语料',
  '价值质量问题',
  '异常/风险语料',
  '边界复核样本',
]

const CATEGORY_NOTES: Record<string, string> = {
  中文正常语料: '中文高价值样本，用来证明治理不是一刀切。',
  英文正常语料: '英文正常样本，用来证明混合语种可进入同一流程。',
  价值质量问题: '中低质量样本，用来展示复核与修正建议。',
  '异常/风险语料': '明确风险样本，用来展示异常识别和证据链。',
  边界复核样本: '上游标签安全但语义可疑，用来展示人工复核。',
}

const DISPOSITION_NOTES: Record<string, string> = {
  中文正常语料: '正常语料放行，证明治理不会一刀切。',
  英文正常语料: '英文正常语料放行，进入同一治理流程。',
  价值质量问题: '中等质量进入复核，低质量进入修正。',
  '异常/风险语料': '明确风险语料进入人工复核。',
  边界复核样本: '上游标签 safe 但语义可疑，交给人工确认。',
}

function numberFrom(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function stringFrom(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function isRisky(sample: InputGuardrailLiveSample): boolean {
  return Boolean(sample.risk_result?.is_abnormal) || sample.disposition === 'review'
}

function isValueIssue(sample: InputGuardrailLiveSample): boolean {
  return sample.track === 'value' && sample.disposition !== 'pass'
}

function evidenceChain(sample: InputGuardrailLiveSample): string[] {
  const riskChain = sample.risk_result?.evidence_chain
  if (Array.isArray(riskChain)) return riskChain.map((item) => String(item))
  return []
}

function mapEvidence(sample: InputGuardrailLiveSample): InputGuardrailEvidenceView {
  const track = sample.track === 'risk' ? 'risk' : 'value'
  return {
    id: sample.id,
    track,
    snippet: truncateText(sample.text, 160),
    suggestion: sample.fix_suggestion,
    evidenceChain: evidenceChain(sample),
    attributionSteps: sample.evidence.map((item) => ({ title: item.title, detail: item.detail })),
    qualityLevel:
      stringFrom(sample.value_result?.quality_level) ||
      stringFrom(sample.risk_result?.status) ||
      sample.source_label,
    dimension: [sample.source_label, sample.expected_issue].filter(Boolean).join(' / '),
    riskL1: stringFrom(sample.risk_result?.category_l1),
    riskL2: stringFrom(sample.risk_result?.category_l2),
    strategyChain: [],
  }
}

function mapFix(sample: InputGuardrailLiveSample): FixItem {
  const disposition = sample.disposition || expectedDisposition(sample)
  return {
    id: sample.id,
    category: categoryOf(sample),
    disposition,
    problemSummary: attributionSummary(sample),
    status: disposition === 'revise' ? '待修正' : '待人工复核',
    snippet: truncateText(sample.text, 120),
    suggestion: sample.fix_suggestion,
  }
}

function attributionSummary(sample: InputGuardrailLiveSample): string {
  const issue = sample.expected_issue
  if (sample.disposition === 'revise') {
    return '事实表达或文化价值定位存在明显问题，需要先修正再复核。'
  }
  if (issue === 'borderline_review') {
    return '上游标签为 safe，但表达意图存在边界不确定性，需要人工确认。'
  }
  if (sample.track === 'risk') {
    const riskLabel =
      stringFrom(sample.risk_result?.category_l2) ||
      stringFrom(sample.risk_result?.category_l1) ||
      issue
    return riskLabel
      ? `检测到 ${riskLabel} 风险信号，需要人工复核。`
      : '检测到风险信号，需要人工复核。'
  }
  if (sample.track === 'value') {
    return sample.source_label === 'medium'
      ? '信息基本可用，但价值表达和文化解释不足，需要人工复核补强。'
      : '价值质量未达到直接放行标准，需要人工确认。'
  }
  return sample.demo_note || sample.fix_suggestion || '未达到直接放行标准，需要人工复核。'
}

function attributionBasis(sample: InputGuardrailLiveSample): string[] {
  const basis = [
    `来源：${sourceTopic(sample)} / ${sample.source_sample_id || sample.id}`,
    sample.source_label ? `上游标签：${sample.source_label}` : '',
    sample.expected_issue ? `触发问题类型：${sample.expected_issue}` : '',
  ].filter(Boolean)

  const valueReason = stringFrom(sample.value_result?.reason)
  if (valueReason) basis.push(`价值判断：${valueReason}`)

  const riskParts = [
    stringFrom(sample.risk_result?.status),
    stringFrom(sample.risk_result?.category_l1),
    stringFrom(sample.risk_result?.category_l2),
  ].filter(Boolean)
  if (riskParts.length) basis.push(`风险判断：${riskParts.join(' / ')}`)

  const evidenceItems = sample.evidence
    .map((item) => [item.title, item.detail].filter(Boolean).join('：'))
    .filter(Boolean)
  basis.push(...evidenceItems.slice(0, 2))

  const riskChain = evidenceChain(sample).slice(0, 2)
  basis.push(...riskChain)

  return [...new Set(basis)].slice(0, 6)
}

function buildValueBasis(sample: InputGuardrailLiveSample): ValueBasis {
  const dim = sample.value_dimension
  const reason = stringFrom(sample.value_result?.reason)
  return {
    primaryDim: dim?.primary || '—',
    secondaryDim: dim?.secondary || '—',
    qualityLevel: dim?.quality_level || stringFrom(sample.value_result?.quality_level) || '未测',
    reason,
    notApplicable: false,
  }
}

function buildRiskBasis(sample: InputGuardrailLiveSample): RiskBasis {
  const r = sample.risk_result
  const isAbnormal = Boolean(r?.is_abnormal)
  const l1 = stringFrom(r?.category_l1)
  const l2 = stringFrom(r?.category_l2)
  const rawChain = r?.evidence_chain
  const evidenceItems = Array.isArray(rawChain)
    ? rawChain.map(String).filter(Boolean).slice(0, 3)
    : []
  return {
    riskStatus: isAbnormal ? '异常' : stringFrom(r?.status) || '安全',
    l1,
    l2,
    evidenceItems,
    notTriggered: !isAbnormal && !l1,
  }
}

function buildDerivation(sample: InputGuardrailLiveSample, disposition: string): string {
  const r = sample.risk_result
  const isAbnormal = Boolean(r?.is_abnormal)
  const l1 = stringFrom(r?.category_l1)
  const dim = sample.value_dimension
  const qualityLevel = dim?.quality_level || stringFrom(sample.value_result?.quality_level)
  if (isAbnormal && l1) return `${l1} 命中且异常 → review`
  if (isAbnormal) return `风险异常 → review`
  if (qualityLevel === 'low') return `价值档位 low → revise`
  if (disposition === 'revise') return `价值表达不足 → revise`
  if (disposition === 'review' && l1) return `${l1} 待复核 → review`
  if (disposition === 'review') return `价值中等 / 边界样本 → review`
  return ''
}

function mapUnreleasedEvidenceRow(sample: InputGuardrailLiveSample): UnreleasedEvidenceRow {
  const disposition = sample.disposition || expectedDisposition(sample)
  const riskResult = sample.risk_result
  const isAbnormal = Boolean(riskResult?.is_abnormal)
  const riskL1Raw = stringFrom(riskResult?.category_l1)
  const dim = sample.value_dimension
  const valueLevel = dim?.quality_level || stringFrom(sample.value_result?.quality_level) || '未测'
  return {
    id: sample.id,
    category: categoryOf(sample),
    disposition,
    dispositionHelp: DISPOSITION_HELP[disposition] || '',
    attributionSummary: attributionSummary(sample),
    valueLevel,
    valueDim: dim?.primary || '',
    riskStatus: isAbnormal ? '异常' : stringFrom(riskResult?.status) || '安全',
    riskL1: riskL1Raw || '未命中',
    derivation: buildDerivation(sample, disposition),
  }
}

function mapUnreleasedEvidenceDetail(sample: InputGuardrailLiveSample): UnreleasedEvidenceDetail {
  const disposition = sample.disposition || expectedDisposition(sample)
  return {
    id: sample.id,
    category: categoryOf(sample),
    disposition,
    dispositionHelp: DISPOSITION_HELP[disposition] || '',
    triggerText: sample.text,
    basis: attributionBasis(sample),
    suggestion: sample.fix_suggestion || '进入人工复核队列，确认后再决定放行、修正或剔除。',
    valueBasis: buildValueBasis(sample),
    riskBasis: buildRiskBasis(sample),
    derivationRule: buildDerivation(sample, disposition),
  }
}

function sourceTopic(sample: InputGuardrailLiveSample): string {
  if (sample.source_asset_id === 'topic1_value_qa_marked_merged_round3_recheck_v1') {
    return '课题一 value_qa'
  }
  if (sample.source_asset_id === 'topic2_dynbench400_static') {
    return '课题二 DynBench400'
  }
  if (sample.source_asset_id === 'project5_input_guardrail_builtin') {
    return '平台内置'
  }
  return sample.source_name || sample.source_asset_id || '本地语料包'
}

function expectedDisposition(sample: InputGuardrailLiveSample): string {
  return sample.expected_disposition || sample.disposition || ''
}

function categoryOf(sample: InputGuardrailLiveSample): string {
  if (sample.demo_category) return sample.demo_category
  if (sample.track === 'risk' && sample.expected_issue === 'borderline_review')
    return '边界复核样本'
  if (sample.track === 'risk') return '异常/风险语料'
  if (sample.track === 'value' && sample.source_label === 'high') return '中文正常语料'
  if (sample.track === 'value') return '价值质量问题'
  if (sample.language === 'en') return '英文正常语料'
  return '其他语料'
}

export function useInputGuardrailLive() {
  const route = useRoute()
  const router = useRouter()
  const packs = ref<InputGuardrailDemoPack[]>([])
  const selectedPackId = ref(DEFAULT_INPUT_PACK_ID)
  const packsLoading = ref(false)
  const packsError = ref('')
  const job = ref<InputGuardrailLiveRun | null>(null)
  const jobError = ref('')
  const running = ref(false)
  const selectedEvidenceId = ref('')
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const selectedPack = computed(
    () => packs.value.find((item) => item.pack_id === selectedPackId.value) || null,
  )
  const samples = computed(() => job.value?.samples || [])
  const valueSamples = computed(() => samples.value.filter((sample) => sample.track === 'value'))
  const riskSamples = computed(() => samples.value.filter((sample) => sample.track === 'risk'))
  const jobBusy = computed(
    () => running.value || job.value?.status === 'pending' || job.value?.status === 'running',
  )
  const ingestLoading = computed(() => packsLoading.value || jobBusy.value)
  const ingestError = computed(() => packsError.value || jobError.value)
  const riskAssetName = computed(() => selectedPack.value?.title || '输入数据治理演示批次')
  const riskPairCount = computed(() => riskSamples.value.length)
  const riskTotal = computed(() => samples.value.length)
  const riskSnippets = computed(() =>
    riskSamples.value.slice(0, 3).map((sample) => truncateText(sample.text)),
  )
  const valueRecords = computed(() =>
    valueSamples.value.map((sample) => ({ id: sample.id, text: sample.text })),
  )
  const sampleRows = computed<DemoSampleRow[]>(() =>
    samples.value.map((sample) => {
      const disposition = expectedDisposition(sample)
      return {
        id: sample.id,
        category: categoryOf(sample),
        sourceTopic: sourceTopic(sample),
        sourceLabel: sample.source_label,
        expectedDisposition: disposition,
        dispositionHelp: DISPOSITION_HELP[disposition] || '',
        snippet: truncateText(sample.text, 120),
      }
    }),
  )
  const categorySummary = computed<DemoCategorySummary[]>(() => {
    const groups = new Map<string, { count: number; dispositions: Set<string> }>()
    for (const sample of samples.value) {
      const category = categoryOf(sample)
      const current = groups.get(category) || { count: 0, dispositions: new Set<string>() }
      current.count += 1
      const disposition = expectedDisposition(sample)
      if (disposition) current.dispositions.add(disposition)
      groups.set(category, current)
    }
    return [...groups.entries()]
      .sort(([left], [right]) => {
        const leftIndex = CATEGORY_ORDER.indexOf(left)
        const rightIndex = CATEGORY_ORDER.indexOf(right)
        return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex)
      })
      .map(([category, item]) => ({
        category,
        count: item.count,
        dispositions: [...item.dispositions],
        note: CATEGORY_NOTES[category] || '',
      }))
  })
  const runSummary = computed<RunDispositionSummary>(() => {
    const counts = new Map<string, number>()
    for (const sample of samples.value) {
      const disposition = sample.disposition || expectedDisposition(sample) || 'pending'
      counts.set(disposition, (counts.get(disposition) || 0) + 1)
    }
    return {
      total: samples.value.length,
      done: job.value?.progress.detect_done || 0,
      pass: counts.get('pass') || 0,
      review: counts.get('review') || 0,
      revise: counts.get('revise') || 0,
      status: job.value?.status || '未运行',
      jobId: job.value?.job_id || '',
    }
  })
  const dispositionSummary = computed<DispositionCategoryRow[]>(() => {
    const groups = new Map<
      string,
      { sampleCount: number; pass: number; review: number; revise: number }
    >()
    for (const sample of samples.value) {
      const category = categoryOf(sample)
      const current = groups.get(category) || { sampleCount: 0, pass: 0, review: 0, revise: 0 }
      const disposition = sample.disposition || expectedDisposition(sample)
      current.sampleCount += 1
      if (disposition === 'pass') current.pass += 1
      if (disposition === 'review') current.review += 1
      if (disposition === 'revise') current.revise += 1
      groups.set(category, current)
    }
    return [...groups.entries()]
      .sort(([left], [right]) => {
        const leftIndex = CATEGORY_ORDER.indexOf(left)
        const rightIndex = CATEGORY_ORDER.indexOf(right)
        return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex)
      })
      .map(([category, item]) => ({
        category,
        ...item,
        note: DISPOSITION_NOTES[category] || '',
      }))
  })
  const valueFixItems = computed(() => samples.value.filter(isValueIssue).map(mapFix))
  const riskFixItems = computed(() => riskSamples.value.filter(isRisky).map(mapFix))
  const valueStats = computed(() => {
    if (!job.value) return []
    const issueCount = valueSamples.value.filter((sample) => sample.disposition !== 'pass').length
    return [
      { label: '价值样本', val: String(valueSamples.value.length) },
      { label: '需修正/复核', val: String(issueCount) },
    ]
  })
  const valueQuality = computed(() => {
    const counts = new Map<string, number>()
    for (const sample of valueSamples.value) {
      const level =
        stringFrom(sample.value_result?.quality_level) || sample.source_label || 'unknown'
      counts.set(level, (counts.get(level) || 0) + 1)
    }
    return [...counts.entries()].map(([label, count]) => ({ label, count }))
  })
  const valueRadar = computed(() =>
    valueSamples.value.slice(0, 3).map((sample) => ({
      name: sample.id,
      score: numberFrom(sample.value_result?.score),
    })),
  )
  const abnormal = computed<AbnormalSlice | null>(() => {
    if (!job.value) return null
    const abnormalCount = riskSamples.value.filter((sample) =>
      Boolean(sample.risk_result?.is_abnormal),
    ).length
    const labels = [
      ...new Set(
        riskSamples.value
          .map((sample) => stringFrom(sample.risk_result?.category_l2))
          .filter(Boolean),
      ),
    ].slice(0, 3)
    return {
      pairCount: riskSamples.value.length,
      total: samples.value.length,
      abnormalCount,
      l1Labels: labels,
      hasDetail: true,
    }
  })
  const poison = computed<PoisonSlice | null>(() => {
    if (!job.value) return null
    const reviewCount = riskSamples.value.filter((sample) => sample.disposition === 'review').length
    return {
      strategyCount: reviewCount,
      bypassCount: 0,
      topStrategies: ['demo_adapter', 'batch_minimal_lineage'].slice(0, reviewCount ? 2 : 1),
      hasDetail: true,
    }
  })
  const lineage = computed<LineageSlice | null>(() => {
    if (!job.value) return null
    return {
      totalNodes: samples.value.length * 4,
      totalEdges: samples.value.length * 3,
      riskyNodes: samples.value.filter((sample) => sample.disposition !== 'pass').length,
      reportSummary: `本批 ${samples.value.length} 条语料生成最小血缘链，绑定 job ${job.value.job_id}`,
      hasDetail: true,
    }
  })
  const valueEvidenceRows = computed(() => samples.value.filter(isValueIssue).map(mapEvidence))
  const riskEvidenceRows = computed(() => riskSamples.value.filter(isRisky).map(mapEvidence))
  const unreleasedSamples = computed(() =>
    samples.value.filter(
      (sample) => (sample.disposition || expectedDisposition(sample)) !== 'pass',
    ),
  )
  const unreleasedEvidenceRows = computed<UnreleasedEvidenceRow[]>(() =>
    unreleasedSamples.value.map(mapUnreleasedEvidenceRow),
  )
  const selectedEvidenceDetail = computed<UnreleasedEvidenceDetail | null>(() => {
    const selected =
      unreleasedSamples.value.find((sample) => sample.id === selectedEvidenceId.value) ||
      unreleasedSamples.value[0]
    return selected ? mapUnreleasedEvidenceDetail(selected) : null
  })
  const evidenceError = computed(() =>
    selectedEvidenceDetail.value ? '' : '运行后显示未放行语料的归因',
  )

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function pickDefaultSample(nextJob: InputGuardrailLiveRun) {
    const issue = nextJob.samples.find((sample) => sample.disposition !== 'pass')
    selectedEvidenceId.value = issue?.id || ''
  }

  async function refreshJob(jobId: string) {
    try {
      const next = await fetchInputGuardrailLiveRun(jobId)
      job.value = next
      jobError.value = ''
      if (
        !selectedEvidenceId.value ||
        !next.samples.some(
          (sample) => sample.id === selectedEvidenceId.value && sample.disposition !== 'pass',
        )
      ) {
        pickDefaultSample(next)
      }
      if (next.status !== 'pending' && next.status !== 'running') {
        running.value = false
        stopPolling()
      }
    } catch (error) {
      jobError.value = error instanceof Error ? error.message : '输入数据治理 live run 不存在'
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
      const list = await fetchInputGuardrailDemoPacks()
      packs.value = list
      if (!list.some((item) => item.pack_id === selectedPackId.value)) {
        selectedPackId.value = list[0]?.pack_id || DEFAULT_INPUT_PACK_ID
      }
    } catch (error) {
      packsError.value = error instanceof Error ? error.message : '输入数据治理演示批次不可达'
    } finally {
      packsLoading.value = false
    }
  }

  async function restoreJobFromQuery() {
    const jobId = typeof route.query.inputJob === 'string' ? route.query.inputJob : ''
    if (!jobId) return
    running.value = true
    await refreshJob(jobId)
    if (job.value && (job.value.status === 'pending' || job.value.status === 'running')) {
      startPolling(job.value.job_id)
    } else {
      running.value = false
    }
  }

  async function runLive() {
    if (!selectedPackId.value || jobBusy.value) return
    running.value = true
    jobError.value = ''
    selectedEvidenceId.value = ''
    try {
      const started = await startInputGuardrailLiveRun({ pack_id: selectedPackId.value })
      await router.replace({ query: { ...route.query, inputJob: started.job_id } })
      await refreshJob(started.job_id)
      startPolling(started.job_id)
    } catch (error) {
      running.value = false
      jobError.value = error instanceof Error ? error.message : '输入数据治理 live run 启动失败'
    }
  }

  function selectPack(packId: string) {
    selectedPackId.value = packId
  }

  function selectEvidenceRow(id: string) {
    selectedEvidenceId.value = id
  }

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
    valueRecords,
    categorySummary,
    sampleRows,
    runSummary,
    dispositionSummary,
    ingestLoading,
    ingestError,
    riskAssetName,
    riskPairCount,
    riskTotal,
    riskSnippets,
    valueLoading: jobBusy,
    valueError: jobError,
    valueStats,
    valueQuality,
    valueRadar,
    riskLoading: jobBusy,
    riskError: jobError,
    abnormal,
    poison,
    lineageLoading: jobBusy,
    lineageError: jobError,
    lineage,
    evidenceLoading: jobBusy,
    evidenceError,
    unreleasedEvidenceRows,
    selectedEvidenceId,
    selectedEvidenceDetail,
    valueEvidenceRows,
    riskEvidenceRows,
    valueFixItems,
    riskFixItems,
    selectPack,
    runLive,
    selectEvidenceRow,
  }
}
