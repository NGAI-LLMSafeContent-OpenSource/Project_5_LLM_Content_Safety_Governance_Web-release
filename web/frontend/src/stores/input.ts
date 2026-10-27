import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  AttributionResult,
  AttributionRow,
  IntegrationEndpoint,
  Topic2KeywordPrediction,
  Topic2KeywordResult,
  Topic2PrerunSamplesResult,
  Topic2PrerunSampleRow,
  Topic4LineageResult,
  ValueAssessmentResult,
  ValueQaAssetStatusResult,
  ValueQaDimensionItem,
} from '@/api/dataInput'
import {
  cloneInputItems,
  inputRadarScores,
  inputRiskScienceStandards,
  inputValueScienceStandards,
  type CorrectionPreviewRange,
  type InputAssessmentRow,
  type InputFixItem,
  type RiskAssessmentSummary,
  type ValueAssessmentSummary,
  emptyRiskAssessmentSummary,
  emptyValueAssessmentSummary,
} from '@/utils/inputMockData'
import { buildTopic2L1RadarScores, formatHarmCategoryL2 } from '@/utils/topic2HarmLabels'
import {
  datasetUploadAllowedExtensions,
  datasetUploadAllowedMimeTypes,
  datasetUploadMaxBytes,
  datasetUploadSupportLabel,
  type DatasetFormModel,
  type DataInputTrack,
} from '@/utils/dataInputConfig'
import type { DataInputWorkflowPayload } from '@/utils/inputWorkflowPayload'

export interface AttributionModuleStatus extends ExternalServiceStatus {
  track: 'value' | 'risk' | ''
  assetId: string
  assetName: string
  total: number
}

export interface DatasetUploadItem {
  id: string
  file: File
  signature: string
  parseStatus: 'idle' | 'parsing' | 'parsed' | 'failed'
  parseReason: string
  recordCount: number
}

export interface DatasetFileAppendResult {
  accepted: DatasetUploadItem[]
  rejected: Array<{ fileName: string; reason: string }>
}

export interface ExternalServiceStatus {
  checked: boolean
  connected: boolean
  loading: boolean
  service: string
  baseUrl: string
  message: string
  source: string
  mode: string
  fallback: boolean
  blockingReason: string
  nextAction: string
  endpoints: IntegrationEndpoint[]
}

export interface Topic2FilterGuardStatus extends ExternalServiceStatus {
  method: string
  taskId: string
  taskStatus: string
  progress: number
  cancellable: boolean
  total: number
  abnormalCount: number
  normalCount: number
}

export interface Topic2PrerunAssetStatus extends ExternalServiceStatus {
  assetId: string
  assetName: string
  total: number
  pairCount: number
  moderators: string[]
  l1Labels: string[]
}

export interface InputLineageSummary {
  totalNodes: number
  totalEdges: number
  metaCount: number
  chunkCount: number
  cleanedChunkCount: number
  questionCount: number
  answerCount: number
  riskyNodes: number
  cleanNodes: number
}

