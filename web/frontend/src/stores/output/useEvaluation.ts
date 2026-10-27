import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import {
  fetchOutputDatasets,
  fetchRiskTaxonomies,
  startEvalTask,
  getEvalTaskStatus,
  getEvalResultSummary,
  fetchBenchmarkResults,
  fetchBenchmarkPredictions,
  fetchTopic3RiskSameVersion,
  type EvalTaskStatusData,
  type RiskTaxonomyData,
  type StaticEvalMeta,
  type Topic3RiskSameVersion,
} from '@/api/output'
import type {
  RadarChartData,
  MultiDatasetRadarData,
  DatasetEvalMetric,
  GroupedMetrics,
  EvalSample,
  Dataset,
  RiskDimension,
  SelectedDataset,
} from '@/types'
import { OutputTrack, RiskLevel, type DataSource } from '@/types'

export interface UseEvaluationDeps {
  selectedDatasets: Ref<SelectedDataset[]>
  riskDimensions: Ref<RiskDimension[]>
  setAvailableDatasets: (datasets: Dataset[]) => void
  initAllCategoryFilters: () => void
  setRiskDimensions: (dimensions: RiskDimension[]) => void
  updateRiskThresholds: (thresholds: { high: number; medium: number; low: number }) => void
}

export function useEvaluation(deps: UseEvaluationDeps) {
  // ============================================================
  // Step 3: 评估
  // ============================================================

  const evalDiversitySamples = ref<EvalSample[]>([])
  const evalRiskSamples = ref<EvalSample[]>([])
  const radarDiversityData = ref<RadarChartData | null>(null)
  const radarRiskData = ref<RadarChartData | null>(null)
  const radarMultiDatasetData = ref<MultiDatasetRadarData | null>(null)
  const datasetEvalMetrics = ref<DatasetEvalMetric[]>([])
  const groupedMetrics = ref<GroupedMetrics | null>(null)
  const selectedRadarMetric = ref('f1')
  const selectedRadarCodes = ref<Set<string>>(new Set())
  const isEvalRunning = ref(false)

  const datasetsSource = ref<DataSource>('')
  const taxonomySource = ref<DataSource>('')
  const datasetsErrorReason = ref('')
  const taxonomyErrorReason = ref('')
  const taxonomyMeta = ref({
    name: '',
    version: '',
    sourceRepo: '',
  })

  const currentEvalTaskId = ref<string | null>(null)
  const evalJobStatus = ref<'idle' | 'pending' | 'running' | 'finished' | 'error'>('idle')
  const evalJobSource = ref<'benchmark' | 'unavailable' | 'error' | ''>('')
  const evalJobLogs = ref<string[]>([])
  const evalJobProgress = ref(0)
  const evalJobStage = ref('')

  const availableStaticDatasets = ref<StaticEvalMeta[]>([])
  const selectedStaticTask = ref('')
  const selectedStaticDatasetId = ref('')
  const selectedStaticModelId = ref('')
  const staticLoading = ref(false)
  const staticResultSource = ref<DataSource>('')
  const staticPredictionsSource = ref<DataSource>('')
  const staticErrorReason = ref('')
  const staticRawMetrics = ref<Record<string, number | null> | null>(null)
  const staticResultMeta = ref<Record<string, string> | null>(null)
  const staticLevelCounts = ref<{ safe: number; high: number; medium: number; low: number } | null>(
    null,
  )
  const staticPerCategory = ref<Record<string, Record<string, number>> | null>(null)
  const staticGroupedMetrics = ref<Record<string, Record<string, Record<string, number>>> | null>(
    null,
  )
  const staticPredictions = ref<Record<string, unknown>[]>([])
  const topic3RiskView = ref<Topic3RiskSameVersion | null>(null)
  const topic3RiskLoading = ref(false)
  const topic3RiskError = ref('')
  let topic3LoadToken = 0

  let taxonomyReady = false
  let evalPollTimer: ReturnType<typeof setInterval> | null = null

  // === 竞态防护：请求版本控制 ===
  let staticLoadToken = 0 // 递增请求序号
  let staticLoadAbortController: AbortController | null = null // 取消旧请求

  // ============================================================
  // Computed
  // ============================================================

  const correctSampleCount = computed(
    () => evalRiskSamples.value.filter((s) => s.isCorrect !== false).length,
  )

  const errorSampleCount = computed(
    () => evalRiskSamples.value.filter((s) => s.isCorrect === false).length,
  )

  const aggregatedMetrics = computed(() => {
    const metrics = datasetEvalMetrics.value
    if (metrics.length === 0) {
      return { accuracy: 0, precision: 0, recall: 0, f1: 0, riskClassAcc: 0, riskRecall: 0 }
    }
    const totalSamples = metrics.reduce((s, m) => s + m.sampleCount, 0)
    if (totalSamples === 0)
      return { accuracy: 0, precision: 0, recall: 0, f1: 0, riskClassAcc: 0, riskRecall: 0 }
    const weighted = (key: keyof DatasetEvalMetric) =>
      metrics.reduce((s, m) => s + (m[key] as number) * m.sampleCount, 0) / totalSamples
    return {
      accuracy: weighted('accuracy'),
      precision: weighted('precision'),
      recall: weighted('recall'),
      f1: weighted('f1'),
      riskClassAcc: weighted('riskClassAcc'),
      riskRecall: weighted('riskRecall'),
    }
  })

  // ============================================================
  // Actions
  // ============================================================

  function setEvalRunning(running: boolean) {
    isEvalRunning.value = running
  }

  async function startEvalJob() {
    const riskDatasets = deps.selectedDatasets.value.filter(
      (dataset) => dataset.track === OutputTrack.RISK,
    )
    const selectedDimensions = deps.riskDimensions.value.filter((d) => d.selected).map((d) => d.key)
    if (riskDatasets.length === 0) return
    if (selectedDimensions.length === 0) {
      evalJobStatus.value = 'error'
      evalJobLogs.value = ['[ERROR] 未选择风险标准类别，请先在“标准体系筛选（风险）”中勾选至少一项']
      return
    }
    if (riskDatasets.length > 1) {
      console.warn(
        '[OutputStore] 当前仅支持单数据集评测，将使用第一个数据集 (%s)，其余 %d 个数据集暂不参与执行',
        riskDatasets[0].name,
        riskDatasets.length - 1,
      )
    }
    try {
      evalJobStatus.value = 'pending'
      evalJobLogs.value = ['正在创建评测任务...']
      evalJobProgress.value = 0

      const result = (await startEvalTask({
        dataset_ids: riskDatasets.map((d) => d.datasetId),
        selected_dimensions: selectedDimensions,
        sampling_config: riskDatasets.map((d) => ({
          dataset_id: d.datasetId,
          sampling_method: d.samplingMethod,
          sample_size: d.sampleSize,
        })),
      })) as unknown as { task_id: string; status: string }

      currentEvalTaskId.value = result.task_id
      evalJobStatus.value = 'running'
      evalJobLogs.value.push(`任务已创建: ${result.task_id}`)
      startPolling()
    } catch {
      evalJobStatus.value = 'error'
      stopPolling()
      evalJobLogs.value = ['[ERROR] 评测任务创建失败，请检查后端服务是否启动']
    }
  }

  function startPolling() {
    stopPolling()
    let pollFailCount = 0
    const MAX_POLL_FAILURES = 3
    evalPollTimer = setInterval(async () => {
      if (!currentEvalTaskId.value) {
        stopPolling()
        return
      }
      try {
        const status = (await getEvalTaskStatus(
          currentEvalTaskId.value,
        )) as unknown as EvalTaskStatusData
        evalJobProgress.value = status.progress
        evalJobStage.value = status.stage_label
        if (status.logs && status.logs.length > 0) {
          evalJobLogs.value = status.logs.map((l) => `[${l.level}] ${l.message}`)
        }
        if (status.status === 'finished' || status.status === 'error') {
          evalJobStatus.value = status.status
          evalJobSource.value = (status.source || '') as 'benchmark' | 'unavailable' | 'error' | ''
          stopPolling()
          if (status.status === 'finished') {
            await loadEvalResults(currentEvalTaskId.value)
          }
        }
      } catch {
        pollFailCount++
        evalJobLogs.value.push(`[WARN] 轮询失败 (${pollFailCount}/${MAX_POLL_FAILURES})`)
        if (pollFailCount >= MAX_POLL_FAILURES) {
          evalJobStatus.value = 'error'
          evalJobLogs.value.push('[ERROR] 评测服务连接中断，请检查后重试')
          stopPolling()
        }
      }
    }, 3000)
  }

  function stopPolling() {
    if (evalPollTimer !== null) {
      clearInterval(evalPollTimer)
      evalPollTimer = null
    }
  }

  async function loadEvalResults(taskId: string) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const summary = (await getEvalResultSummary(taskId)) as any
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      evalRiskSamples.value = summary.samples.map((s: any) => ({
        id: s.id,
        text: s.text,
        dimensionScores: s.dimension_scores,
        overallLevel: s.overall_level as 'HIGH' | 'MEDIUM' | 'LOW',
        overallScore: s.overall_score as number,
        summary: s.summary as string,
        datasetId: s.dataset_id as string,
        datasetName: s.dataset_name as string,
        goldBinaryLabel: s.gold_binary_label as string,
        predBinaryLabel: s.pred_binary_label as string,
        goldCategory: s.gold_category as string,
        goldCategoryCode: s.gold_category_code as string,
        predCategory: s.pred_category as string,
        predCategoryCode: s.pred_category_code as string,
        goldLevel: s.gold_level as string,
        predLevel: s.pred_level as string,
        isCorrect: s.is_correct as boolean,
        isCategoryCorrect: s.is_category_correct as boolean,
      }))
      if (summary.radar_risk_data) {
        radarRiskData.value = summary.radar_risk_data as unknown as RadarChartData
      }
      if (summary.radar_multi_dataset) {
        radarMultiDatasetData.value =
          summary.radar_multi_dataset as unknown as MultiDatasetRadarData
      }
      if (summary.dataset_metrics) {
        datasetEvalMetrics.value = summary.dataset_metrics as DatasetEvalMetric[]
      }
      if (summary.grouped_metrics) {
        groupedMetrics.value = summary.grouped_metrics as GroupedMetrics
      }
    } catch {
      evalJobLogs.value.push('[ERROR] 结果加载失败，未生成 Mock 结果')
    }
  }

  function toggleRadarCode(code: string) {
    const next = new Set(selectedRadarCodes.value)
    if (next.has(code)) {
      next.delete(code)
    } else {
      next.add(code)
    }
    selectedRadarCodes.value = next
  }

  function initRadarCodes() {
    const codes = deps.riskDimensions.value.filter((d) => d.selected).map((d) => d.key)
    selectedRadarCodes.value = new Set(codes)
  }

  function resetEvalJob() {
    stopPolling()
    currentEvalTaskId.value = null
    evalJobStatus.value = 'idle'
    evalJobSource.value = ''
    evalJobLogs.value = []
    evalJobProgress.value = 0
    evalJobStage.value = ''
  }

  async function loadOutputDatasets() {
    datasetsSource.value = ''
    try {
      const data = (await fetchOutputDatasets()) as unknown as Dataset[]
      if (data && data.length > 0) {
        deps.setAvailableDatasets(data)
        deps.initAllCategoryFilters()
        datasetsSource.value = 'benchmark'
      } else {
        datasetsSource.value = 'error'
        datasetsErrorReason.value =
          '后端 API 已连通，但未返回数据集（Benchmark 服务可能不可达或未配置测试数据）'
      }
    } catch {
      datasetsSource.value = 'error'
      datasetsErrorReason.value = '后端 API 请求失败，无法连接 Benchmark 服务'
    }
  }

  function metricRecord(source: Record<string, number | null>): Record<string, number | null> {
    const raw: Record<string, number | null> = {}
    for (const [key, val] of Object.entries(source)) {
      raw[key] = typeof val === 'number' && !Number.isNaN(val) ? val : null
    }
    return raw
  }

  async function loadTopic3RiskSameVersion(assetVersion = '', assetId = '') {
    const myToken = ++topic3LoadToken
    topic3RiskLoading.value = true
    topic3RiskError.value = ''
    staticLoading.value = true
    staticErrorReason.value = ''
    try {
      const data = await fetchTopic3RiskSameVersion({
        ...(assetVersion ? { assetVersion } : {}),
        ...(assetId ? { assetId } : {}),
      })
      if (myToken !== topic3LoadToken) return
      topic3RiskView.value = data
      const raw = metricRecord({
        ...data.result_display.primary_metrics,
        ...data.result_display.supporting_metrics,
      })
      if (typeof data.sample_count === 'number' && raw.num_examples == null) {
        raw.num_examples = data.sample_count
      }
      const task = data.result_display.task ?? ''
      staticRawMetrics.value = raw
      staticResultSource.value = 'benchmark'
      staticResultMeta.value = {
        asset_id: data.asset_id,
        asset_version: data.asset_version ?? '',
        asset_sha256: data.asset_sha256,
        run_name: data.result_display.run_id ?? '',
        task,
        dataset_id: data.asset_id,
        model_id: data.result_display.model_id ?? '',
        model_name: data.result_display.model_id ?? '',
        created_at: '',
        result_version: data.asset_version ?? '',
      }
      selectedStaticDatasetId.value = data.asset_id
      selectedStaticModelId.value = data.result_display.model_id ?? ''
      selectedStaticTask.value = task
      const predictionsBySample = new Map(
        (data.predictions ?? []).map((row) => [row.sample_id, row]),
      )
      staticPredictionsSource.value = data.sample_details.length ? 'benchmark' : 'unavailable'
      staticPredictions.value = data.sample_details.map((sample) => {
        const prediction = predictionsBySample.get(sample.sample_id)
        return {
          index: sample.sample_id,
          sample_id: sample.sample_id,
          example: { prompt: sample.prompt, response: sample.response },
          response: sample.response,
          risk_category: sample.risk_category,
          prediction_missing: !prediction,
          pred_categories: prediction ? prediction.pred_categories : null,
          gold_level: sample.risk_level_id,
          risk_level_id: sample.risk_level_id,
        }
      })
      staticErrorReason.value = data.result_display.available ? '' : '当前评测对象还没有同版本结果'
    } catch (error) {
      if (myToken !== topic3LoadToken) return
      topic3RiskView.value = null
      staticRawMetrics.value = null
      staticPredictions.value = []
      staticResultSource.value = 'unavailable'
      staticPredictionsSource.value = 'unavailable'
      topic3RiskError.value =
        error instanceof Error ? error.message : '课题三风险同版本结果不可用'
      staticErrorReason.value = topic3RiskError.value
    } finally {
      if (myToken === topic3LoadToken) {
        topic3RiskLoading.value = false
        staticLoading.value = false
      }
    }
  }

  async function loadStaticOptions() {
    try {
      const data = await fetchBenchmarkResults('', '', '')
      const seen = new Set<string>()
      availableStaticDatasets.value = data.results.filter((r: StaticEvalMeta) => {
        const key = `${r.task}|${r.dataset_id}|${r.model_id}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    } catch {
      availableStaticDatasets.value = []
    }
  }

  async function loadStaticResults(datasetId: string, modelId = '', task = '') {
    if (!datasetId) return

    // === 竞态防护：取消旧请求，分配新 token ===
    if (staticLoadAbortController) {
      staticLoadAbortController.abort()
    }
    const myToken = ++staticLoadToken
    staticLoadAbortController = new AbortController()
    const signal = staticLoadAbortController.signal

    // 更新当前选择的数据集 ID（供 UI 显示）
    selectedStaticDatasetId.value = datasetId
    selectedStaticModelId.value = modelId
    selectedStaticTask.value = task

    staticLoading.value = true
    staticResultSource.value = ''
    staticPredictionsSource.value = ''
    staticErrorReason.value = ''
    // 清空旧状态（避免显示混合数据）
    staticRawMetrics.value = null
    staticResultMeta.value = null
    staticLevelCounts.value = null
    staticPerCategory.value = null
    staticGroupedMetrics.value = null
    staticPredictions.value = []
    datasetEvalMetrics.value = []

    try {
      // 通过后端代理获取静态评测结果（传递 signal 以支持取消）
      const data = await fetchBenchmarkResults(datasetId, modelId, task, signal)

      // === 写入前验证：token 是否仍是最新的 ===
      if (myToken !== staticLoadToken) {
        // 过期响应，丢弃
        console.log(
          `[loadStaticResults] Token ${myToken} 已过期（当前 ${staticLoadToken}），丢弃响应`,
        )
        return
      }

      if (data.selected?.metrics) {
        staticResultSource.value = (data.source as DataSource) || 'benchmark_static'
        const m = data.selected.metrics
        const raw: Record<string, number | null> = {}
        for (const [key, val] of Object.entries(m as unknown as Record<string, unknown>)) {
          if (typeof val === 'number' && !Number.isNaN(val)) {
            raw[key] = val
          }
        }
        staticRawMetrics.value = raw
        staticResultMeta.value = {
          run_name: String(data.selected.run_name ?? ''),
          task: String(data.selected.task ?? task),
          dataset_id: String(data.selected.dataset_id ?? datasetId),
          model_id: String(data.selected.model_id ?? modelId),
          model_name: String(data.selected.model_name ?? ''),
          created_at: String(data.selected.created_at ?? ''),
          result_version: String(data.selected.result_version ?? ''),
        }
        const perCat =
          (m as unknown as Record<string, unknown>).risk_class_per_category ??
          m.per_category_metrics ??
          ((m as unknown as Record<string, unknown>).grouped_metrics as Record<string, unknown>)
            ?.risk_category_code
        staticPerCategory.value = (perCat as Record<string, Record<string, number>>) ?? null

        const gmRaw = (m as unknown as Record<string, unknown>).grouped_metrics as
          | Record<string, Record<string, Record<string, number>>>
          | undefined
        staticGroupedMetrics.value = gmRaw ?? null

        datasetEvalMetrics.value = []

        const gm = (m as unknown as Record<string, unknown>).grouped_metrics as
          | { risk_level_id?: Record<string, { num_examples?: number }> }
          | undefined
        const rlid = gm?.risk_level_id
        if (rlid) {
          staticLevelCounts.value = {
            safe: (rlid.safe?.['num_examples'] ?? rlid.SAFE?.['num_examples']) || 0,
            high:
              (rlid.high?.['num_examples'] ??
                rlid.HIGH?.['num_examples'] ??
                rlid.level_3?.['num_examples']) ||
              0,
            medium:
              (rlid.medium?.['num_examples'] ??
                rlid.MEDIUM?.['num_examples'] ??
                rlid.level_2?.['num_examples']) ||
              0,
            low:
              (rlid.low?.['num_examples'] ??
                rlid.LOW?.['num_examples'] ??
                rlid.level_1?.['num_examples']) ||
              0,
          }
        } else {
          const total = (m.num_examples as number) || 0
          const unsafe =
            (m.risk_class_detected as number) ??
            (m.risk_class_total as number) ??
            (m.risk_total as number) ??
            0
          const safeCount = Math.max(0, total - unsafe)
          staticLevelCounts.value = { safe: safeCount, high: unsafe, medium: 0, low: 0 }
        }

        if (!taxonomyReady && perCat) {
          deps.setRiskDimensions(
            Object.entries(perCat as Record<string, unknown>).map(([name, cat]) => ({
              key: name,
              code: name,
              label: name,
              category: 'ai4sci' as const,
              level:
                ((cat as Record<string, number>).acc ?? 0) > 0.6
                  ? RiskLevel.HIGH
                  : ((cat as Record<string, number>).acc ?? 0) > 0.4
                    ? RiskLevel.MEDIUM
                    : RiskLevel.LOW,
              selected: true,
            })),
          )
        }
      } else {
        staticRawMetrics.value = null
        staticResultSource.value = 'unavailable'
        staticErrorReason.value = 'Benchmark 静态结果接口未返回 selected.metrics'
      }

      // === 继续加载预测样本（共享同一个 token）===
      await loadStaticPredictions(datasetId, modelId, task, myToken, signal)
    } catch (err) {
      // AbortError 不需要处理（被取消的请求）
      if (err instanceof Error && err.name === 'AbortError') {
        console.log(`[loadStaticResults] Token ${myToken} 请求被取消`)
        return
      }
      // 其他错误：仅在 token 仍是最新时写入错误状态
      if (myToken === staticLoadToken) {
        staticRawMetrics.value = null
        staticResultSource.value = 'unavailable'
        staticErrorReason.value = 'Benchmark 静态结果不可达或请求失败'
      }
    } finally {
      // === 只有最新请求才能关闭 loading ===
      if (myToken === staticLoadToken) {
        staticLoading.value = false
        staticLoadAbortController = null
      }
    }
  }

  async function loadStaticPredictions(
    datasetId: string,
    modelId = '',
    task = '',
    token?: number,
    signal?: AbortSignal,
  ) {
    // 内部调用（无 token）时，直接清空并加载（用于独立调用场景）
    const myToken = token ?? ++staticLoadToken

    staticPredictions.value = []
    try {
      const data = (await fetchBenchmarkPredictions(
        datasetId,
        modelId,
        task,
        3000,
        signal,
      )) as unknown as {
        source?: string
        rows?: Record<string, unknown>[]
      }

      // === 写入前验证：token 是否仍是最新的 ===
      if (myToken !== staticLoadToken) {
        console.log(
          `[loadStaticPredictions] Token ${myToken} 已过期（当前 ${staticLoadToken}），丢弃响应`,
        )
        return
      }

      staticPredictions.value = data?.rows || []
      staticPredictionsSource.value = (data?.source as DataSource) || 'benchmark_static'
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log(`[loadStaticPredictions] Token ${myToken} 请求被取消`)
        return
      }
      if (myToken === staticLoadToken) {
        staticPredictions.value = []
        staticPredictionsSource.value = 'unavailable'
      }
    }
  }

  async function loadTaxonomyDimensions() {
    taxonomySource.value = ''
    try {
      const data = (await fetchRiskTaxonomies()) as unknown as RiskTaxonomyData
      const categories = data?.categories
      if (categories && categories.length > 0) {
        taxonomyMeta.value = {
          name: data.taxonomy_name || '',
          version: data.version || '',
          sourceRepo: data.source_repo || '',
        }
        deps.setRiskDimensions(
          categories.map((cat) => ({
            key: cat.key,
            code: cat.key,
            label: cat.label,
            category: cat.category,
            level: cat.level as string as RiskLevel,
            selected: false,
            definition: cat.definition,
            subcategories: cat.subcategories,
          })),
        )
        if (data.threshold_defaults) {
          deps.updateRiskThresholds({
            high: data.threshold_defaults.high,
            medium: data.threshold_defaults.medium,
            low: data.threshold_defaults.low,
          })
        }
        taxonomySource.value = (data.source as DataSource) || 'real'
        taxonomyReady = true
      } else {
        taxonomySource.value = 'error'
        taxonomyErrorReason.value =
          '后端 API 已连通，但标准体系分类数据为空（Benchmark 数据库中未录入分类维度）'
        taxonomyReady = true
      }
    } catch {
      taxonomySource.value = 'error'
      taxonomyErrorReason.value = '后端 API 请求失败，无法连接 Benchmark 服务'
      taxonomyReady = true
    }
  }

  return {
    evalDiversitySamples,
    evalRiskSamples,
    radarDiversityData,
    radarRiskData,
    radarMultiDatasetData,
    datasetEvalMetrics,
    groupedMetrics,
    selectedRadarMetric,
    selectedRadarCodes,
    isEvalRunning,
    setEvalRunning,
    datasetsSource,
    taxonomySource,
    taxonomyMeta,
    datasetsErrorReason,
    taxonomyErrorReason,
    currentEvalTaskId,
    evalJobStatus,
    evalJobSource,
    evalJobLogs,
    evalJobProgress,
    evalJobStage,
    availableStaticDatasets,
    selectedStaticTask,
    selectedStaticDatasetId,
    selectedStaticModelId,
    staticLoading,
    staticResultSource,
    staticPredictionsSource,
    staticErrorReason,
    staticRawMetrics,
    staticResultMeta,
    staticLevelCounts,
    staticPerCategory,
    staticGroupedMetrics,
    staticPredictions,
    topic3RiskView,
    topic3RiskLoading,
    topic3RiskError,
    loadTopic3RiskSameVersion,
    loadStaticPredictions,
    correctSampleCount,
    errorSampleCount,
    aggregatedMetrics,
    startEvalJob,
    resetEvalJob,
    loadEvalResults,
    loadOutputDatasets,
    loadTaxonomyDimensions,
    loadStaticOptions,
    loadStaticResults,
    stopPolling,
    toggleRadarCode,
    initRadarCodes,
  }
}
