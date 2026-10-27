import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useNavigation } from './output/useNavigation'
import { useInference } from './output/useInference'
import { useStrategy } from './output/useStrategy'
import { useAttribution } from './output/useAttribution'
import { useEvaluation } from './output/useEvaluation'
import type { UseEvaluationDeps } from './output/useEvaluation'
import { useCorrection } from './output/useCorrection'
import type {
  SelectedDataset,
  DiversityDimension,
  RiskDimension,
  CustomRule,
  Dataset,
  AttributionNode,
  EvalSample,
  RadarChartData,
} from '@/types'
import type { DataAsset, AssetState } from '@/types'
import {
  allStaticAssets,
  staticEvaluableDatasets as allStaticEvaluable,
} from '@/utils/outputAssetData'
import { OutputTrack, SamplingMethod, RiskLevel, DiversityLevel, type DataSource } from '@/types'
import {
  mockDiversityDimensions,
  mockDiversityAttributionNodes,
  mockCorrectionSamples,
} from '@/utils/output-mock'
import {
  fetchCultureCorpusGenerationJob,
  fetchCultureCorpusGenerationSamples,
  fetchCultureAssessmentDatasets,
  fetchCultureAssessmentStaticView,
  fetchCultureAssessmentStaticViews,
  fetchCultureCorpusSamples,
  fetchCultureSamples,
  startCultureCorpusGenerationJob,
  stopCultureCorpusGenerationJob,
  type CultureAssessmentDatasetDTO,
  type CultureAssessmentStaticViewDTO,
  type CultureCorpusGenerationRequest,
  type CultureCorpusGenerationStatus,
  type CultureCorpusSamplesQuery,
  type CultureSampleDTO,
} from '@/api/output'

export interface CultureCorpusRunSummary {
  runId: string
  count: number
  source: 'live' | 'static'
  ethnicCounts: Record<string, number>
  difficultyCounts: Record<string, number>
  previewSamples: CultureSampleDTO[]
}