export const useInputStore = defineStore('input', () => {
  const datasetForm = ref<DatasetFormModel>({
    name: '',
    domain: '少数民族语言',
    volume: '1-10 万条',
    desc: '',
  })

  const uploadedFiles = ref<DatasetUploadItem[]>([])
  const customCorpusTrack = ref<DataInputTrack>('value')
  const uploadParseLoading = ref(false)
  const parsedUploadRecords = ref<Array<Record<string, unknown>>>([])
  const isDraggingFiles = ref(false)
  const corpusCatalog = ref<
    Array<{
      assetId: string
      name: string
      kind: string
      sourceLabel: string
      sampleCount: number
      ready: boolean
      description: string
      trackHint: string
      track: 'value' | 'risk' | ''
    }>
  >([])
  const corpusCatalogLoading = ref(false)
  const corpusCatalogMessage = ref('')
  const valueSelectedCorpus = ref<{
    assetId: string
    name: string
    kind: string
    sourceLabel: string
    total: number
  } | null>(null)
  const valueCorpusRecords = ref<Array<{ id: string; text: string; meta: Record<string, string> }>>(
    [],
  )
  const riskSelectedCorpus = ref<{
    assetId: string
    name: string
    kind: string
    sourceLabel: string
    total: number
  } | null>(null)
  const riskCorpusRecords = ref<Array<{ id: string; text: string; meta: Record<string, string> }>>(
    [],
  )
  /** 血缘图谱默认使用课题四静态预跑（无需启动课题四仓库） */
  const lineageCorpusSource = ref<'value' | 'risk' | 'topic4_static'>('topic4_static')
  const corpusSelectLoading = ref(false)
  /** 风险轨评估来源：静态预跑优先，neuron 为可选实时识别 */
  const riskAssessmentSource = ref<'static' | 'neuron' | ''>('')
  const activeDataInputStep = ref(1)
  const currentTrack = ref<DataInputTrack>('value')

  const valueScienceStandards = ref(cloneInputItems(inputValueScienceStandards))
  const riskScienceStandards = ref(cloneInputItems(inputRiskScienceStandards))
  const valueThresholdExcellent = ref('0.75')
  const valueThresholdGood = ref('0.45')
  const riskThresholdHigh = ref('0.7')
  const riskThresholdMid = ref('0.4')
  const riskThresholdLow = ref('0.2')
  const valueCustomRules = ref([
    '对含民族称谓片段强制套用尊重性用语模板',
    '涉及非遗描述时优先保留传承语境',
  ])
  const riskCustomRules = ref(['过滤包含特定敏感词的样本', '高风险样本进入人工复核白名单'])
  const newValueRule = ref('')
  const newRiskRule = ref('')

  const lineageNodes = ref<Topic4LineageResult['nodes']>([])
  const lineageEdges = ref<Topic4LineageResult['edges']>([])
  const topic4WorkflowStages = ref<Topic4LineageResult['workflowStages']>([])
  const topic4Annotations = ref<Topic4LineageResult['annotations']>([])
  const topic4CleaningActions = ref<Topic4LineageResult['cleaningActions']>([])
  const topic4ReportSummary = ref('')
  const selectedLineageNodeId = ref('')
  const lineageSummary = ref<InputLineageSummary>({
    totalNodes: 0,
    totalEdges: 0,
    metaCount: 0,
    chunkCount: 0,
    cleanedChunkCount: 0,
    questionCount: 0,
    answerCount: 0,
    riskyNodes: 0,
    cleanNodes: 0,
  })
  const topic4LineageStatus = ref<ExternalServiceStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: 'Project 4 Input Workflow',
    baseUrl: '',
    message: '尚未连接课题四输入侧血缘图谱服务。',
    source: 'topic4_input_workflow',
    mode: 'remote_service',
    fallback: false,
    blockingReason: '',
    nextAction: '进入血缘图谱节点后会自动检查服务健康状态，并同步调用 build_graph 和 graph/merge。',
    endpoints: [],
  })
  const selectedLineageNode = computed(
    () =>
      lineageNodes.value.find((node) => node.id === selectedLineageNodeId.value) ??
      lineageNodes.value[0],
  )

  const topic2FilterGuardStatus = ref<Topic2FilterGuardStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: 'Project 2 neuron',
    baseUrl: '',
    message: '尚未连接课题二 neuron / keyword 输入风险识别服务。',
    source: 'topic2_activation_probe',
    mode: 'remote_service',
    method: 'activation_probe',
    taskId: '',
    taskStatus: 'idle',
    progress: 0,
    cancellable: false,
    fallback: false,
    blockingReason: '',
    nextAction: '默认使用 neuron；也可切换到 keyword。',
    endpoints: [],
    total: 0,
    abnormalCount: 0,
    normalCount: 0,
  })
  const topic2RiskDetectMethod = ref<'activation_probe' | 'keyword'>('activation_probe')
  const topic2KeywordPredictions = ref<Topic2KeywordPrediction[]>([])
  const topic2PrerunAssetStatus = ref<Topic2PrerunAssetStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: '课题二正式预跑评测资产',
    baseUrl: '',
    message: '尚未载入课题二正式预跑评测资产。',
    source: 'benchmark_prerun_snapshot',
    mode: 'asset_registry',
    fallback: false,
    blockingReason: '',
    nextAction: '载入后会把课题二正式预跑结果、L1/L2 标签和评测器判定同步到评估、归因、修正展示。',
    endpoints: [],
    assetId: '',
    assetName: '',
    total: 0,
    pairCount: 0,
    moderators: [],
    l1Labels: [],
  })
  const valueAttributionStatus = ref<AttributionModuleStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: '课题一价值归因',
    baseUrl: '',
    message: '尚未载入课题一 value_qa / Risk Cause 价值归因。',
    source: 'topic1_value_qa',
    mode: 'attribution_module',
    fallback: false,
    blockingReason: '',
    nextAction: '进入归因页后可从 Benchmark value_qa 资产载入价值归因证据链。',
    endpoints: [],
    track: 'value',
    assetId: '',
    assetName: '',
    total: 0,
  })
  const riskAttributionStatus = ref<AttributionModuleStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: '课题二风险归因',
    baseUrl: '',
    message: '尚未生成课题二风险归因证据链。',
    source: 'topic2_activation_probe',
    mode: 'attribution_module',
    fallback: false,
    blockingReason: '',
    nextAction: '先完成 neuron / keyword 识别，或载入预跑资产，再生成风险归因。',
    endpoints: [],
    track: 'risk',
    assetId: '',
    assetName: '',
    total: 0,
  })
  const topic1ValueQaAssetStatus = ref<AttributionModuleStatus>({
    checked: false,
    connected: false,
    loading: false,
    service: '课题一 value_qa 价值评测语料',
    baseUrl: '',
    message: '尚未载入课题一 value_qa 资产。',
    source: 'topic1_value_qa',
    mode: 'asset_registry',
    fallback: false,
    blockingReason: '',
    nextAction: '进入价值轨后会自动同步筛选维度、评估样本、归因证据与待提升修正项。',
    endpoints: [],
    track: 'value',
    assetId: '',
    assetName: '',
    total: 0,
  })

  const radarScores = ref({ ...inputRadarScores })
  const valueStats = ref<Array<{ val: string; label: string }>>([])
  const riskStats = ref<Array<{ val: string; label: string }>>([])
  const riskAssessmentSummary = ref<RiskAssessmentSummary>(emptyRiskAssessmentSummary())
  const valueAssessmentSummary = ref<ValueAssessmentSummary>(emptyValueAssessmentSummary())
  const valueAssessmentRows = ref<InputAssessmentRow[]>([])
  const riskAssessmentRows = ref<InputAssessmentRow[]>([])

  const valueFixes = ref<InputFixItem[]>([])
  const riskFixes = ref<InputFixItem[]>([])
  const expandedFixId = ref('')
  const fixDirtyMap = ref<Record<string, boolean>>({})
  const correctionPreviewRange = ref<CorrectionPreviewRange>('待处理')

  const lastSubmittedWorkflow = ref<DataInputWorkflowPayload | null>(null)
  const lastSubmittedAt = ref('')
  const currentFixes = computed(() =>
    currentTrack.value === 'value' ? valueFixes.value : riskFixes.value,
  )
  const filteredFixes = computed(() => {
    if (correctionPreviewRange.value === 'all') return currentFixes.value
    return currentFixes.value.filter((item) => item.status === correctionPreviewRange.value)
  })

  function setCurrentTrack(nextTrack: DataInputTrack) {
    currentTrack.value = nextTrack
  }

  function setCustomCorpusTrack(nextTrack: DataInputTrack) {
    customCorpusTrack.value = nextTrack
    currentTrack.value = nextTrack
    if (uploadedFiles.value.length === 0) return
    if (nextTrack === 'value') clearValueSelectedCorpus()
    else clearRiskSelectedCorpus()
  }

  function setActiveDataInputStep(step: number) {
    activeDataInputStep.value = Math.min(Math.max(step, 1), 6)
  }

  function setDraggingFiles(value: boolean) {
    isDraggingFiles.value = value
  }

  function setCorpusCatalogLoading(value: boolean) {
    corpusCatalogLoading.value = value
  }

  function setCorpusSelectLoading(value: boolean) {
    corpusSelectLoading.value = value
  }

  function applyCorpusCatalog(payload: {
    connected: boolean
    message: string
    items: Array<{
      asset_id: string
      name: string
      kind: string
      source_label: string
      sample_count: number
      ready: boolean
      description: string
      track_hint: string
      track?: string
    }>
  }) {
    corpusCatalogMessage.value = payload.message
    corpusCatalog.value = (payload.items || []).map((item) => {
      const trackRaw = String(item.track || '').toLowerCase()
      const kind = String(item.kind || '')
      const track: 'value' | 'risk' | '' =
        trackRaw === 'value' || trackRaw === 'risk'
          ? trackRaw
          : kind === 'value_qa'
            ? 'value'
            : kind === 'risk_static_dynbench' || kind === 'topic2_prerun'
              ? 'risk'
              : ''
      return {
        assetId: item.asset_id,
        name: item.name,
        kind: item.kind,
        sourceLabel: item.source_label,
        sampleCount: item.sample_count || 0,
        ready: item.ready !== false,
        description: item.description || '',
        trackHint: item.track_hint || '',
        track,
      }
    })
  }

  function clearValueSelectedCorpus() {
    valueSelectedCorpus.value = null
    valueCorpusRecords.value = []
  }

  function clearRiskSelectedCorpus() {
    riskSelectedCorpus.value = null
    riskCorpusRecords.value = []
    riskAssessmentSource.value = ''
  }

  function clearSelectedCorpus() {
    clearValueSelectedCorpus()
    clearRiskSelectedCorpus()
  }

  function setLineageCorpusSource(source: 'value' | 'risk' | 'topic4_static') {
    lineageCorpusSource.value = source
  }

  function applySelectedCorpus(
    payload: {
      asset_id: string
      asset_name: string
      kind: string
      source_label: string
      total: number
      records: Array<{ id: string; text: string; meta?: Record<string, string> }>
    },
    track?: 'value' | 'risk',
  ) {
    const kind = String(payload.kind || '')
    const resolvedTrack: 'value' | 'risk' =
      track ||
      (kind === 'value_qa'
        ? 'value'
        : kind === 'risk_static_dynbench' || kind === 'topic2_prerun'
          ? 'risk'
          : 'value')
    const selected = {
      assetId: payload.asset_id,
      name: payload.asset_name,
      kind: payload.kind,
      sourceLabel: payload.source_label,
      total: payload.total,
    }
    const records = (payload.records || [])
      .map((row) => ({
        id: row.id,
        text: row.text,
        meta: row.meta || {},
      }))
      .filter((row) => row.text.trim())

    if (resolvedTrack === 'risk') {
      riskSelectedCorpus.value = selected
      riskCorpusRecords.value = records
      if (kind === 'risk_static_dynbench') {
        applyRiskStaticCorpusResult(records, selected)
      }
    } else {
      valueSelectedCorpus.value = selected
      valueCorpusRecords.value = records
    }

    uploadedFiles.value = []
    parsedUploadRecords.value = []
    if (payload.asset_name) {
      const valuePart = valueSelectedCorpus.value
        ? `价值：${valueSelectedCorpus.value.name}`
        : '价值：未选'
      const riskPart = riskSelectedCorpus.value
        ? `风险：${riskSelectedCorpus.value.name}`
        : '风险：未选'
      datasetForm.value = {
        ...datasetForm.value,
        name:
          resolvedTrack === 'risk' && !valueSelectedCorpus.value
            ? payload.asset_name
            : valueSelectedCorpus.value?.name || payload.asset_name,
        desc: `${valuePart}；${riskPart}（分轨绑定；血缘默认课题四静态预跑）`,
      }
    }
  }

  function applyRiskStaticCorpusResult(
    records: Array<{ id: string; text: string; meta: Record<string, string> }>,
    selected?: { assetId: string; name: string; sourceLabel: string; total: number } | null,
  ) {
    const rows = records.map(toRiskStaticAssessmentRow)
    const highRiskCount = rows.filter((row) => row.isAbnormal).length
    const normalCount = Math.max(rows.length - highRiskCount, 0)
    const anomalyRate = rows.length > 0 ? highRiskCount / rows.length : 0
    const l1Covered = rows.filter((row) => Boolean(row.riskCategoryL1?.trim())).length

    riskAssessmentSource.value = 'static'
    topic2KeywordPredictions.value = []
    riskAssessmentRows.value = rows
    riskAssessmentSummary.value = {
      total: rows.length,
      abnormal: highRiskCount,
      normal: normalCount,
      highRisk: highRiskCount,
      l1Covered,
      anomalyRate,
      method: 'static_prerun',
      methodLabel: '课题二静态预跑',
      ready: rows.length > 0,
    }
    riskStats.value = [
      { val: `${Math.round(anomalyRate * 100)}%`, label: '异常率' },
      { val: String(rows.length), label: '检测条数' },
      { val: String(normalCount), label: '安全样本' },
      { val: String(highRiskCount), label: '异常条数' },
    ]
    radarScores.value = {
      ...radarScores.value,
      ...buildRiskStaticL1RadarScores(rows),
    }
    riskFixes.value = rows
      .filter((row) => row.isAbnormal)
      .map((row) => ({
        id: `risk-static-fix-${row.id}`,
        title: `${row.id} 静态预跑异常复核`,
        status: '待处理',
        original: row.snippet,
        suggest: row.suggestion,
        recommended: row.suggestion,
      }))
    if (riskFixes.value.length === 0) expandedFixId.value = ''

    setTopic2PrerunAssetStatus({
      connected: rows.length > 0,
      service: '课题二静态预跑兜底',
      message:
        rows.length > 0
          ? `已载入静态预跑 ${rows.length} 条（默认展示；可切换 neuron 实时识别）。`
          : '静态预跑语料为空。',
      source: 'risk_static_dynbench',
      mode: 'static_prerun',
      fallback: false,
      blockingReason: '',
      nextAction: '进入风险评估可直接查看静态标签，或点击开始实时识别调用 neuron / keyword。',
      endpoints: [],
      assetId: selected?.assetId || riskSelectedCorpus.value?.assetId || '',
      assetName: selected?.name || riskSelectedCorpus.value?.name || '',
      total: rows.length,
      pairCount: 0,
      moderators: [],
      l1Labels: Array.from(
        new Set(
          rows
            .map((row) => row.riskCategoryL1)
            .filter((label): label is string => Boolean(label && label.trim())),
        ),
      ),
    })
  }

  function setUploadParseLoading(value: boolean) {
    uploadParseLoading.value = value
  }

  function clearParsedUploadRecords() {
    parsedUploadRecords.value = []
  }

  function setParsedUploadRecords(records: Array<Record<string, unknown>>) {
    parsedUploadRecords.value = records
  }

  function markUploadsParsing(fileIds: string[]) {
    const idSet = new Set(fileIds)
    uploadedFiles.value = uploadedFiles.value.map((item) =>
      idSet.has(item.id)
        ? { ...item, parseStatus: 'parsing', parseReason: '', recordCount: 0 }
        : item,
    )
  }

  function applyUploadParseOutcome(payload: {
    fileIds: string[]
    records: Array<Record<string, unknown>>
    failures: Array<{ name: string; reason: string }>
  }) {
    const idSet = new Set(payload.fileIds)
    const failureByName = new Map(payload.failures.map((item) => [item.name, item.reason] as const))
    const recordCountBySource = new Map<string, number>()
    payload.records.forEach((record) => {
      const source = String(record.source || '').trim()
      if (!source) return
      recordCountBySource.set(source, (recordCountBySource.get(source) || 0) + 1)
    })

    uploadedFiles.value = uploadedFiles.value.map((item) => {
      if (!idSet.has(item.id)) return item
      const failureReason = failureByName.get(item.file.name)
      if (failureReason) {
        return {
          ...item,
          parseStatus: 'failed',
          parseReason: failureReason,
          recordCount: 0,
        }
      }
      return {
        ...item,
        parseStatus: 'parsed',
        parseReason: '',
        recordCount: recordCountBySource.get(item.file.name) || 0,
      }
    })

    const keptSources = new Set(
      uploadedFiles.value
        .filter((item) => item.parseStatus === 'parsed')
        .map((item) => item.file.name),
    )
    const retained = parsedUploadRecords.value.filter((record) =>
      keptSources.has(String(record.source || '')),
    )
    const incoming = payload.records.filter((record) =>
      keptSources.has(String(record.source || '')),
    )
    const retainedWithoutIncoming = retained.filter(
      (record) =>
        !incoming.some((item) => String(item.source || '') === String(record.source || '')),
    )
    parsedUploadRecords.value = [...retainedWithoutIncoming, ...incoming]
  }

  function appendFiles(files: File[]): DatasetFileAppendResult {
    const existing = new Set(uploadedFiles.value.map((item) => item.signature))
    const merged = [...uploadedFiles.value]
    const accepted: DatasetUploadItem[] = []
    const rejected: DatasetFileAppendResult['rejected'] = []

    files.forEach((file) => {
      const validationMessage = validateDatasetFile(file, existing)
      if (validationMessage) {
        rejected.push({ fileName: file.name, reason: validationMessage })
        return
      }

      const signature = datasetFileSignature(file)
      const item: DatasetUploadItem = {
        id: createDatasetUploadId(),
        file,
        signature,
        parseStatus: 'idle',
        parseReason: '',
        recordCount: 0,
      }
      existing.add(signature)
      accepted.push(item)
      merged.push(item)
    })
    uploadedFiles.value = merged
    if (accepted.length > 0) {
      setCustomCorpusTrack(customCorpusTrack.value)
    }
    return { accepted, rejected }
  }

  function removeUploadedFile(fileId: string) {
    const removed = uploadedFiles.value.find((item) => item.id === fileId)
    uploadedFiles.value = uploadedFiles.value.filter((item) => item.id !== fileId)
    if (!removed) return
    parsedUploadRecords.value = parsedUploadRecords.value.filter(
      (record) => String(record.source || '') !== removed.file.name,
    )
  }

  function toggleScienceStandard(targetTrack: DataInputTrack, id: string) {
    const list = targetTrack === 'value' ? valueScienceStandards.value : riskScienceStandards.value
    const item = list.find((standard) => standard.id === id)
    if (item) item.enabled = !item.enabled
  }

  function addRule(targetTrack: DataInputTrack, value: string) {
    const target = targetTrack === 'value' ? valueCustomRules : riskCustomRules
    const trimmed = value.trim()
    if (!trimmed) return
    if (target.value.includes(trimmed)) return
    target.value.push(trimmed)
  }

  function removeRule(targetTrack: DataInputTrack, index: number) {
    const target = targetTrack === 'value' ? valueCustomRules : riskCustomRules
    target.value.splice(index, 1)
  }

  function updateValueThreshold(kind: 'excellent' | 'good', value: string) {
    const nextValue = normalizeThreshold(value)
    const currentExcellent = normalizeThreshold(valueThresholdExcellent.value)
    const currentGood = normalizeThreshold(valueThresholdGood.value)

    if (kind === 'excellent') {
      valueThresholdExcellent.value = formatThreshold(Math.max(nextValue, currentGood + 0.05))
      return
    }

    valueThresholdGood.value = formatThreshold(Math.min(nextValue, currentExcellent - 0.05))
  }

  function updateRiskThreshold(kind: 'high' | 'medium' | 'low', value: string) {
    const nextValue = normalizeThreshold(value)
    const high = normalizeThreshold(riskThresholdHigh.value)
    const medium = normalizeThreshold(riskThresholdMid.value)
    const low = normalizeThreshold(riskThresholdLow.value)

    if (kind === 'high') {
      riskThresholdHigh.value = formatThreshold(Math.max(nextValue, medium))
      return
    }

    if (kind === 'medium') {
      riskThresholdMid.value = formatThreshold(Math.min(Math.max(nextValue, low), high))
      return
    }

    riskThresholdLow.value = formatThreshold(Math.min(nextValue, medium))
  }

  function setExpandedFixId(id: string) {
    expandedFixId.value = expandedFixId.value === id ? '' : id
  }

  function updateSuggestedFixText(targetTrack: DataInputTrack, id: string, value: string) {
    const item = findFix(targetTrack, id)
    if (!item) return
    item.suggest = value
    fixDirtyMap.value[id] = item.suggest !== item.recommended
  }

  function applyRecommendedFix(targetTrack: DataInputTrack, id: string) {
    const item = findFix(targetTrack, id)
    if (!item) return
    item.suggest = item.recommended
    fixDirtyMap.value[id] = false
  }

  function resetFixText(targetTrack: DataInputTrack, id: string) {
    const item = findFix(targetTrack, id)
    if (!item) return
    item.suggest = item.original
    fixDirtyMap.value[id] = true
  }

  function markFixStatus(targetTrack: DataInputTrack, id: string, status: InputFixItem['status']) {
    const item = findFix(targetTrack, id)
    if (!item) return
    item.status = status
    if (status === '已采纳' || status === '已跳过' || status === '需复核') {
      expandedFixId.value = ''
    }
    if (status === '已采纳') {
      fixDirtyMap.value[id] = false
    }
  }

  function findFix(targetTrack: DataInputTrack, id: string) {
    const targetList = targetTrack === 'value' ? valueFixes.value : riskFixes.value
    return targetList.find((fix) => fix.id === id)
  }

  function rememberWorkflowSubmission(payload: DataInputWorkflowPayload) {
    lastSubmittedWorkflow.value = payload
    lastSubmittedAt.value = new Date().toISOString()
  }

  function setTopic4LineageLoading(value: boolean) {
    topic4LineageStatus.value.loading = value
  }

  function setTopic4LineageStatus(status: Partial<ExternalServiceStatus>) {
    topic4LineageStatus.value = {
      ...topic4LineageStatus.value,
      ...status,
      checked: true,
    }
  }

  function applyTopic4LineageResult(result: Topic4LineageResult) {
    setTopic4LineageStatus({
      connected: result.connected,
      service: result.service,
      baseUrl: result.base_url,
      message: result.message,
      source: result.source,
      mode: result.mode,
      fallback: result.fallback,
      blockingReason: result.blocking_reason,
      nextAction: result.next_action,
      endpoints: result.endpoints,
    })

    if (!result.connected || result.nodes.length === 0) return

    lineageNodes.value = result.nodes
    lineageEdges.value = result.edges
    topic4WorkflowStages.value = result.workflowStages
    topic4Annotations.value = result.annotations
    topic4CleaningActions.value = result.cleaningActions
    topic4ReportSummary.value = result.reportSummary
    lineageSummary.value = result.summary
    selectedLineageNodeId.value = result.selectedNodeId || result.nodes[0].id
  }

  function clearTopic4LineageResult() {
    lineageNodes.value = []
    lineageEdges.value = []
    topic4WorkflowStages.value = []
    topic4Annotations.value = []
    topic4CleaningActions.value = []
    topic4ReportSummary.value = ''
    lineageSummary.value = {
      totalNodes: 0,
      totalEdges: 0,
      metaCount: 0,
      chunkCount: 0,
      cleanedChunkCount: 0,
      questionCount: 0,
      answerCount: 0,
      riskyNodes: 0,
      cleanNodes: 0,
    }
    selectedLineageNodeId.value = ''
  }

  function setTopic2RiskDetectMethod(method: 'activation_probe' | 'keyword') {
    topic2RiskDetectMethod.value = method
    topic2FilterGuardStatus.value.method = method
    if (method === 'activation_probe') {
      topic2FilterGuardStatus.value.service = 'Project 2 neuron'
      topic2FilterGuardStatus.value.source = 'topic2_activation_probe'
      topic2FilterGuardStatus.value.nextAction = '点击启动后将调用远程 neuron 识别服务。'
    } else {
      topic2FilterGuardStatus.value.service = 'Project 2 keyword'
      topic2FilterGuardStatus.value.source = 'topic2_filterguard'
      topic2FilterGuardStatus.value.nextAction = '点击启动后将调用本地 keyword 识别服务。'
    }
  }

  function setTopic2FilterGuardLoading(value: boolean) {
    topic2FilterGuardStatus.value.loading = value
  }

  function setTopic2PrerunAssetLoading(value: boolean) {
    topic2PrerunAssetStatus.value.loading = value
  }

  function setTopic2FilterGuardStatus(status: Partial<Topic2FilterGuardStatus>) {
    topic2FilterGuardStatus.value = {
      ...topic2FilterGuardStatus.value,
      ...status,
      checked: true,
    }
  }

  function clearTopic2RiskScanTaskState() {
    setTopic2FilterGuardStatus({
      taskId: '',
      taskStatus: 'idle',
      progress: 0,
      cancellable: false,
    })
  }

  function setTopic2PrerunAssetStatus(status: Partial<Topic2PrerunAssetStatus>) {
    topic2PrerunAssetStatus.value = {
      ...topic2PrerunAssetStatus.value,
      ...status,
      checked: true,
    }
  }

  function applyTopic2KeywordResult(result: Topic2KeywordResult) {
    riskAssessmentSource.value = result.connected ? 'neuron' : riskAssessmentSource.value
    setTopic2FilterGuardStatus({
      connected: result.connected,
      service: result.service,
      baseUrl: result.base_url,
      message: result.message,
      source: result.source,
      mode: result.mode,
      method: result.method,
      fallback: result.fallback,
      blockingReason: result.blocking_reason,
      nextAction: result.next_action,
      endpoints: result.endpoints,
      taskStatus: result.connected ? 'completed' : 'failed',
      progress: 100,
      cancellable: false,
      total: result.total,
      abnormalCount: result.abnormal_count,
      normalCount: result.normal_count,
    })

    if (!result.connected) {
      clearTopic2KeywordResult()
      return
    }

    topic2KeywordPredictions.value = result.predictions
    riskAssessmentRows.value = result.predictions.map(toRiskAssessmentRow)
    const l1Covered = result.predictions.filter(
      (item) => Boolean(item.risk_category_l1?.trim()) || Boolean(item.predicted_l1_id?.trim()),
    ).length
    const isNeuron =
      result.method === 'activation_probe' || result.source === 'topic2_activation_probe'
    const methodLabel = isNeuron ? 'neuron' : 'keyword'
    const anomalyRate = result.total > 0 ? result.abnormal_count / result.total : 0
    // Prefer Topic2 abnormal_count for the high-risk secondary metric so UI stays API-aligned.
    const highRiskDisplay = result.abnormal_count

    riskAssessmentSummary.value = {
      total: result.total,
      abnormal: result.abnormal_count,
      normal: result.normal_count,
      highRisk: highRiskDisplay,
      l1Covered,
      anomalyRate,
      method: result.method || (isNeuron ? 'activation_probe' : 'keyword'),
      methodLabel,
      ready: true,
    }
    riskStats.value = [
      { val: `${Math.round(anomalyRate * 100)}%`, label: '异常率' },
      { val: String(result.total), label: '检测条数' },
      { val: String(result.normal_count), label: '安全样本' },
      { val: String(highRiskDisplay), label: '异常条数' },
    ]
    radarScores.value = {
      ...radarScores.value,
      ...buildTopic2L1RadarScores(result.predictions),
    }
    if (result.total > 0 && !isNeuron) {
      const hitSampleCount = result.predictions.filter((item) => item.findings.length > 0).length
      if (hitSampleCount === 0) {
        setTopic2FilterGuardStatus({
          message: `${result.message} 当前全部样本风险分为 0，表示 keyword 词表未命中；若语料为中文风险内容，请确认 keyword 服务已加载中文词表后重试。`,
        })
      }
    }
    riskFixes.value = result.predictions.filter((item) => item.is_abnormal).map(toRiskFixItem)
    if (riskFixes.value.length === 0) expandedFixId.value = ''
  }

  function applyTopic2PrerunAssetResult(result: Topic2PrerunSamplesResult) {
    const rows = result.rows.map(toTopic2PrerunAssessmentRow)
    setTopic2PrerunAssetStatus({
      connected: result.connected,
      service: result.service,
      baseUrl: result.base_url,
      message: result.message,
      source: result.source,
      mode: result.mode,
      fallback: result.fallback,
      blockingReason: result.blocking_reason,
      nextAction: result.next_action,
      endpoints: result.endpoints,
      assetId: result.asset_id,
      assetName: result.asset_name,
      total: result.total,
      pairCount: result.pair_count,
      moderators: result.moderators,
      l1Labels: result.l1_labels,
    })

    topic2KeywordPredictions.value = []
    riskAssessmentRows.value = rows
    const highRiskCount = rows.filter(
      (row) => row.status === '异常' || row.status === '高风险' || row.isAbnormal,
    ).length
    const normalCount = Math.max(result.total - highRiskCount, 0)
    const anomalyRate = result.total > 0 ? highRiskCount / result.total : 0
    const l1Covered = rows.filter((row) => Boolean(row.riskCategoryL1?.trim())).length
    riskAssessmentSummary.value = {
      total: result.total,
      abnormal: highRiskCount,
      normal: normalCount,
      highRisk: highRiskCount,
      l1Covered,
      anomalyRate,
      method: 'prerun_asset',
      methodLabel: '课题二预跑资产',
      ready: true,
    }
    riskStats.value = [
      { val: `${Math.round(anomalyRate * 100)}%`, label: '异常率' },
      { val: String(result.total), label: '检测条数' },
      { val: String(normalCount), label: '安全样本' },
      { val: String(highRiskCount), label: '异常条数' },
    ]
    riskFixes.value = rows
      .filter((row) => row.status === '异常' || row.status === '高风险' || row.isAbnormal)
      .map((row) => ({
        id: `topic2-prerun-fix-${row.id}`,
        title: `${row.id} 课题二预跑漏检复核`,
        status: '待处理',
        original: row.snippet,
        suggest: row.suggestion,
        recommended: row.suggestion,
      }))
    if (riskFixes.value.length === 0) expandedFixId.value = ''
  }

  function clearTopic2KeywordResult() {
    topic2KeywordPredictions.value = []
    riskAssessmentRows.value = []
    riskAssessmentSummary.value = emptyRiskAssessmentSummary()
    riskStats.value = [
      { val: '0%', label: '异常率' },
      { val: '0', label: '检测条数' },
      { val: '0', label: '安全样本' },
      { val: '0', label: '异常条数' },
    ]
    riskFixes.value = []
    expandedFixId.value = ''
    topic2FilterGuardStatus.value.total = 0
    topic2FilterGuardStatus.value.abnormalCount = 0
    topic2FilterGuardStatus.value.normalCount = 0
  }

  function clearTopic2PrerunAssetResult() {
    setTopic2PrerunAssetStatus({
      connected: false,
      message: '尚未载入课题二正式预跑评测资产。',
      blockingReason: '',
      nextAction:
        '请先在 Benchmark 资产管理中导入课题二正式预跑快照，再回到输入风险评估页载入平台资产。',
      assetId: '',
      assetName: '',
      total: 0,
      pairCount: 0,
      moderators: [],
      l1Labels: [],
    })
  }

  function setValueAttributionLoading(value: boolean) {
    valueAttributionStatus.value.loading = value
  }

  function setRiskAttributionLoading(value: boolean) {
    riskAttributionStatus.value.loading = value
  }

  function setTopic1ValueQaAssetLoading(value: boolean) {
    topic1ValueQaAssetStatus.value.loading = value
  }

  function applyTopic1ValueQaAssetStatus(result: ValueQaAssetStatusResult) {
    topic1ValueQaAssetStatus.value = {
      ...topic1ValueQaAssetStatus.value,
      checked: true,
      connected: result.connected,
      service: result.service,
      message: result.message,
      source: result.source,
      mode: result.mode,
      fallback: result.fallback,
      blockingReason: result.blocking_reason,
      nextAction: result.next_action,
      endpoints: result.endpoints,
      track: 'value',
      assetId: result.asset_id,
      assetName: result.asset_name,
      total: result.total,
    }
  }

  function applyValueAssessmentResult(result: ValueAssessmentResult) {
    applyTopic1ValueQaAssetStatus({
      connected: result.connected,
      service: result.service,
      message: result.message,
      source: result.source,
      mode: result.mode,
      fallback: result.fallback,
      blocking_reason: result.blocking_reason,
      next_action: result.next_action,
      endpoints: result.endpoints,
      asset_id: result.asset_id,
      asset_name: result.asset_name,
      total: result.total,
      group_count: result.group_count,
      qc_status: '',
      trace_status: '',
      quality_level_distribution: result.quality_level_distribution,
      primary_dimension_distribution: {},
      secondary_dimension_distribution: {},
    })
    if (!result.connected) return

    valueAssessmentRows.value = result.rows.map(toAttributionAssessmentRow)
    const excellent = result.rows.filter((row) => row.status === '优').length
    const good = result.rows.filter((row) => row.status === '良').length
    const improve = result.rows.filter(
      (row) => row.status === '待提升' || row.quality_level === 'low',
    ).length
    const total = result.total || result.rows.length
    valueAssessmentSummary.value = {
      total,
      excellent,
      good,
      improve,
      improveRate: total > 0 ? improve / total : 0,
      ready: true,
    }
    if (result.stats.length > 0) {
      valueStats.value = result.stats.map((item) => ({ val: item.val, label: item.label }))
    } else {
      valueStats.value = [
        { val: `${Math.round((total > 0 ? improve / total : 0) * 100)}%`, label: '待提升占比' },
        { val: String(total), label: '总数据条数' },
        { val: String(excellent), label: '优档条数' },
        { val: String(good), label: '良档条数' },
      ]
    }
    if (Object.keys(result.radar_scores).length > 0) {
      radarScores.value = { ...radarScores.value, ...result.radar_scores }
    }
    valueFixes.value = (result.fix_rows.length > 0 ? result.fix_rows : result.rows)
      .filter((row) => row.status === '待提升' || row.quality_level === 'low')
      .map(toValueAttributionFixItem)
    if (valueFixes.value.length === 0) expandedFixId.value = ''
  }

  function applyValueQaScienceStandards(dimensions: ValueQaDimensionItem[]) {
    const secondary = dimensions.filter((item) => item.kind === 'secondary')
    const source =
      secondary.length > 0 ? secondary : dimensions.filter((item) => item.kind === 'primary')
    if (source.length === 0) return
    const previousEnabledById = new Map(
      valueScienceStandards.value.map((item) => [item.id, item.enabled] as const),
    )
    const previousEnabledByName = new Map(
      valueScienceStandards.value.map((item) => [item.name, item.enabled] as const),
    )
    const hadPrevious = valueScienceStandards.value.some((item) => item.tag === '课题一')
    valueScienceStandards.value = source.map((item) => {
      const id = `topic1-science-${item.name}`
      const enabled = hadPrevious
        ? (previousEnabledById.get(id) ?? previousEnabledByName.get(item.name) ?? true)
        : true
      return {
        id,
        name: item.name,
        desc: `课题一 value_qa 维度 · ${item.count} 组`,
        tag: '课题一',
        enabled,
      }
    })
  }

  function setScienceStandardEnabled(targetTrack: DataInputTrack, id: string, enabled: boolean) {
    const list = targetTrack === 'value' ? valueScienceStandards.value : riskScienceStandards.value
    const item = list.find((standard) => standard.id === id || standard.name === id)
    if (item) item.enabled = enabled
  }

  /** 风险轨副区：本批语料出现的 L2 标签（展示中文名） */
  function applyRiskL2ScienceStandards(
    dimensions: Array<{ name: string; count: number; l1Code?: string }>,
  ) {
    if (dimensions.length === 0) {
      riskScienceStandards.value = []
      return
    }
    const previousEnabledById = new Map(
      riskScienceStandards.value.map((item) => [item.id, item.enabled] as const),
    )
    const previousEnabledByName = new Map(
      riskScienceStandards.value.map((item) => [item.name, item.enabled] as const),
    )
    const previousEnabledByRaw = new Map(
      riskScienceStandards.value
        .filter((item) => item.rawName)
        .map((item) => [String(item.rawName), item.enabled] as const),
    )
    const hadPrevious = riskScienceStandards.value.length > 0
    riskScienceStandards.value = dimensions.map((item) => {
      const displayName = formatHarmCategoryL2(item.name) || item.name
      const id = `topic2-l2-${item.name}`
      const enabled = hadPrevious
        ? (previousEnabledById.get(id) ??
          previousEnabledByRaw.get(item.name) ??
          previousEnabledByName.get(displayName) ??
          true)
        : true
      return {
        id,
        name: displayName,
        rawName: item.name,
        l1Code: item.l1Code || '',
        parentEnabled: true,
        desc: item.l1Code
          ? `课题二 L2 · 归属 ${item.l1Code} · 本批 ${item.count} 条`
          : `课题二 L2 · 本批 ${item.count} 条`,
        tag: item.l1Code || 'L2',
        enabled,
      }
    })
  }

  /** Disable / uncheck L2 tags whose parent L1 is off. */
  function syncRiskL2WithParentL1(enabledL1Codes: string[]) {
    const enabled = new Set(enabledL1Codes)
    riskScienceStandards.value.forEach((item) => {
      const parentOn = !item.l1Code || enabled.has(item.l1Code)
      item.parentEnabled = parentOn
      if (!parentOn) item.enabled = false
    })
  }

  function applyAttributionResult(result: AttributionResult) {
    const statusPayload = {
      checked: true,
      connected: result.connected,
      service: result.service,
      message: result.message,
      source: result.source,
      mode: result.mode,
      fallback: result.fallback,
      blockingReason: result.blocking_reason,
      nextAction: result.next_action,
      endpoints: result.endpoints,
      track: (result.track === 'value' || result.track === 'risk' ? result.track : '') as
        | 'value'
        | 'risk'
        | '',
      assetId: result.asset_id,
      assetName: result.asset_name,
      total: result.total,
    }

    if (result.track === 'value') {
      // 归因状态独立维护，避免覆盖筛选/评估页的 value_qa 资产状态
      valueAttributionStatus.value = { ...valueAttributionStatus.value, ...statusPayload }
      if (!result.connected) return
      valueAssessmentRows.value = result.rows.map(toAttributionAssessmentRow)
      if (result.stats.length > 0) {
        valueStats.value = result.stats.map((item) => ({ val: item.val, label: item.label }))
      }
      const excellent = result.rows.filter((row) => row.status === '优').length
      const good = result.rows.filter((row) => row.status === '良').length
      const improve = result.rows.filter((row) => row.status === '待提升').length
      const total = result.total || result.rows.length
      valueAssessmentSummary.value = {
        total,
        excellent,
        good,
        improve,
        improveRate: total > 0 ? improve / total : 0,
        ready: true,
      }
      valueFixes.value = result.rows
        .filter((row) => row.status === '待提升')
        .map(toValueAttributionFixItem)
      if (valueFixes.value.length === 0) expandedFixId.value = ''
      return
    }

    riskAttributionStatus.value = { ...riskAttributionStatus.value, ...statusPayload }
    if (!result.connected) return
    riskAssessmentRows.value = result.rows.map(toAttributionAssessmentRow)
    const total = result.total || result.rows.length
    const highRiskCount = result.rows.filter(
      (row) => row.status === '异常' || row.status === '高风险',
    ).length
    const abnormalCount = result.rows.filter(
      (row) => row.status === '异常' || row.status === '高风险' || row.status === '中风险',
    ).length
    const normalCount = Math.max(total - abnormalCount, 0)
    const l1Covered = result.rows.filter(
      (row) => Boolean(row.risk_category_l1?.trim()) || Boolean(row.predicted_l1_id?.trim()),
    ).length
    const anomalyRate = total > 0 ? abnormalCount / total : 0
    riskAssessmentSummary.value = {
      total,
      abnormal: abnormalCount,
      normal: normalCount,
      highRisk: highRiskCount || abnormalCount,
      l1Covered,
      anomalyRate,
      method: 'risk_attribution',
      methodLabel: '风险归因资产',
      ready: true,
    }
    if (result.stats.length > 0) {
      riskStats.value = result.stats.map((item) => ({ val: item.val, label: item.label }))
    } else {
      riskStats.value = [
        { val: `${Math.round(anomalyRate * 100)}%`, label: '异常率' },
        { val: String(total), label: '检测条数' },
        { val: String(normalCount), label: '安全样本' },
        { val: String(abnormalCount), label: '异常条数' },
      ]
    }
    radarScores.value = {
      ...radarScores.value,
      ...buildTopic2L1RadarScores(
        result.rows.map((row) => ({
          is_abnormal: row.status === '异常' || row.status === '高风险' || row.status === '中风险',
          risk_category_l1: row.risk_category_l1,
          predicted_l1_id: row.predicted_l1_id,
        })),
      ),
    }
    riskFixes.value = result.rows
      .filter((row) => row.status === '异常' || row.status === '高风险' || row.status === '中风险')
      .map(toRiskAttributionFixItem)
    if (riskFixes.value.length === 0) expandedFixId.value = ''
  }

  function validateDatasetFile(file: File, existingFileSignatures: Set<string>) {
    if (existingFileSignatures.has(datasetFileSignature(file))) return '文件已存在'
    if (file.size > datasetUploadMaxBytes) return '单文件超过 500MB'

    const lowerName = file.name.toLowerCase()
    const hasAllowedExtension = datasetUploadAllowedExtensions.some((extension) =>
      lowerName.endsWith(extension),
    )
    const hasAllowedMimeType =
      !file.type || datasetUploadAllowedMimeTypes.includes(file.type.toLowerCase())

    if (!hasAllowedExtension || !hasAllowedMimeType) {
      return `仅支持 ${datasetUploadSupportLabel} 文件`
    }
    return ''
  }

  function datasetFileSignature(file: File) {
    return `${file.name}::${file.size}::${file.lastModified}`
  }

  function createDatasetUploadId() {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  function normalizeThreshold(value: string) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) return 0
    return Math.min(Math.max(parsed, 0), 1)
  }

  function formatThreshold(value: number) {
    const normalized = Math.min(Math.max(value, 0), 1)
    return Number(normalized.toFixed(2)).toString()
  }

  return {
    datasetForm,
    uploadedFiles,
    customCorpusTrack,
    uploadParseLoading,
    parsedUploadRecords,
    isDraggingFiles,
    corpusCatalog,
    corpusCatalogLoading,
    corpusCatalogMessage,
    valueSelectedCorpus,
    valueCorpusRecords,
    riskSelectedCorpus,
    riskCorpusRecords,
    lineageCorpusSource,
    riskAssessmentSource,
    corpusSelectLoading,
    activeDataInputStep,
    valueScienceStandards,
    riskScienceStandards,
    valueThresholdExcellent,
    valueThresholdGood,
    riskThresholdHigh,
    riskThresholdMid,
    riskThresholdLow,
    valueCustomRules,
    riskCustomRules,
    newValueRule,
    newRiskRule,
    lineageNodes,
    lineageEdges,
    topic4WorkflowStages,
    topic4Annotations,
    topic4CleaningActions,
    topic4ReportSummary,
    lineageSummary,
    topic4LineageStatus,
    topic2FilterGuardStatus,
    topic2RiskDetectMethod,
    topic2PrerunAssetStatus,
    topic2KeywordPredictions,
    valueAttributionStatus,
    riskAttributionStatus,
    topic1ValueQaAssetStatus,
    selectedLineageNodeId,
    selectedLineageNode,
    radarScores,
    valueStats,
    riskStats,
    riskAssessmentSummary,
    valueAssessmentSummary,
    valueAssessmentRows,
    riskAssessmentRows,
    valueFixes,
    riskFixes,
    expandedFixId,
    fixDirtyMap,
    correctionPreviewRange,
    filteredFixes,
    currentFixes,
    currentTrack,
    lastSubmittedWorkflow,
    lastSubmittedAt,
    setExpandedFixId,
    setCurrentTrack,
    setCustomCorpusTrack,
    setActiveDataInputStep,
    setDraggingFiles,
    setCorpusCatalogLoading,
    setCorpusSelectLoading,
    applyCorpusCatalog,
    clearSelectedCorpus,
    clearValueSelectedCorpus,
    clearRiskSelectedCorpus,
    setLineageCorpusSource,
    applySelectedCorpus,
    applyRiskStaticCorpusResult,
    appendFiles,
    removeUploadedFile,
    setUploadParseLoading,
    clearParsedUploadRecords,
    setParsedUploadRecords,
    markUploadsParsing,
    applyUploadParseOutcome,
    toggleScienceStandard,
    setScienceStandardEnabled,
    syncRiskL2WithParentL1,
    addRule,
    removeRule,
    updateValueThreshold,
    updateRiskThreshold,
    updateSuggestedFixText,
    applyRecommendedFix,
    resetFixText,
    markFixStatus,
    rememberWorkflowSubmission,
    setTopic4LineageLoading,
    setTopic4LineageStatus,
    applyTopic4LineageResult,
    clearTopic4LineageResult,
    setTopic2FilterGuardLoading,
    setTopic2RiskDetectMethod,
    setTopic2PrerunAssetLoading,
    setTopic2FilterGuardStatus,
    setTopic2PrerunAssetStatus,
    clearTopic2RiskScanTaskState,
    applyTopic2KeywordResult,
    applyTopic2PrerunAssetResult,
    clearTopic2KeywordResult,
    clearTopic2PrerunAssetResult,
    setValueAttributionLoading,
    setRiskAttributionLoading,
    setTopic1ValueQaAssetLoading,
    applyTopic1ValueQaAssetStatus,
    applyValueAssessmentResult,
    applyValueQaScienceStandards,
    applyRiskL2ScienceStandards,
    applyAttributionResult,
  }
})

