import { computed, onMounted, ref, watch, type Ref } from 'vue'
import {
  getResolvedTopic3RiskAsset,
  getTopic3RiskAssetVersions,
  getTopic3RiskEvaluationSummary,
  getTopic3RiskSameVersionEvaluationSummary,
} from '@/api/benchmark'
import type {
  BenchmarkArtifactItem,
  BenchmarkTopic3RiskAssetStatus,
  BenchmarkTopic3RiskAssetVersion,
  BenchmarkTopic3RiskEvaluationSummary,
} from '@/types'

const RISK_LEVELS = ['safe', 'low', 'medium', 'high'] as const
const STATUS_LABELS: Record<BenchmarkTopic3RiskAssetStatus, string> = {
  current: '当前',
  historical: '历史',
  unregistered: '未登记',
}
const STATUS_CLASSES: Record<BenchmarkTopic3RiskAssetStatus, string> = {
  current: 'is-valid',
  historical: 'is-muted',
  unregistered: 'is-pending',
}

interface UseTopic3RiskAssetVersionsOptions {
  assetId: Ref<string | undefined>
  fallbackAsset: Ref<BenchmarkArtifactItem | null | undefined>
}

export function useTopic3RiskAssetVersions(options: UseTopic3RiskAssetVersionsOptions) {
  const loadingVersions = ref(true)
  const loadError = ref('')
  const versions = ref<BenchmarkTopic3RiskAssetVersion[]>([])
  const seriesName = ref('')
  const selectedAssetId = ref('')
  const resolvedOverride = ref<BenchmarkTopic3RiskAssetVersion | null>(null)
  const loadingEvaluation = ref(false)
  const evaluationError = ref('')
  const evaluation = ref<BenchmarkTopic3RiskEvaluationSummary | null>(null)
  const drawerVisible = ref(false)
  const showHistory = ref(false)
  const evaluationRequestSeq = ref(0)

  const fallbackVersion = computed<BenchmarkTopic3RiskAssetVersion | null>(() => {
    if (!options.assetId.value || !options.fallbackAsset.value) return null
    const asset = options.fallbackAsset.value
    const manifest = asset.manifest || {}
    return {
      series_id: String(manifest.series_id || ''),
      asset_id: asset.asset_id,
      asset_version: nullableString(manifest.asset_version),
      asset_sha256: String(manifest.asset_sha256 || asset.artifact_sha256 || ''),
      asset_status: 'unregistered',
      series_name: '',
      name: asset.name,
      sample_count: nullableNumber(manifest.sample_count),
      safe_count: nullableNumber(manifest.safe_total),
      risk_count: nullableNumber(manifest.risk_total),
      risk_level_distribution: numberRecord(manifest.risk_level_distribution),
      language_distribution: numberRecord(manifest.language_distribution),
      category_distribution: numberRecord(manifest.category_distribution),
      evaluation_status: String(manifest.evaluation_status || ''),
      registered_at: asset.created_at ?? null,
    }
  })

  const selected = computed(() => {
    if (resolvedOverride.value) return resolvedOverride.value
    const found = versions.value.find((item) => item.asset_id === selectedAssetId.value)
    return found ?? fallbackVersion.value
  })

  const selectOptions = computed(() => {
    const visible = showHistory.value
      ? versions.value
      : versions.value.filter(
          (item) => item.asset_status === 'current' || item.asset_id === selectedAssetId.value,
        )
    const current = selected.value
    if (current && !visible.some((item) => item.asset_id === current.asset_id)) {
      return [current, ...visible]
    }
    return visible
  })

  const statusClass = computed(() => {
    const status = selected.value?.asset_status
    return status ? STATUS_CLASSES[status] : 'is-pending'
  })

  const levelItems = computed(() => {
    const distribution = selected.value?.risk_level_distribution || {}
    return RISK_LEVELS.map((level) => ({
      level,
      count: typeof distribution[level] === 'number' ? formatCount(distribution[level]) : '—',
    }))
  })

  const languageItems = computed(() =>
    countEntries(selected.value?.language_distribution).map(([language, count]) => ({
      language,
      count: formatCount(count),
    })),
  )

  const categoryItems = computed(() =>
    countEntries(selected.value?.category_distribution).map(([code, count]) => ({
      code,
      count: formatCount(count),
    })),
  )

  const primaryResult = computed(
    () => evaluation.value?.results.find((item) => item.role === 'primary') ?? null,
  )
  const baselineResult = computed(
    () => evaluation.value?.results.find((item) => item.role === 'baseline') ?? null,
  )
  const primaryModelLabel = computed(
    () => primaryResult.value?.display_name || primaryResult.value?.model_id || '主评估器',
  )
  const primaryMetricDefs = computed(() => evaluation.value?.primary_metrics ?? [])
  const baselineMessage = computed(() => {
    const message = evaluation.value?.comparison?.message
    if (message) return message
    if (!evaluation.value?.available) return '暂无同版本评测结果'
    if (!primaryResult.value) return '暂无主评估器结果'
    if (!baselineResult.value) return '暂无同版本基线'
    return ''
  })

  onMounted(() => {
    void load()
  })

  watch(options.assetId, () => {
    void load()
  })

  async function load() {
    loadingVersions.value = true
    loadError.value = ''
    resolvedOverride.value = null
    evaluation.value = null
    evaluationError.value = ''
    evaluationRequestSeq.value += 1
    try {
      const data = await getTopic3RiskAssetVersions()
      versions.value = data.versions
      seriesName.value = data.series_name
      if (options.assetId.value) {
        await selectResourceAsset(options.assetId.value)
      } else {
        selectedAssetId.value =
          versions.value.find((item) => item.asset_id === data.current_asset_id)?.asset_id ?? ''
      }
    } catch (error) {
      loadError.value =
        error instanceof Error ? error.message : '课题三风险 Benchmark 版本元数据读取失败'
    } finally {
      loadingVersions.value = false
    }
    await loadEvaluation()
  }

  async function selectResourceAsset(assetIdValue: string) {
    const registered = versions.value.find((item) => item.asset_id === assetIdValue)
    if (registered) {
      selectedAssetId.value = registered.asset_id
      return
    }
    try {
      resolvedOverride.value = await getResolvedTopic3RiskAsset({ asset_id: assetIdValue })
      selectedAssetId.value = resolvedOverride.value.asset_id
    } catch {
      selectedAssetId.value = assetIdValue
    }
  }

  function handleVersionChange(event: Event) {
    selectedAssetId.value = (event.target as HTMLSelectElement).value
    resolvedOverride.value = null
    void loadEvaluation()
  }

  function toggleHistory() {
    showHistory.value = !showHistory.value
  }

  async function loadEvaluation() {
    const requestSeq = ++evaluationRequestSeq.value
    evaluation.value = null
    evaluationError.value = ''
    const current = selected.value
    if (!current) {
      return
    }
    loadingEvaluation.value = true
    try {
      const data =
        current.asset_status === 'unregistered'
          ? await getTopic3RiskEvaluationSummary(current.asset_id)
          : await getTopic3RiskSameVersionEvaluationSummary({ asset_id: current.asset_id })
      if (requestSeq !== evaluationRequestSeq.value) return
      if (!identityMatches(current, data)) {
        evaluationError.value =
          '评测结果与所选资产标识或内容哈希不一致，已停止展示以避免跨版本拼接。'
        return
      }
      evaluation.value = data
    } catch (error) {
      if (requestSeq !== evaluationRequestSeq.value) return
      evaluationError.value = error instanceof Error ? error.message : '同版本评测结果暂时不可用'
    } finally {
      if (requestSeq === evaluationRequestSeq.value) {
        loadingEvaluation.value = false
      }
    }
  }

  return {
    loadingVersions,
    loadError,
    versions,
    seriesName,
    selectedAssetId,
    selected,
    selectOptions,
    statusClass,
    loadingEvaluation,
    evaluationError,
    evaluation,
    drawerVisible,
    showHistory,
    levelItems,
    languageItems,
    categoryItems,
    primaryResult,
    baselineResult,
    primaryModelLabel,
    primaryMetricDefs,
    baselineMessage,
    handleVersionChange,
    toggleHistory,
    statusLabel,
    formatCount,
    formatMetric,
  }
}

function identityMatches(
  current: BenchmarkTopic3RiskAssetVersion,
  result: BenchmarkTopic3RiskEvaluationSummary,
) {
  if (result.asset_id !== current.asset_id) return false
  if (!current.asset_sha256 || !result.asset_sha256) return false
  return result.asset_sha256 === current.asset_sha256
}

function statusLabel(status?: BenchmarkTopic3RiskAssetStatus) {
  return status ? STATUS_LABELS[status] : '—'
}

function formatCount(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—'
}

function formatMetric(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return `${Math.round(value * 1000) / 10}%`
}

function nullableString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : null
}

function nullableNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function numberRecord(value: unknown): Record<string, number> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).filter(
      (entry): entry is [string, number] => typeof entry[1] === 'number',
    ),
  )
}

function countEntries(value: Record<string, number> | undefined) {
  return Object.entries(value || {}).sort((a, b) => a[0].localeCompare(b[0]))
}
