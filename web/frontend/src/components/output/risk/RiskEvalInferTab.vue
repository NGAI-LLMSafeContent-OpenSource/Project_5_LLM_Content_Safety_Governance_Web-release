<template>
  <div class="content">
    <div class="section-title">
      单样本推理验证
      <small>用于模型链路验证，不回写上方静态指标</small>
    </div>
    <div class="infer-panel" style="margin-top: 0; border-color: var(--border-color)">
      <div class="infer-split">
        <div class="infer-control">
          <div class="infer-field">
            <label class="infer-label">选择现有算法</label>
            <select v-model="inferModelId" class="infer-select">
              <option
                v-if="topic3ModelId && !inferModelIds.has(topic3ModelId)"
                :value="topic3ModelId"
              >
                {{ topic3ModelId }}
              </option>
              <option v-for="m in INFER_MODELS" :key="m.id" :value="m.id">
                {{ m.name }}
              </option>
            </select>
          </div>
          <div class="infer-field">
            <label class="infer-label">评测数据</label>
            <select v-model="inferDatasetId" class="infer-select">
              <option v-if="!datasets.length" value="" disabled>
                请先在测试数据选择页选择风险数据集
              </option>
              <option v-for="ds in datasets" :key="ds.datasetId" :value="ds.datasetId">
                {{ ds.name || ds.datasetId }} · {{ ds.recordCount }}条
              </option>
            </select>
          </div>
          <div class="infer-field">
            <label class="infer-label">类别</label>
            <select v-model="inferCategory" class="infer-select">
              <option value="">全部</option>
              <option v-for="cat in inferCategoryOptions" :key="cat.code" :value="cat.code">
                {{ cat.code }} {{ cat.label }}
              </option>
            </select>
          </div>
          <div class="infer-field">
            <label class="infer-label">样例库</label>
            <select v-model="selectedExampleIdx" class="infer-select" @change="onInferSampleSelect">
              <option :value="-1">
                {{ datasetSamplesLoading ? '正在加载数据集样例...' : '选择样例填入 Response' }}
              </option>
              <template v-for="(ex, i) in inferSamples">
                <option v-if="ex.isDivider" :key="ex.id" disabled :value="-1">
                  {{ ex.name }}
                </option>
                <option v-else :key="ex.id" :value="i">
                  {{ ex.name }}
                </option>
              </template>
            </select>
            <div class="infer-source-note" :class="{ warn: datasetSamplesError }">
              {{ datasetSampleSourceText }}
            </div>
          </div>
          <div class="infer-field">
            <label class="infer-label">Response</label>
            <textarea
              :value="store.inferResponse"
              class="infer-textarea"
              rows="10"
              placeholder="输入或选择需要评测的大模型 response"
              @input="onInferTextInput"
            ></textarea>
          </div>
          <button
            class="infer-btn"
            :disabled="!store.inferResponse.trim() || store.inferLoading"
            @click="store.runInfer()"
          >
            <span v-if="store.inferLoading" class="infer-spinner"></span>
            {{ store.inferLoading ? '推理中...' : '开始推理' }}
          </button>
        </div>
        <div class="infer-result">
          <template v-if="store.inferLoading">
            <div class="infer-status infer-running">
              <span class="infer-spinner" aria-hidden="true"></span>
              <span>
                <b>正在推理</b>
                <small>正在加载模型并执行安全分类与风险分级，请稍候</small>
              </span>
            </div>
            <div class="infer-progress"><span></span></div>
          </template>
          <template v-else-if="!store.inferResult">
            <div class="infer-placeholder">
              <div class="infer-placeholder-icon">
                <svg
                  width="40"
                  height="40"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <p>
                选择样本或输入 Response 文本后点击「开始推理」，查看模型动态推理过程与预测结果。
              </p>
            </div>
          </template>
          <template v-else>
            <div class="infer-status" :class="store.inferResult.ok ? 'infer-ok' : 'infer-err'">
              <span class="infer-status-icon">{{ store.inferResult.ok ? '✓' : '✗' }}</span>
              <span>{{ store.inferResult.ok ? '推理完成' : '推理失败' }}</span>
              <span v-if="store.inferShowMockLabel" class="infer-mock-tag">模拟数据</span>
              <span v-else-if="store.inferSource === 'unavailable'" class="infer-mock-tag">
                服务不可用
              </span>
            </div>

            <div class="infer-result-summary" :class="{ single: !selectedGroundtruth }">
              <div class="result-panel pred-panel">
                <h3>模型预测结果</h3>
                <div class="result-row">
                  <span>是否有害</span>
                  <b>{{ inferHarmLabel }}</b>
                </div>
                <div class="result-row">
                  <span>预测分级</span>
                  <b>{{ inferLevelLabel }}</b>
                </div>
                <div class="result-row">
                  <span>预测分类</span>
                  <b>{{ inferCategoryLabel }}</b>
                </div>
              </div>
              <div v-if="selectedGroundtruth" class="result-panel gold-panel">
                <h3>Groundtruth</h3>
                <div class="result-row">
                  <span>是否有害</span>
                  <b>{{ selectedGroundtruth.harm }}</b>
                </div>
                <div class="result-row">
                  <span>标注分级</span>
                  <b>{{ selectedGroundtruth.level }}</b>
                </div>
                <div class="result-row">
                  <span>标注分类</span>
                  <b>{{ selectedGroundtruth.category }}</b>
                </div>
              </div>
            </div>

            <div class="infer-detail-stack">
              <section class="infer-detail-card">
                <h3>输入 Response</h3>
                <pre>{{ inferInputResponse }}</pre>
              </section>
              <details class="infer-detail-card">
                <summary>构造评测 Prompt</summary>
                <pre>{{ inferPrompt }}</pre>
              </details>
              <details class="infer-detail-card" open>
                <summary>模型原始输出</summary>
                <pre>{{ inferRawOutput }}</pre>
              </details>
              <details
                v-if="store.inferResult.stderr || store.inferResult.stdout"
                class="infer-detail-card run-log-card"
                open
              >
                <summary>运行日志</summary>
                <pre>{{ store.inferResult.stderr || store.inferResult.stdout }}</pre>
              </details>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useOutputStore } from '@/stores/output'