function toRiskAssessmentRow(item: Topic2KeywordPrediction): InputAssessmentRow {
  const detectMethod = item.detect_method || 'keyword'
  return {
    id: item.id,
    score: item.score.toFixed(2),
    status: item.status,
    snippet: item.text,
    suggestion: item.action || item.suggestion,
    source: detectMethod === 'activation_probe' ? 'topic2_activation_probe' : 'topic2_filterguard',
    lineageNodeId: item.lineage_node_id,
    lineageNodeLabel: item.lineage_node_label,
    riskCategoryL1: item.risk_category_l1,
    riskCategoryL2: item.risk_category_l2,
    predictedL1Id: item.predicted_l1_id || '',
    detectMethod,
    action: item.action || item.suggestion,
    isAbnormal: item.is_abnormal,
    evidenceChain: item.evidence_chain,
    findings: item.findings.map((finding) => ({
      keyword: finding.keyword,
      evidence: finding.evidence,
      riskType: finding.risk_type,
    })),
  }
}

function toRiskStaticAssessmentRow(row: {
  id: string
  text: string
  meta: Record<string, string>
}): InputAssessmentRow {
  const originalLabel = String(row.meta.original_label || '').toLowerCase()
  const isAbnormal =
    originalLabel === 'unsafe' || String(row.meta.is_risky || '').toLowerCase() === 'true'
  const l1 = row.meta.harm_category_l1 || row.meta.harm_category_L1 || ''
  const l2 = row.meta.harm_category_l2 || row.meta.harm_category_L2 || ''
  return {
    id: row.id,
    score: isAbnormal ? '1.00' : '0.00',
    status: isAbnormal ? '异常' : '安全',
    snippet: row.text,
    suggestion: isAbnormal
      ? [
          '【处置要点】静态 DynBench 仅有 unsafe 标签，无安全改写正文。',
          l1 ? `- L1：${l1}` : '',
          l2 ? `- L2：${l2}` : '',
          '- 建议：剔除、脱敏关键实体，或人工改写后复检。',
        ]
          .filter(Boolean)
          .join('\n')
      : '静态预跑标注为 safe，可纳入安全样本抽检。',
    source: 'risk_static_dynbench',
    lineageNodeId: '',
    lineageNodeLabel: row.id,
    riskCategoryL1: l1,
    riskCategoryL2: l2,
    predictedL1Id: '',
    detectMethod: 'static_prerun',
    action: isAbnormal ? '复核并清洗' : '保留抽检',
    isAbnormal,
    evidenceChain: [
      `original_label=${originalLabel || 'unknown'}`,
      l1 ? `harm_category_L1=${l1}` : '',
      l2 ? `harm_category_L2=${l2}` : '',
    ].filter(Boolean),
    findings: l1
      ? [
          {
            keyword: l1,
            evidence: row.text.slice(0, 120),
            riskType: l1,
          },
        ]
      : [],
  }
}