export const useOutputStore = defineStore('output', () => {
  // ============================================================
  // 向导导航状态
  // ============================================================

  const nav = useNavigation()

  // ============================================================
  // Step 1: 数据集选择
  // ============================================================

  const availableDatasets = ref<Dataset[]>([])
  const staticAssets = ref<DataAsset[]>([])
  const expandedAssetId = ref<string | null>(null)

  const selectedDatasets = ref<SelectedDataset[]>([])
  const dsSearchQuery = ref('')
  const checkedDatasetIds = ref<string[]>([])
  const dsCategoryFilters = ref<Record<string, boolean>>({})
  const cultureCorpusJob = ref<CultureCorpusGenerationStatus | null>(null)
  const cultureCorpusJobLoading = ref(false)
  const cultureCorpusJobError = ref('')
  const cultureCorpusJobSamples = ref<CultureSampleDTO[]>([])
  const cultureCorpusStaticOptions = ref({
    runIds: [] as string[],
    ethnicGroups: [] as string[],
    difficultyLevels: [] as string[],
  })
  const cultureCorpusStaticOptionsLoading = ref(false)
  const cultureCorpusStaticOptionsError = ref('')
  const cultureCorpusRunSummaries = ref<CultureCorpusRunSummary[]>([])
  const cultureCorpusRunHistoryLoading = ref(false)
  const cultureCorpusRunHistoryError = ref('')
  const cultureAssessmentDatasets = ref<CultureAssessmentDatasetDTO[]>([])
  const cultureAssessmentDatasetsLoading = ref(false)
  const cultureAssessmentDatasetsError = ref('')
  const cultureAssessmentStaticViews = ref<
    Array<{
      id: string
      title: string
      dataset_id: string
      dataset_label: string
      highlights?: string[]
      advantage_summary?: string
    }>
  >([])
  const cultureAssessmentStaticView = ref<CultureAssessmentStaticViewDTO | null>(null)
  const cultureAssessmentStaticLoading = ref(false)
  const cultureAssessmentStaticError = ref('')
  let cultureCorpusPollTimer: ReturnType<typeof setInterval> | null = null

  const filteredDatasets = computed(() => {
    let list = availableDatasets.value
    const q = dsSearchQuery.value.toLowerCase()
    if (q) {
      list = list.filter(
        (ds) =>
          ds.name.toLowerCase().includes(q) || (ds.subType && ds.subType.toLowerCase().includes(q)),
      )
    }
    const activeFilters = Object.entries(dsCategoryFilters.value)
      .filter(([, v]) => !v)
      .map(([k]) => k)
    if (activeFilters.length > 0) {
      list = list.filter((ds) => !activeFilters.includes(ds.subType ?? ''))
    }
    return list
  })

  // ============================================================
  // Step 2: 维度筛选
  // ============================================================

  const diversityDimensions = ref<DiversityDimension[]>([])
  const riskDimensions = ref<RiskDimension[]>([])
  const customDiversityRules = ref<CustomRule[]>([])
  const customRiskRules = ref<CustomRule[]>([])
  const diversityThresholds = ref({ excellent: 0.75, good: 0.45 })
  const riskThresholds = ref({ high: 0.7, medium: 0.4, low: 0.2 })

  const selectedDiversityDimensions = computed(() =>
    diversityDimensions.value.filter((d) => d.selected),
  )
  const selectedRiskDimensions = computed(() => riskDimensions.value.filter((d) => d.selected))

  // ============================================================
  // Step 3: 评估 + 单样本推理
  // ============================================================

  const infer = useInference()

  const evaluationDeps: UseEvaluationDeps = {
    selectedDatasets,
    riskDimensions,
    setAvailableDatasets,
    initAllCategoryFilters,
    setRiskDimensions,
    updateRiskThresholds: (t) => {
      riskThresholds.value = t
    },
  }
  const evaluation = useEvaluation(evaluationDeps)
  const hiddenOutputDatasetIds = new Set([
    'seed_v4_multilabel',
    'seed_v3_multilabel',
    'seed_v2_multilabel',
    'seed_v1_1_response_en',
    'binary_response_hist',
    'infer_examples',
    'safety_bingo',
    'safety_bingo_testset',
    'safety_bingo_ti',
    'project3_culture_db',
    'project3_cultural_corpus_runs',
    'culture_assessment_cultural_evaluation_ui_batch_30',
  ])

  const allAssets = computed<DataAsset[]>(() => {
    const apiOnly = availableDatasets.value.filter(
      (ds) => !allStaticEvaluable.some((a) => a.datasetId === ds.id),
    )
    const apiMapped: DataAsset[] = apiOnly.map((ds) => ({
      id: ds.id,
      name: ds.name,
      assetState: 'evaluable' as AssetState,
      scenario: ds.type === 'science' ? 'AI for Science' : '文化多样性内容',
      source: 'Benchmark',
      track: OutputTrack.RISK,
      description: ds.description,
      datasetId: ds.id,
      sampleCount: ds.recordCount,
      language: ds.language,
    }))
    const sourceOk =
      evaluation.datasetsSource.value === 'benchmark' || evaluation.datasetsSource.value === 'api'
    const evaluable = sourceOk ? allStaticEvaluable : []
    const cultureCorpusTotal = cultureCorpusRunSummaries.value.reduce(
      (sum, run) => sum + run.count,
      0,
    )
    const normalizedStaticAssets = staticAssets.value.map((asset) =>
      asset.id === 'project3_cultural_corpus_runs' && cultureCorpusTotal > 0
        ? { ...asset, sampleCount: cultureCorpusTotal }
        : asset,
    )
    const assessmentAssets: DataAsset[] = cultureAssessmentDatasets.value.map((dataset) => ({
      id: `culture_assessment_${dataset.id}`,
      name:
        dataset.id === 'framework_cultural_diversity_evaluation_dataset_v1'
          ? 'Cultural Diversity Evaluation Dataset V1(500)'
          : dataset.label,
      assetState: 'mapped' as AssetState,
      scenario: '文化多样性内容',
      source: 'Project3:Cultural_Diversity_Assessment_Tool',
      track: OutputTrack.DIVERSITY,
      selectable: dataset.exists,
      description: `${dataset.description} 用于文化多样性 Benchmark 评测，包含民族识别、文化差异度和综合通过率指标。`,
      datasetId: dataset.id,
      sampleCount: dataset.sample_count,
      language: '中文 · 回族/维吾尔族/蒙古族/藏族',
      hasStaticResult:
        dataset.id === 'cultural_evaluation_ui_batch_30' ||
        dataset.id === 'framework_cultural_diversity_evaluation_dataset_v1',
      canDynamicEval: true,
      resultVersion: 'culture-assessment-static',
      runName:
        dataset.id === 'cultural_evaluation_ui_batch_30'
          ? 'ui_batch_30_direct_vs_agent'
          : dataset.id === 'framework_cultural_diversity_evaluation_dataset_v1'
            ? 'cultural_diversity_evaluation_dataset_v1'
            : '',
      existingFields: [
        'background',
        'user_query',
        'implied_ethnic_group',
        'difficulty_level',
        'expected_answer',
        'scoring_rubric',
        'review_result',
      ],
      detailBlocks: [
        {
          title: '评测口径',
          tags: ['民族识别', '文化差异度', '综合通过率', '抽象化替换测试', 'L1/L2/L3'],
        },
        {
          title: '样本预览',
          kv: [
            ['样本 ID', dataset.preview_sample_id || '—'],
            ['民族', dataset.preview_ethnic_group || '—'],
            ['难度', dataset.preview_difficulty_level || '—'],
          ],
        },
      ],
    }))
    return [...evaluable, ...apiMapped, ...normalizedStaticAssets, ...assessmentAssets].filter(
      (asset) =>
        !hiddenOutputDatasetIds.has(asset.id) &&
        (!asset.datasetId || !hiddenOutputDatasetIds.has(asset.datasetId)),
    )
  })

  // ============================================================
  // Step 4: 归因
  // ============================================================

  const attr = useAttribution()

  // ============================================================
  // Step 5: 修正
  // ============================================================

  const correction = useCorrection()

  // ============================================================
  // 备用：策略建议字段保留给后续真实接口，不在主流程注入 mock
  // ============================================================

  const strat = useStrategy()

  // ============================================================
  // 导航 Actions
  // ============================================================

  function setCurrentStep(step: number) {
    nav.currentStep.value = step
  }

  function setCurrentTrack(track: OutputTrack | null) {
    nav.currentTrack.value = track
  }

  function goToStep(step: number, track?: OutputTrack) {
    if (step < 1 || step > 5) return
    if (step >= 2 && step <= 5) {
      nav.currentTrack.value = track ?? nav.currentTrack.value ?? OutputTrack.DIVERSITY
    } else {
      nav.currentTrack.value = null
    }
    nav.currentStep.value = step
  }

  // ============================================================
  // 数据集 Actions
  // ============================================================

  function setAvailableDatasets(datasets: Dataset[]) {
    availableDatasets.value = datasets
  }

  function setDsCategoryFilter(category: string, visible: boolean) {
    dsCategoryFilters.value[category] = visible
  }

  function setDsSearchQuery(query: string) {
    dsSearchQuery.value = query
  }

  function toggleCheckedDataset(id: string) {
    const idx = checkedDatasetIds.value.indexOf(id)
    if (idx === -1) checkedDatasetIds.value.push(id)
    else checkedDatasetIds.value.splice(idx, 1)
  }

  function isDatasetChecked(id: string): boolean {
    return checkedDatasetIds.value.includes(id)
  }

  function clearCheckedDatasets() {
    checkedDatasetIds.value = []
  }

  function addSelectedFromChecked() {
    if (checkedDatasetIds.value.length === 0) return
    for (const id of checkedDatasetIds.value) {
      const ds = availableDatasets.value.find((d) => d.id === id)
      if (ds) {
        addSelectedDataset(ds)
        continue
      }
      const asset = allAssets.value.find((a) => a.datasetId === id || a.id === id)
      if (asset && isAssetSelectable(asset)) {
        addSelectedDataset({
          id: asset.datasetId || asset.id,
          name: asset.name,
          type: asset.track === OutputTrack.DIVERSITY ? 'culture' : 'science',
          description: asset.description,
          recordCount: asset.sampleCount || 0,
          language: asset.language,
          riskLevel: 'MEDIUM',
          createdAt: '',
          updatedAt: '',
        })
      }
    }
    clearCheckedDatasets()
  }

  function toggleDsCategoryFilter(key: string) {
    const current = dsCategoryFilters.value[key] ?? true
    setDsCategoryFilter(key, !current)
  }

  function initAllCategoryFilters() {
    for (const ds of availableDatasets.value) {
      const key = ds.subType ?? ds.type
      if (!(key in dsCategoryFilters.value)) {
        dsCategoryFilters.value[key] = true
      }
    }
  }

  function addSelectedDataset(ds: Dataset) {
    const exists = selectedDatasets.value.find((s) => s.datasetId === ds.id)
    if (exists) return
    const asset = allAssets.value.find((item) => item.datasetId === ds.id || item.id === ds.id)
    const assetTrack = asset?.track
    const isStaticCultureCorpus = asset?.id === 'project3_cultural_corpus_runs'
    const isCultureAssessment = asset?.id.startsWith('culture_assessment_')
    selectedDatasets.value.push({
      datasetId: ds.id,
      name: ds.name,
      recordCount: ds.recordCount,
      riskLevel: ds.riskLevel as RiskLevel,
      subType: ds.subType ?? ds.type,
      language: ds.language ?? '中文',
      track: assetTrack ?? (ds.type === 'culture' ? OutputTrack.DIVERSITY : OutputTrack.RISK),
      dataSource: isStaticCultureCorpus
        ? 'corpus_static'
        : isCultureAssessment
          ? 'culture_assessment_static'
          : asset?.id === 'project3_culture_db'
            ? 'real'
            : asset?.hasStaticResult
              ? 'benchmark_static'
              : undefined,
      resultVersion:
        asset?.id === 'project3_culture_db' ? 'culture_samples_real' : asset?.resultVersion,
      runName:
        asset?.id === 'project3_culture_db' ? 'Project3 Cultural Gen /api/samples' : asset?.runName,
      cultureCorpusFilters: isStaticCultureCorpus
        ? { runIds: [], ethnicGroups: [], difficultyLevels: [] }
        : undefined,
      samplingMethod: SamplingMethod.FULL,
      sampleSize: ds.recordCount,
    })
    if (isStaticCultureCorpus) {
      void loadCultureCorpusStaticOptions()
    }
  }

  function removeSelectedDataset(datasetId: string) {
    selectedDatasets.value = selectedDatasets.value.filter((s) => s.datasetId !== datasetId)
  }

  function updateSamplingMethod(datasetId: string, method: SamplingMethod) {
    const item = selectedDatasets.value.find((s) => s.datasetId === datasetId)
    if (!item) return
    item.samplingMethod = method
    if (method === SamplingMethod.FULL) {
      item.sampleSize = item.recordCount
    }
  }

  function updateSampleSize(datasetId: string, size: number) {
    const item = selectedDatasets.value.find((s) => s.datasetId === datasetId)
    if (!item) return
    item.sampleSize = Math.max(1, Math.min(size, item.recordCount))
  }

  function uniqueSorted(values: Array<string | undefined | null>) {
    return Array.from(new Set(values.filter((value): value is string => !!value))).sort()
  }

  async function loadCultureCorpusStaticOptions(force = false) {
    if (!force && cultureCorpusStaticOptions.value.runIds.length > 0)
      return cultureCorpusStaticOptions.value
    cultureCorpusStaticOptionsLoading.value = true
    cultureCorpusStaticOptionsError.value = ''
    try {
      const data = await fetchCultureCorpusSamples({ include_live_runs: true, limit: 5000 })
      cultureCorpusStaticOptions.value = {
        runIds: uniqueSorted([
          ...Object.keys(data.run_counts || {}),
          ...data.samples.map((sample) => sample.runId),
        ]),
        ethnicGroups: uniqueSorted([
          ...Object.keys(data.ethnic_counts || {}),
          ...data.samples.map((sample) => sample.ethnic),
        ]),
        difficultyLevels: uniqueSorted([
          ...Object.keys(data.difficulty_counts || {}),
          ...data.samples.map((sample) => sample.difficultyLevel),
        ]),
      }
      return cultureCorpusStaticOptions.value
    } catch (error: unknown) {
      cultureCorpusStaticOptionsError.value =
        error instanceof Error ? error.message : '文化语料批次筛选项加载失败'
      return cultureCorpusStaticOptions.value
    } finally {
      cultureCorpusStaticOptionsLoading.value = false
    }
  }

  function buildCultureCorpusRunSummaries(samples: CultureSampleDTO[]): CultureCorpusRunSummary[] {
    const map = new Map<string, CultureCorpusRunSummary>()
    for (const sample of samples) {
      const runId = sample.runId || '未标注批次'
      const current =
        map.get(runId) ||
        ({
          runId,
          count: 0,
          source: runId.startsWith('topic5_') ? 'live' : 'static',
          ethnicCounts: {},
          difficultyCounts: {},
          previewSamples: [],
        } satisfies CultureCorpusRunSummary)
      current.count += 1
      if (sample.ethnic) {
        current.ethnicCounts[sample.ethnic] = (current.ethnicCounts[sample.ethnic] || 0) + 1
      }
      if (sample.difficultyLevel) {
        current.difficultyCounts[sample.difficultyLevel] =
          (current.difficultyCounts[sample.difficultyLevel] || 0) + 1
      }
      if (current.previewSamples.length < 3) {
        current.previewSamples.push(sample)
      }
      map.set(runId, current)
    }
    return Array.from(map.values()).sort((a, b) => b.runId.localeCompare(a.runId))
  }

  async function loadCultureCorpusRunHistory(force = false) {
    if (!force && cultureCorpusRunSummaries.value.length > 0) return cultureCorpusRunSummaries.value
    cultureCorpusRunHistoryLoading.value = true
    cultureCorpusRunHistoryError.value = ''
    try {
      const data = await fetchCultureCorpusSamples({ include_live_runs: true, limit: 5000 })
      cultureCorpusRunSummaries.value = buildCultureCorpusRunSummaries(data.samples || [])
      cultureCorpusStaticOptions.value = {
        runIds: uniqueSorted([
          ...Object.keys(data.run_counts || {}),
          ...data.samples.map((sample) => sample.runId),
        ]),
        ethnicGroups: uniqueSorted([
          ...Object.keys(data.ethnic_counts || {}),
          ...data.samples.map((sample) => sample.ethnic),
        ]),
        difficultyLevels: uniqueSorted([
          ...Object.keys(data.difficulty_counts || {}),
          ...data.samples.map((sample) => sample.difficultyLevel),
        ]),
      }
      return cultureCorpusRunSummaries.value
    } catch (error: unknown) {
      cultureCorpusRunHistoryError.value =
        error instanceof Error ? error.message : '文化语料批次历史加载失败'
      return cultureCorpusRunSummaries.value
    } finally {
      cultureCorpusRunHistoryLoading.value = false
    }
  }

  async function loadCultureAssessmentDatasets(force = false) {
    if (!force && cultureAssessmentDatasets.value.length > 0) return cultureAssessmentDatasets.value
    cultureAssessmentDatasetsLoading.value = true
    cultureAssessmentDatasetsError.value = ''
    try {
      const data = await fetchCultureAssessmentDatasets()
      cultureAssessmentDatasets.value = data.datasets || []
      return cultureAssessmentDatasets.value
    } catch (error: unknown) {
      cultureAssessmentDatasets.value = []
      cultureAssessmentDatasetsError.value =
        error instanceof Error ? error.message : '文化评测 Benchmark 数据集加载失败'
      return cultureAssessmentDatasets.value
    } finally {
      cultureAssessmentDatasetsLoading.value = false
    }
  }

  async function loadCultureAssessmentStaticViews(force = false) {
    if (!force && cultureAssessmentStaticViews.value.length > 0)
      return cultureAssessmentStaticViews.value
    cultureAssessmentStaticLoading.value = true
    cultureAssessmentStaticError.value = ''
    try {
      const data = await fetchCultureAssessmentStaticViews()
      cultureAssessmentStaticViews.value = data.views || []
      return cultureAssessmentStaticViews.value
    } catch (error: unknown) {
      cultureAssessmentStaticViews.value = []
      cultureAssessmentStaticError.value =
        error instanceof Error ? error.message : '文化评测静态视图加载失败'
      return cultureAssessmentStaticViews.value
    } finally {
      cultureAssessmentStaticLoading.value = false
    }
  }

  async function loadCultureAssessmentStaticView(viewId = '') {
    cultureAssessmentStaticLoading.value = true
    cultureAssessmentStaticError.value = ''
    try {
      const views = await loadCultureAssessmentStaticViews()
      const selectedViewId = viewId || views[0]?.id || 'ui_batch_30_direct_vs_agent'
      const data = await fetchCultureAssessmentStaticView(selectedViewId)
      cultureAssessmentStaticView.value = data
      return data
    } catch (error: unknown) {
      cultureAssessmentStaticView.value = null
      cultureAssessmentStaticError.value =
        error instanceof Error ? error.message : '文化评测静态对比结果加载失败'
      return null
    } finally {
      cultureAssessmentStaticLoading.value = false
    }
  }

  function updateCultureCorpusFilters(
    datasetId: string,
    patch: Partial<{ runIds: string[]; ethnicGroups: string[]; difficultyLevels: string[] }>,
  ) {
    const item = selectedDatasets.value.find((s) => s.datasetId === datasetId)
    if (!item || item.dataSource !== 'corpus_static') return
    item.cultureCorpusFilters = {
      runIds: patch.runIds ?? item.cultureCorpusFilters?.runIds ?? [],
      ethnicGroups: patch.ethnicGroups ?? item.cultureCorpusFilters?.ethnicGroups ?? [],
      difficultyLevels: patch.difficultyLevels ?? item.cultureCorpusFilters?.difficultyLevels ?? [],
    }
  }

  function clearCultureCorpusPolling() {
    if (cultureCorpusPollTimer) {
      clearInterval(cultureCorpusPollTimer)
      cultureCorpusPollTimer = null
    }
  }

  async function refreshCultureCorpusGenerationJob(jobId?: string) {
    const id = jobId || cultureCorpusJob.value?.job_id
    if (!id) return null
    const data = await fetchCultureCorpusGenerationJob(id)
    cultureCorpusJob.value = data
    cultureCorpusJobSamples.value = data.samples || []
    if (!data.running) {
      clearCultureCorpusPolling()
    }
    return data
  }

  function startCultureCorpusPolling(jobId: string) {
    clearCultureCorpusPolling()
    cultureCorpusPollTimer = setInterval(() => {
      void refreshCultureCorpusGenerationJob(jobId).catch((error: unknown) => {
        cultureCorpusJobError.value =
          error instanceof Error ? error.message : '文化语料生成任务状态查询失败'
        clearCultureCorpusPolling()
      })
    }, 2000)
  }

  async function startCultureCorpusGeneration(payload: CultureCorpusGenerationRequest) {
    cultureCorpusJobLoading.value = true
    cultureCorpusJobError.value = ''
    try {
      const data = await startCultureCorpusGenerationJob(payload)
      cultureCorpusJob.value = data
      cultureCorpusJobSamples.value = data.samples || []
      if (data.running) {
        startCultureCorpusPolling(data.job_id)
      }
      return data
    } catch (error: unknown) {
      cultureCorpusJobError.value =
        error instanceof Error ? error.message : '文化语料生成任务启动失败'
      throw error
    } finally {
      cultureCorpusJobLoading.value = false
    }
  }

  async function stopCultureCorpusGeneration() {
    const id = cultureCorpusJob.value?.job_id
    if (!id) return null
    cultureCorpusJobLoading.value = true
    cultureCorpusJobError.value = ''
    try {
      const data = await stopCultureCorpusGenerationJob(id)
      cultureCorpusJob.value = data
      cultureCorpusJobSamples.value = data.samples || []
      clearCultureCorpusPolling()
      return data
    } catch (error: unknown) {
      cultureCorpusJobError.value =
        error instanceof Error ? error.message : '文化语料生成任务停止失败'
      throw error
    } finally {
      cultureCorpusJobLoading.value = false
    }
  }

  async function loadCultureCorpusGeneratedSamples() {
    const id = cultureCorpusJob.value?.job_id
    if (!id) return []
    const data = await fetchCultureCorpusGenerationSamples(id, 200)
    cultureCorpusJobSamples.value = data.samples || []
    return cultureCorpusJobSamples.value
  }

  async function syncCultureCorpusGeneratedRun() {
    const job = cultureCorpusJob.value
    if (!job || job.generated <= 0) return false
    await loadCultureCorpusGeneratedSamples()
    await loadCultureCorpusRunHistory(true)
    return true
  }

  // ============================================================
  // 维度筛选 Actions
  // ============================================================

  function setDiversityDimensions(dimensions: DiversityDimension[]) {
    diversityDimensions.value = dimensions
  }

  function setRiskDimensions(dimensions: RiskDimension[]) {
    riskDimensions.value = dimensions
  }

  function toggleDiversityDimension(key: string) {
    const dim = diversityDimensions.value.find((d) => d.key === key)
    if (dim) dim.selected = !dim.selected
  }

  function toggleRiskDimension(key: string) {
    const dim = riskDimensions.value.find((d) => d.key === key)
    if (dim) dim.selected = !dim.selected
  }

  function selectAllDimensions() {
    diversityDimensions.value.forEach((d) => (d.selected = true))
    riskDimensions.value.forEach((d) => (d.selected = true))
  }

  function deselectAllDimensions() {
    diversityDimensions.value.forEach((d) => (d.selected = false))
    riskDimensions.value.forEach((d) => (d.selected = false))
  }

  function selectRecommendedDimensions() {
    riskDimensions.value.forEach((d) => (d.selected = d.level === 'HIGH' || d.level === 'MEDIUM'))
    diversityDimensions.value.forEach((d) => (d.selected = true))
  }

  function selectAllDimensionsForTrack(track: OutputTrack) {
    if (track === OutputTrack.DIVERSITY) {
      diversityDimensions.value.forEach((d) => (d.selected = true))
    } else {
      riskDimensions.value.forEach((d) => (d.selected = true))
    }
  }

  function deselectAllDimensionsForTrack(track: OutputTrack) {
    if (track === OutputTrack.DIVERSITY) {
      diversityDimensions.value.forEach((d) => (d.selected = false))
    } else {
      riskDimensions.value.forEach((d) => (d.selected = false))
    }
  }

  const RECOMMENDED_DIVERSITY_KEYS = new Set([
    'div_open_science',
    'div_method_rigor',
    'div_ethics_positive',
    'div_inclusion',
    'div_representation',
    'div_heritage',
  ])

  function selectRecommendedForTrack(track: OutputTrack) {
    if (track === OutputTrack.DIVERSITY) {
      diversityDimensions.value.forEach((d) => (d.selected = RECOMMENDED_DIVERSITY_KEYS.has(d.key)))
    } else {
      const dims = riskDimensions.value
      dims.forEach((d) => (d.selected = false))
      const count = 4 + Math.floor(Math.random() * 5)
      const indices = new Set<number>()
      while (indices.size < Math.min(count, dims.length)) {
        indices.add(Math.floor(Math.random() * dims.length))
      }
      for (const i of indices) {
        dims[i].selected = true
      }
    }
  }

  // ============================================================
  // 阈值 & 自定义规则 Actions
  // ============================================================

  function updateDiversityThreshold(key: 'excellent' | 'good', value: number) {
    diversityThresholds.value[key] = value
  }

  function updateRiskThreshold(key: 'high' | 'medium' | 'low', value: number) {
    const t = riskThresholds.value
    if (key === 'high') {
      t.high = value
      if (t.medium > t.high) t.medium = t.high
      if (t.low > t.medium) t.low = t.medium
    } else if (key === 'medium') {
      t.medium = Math.min(value, t.high)
      if (t.low > t.medium) t.low = t.medium
    } else {
      t.low = Math.min(value, t.medium)
    }
  }

  function addCustomDiversityRule(text: string) {
    customDiversityRules.value.push({
      id: `dr-${Date.now()}`,
      text,
    })
  }

  function removeCustomDiversityRule(id: string) {
    customDiversityRules.value = customDiversityRules.value.filter((r) => r.id !== id)
  }

  function addCustomRiskRule(text: string) {
    customRiskRules.value.push({
      id: `rr-${Date.now()}`,
      text,
    })
  }

  function removeCustomRiskRule(id: string) {
    customRiskRules.value = customRiskRules.value.filter((r) => r.id !== id)
  }

  // ============================================================
  // 多样性数据加载（从 Cultural Gen BFF 获取真实数据，替换 Mock）
  // ============================================================

  /** 将 CultureSample 评分映射到多样性维度等级 */
  function mapScoreToDiversityLevel(score: number): DiversityLevel {
    if (score >= 85) return DiversityLevel.EXCELLENT
    if (score >= 70) return DiversityLevel.GOOD
    return DiversityLevel.NEEDS_IMPROVEMENT
  }

  /** 从 Cultural Gen 样本生成多样性评估样本 */
  function buildDiversityEvalSamples(samples: CultureSampleDTO[]): EvalSample[] {
    return samples.map((s) => {
      if (s.evaluationKind === 'reference_review') {
        const accuracy = Number(s.reviewAccuracy || 0)
        return {
          id: `DIV-CORPUS-${s.id}`,
          text: s.fullQuestion,
          dimensionScores: {},
          overallLevel: s.reviewPassed
            ? DiversityLevel.EXCELLENT
            : DiversityLevel.NEEDS_IMPROVEMENT,
          overallScore: accuracy / 5,
          summary: `${s.ethnic} · ${s.difficultyLevel || '未标注难度'} · 文化准确性审核 ${accuracy || '未提供'}/5`,
          evaluationKind: 'reference_review',
          ethnic: s.ethnic,
          category: s.category,
          difficultyLevel: s.difficultyLevel,
          runId: s.runId,
          expectedAnswer: s.expected,
          bgType: s.bgType,
          cues: s.cues,
          knowledge: s.knowledge,
          mustHave: s.rubric?.must_have || [],
          penalty: s.rubric?.penalty || [],
          reviewAccuracy: s.reviewAccuracy ?? null,
        } as EvalSample
      }
      const cultureLevel: DiversityLevel = mapScoreToDiversityLevel(s.cultureScore)
      const semanticLevel: DiversityLevel = mapScoreToDiversityLevel(s.semanticScore)
      const integrityLevel: DiversityLevel = mapScoreToDiversityLevel(s.integrityScore)
      const avgScore = Math.round((s.cultureScore + s.semanticScore + s.integrityScore) / 3)
      const overallLevel: DiversityLevel =
        avgScore >= 85
          ? DiversityLevel.EXCELLENT
          : avgScore >= 70
            ? DiversityLevel.GOOD
            : DiversityLevel.NEEDS_IMPROVEMENT
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const dimScores: Record<string, DiversityLevel | RiskLevel> = {
        文化包容与尊重: cultureLevel,
        代表性与覆盖面: semanticLevel,
        开放科学与可复现: integrityLevel,
      }
      return {
        id: `DIV-CUL-${s.id}`,
        text: s.fullQuestion,
        ethnic: s.ethnic || s.inferred,
        category: s.category,
        expectedAnswer: s.expected,
        generatedAnswer: s.generated,
        knowledge: s.knowledge,
        bgType: s.bgType,
        cues: s.cues,
        cultureScore: s.cultureScore,
        semanticScore: s.semanticScore,
        integrityScore: s.integrityScore,
        wrongExample: s.wrongExample,
        fixSuggestion: s.fixSuggestion,
        improveItems: s.improveItems,
        dimensionScores: dimScores,
        overallLevel,
        overallScore: avgScore / 100,
        summary: `${s.inferred} / ${s.category} · 文化${s.cultureScore} 语义${s.semanticScore} 完整${s.integrityScore}`,
      } as EvalSample
    })
  }

  /** 从 Cultural Gen 样本按民族聚合生成多样性雷达数据 */
  function buildDiversityRadarFromSamples(samples: CultureSampleDTO[]): RadarChartData {
    const ethnicScores: Record<
      string,
      { culture: number[]; semantic: number[]; integrity: number[] }
    > = {}
    for (const s of samples) {
      const e = s.ethnic
      if (!ethnicScores[e]) ethnicScores[e] = { culture: [], semantic: [], integrity: [] }
      ethnicScores[e].culture.push(s.cultureScore)
      ethnicScores[e].semantic.push(s.semanticScore)
      ethnicScores[e].integrity.push(s.integrityScore)
    }
    const dimensions = Object.keys(ethnicScores)
    const avg = (arr: number[]) => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length)
    return {
      dimensions,
      series: [
        {
          name: '文化适配',
          values: dimensions.map((e) => avg(ethnicScores[e].culture)),
          fill: 'rgba(63,185,129,0.12)',
          stroke: '#3fb981',
        },
        {
          name: '语义质量',
          values: dimensions.map((e) => avg(ethnicScores[e].semantic)),
          fill: 'rgba(59,130,246,0.10)',
          stroke: '#3b82f6',
        },
        {
          name: '完整度',
          values: dimensions.map((e) => avg(ethnicScores[e].integrity)),
          fill: 'rgba(245,158,11,0.10)',
          stroke: '#f59e0b',
        },
      ],
    }
  }

  /** 从 Cultural Gen 样本生成归因节点 */
  function buildDiversityAttributionFromSamples(samples: CultureSampleDTO[]): AttributionNode[] {
    return samples.slice(0, 10).map((s) => {
      const clues = s.cues.length > 0 ? s.cues.join('、') : s.inferred
      const cultureLevel: DiversityLevel = mapScoreToDiversityLevel(s.cultureScore)
      const semanticLevel: DiversityLevel = mapScoreToDiversityLevel(s.semanticScore)
      const integrityLevel: DiversityLevel = mapScoreToDiversityLevel(s.integrityScore)
      const avgScore = Math.round((s.cultureScore + s.semanticScore + s.integrityScore) / 3)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const signals: Record<string, DiversityLevel | RiskLevel> = {
        文化包容与尊重: cultureLevel,
        代表性与覆盖面: semanticLevel,
        开放科学与可复现: integrityLevel,
      }
      const rand = () => 0.8 + Math.random() * 0.15
      return {
        id: `DIV-CUL-${s.id}`,
        signals,
        chain: `${clues}(${rand().toFixed(2)}) + 知识检索(${rand().toFixed(2)}) → ${s.inferred}文化推理(${(avgScore / 100).toFixed(2)}) → ${s.category}类文化输出`,
        reasonPath: `${clues}(${rand().toFixed(2)}) + 知识检索(${rand().toFixed(2)}) → ${s.inferred}文化推理(${(avgScore / 100).toFixed(2)}) → ${s.category}类文化输出`,
        weight: avgScore / 100,
      } as AttributionNode
    })
  }

  const diversityEvalSource = ref<DataSource>('')

  async function loadDiversityData() {
    diversityEvalSource.value = ''
    try {
      const assessmentDataset = selectedDiversityDatasets.value.find(
        (dataset) => dataset.dataSource === 'culture_assessment_static',
      )
      if (assessmentDataset) {
        const viewId = assessmentDataset.runName || 'ui_batch_30_direct_vs_agent'
        diversityEvalSource.value = 'culture_assessment_static'
        if (cultureAssessmentStaticView.value?.view_id !== viewId) {
          cultureAssessmentStaticView.value = null
        }
        evaluation.evalDiversitySamples.value = []
        evaluation.radarDiversityData.value = null
        attr.diversityAttributionNodes.value = []
        const view = await loadCultureAssessmentStaticView(viewId)
        if (!view) {
          diversityEvalSource.value = 'unavailable'
        }
        return Boolean(view)
      }
      const staticCorpusDataset = selectedDiversityDatasets.value.find(
        (dataset) => dataset.dataSource === 'corpus_static',
      )
      const useStaticCorpus = !!staticCorpusDataset
      let data: { source: string; samples: CultureSampleDTO[]; total: number } | null = null
      const corpusQuery: CultureCorpusSamplesQuery = {}
      if (staticCorpusDataset?.cultureCorpusFilters?.runIds.length) {
        corpusQuery.run_id = staticCorpusDataset.cultureCorpusFilters.runIds
      }
      if (staticCorpusDataset?.cultureCorpusFilters?.ethnicGroups.length) {
        corpusQuery.ethnic = staticCorpusDataset.cultureCorpusFilters.ethnicGroups
      }
      if (staticCorpusDataset?.cultureCorpusFilters?.difficultyLevels.length) {
        corpusQuery.difficulty = staticCorpusDataset.cultureCorpusFilters.difficultyLevels
      }
      if (
        staticCorpusDataset?.cultureCorpusFilters?.runIds.some((runId) =>
          runId.startsWith('topic5_'),
        )
      ) {
        corpusQuery.include_live_runs = true
      }
      if (
        staticCorpusDataset &&
        (staticCorpusDataset.samplingMethod !== SamplingMethod.FULL ||
          staticCorpusDataset.sampleSize < staticCorpusDataset.recordCount)
      ) {
        corpusQuery.limit = staticCorpusDataset.sampleSize
      }
      data = (await (useStaticCorpus
        ? fetchCultureCorpusSamples(corpusQuery)
        : fetchCultureSamples())) as unknown as {
        source: string
        samples: CultureSampleDTO[]
        total: number
      } | null
      if (data && data.samples && data.samples.length > 0) {
        evaluation.evalDiversitySamples.value = buildDiversityEvalSamples(data.samples)
        const isCorpus = data.source === 'corpus_static'
        evaluation.radarDiversityData.value = isCorpus
          ? null
          : buildDiversityRadarFromSamples(data.samples)
        attr.diversityAttributionNodes.value = isCorpus
          ? []
          : buildDiversityAttributionFromSamples(data.samples)
        diversityEvalSource.value = isCorpus
          ? 'corpus_static'
          : data.source === 'real'
            ? 'real'
            : 'demo_fixture'
        return data.source === 'real' || isCorpus
      }
      diversityEvalSource.value = 'unavailable'
      return false
    } catch {
      diversityEvalSource.value = 'unavailable'
      return false
    }
  }

  // ============================================================
  // 统一初始化（Mock 数据仅用于尚无 API 的模块）
  // ============================================================

  function initPlaceholderMockData() {
    if (diversityDimensions.value.length === 0) {
      setDiversityDimensions(mockDiversityDimensions)
    }
    if (staticAssets.value.length === 0) {
      staticAssets.value = allStaticAssets
    }
    void loadCultureAssessmentDatasets()
    // 风险链 Step 1–3 禁止静默 mock；Step 4–5 占位保留
    if (attr.diversityAttributionNodes.value.length === 0) {
      attr.diversityAttributionNodes.value = mockDiversityAttributionNodes
    }
    if (correction.correctionSamples.value.length === 0) {
      correction.correctionSamples.value = mockCorrectionSamples
    }
  }

  // ============================================================
  // 计算属性
  // ============================================================

  const selectedDatasetsTotal = computed(() => selectedDatasets.value.length)

  const selectedDatasetsSampleTotal = computed(() =>
    selectedDatasets.value.reduce((sum, s) => sum + s.sampleSize, 0),
  )

  const selectedDimCount = computed(
    () => selectedDiversityDimensions.value.length + selectedRiskDimensions.value.length,
  )

  const totalDimCount = computed(
    () => diversityDimensions.value.length + riskDimensions.value.length,
  )

  const selectedDatasetsDomain = computed(() => {
    const selected = selectedDatasets.value
    if (selected.length === 0) return '未选择数据集'
    const tracks = new Set(selected.map((dataset) => dataset.track))
    const parts: string[] = []
    if (tracks.has(OutputTrack.RISK)) parts.push('风险治理')
    if (tracks.has(OutputTrack.DIVERSITY)) parts.push('多民族语言文化多样性')
    return parts.length > 0 ? parts.join(' · ') : '综合领域'
  })

  const selectedRiskDatasets = computed(() =>
    selectedDatasets.value.filter((dataset) => dataset.track === OutputTrack.RISK),
  )
  const selectedDiversityDatasets = computed(() =>
    selectedDatasets.value.filter((dataset) => dataset.track === OutputTrack.DIVERSITY),
  )

  function isAssetSelectable(asset: DataAsset): boolean {
    return asset.assetState === 'evaluable' || asset.selectable === true
  }

  // ============================================================
  // Return block
  // ============================================================

  return {
    // 导航
    ...nav,
    setCurrentStep,
    setCurrentTrack,
    goToStep,

    // 数据集
    availableDatasets,
    staticAssets,
    allAssets,
    expandedAssetId,
    selectedDatasets,
    dsSearchQuery,
    dsCategoryFilters,
    filteredDatasets,
    checkedDatasetIds,
    cultureCorpusJob,
    cultureCorpusJobLoading,
    cultureCorpusJobError,
    cultureCorpusJobSamples,
    cultureCorpusStaticOptions,
    cultureCorpusStaticOptionsLoading,
    cultureCorpusStaticOptionsError,
    cultureCorpusRunSummaries,
    cultureCorpusRunHistoryLoading,
    cultureCorpusRunHistoryError,
    cultureAssessmentDatasets,
    cultureAssessmentDatasetsLoading,
    cultureAssessmentDatasetsError,
    cultureAssessmentStaticViews,
    cultureAssessmentStaticView,
    cultureAssessmentStaticLoading,
    cultureAssessmentStaticError,
    setAvailableDatasets,
    setDsCategoryFilter,
    setDsSearchQuery,
    toggleCheckedDataset,
    isDatasetChecked,
    clearCheckedDatasets,
    addSelectedFromChecked,
    toggleDsCategoryFilter,
    initAllCategoryFilters,
    addSelectedDataset,
    removeSelectedDataset,
    updateSamplingMethod,
    updateSampleSize,
    startCultureCorpusGeneration,
    refreshCultureCorpusGenerationJob,
    stopCultureCorpusGeneration,
    loadCultureCorpusGeneratedSamples,
    syncCultureCorpusGeneratedRun,
    clearCultureCorpusPolling,
    loadCultureCorpusStaticOptions,
    updateCultureCorpusFilters,
    loadCultureCorpusRunHistory,
    loadCultureAssessmentDatasets,
    loadCultureAssessmentStaticViews,
    loadCultureAssessmentStaticView,
    selectedDatasetsTotal,
    selectedDatasetsSampleTotal,
    initPlaceholderMockData,

    // 多样性真实数据加载
    diversityEvalSource,
    loadDiversityData,

    // 维度筛选
    diversityDimensions,
    riskDimensions,
    customDiversityRules,
    customRiskRules,
    diversityThresholds,
    riskThresholds,
    selectedDiversityDimensions,
    selectedRiskDimensions,
    selectedDimCount,
    totalDimCount,
    selectedDatasetsDomain,
    selectedRiskDatasets,
    selectedDiversityDatasets,
    isAssetSelectable,
    setDiversityDimensions,
    setRiskDimensions,
    toggleDiversityDimension,
    toggleRiskDimension,
    selectAllDimensions,
    deselectAllDimensions,
    selectRecommendedDimensions,
    selectAllDimensionsForTrack,
    deselectAllDimensionsForTrack,
    selectRecommendedForTrack,
    updateDiversityThreshold,
    updateRiskThreshold,
    addCustomDiversityRule,
    removeCustomDiversityRule,
    addCustomRiskRule,
    removeCustomRiskRule,

    // 评估 (Step 3)
    ...evaluation,

    // 单样本推理
    ...infer,

    // 归因 (Step 4)
    ...attr,

    // 修正 (Step 5)
    ...correction,

    // 备用策略建议字段
    ...strat,
  }
})