import { fetchBenchmarkPredictions } from '@/api/output'
import { INFER_MODELS, INFER_PRESET_EXAMPLES } from '@/utils/inferExamples'
import { normalizeCategoryList } from './normalizeCategoryList'
import { SAMPLES } from './samplesData'

const store = useOutputStore()

const props = defineProps<{
  datasets: Array<{ datasetId: string; name?: string; recordCount: number }>
}>()

const inferModelId = ref<string>(INFER_MODELS[0].id)
watch(
  inferModelId,
  (id) => {
    store.inferModelId = id
  },
  { immediate: true },
)
const inferDatasetId = ref(props.datasets[0]?.datasetId || '')
const inferCategory = ref('')
const datasetSamplesLoading = ref(false)
const datasetSamplesError = ref('')
const datasetSampleRows = ref<Record<string, unknown>[]>([])
let datasetSampleAbortController: AbortController | null = null

const inferCategoryOptions = computed(() =>
  store.riskDimensions
    .filter((d) => d.selected && (d.category === 'ai4sci' || d.key.startsWith('C')))
    .map((d) => ({ code: d.code || d.key, label: d.label })),
)

interface InferSampleEntry {
  id: string
  name: string
  response: string
  isDivider: boolean
  goldCats: string[]
  goldLevel: string
  goldHarm: string
}
const inferModelIds = new Set<string>(INFER_MODELS.map((item) => item.id))
function isTopic3RiskAsset(datasetId: string): boolean {
  const view = store.topic3RiskView
  if (!view || !datasetId) return false
  return view.asset_id === datasetId || view.versions.some((item) => item.asset_id === datasetId)
}
const topic3ModelId = computed(() => {
  if (!isTopic3RiskAsset(inferDatasetId.value)) return ''
  const view = store.topic3RiskView
  return view?.primary_evaluator.model_id || view?.result_display.model_id || ''
})
const inferTaskForDataset = computed(() => {
  if (isTopic3RiskAsset(inferDatasetId.value)) {
    return store.topic3RiskView?.result_display.task || store.staticResultMeta?.task || ''
  }
  const match = store.availableStaticDatasets.find(
    (item) => item.dataset_id === inferDatasetId.value,
  )
  return match?.task || 'binary'
})
const selectedStaticPredictionOption = computed(() => {
  const options = store.availableStaticDatasets.filter(
    (item) => item.dataset_id === inferDatasetId.value,
  )
  return (
    options.find((item) => item.task === inferTaskForDataset.value) ||
    options.find((item) => item.task === 'joint_level_then_multilabel') ||
    options.find((item) => item.task === 'multilabel_then_severity') ||
    options.find((item) => item.task === store.selectedStaticTask) ||
    options[0]
  )
})
const datasetSampleEntries = computed<InferSampleEntry[]>(() =>
  datasetSampleRows.value
    .map((row, index) => {
      const example = ((row.example as Record<string, unknown>) || {}) as Record<string, unknown>
      const response = String(
        example.response || example.text || row.response || row.text || row.output || '',
      )
      if (!response.trim()) return null
      const goldCats = normalizeCategoryList(
        row.gold_categories || row.gold_category || row.risk_category,
      )
      const predCats = normalizeCategoryList(row.pred_categories || row.pred_category)
      const level = normalizeLevel(row.gold_level || row.pred_level || row.risk_level_id)
      const titleCats = goldCats.length ? goldCats : predCats
      const rowIndex = row.index ?? row.id ?? index + 1
      return {
        id: `dataset-${inferDatasetId.value}-${rowIndex}`,
        name: `#${rowIndex} · ${level} · ${titleCats.join('、') || '未标注类别'}`,
        response,
        isDivider: false,
        goldCats,
        goldLevel: level,
        goldHarm: normalizeHarm(
          row.gold_binary_label || example.response_safetype || example.safe_type,
        ),
      }
    })
    .filter((item): item is InferSampleEntry => Boolean(item)),
)
const inferSamplesRaw = computed<InferSampleEntry[]>(() => [
  {
    id: '__divider__',
    name: datasetSamplesLoading.value
      ? '— 当前数据集样例加载中 —'
      : datasetSamplesError.value
        ? '— 当前数据集样例不可用 —'
        : `— 当前数据集样例（${datasetSampleEntries.value.length} 条）—`,
    response: '',
    isDivider: true,
    goldCats: [],
    goldLevel: '',
    goldHarm: '',
  },
  ...datasetSampleEntries.value,
  {
    id: '__divider_static__',
    name: '— Benchmark 快照样例兜底 —',
    response: '',
    isDivider: true,
    goldCats: [],
    goldLevel: '',
    goldHarm: '',
  },
  ...SAMPLES.map((s) => ({
    id: s.id,
    name: `${s.id} · ${s.level} · ${s.gold.join('、')}`,
    response: s.response,
    isDivider: false,
    goldCats: s.gold,
    goldLevel: s.level,
    goldHarm: s.gold.length ? '有害' : '安全',
  })),
  {
    id: '__divider2__',
    name: '— 预置样例 —',
    response: '',
    isDivider: true,
    goldCats: [],
    goldLevel: '',
    goldHarm: '',
  },
  ...INFER_PRESET_EXAMPLES.map((ex) => ({
    id: ex.id,
    name: ex.name,
    response: ex.response,
    isDivider: false,
    goldCats: [] as string[],
    goldLevel: '',
    goldHarm: '',
  })),
])

