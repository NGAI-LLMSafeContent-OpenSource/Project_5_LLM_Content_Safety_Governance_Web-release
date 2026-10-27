<template>
  <div class="sel-panel">
    <div class="col-head">
      已选测试数据
      <span class="col-head-tag">{{ selectedDatasetsTotal }} 个</span>
    </div>
    <div class="sel-list">
      <div v-if="selectedDatasets.length === 0" class="sel-empty">
        请从左侧列表中选择风险轨道或多样性轨道数据集
      </div>
      <div v-if="diversitySourceHint" class="sel-warning">
        {{ diversitySourceHint }}
      </div>
      <div v-for="ds in selectedDatasets" :key="ds.datasetId" class="sel-item">
        <div class="sel-item-head">
          <span class="sel-item-name">{{ ds.datasetId }}</span>
          <button
            class="remove-btn"
            title="移除"
            @click="store.removeSelectedDataset(ds.datasetId)"
          >
            &times;
          </button>
        </div>
        <div class="sel-item-meta">{{ ds.name }} &middot; {{ ds.recordCount }} 条</div>
        <div class="sel-tags">
          <span
            class="sel-tag"
            :class="ds.track === OutputTrack.DIVERSITY ? 'tag-diversity' : 'tag-risk'"
          >
            {{ ds.track === OutputTrack.DIVERSITY ? '多样性轨道' : '风险轨道' }}
          </span>
          <span v-if="ds.dataSource" class="sel-tag tag-source">
            {{ dataSourceLabel(ds.dataSource) }}
          </span>
          <span v-if="ds.resultVersion" class="sel-tag tag-version">
            {{ ds.resultVersion }}
          </span>
        </div>
        <div v-if="ds.dataSource === 'corpus_static'" class="corpus-filter">
          <div class="corpus-filter-head">
            <div>
              <span>文化语料批次筛选</span>
              <small>先确定候选范围</small>
            </div>
            <button
              type="button"
              class="mini-link"
              @click="store.loadCultureCorpusStaticOptions(true)"
            >
              刷新
            </button>
          </div>
          <div v-if="cultureCorpusStaticOptionsError" class="corpus-filter-error">
            {{ cultureCorpusStaticOptionsError }}
          </div>
          <div class="corpus-filter-grid">
            <label class="corpus-run-field">
              <span>运行批次</span>
              <input
                v-model.trim="cultureRunSearch"
                class="corpus-run-search"
                type="search"
                placeholder="搜索批次 ID"
                :disabled="cultureCorpusStaticOptionsLoading"
              />
              <select
                :value="ds.cultureCorpusFilters?.runIds[0] || ''"
                :disabled="cultureCorpusStaticOptionsLoading"
                @change="onCorpusRunChange(ds.datasetId, $event)"
              >
                <option value="">全部批次</option>
                <option v-for="runId in visibleCorpusRunIds" :key="runId" :value="runId">
                  {{ runOptionLabel(runId) }}
                </option>
              </select>
              <em v-if="!cultureRunSearch && hiddenRunCount > 0">
                默认显示最近 30 个批次，另有 {{ hiddenRunCount }} 个历史批次可搜索。
              </em>
            </label>
            <label>
              <span>民族</span>
              <select
                :value="ds.cultureCorpusFilters?.ethnicGroups[0] || ''"
                :disabled="cultureCorpusStaticOptionsLoading"
                @change="onCorpusEthnicChange(ds.datasetId, $event)"
              >
                <option value="">全部民族</option>
                <option
                  v-for="ethnic in cultureCorpusStaticOptions.ethnicGroups"
                  :key="ethnic"
                  :value="ethnic"
                >
                  {{ ethnic }}
                </option>
              </select>
            </label>
            <label>
              <span>难度</span>
              <select
                :value="ds.cultureCorpusFilters?.difficultyLevels[0] || ''"
                :disabled="cultureCorpusStaticOptionsLoading"
                @change="onCorpusDifficultyChange(ds.datasetId, $event)"
              >
                <option value="">全部难度</option>
                <option
                  v-for="level in cultureCorpusStaticOptions.difficultyLevels"
                  :key="level"
                  :value="level"
                >
                  {{ level }}
                </option>
              </select>
            </label>
          </div>
          <div class="corpus-filter-note">筛选先确定候选范围；取样只在候选范围内生效。</div>
        </div>
        <div class="sample-row" :class="{ 'sample-row-corpus': ds.dataSource === 'corpus_static' }">
          <label>{{ ds.dataSource === 'corpus_static' ? '筛选后使用' : '采样方式：' }}</label>
          <select :value="ds.samplingMethod" @change="onSamplingChange(ds.datasetId, $event)">
            <option
              v-for="m in samplingMethodsForDataset(ds.dataSource)"
              :key="m.value"
              :value="m.value"
            >
              {{ m.label }}
            </option>
          </select>
          <label>{{ ds.dataSource === 'corpus_static' ? '最多取样' : '数量：' }}</label>
          <input
            class="size-input"
            type="number"
            :value="ds.sampleSize"
            :min="1"
            :max="ds.recordCount"
            :disabled="ds.samplingMethod === SamplingMethod.FULL"
            @change="onSampleSizeChange(ds.datasetId, $event)"
          />
        </div>
        <div v-if="ds.dataSource === 'corpus_static'" class="sample-row-note">
          “最多取样”不会改变批次、民族、难度筛选条件；全量表示使用当前筛选结果。
        </div>
      </div>
    </div>
    <div class="sel-summary">
      <div class="sel-summary-row">
        <span>已选数据集</span>
        <strong>{{ selectedDatasetsTotal }} 个</strong>
      </div>
      <div class="sel-summary-row">
        <span>采样总量</span>
        <strong class="text-blue">{{ selectedDatasetsSampleTotal.toLocaleString() }} 条</strong>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useOutputStore } from '@/stores/output'