function buildRiskStaticL1RadarScores(rows: InputAssessmentRow[]): Record<string, number> {
  // Same口径 as neuron: 该 L1 异常条数 / 本批总条数
  return buildTopic2L1RadarScores(
    rows.map((row) => ({
      is_abnormal: row.isAbnormal,
      risk_category_l1: row.riskCategoryL1,
      predicted_l1_id: row.predictedL1Id,
    })),
  )
}

function toRiskFixItem(item: Topic2KeywordPrediction): InputFixItem {
  const detectMethod = item.detect_method || 'keyword'
  const action =
    item.action ||
    (item.is_abnormal
      ? '建议结合上下文复核，必要时删除、脱敏或改写该片段。'
      : '可纳入安全样本抽检。')
  const disposition = buildRiskDispositionDraft(item) || item.suggestion || action
  const title =
    detectMethod === 'activation_probe' ? `${item.id} neuron 复核` : `${item.id} keyword 命中复核`
  const methodLabel = detectMethod === 'activation_probe' ? 'neuron' : 'keyword'
  const l1 =
    item.risk_category_l1 || (item.predicted_l1_id ? `L1 id=${item.predicted_l1_id}` : '未返回 L1')
  const status = item.status || (item.is_abnormal ? '异常' : '安全')
  const attributionSteps = [
    {
      title: '绑定血缘',
      detail: item.lineage_node_label || item.lineage_node_id || '未绑定血缘节点',
    },
    { title: '课题二识别', detail: methodLabel },
    { title: 'L1 路由', detail: l1 },
    { title: '判定', detail: `${status} · 风险分 ${item.score.toFixed(2)}` },
    { title: '处置', detail: action },
  ]
  return {
    id: `topic2-fix-${item.id}`,
    sampleId: item.id,
    title,
    status: '待处理',
    original: item.text,
    suggest: disposition,
    recommended: disposition,
    evidenceChain: item.evidence_chain,
    attributionSteps,
    lineageNodeLabel: item.lineage_node_label,
    contractStatus: item.correction_contract_status,
    riskCategoryL1: item.risk_category_l1,
    riskCategoryL2: item.risk_category_l2,
    predictedL1Id: item.predicted_l1_id || '',
    detectMethod,
    action,
    note: '课题二未提供安全改写正文',
  }
}