const inferSamples = computed(() => {
  if (!inferCategory.value) return inferSamplesRaw.value
  return inferSamplesRaw.value.filter(
    (ex) => ex.isDivider || ex.goldCats.length === 0 || ex.goldCats.includes(inferCategory.value),
  )
})
const datasetSampleSourceText = computed(() => {
  if (!inferDatasetId.value) return '未选择风险数据集，当前只能使用兜底样例或手动输入。'
  if (datasetSamplesLoading.value) return '正在从 Benchmark predictions 读取当前数据集样例。'
  if (datasetSamplesError.value) return datasetSamplesError.value
  if (datasetSampleEntries.value.length) {
    return `已加载 ${datasetSampleEntries.value.length} 条当前数据集样例；类别范围会同步过滤样例库。`
  }
  return '当前数据集未返回可填入 Response 的样例，可使用兜底样例或手动输入。'
})

const selectedExampleIdx = ref(-1)

function onInferSampleSelect() {
  const idx = selectedExampleIdx.value
  const item = inferSamples.value[idx]
  if (item && !item.isDivider && item.response) {
    store.setInferResponse(item.response)
  }
}

function onInferTextInput(e: Event) {
  store.setInferResponse((e.target as HTMLTextAreaElement).value)
}

async function loadDatasetSamples() {
  selectedExampleIdx.value = -1
  datasetSampleRows.value = []
  datasetSamplesError.value = ''
  if (!inferDatasetId.value) return
  if (datasetSampleAbortController) {
    datasetSampleAbortController.abort()
  }
  datasetSampleAbortController = new AbortController()
  datasetSamplesLoading.value = true
  try {
    if (isTopic3RiskAsset(inferDatasetId.value)) {
      const current = store.topic3RiskView
      if (!current || current.asset_id !== inferDatasetId.value) {
        const version =
          current?.versions.find((item) => item.asset_id === inferDatasetId.value)?.asset_version ??
          ''
        await store.loadTopic3RiskSameVersion(version, inferDatasetId.value)
      }
      const view = store.topic3RiskView
      if (!view || view.asset_id !== inferDatasetId.value) {
        datasetSamplesError.value =
          store.topic3RiskError || '当前评测对象没有可填入的同版本样本。'
        return
      }
      datasetSampleRows.value = store.staticPredictions
      if (topic3ModelId.value) inferModelId.value = topic3ModelId.value
      store.inferTask = inferTaskForDataset.value
      if (!datasetSampleRows.value.length) {
        datasetSamplesError.value = '当前评测对象没有可填入的同版本样本。'
      }
      return
    }
    const option = selectedStaticPredictionOption.value
    const data = await fetchBenchmarkPredictions(
      inferDatasetId.value,
      option?.model_id || '',
      option?.task || '',
      200,
      datasetSampleAbortController.signal,
    )
    datasetSampleRows.value = ((data.rows || []) as unknown as Record<string, unknown>[]).slice(
      0,
      200,
    )
    if (!datasetSampleRows.value.length) {
      datasetSamplesError.value = '当前数据集 predictions 为空，未加载到数据集样例。'
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') return
    datasetSamplesError.value =
      '当前数据集样例接口不可用，已保留 Benchmark 快照样例和预置样例兜底。'
  } finally {
    datasetSamplesLoading.value = false
  }
}

function normalizeLevel(value: unknown): string {
  const text = String(value ?? '')
  if (text.includes('3') || /high/i.test(text)) return '高风险'
  if (text.includes('2') || /medium/i.test(text)) return '中风险'
  if (text.includes('1') || /low/i.test(text)) return '低风险'
  if (text === '0' || /safe/i.test(text)) return '安全'
  return '未标注等级'
}

function normalizeHarm(value: unknown): string {
  const text = String(value ?? '').toLowerCase()
  if (text === '0' || text === 'safe' || text === '安全') return '安全'
  if (text === '1' || text === 'unsafe' || text === '有害') return '有害'
  return '有害'
}

const selectedSample = computed(() => {
  const item = inferSamples.value[selectedExampleIdx.value]
  return item && !item.isDivider ? item : null
})

const selectedGroundtruth = computed(() => {
  const item = selectedSample.value
  if (!item || (!item.goldCats.length && !item.goldLevel)) return null
  return {
    harm: item.goldHarm || (item.goldCats.length ? '有害' : '安全'),
    level: item.goldLevel || '未标注等级',
    category: item.goldCats.join('、') || '未标注类别',
  }
})

const inferResultBody = computed<Record<string, unknown>>(() => {
  const data = (store.inferResult || {}) as Record<string, unknown>
  return ((data.result as Record<string, unknown>) || data) as Record<string, unknown>
})

const inferStepsRaw = computed<Array<{ name?: string; detail?: unknown }>>(
  () => (store.inferResult?.steps || []) as Array<{ name?: string; detail?: unknown }>,
)

function stepDetail(name: string): Record<string, unknown> {
  const step = inferStepsRaw.value.find((item) => item.name === name)
  return typeof step?.detail === 'object' && step.detail !== null
    ? (step.detail as Record<string, unknown>)
    : {}
}

const inferInputResponse = computed(() =>
  String(stepDetail('输入 Response').response || store.inferResponse || ''),
)
const inferPrompt = computed(() =>
  String(stepDetail('构造评测 Prompt').prompt || store.inferResult?.prompt_used || '-'),
)
const inferRawOutput = computed(() =>
  String(stepDetail('模型原始输出').raw_response || store.inferResult?.raw_response || '-'),
)

const inferHarmLabel = computed(() => {
  const st = store.inferResult?.pred_safe_type
  if (!st) return '—'
  if (st === 'error') return '推理异常'
  if (st === 'safe') return '安全'
  return st.toLowerCase() === 'unsafe' ? '有害' : st
})
const inferLevelLabel = computed(() => {
  const lv = store.inferResult?.pred_risk_level
  if (!lv && lv !== 0 && lv !== '0') return '—'
  const s = String(lv)
  if (s.includes('3')) return '高风险'
  if (s.includes('2')) return '中风险'
  if (s.includes('1')) return '低风险'
  if (s === '0') return '无风险'
  return s
})

const inferCategoryLabel = computed(() => {
  const result = inferResultBody.value
  const categories = Array.isArray(result.risk_categories) ? result.risk_categories : null
  const names = (result.risk_category_names as Record<string, string> | undefined) || {}
  if (categories?.length) {
    return categories.map((code) => `${code} ${names[String(code)] || ''}`.trim()).join('；')
  }
  return (
    [
      result.risk_category_code,
      result.risk_category_name || names[String(result.risk_category_code || '')],
    ]
      .filter(Boolean)
      .join(' ') || String(result.risk_category || store.inferResult?.pred_category || '—')
  )
})

onMounted(() => {
  loadDatasetSamples()
})

watch(
  () => props.datasets,
  (list) => {
    if (
      inferDatasetId.value &&
      list.some((dataset) => dataset.datasetId === inferDatasetId.value)
    ) {
      return
    }
    inferDatasetId.value = list[0]?.datasetId || ''
  },
  { deep: true },
)

watch(inferDatasetId, () => {
  if (isTopic3RiskAsset(inferDatasetId.value)) {
    if (topic3ModelId.value) inferModelId.value = topic3ModelId.value
  } else {
    const option = selectedStaticPredictionOption.value
    if (option?.model_id && !String(option.model_id).includes('root_autodl-tmp')) {
      inferModelId.value = option.model_id
    }
  }
  store.inferTask = inferTaskForDataset.value
  loadDatasetSamples()
})

watch(topic3ModelId, (modelId) => {
  if (modelId && isTopic3RiskAsset(inferDatasetId.value)) inferModelId.value = modelId
})

watch(
  () => store.topic3RiskView?.asset_id ?? '',
  (assetId) => {
    if (assetId && assetId === inferDatasetId.value) loadDatasetSamples()
  },
)

watch(
  inferTaskForDataset,
  (task) => {
    store.inferTask = task
  },
  { immediate: true },
)
</script>

<style src="./RiskEvalInferTab.css" scoped></style>