import { OutputTrack, SamplingMethod, type DataSource } from '@/types'
import { dataSourceLabel } from '@/utils/outputHelpers'

const store = useOutputStore()
const {
  selectedDatasets,
  selectedDatasetsTotal,
  selectedDatasetsSampleTotal,
  cultureCorpusStaticOptions,
  cultureCorpusStaticOptionsLoading,
  cultureCorpusStaticOptionsError,
  cultureCorpusRunSummaries,
} = storeToRefs(store)

const samplingMethods = [
  { value: SamplingMethod.FULL, label: '全量' },
  { value: SamplingMethod.RANDOM, label: '随机' },
]

const corpusSamplingMethods = [
  { value: SamplingMethod.FULL, label: '使用当前筛选结果' },
  { value: SamplingMethod.RANDOM, label: '从筛选结果随机取样' },
]

const cultureRunSearch = ref('')

const selectedCorpusRunIds = computed(() =>
  selectedDatasets.value.flatMap((dataset) => dataset.cultureCorpusFilters?.runIds || []),
)

const visibleCorpusRunIds = computed(() => {
  const q = cultureRunSearch.value.toLowerCase()
  const all = cultureCorpusStaticOptions.value.runIds
  const base = q
    ? all
        .filter((runId) => runId.toLowerCase().includes(q))
        .slice(-50)
        .reverse()
    : all.slice(-30).reverse()
  return Array.from(new Set([...selectedCorpusRunIds.value, ...base])).filter(Boolean)
})

const hiddenRunCount = computed(() =>
  Math.max(0, cultureCorpusStaticOptions.value.runIds.length - visibleCorpusRunIds.value.length),
)

const diversitySourceHint = computed(() => {
  const diversitySources = selectedDatasets.value.filter(
    (dataset) => dataset.track === OutputTrack.DIVERSITY,
  )
  if (diversitySources.length <= 1) return ''
  if (diversitySources.some((dataset) => dataset.dataSource === 'corpus_static')) {
    return '已选择多个多样性数据源；当前评估会优先使用文化语料批次集合。如需评估动态文化样本集，请先移除批次集合。'
  }
  return '已选择多个多样性数据源；当前评估默认使用第一个可用文化数据源。'
})

function samplingMethodsForDataset(source?: DataSource) {
  return source === 'corpus_static' ? corpusSamplingMethods : samplingMethods
}

function runOptionLabel(runId: string) {
  const summary = cultureCorpusRunSummaries.value.find((item) => item.runId === runId)
  if (!summary) return runId
  const source = summary.source === 'live' ? '实时生成' : '预跑批次'
  const ethnic = Object.keys(summary.ethnicCounts).slice(0, 2).join('/')
  const difficulty = Object.keys(summary.difficultyCounts).slice(0, 3).join('/')
  const tags = [source, `${summary.count}条`, ethnic, difficulty].filter(Boolean).join(' · ')
  return `${runId} · ${tags}`
}

function onSamplingChange(datasetId: string, e: Event) {
  store.updateSamplingMethod(datasetId, (e.target as HTMLSelectElement).value as SamplingMethod)
}

function onSampleSizeChange(datasetId: string, e: Event) {
  store.updateSampleSize(datasetId, Number((e.target as HTMLInputElement).value))
}

function selectedSingleValue(e: Event) {
  const value = (e.target as HTMLSelectElement).value
  return value ? [value] : []
}

function onCorpusRunChange(datasetId: string, e: Event) {
  store.updateCultureCorpusFilters(datasetId, { runIds: selectedSingleValue(e) })
}

function onCorpusEthnicChange(datasetId: string, e: Event) {
  store.updateCultureCorpusFilters(datasetId, { ethnicGroups: selectedSingleValue(e) })
}

function onCorpusDifficultyChange(datasetId: string, e: Event) {
  store.updateCultureCorpusFilters(datasetId, { difficultyLevels: selectedSingleValue(e) })
}

onMounted(() => {
  void store.loadCultureCorpusStaticOptions()
  void store.loadCultureCorpusRunHistory()
})
</script>

<style src="./SelectedDatasetsPanel.css" scoped></style>