function buildRiskDispositionDraft(item: Topic2KeywordPrediction): string {
  if (!item.is_abnormal) return ''
  const lines: string[] = ['【处置要点】课题二未提供安全改写正文，请按证据人工处理：']
  const findings = item.findings || []
  if (findings.length > 0) {
    findings.slice(0, 5).forEach((finding) => {
      const keyword = (finding.keyword || '').trim()
      const evidence = (finding.evidence || '').trim().replace(/\s+/g, ' ')
      const short = evidence.length > 72 ? `${evidence.slice(0, 72)}…` : evidence
      if (keyword && short) lines.push(`- 命中「${keyword}」：相关片段「${short}」`)
      else if (keyword) lines.push(`- 命中「${keyword}」`)
      else if (short) lines.push(`- 证据片段「${short}」`)
    })
  }
  const l1 = item.risk_category_l1 || item.predicted_l1_id
  if (l1)
    lines.push(
      `- 风险类别 / L1：${l1}${item.risk_category_l2 ? ` / ${item.risk_category_l2}` : ''}`,
    )
  lines.push('- 建议动作：删除或替换风险片段 → 复跑识别 → 再决定是否入训。')
  return lines.length > 2 ? lines.join('\n') : ''
}

function toTopic2PrerunAssessmentRow(row: Topic2PrerunSampleRow): InputAssessmentRow {
  const isAbnormal = row.status === '异常' || row.status === '高风险' || row.status === '中风险'
  return {
    id: row.id,
    score: row.score.toFixed(2),
    status: row.status,
    snippet: row.snippet,
    suggestion: row.suggestion,
    source: 'topic2_prerun_snapshot',
    riskCategoryL1: row.harm_category_l1,
    riskCategoryL2: row.harm_category_l2,
    isAbnormal,
    difficultyLevel: row.difficulty_level,
    strategyChain: row.strategy_chain,
  }
}

function toAttributionAssessmentRow(row: AttributionRow): InputAssessmentRow {
  const isAbnormal = row.status === '异常' || row.status === '高风险' || row.status === '中风险'
  return {
    id: row.id,
    score: row.score,
    status: row.status,
    snippet: row.snippet,
    suggestion: row.suggestion,
    source: row.source,
    summary: row.summary,
    lineageNodeId: row.lineage_node_id,
    lineageNodeLabel: row.lineage_node_label,
    riskCategoryL1: row.risk_category_l1,
    riskCategoryL2: row.risk_category_l2,
    predictedL1Id: row.predicted_l1_id,
    detectMethod: row.detect_method,
    action: row.action || row.suggestion,
    isAbnormal,
    evidenceChain: row.evidence_chain,
    attributionSteps: (row.attribution_steps || []).map((step) => ({
      title: step.title,
      detail: step.detail,
    })),
    note: row.note || '',
    findings: row.findings.map((finding) => ({
      keyword: finding.keyword,
      evidence: finding.evidence,
      riskType: finding.risk_type,
      label: finding.label,
    })),
    issueSpans: (row.issue_spans || []).map((issue) => ({
      type: issue.type,
      sentence: issue.sentence,
      span: issue.span,
    })),
    dimension: row.dimension,
    topic: row.topic,
    trueLabel: row.true_label,
    predictedLabel: row.predicted_label,
    qualityLevel: row.quality_level,
    groupId: row.group_id,
    difficultyLevel: row.difficulty_level,
    strategyChain: row.strategy_chain,
  }
}

function toValueAttributionFixItem(row: AttributionRow): InputFixItem {
  const draft = row.suggestion || ''
  const tip = row.action || ''
  return {
    id: `value-attr-fix-${row.id}`,
    sampleId: row.id,
    title: `${row.id} 价值待提升修正`,
    status: '待处理',
    original: row.snippet,
    suggest: draft,
    recommended: draft,
    action: tip,
    note: row.note || (tip ? '' : ''),
    evidenceChain: row.evidence_chain,
    attributionSteps: (row.attribution_steps || []).map((step) => ({
      title: step.title,
      detail: step.detail,
    })),
    contractStatus: 'topic1_value_high_reference',
    issueSpans: row.issue_spans?.map((issue) => ({
      type: issue.type,
      sentence: issue.sentence,
      span: issue.span,
    })),
  }
}

function toRiskAttributionFixItem(row: AttributionRow): InputFixItem {
  const action = row.action || row.suggestion
  const disposition = row.suggestion || action
  const method = row.detect_method || ''
  const title =
    method === 'activation_probe' ? `${row.id} neuron 归因复核` : `${row.id} 风险归因复核`
  return {
    id: `risk-attr-fix-${row.id}`,
    sampleId: row.id,
    title,
    status: '待处理',
    original: row.snippet,
    suggest: disposition,
    recommended: disposition,
    evidenceChain: row.evidence_chain,
    attributionSteps: (row.attribution_steps || []).map((step) => ({
      title: step.title,
      detail: step.detail,
    })),
    lineageNodeLabel: row.lineage_node_label,
    contractStatus: 'pending_topic2_contract',
    riskCategoryL1: row.risk_category_l1,
    riskCategoryL2: row.risk_category_l2,
    predictedL1Id: row.predicted_l1_id,
    detectMethod: method,
    action,
    note: row.note || '课题二未提供安全改写正文',
  }
}
