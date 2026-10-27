<template>
  <section class="cbrne-query" data-testid="cbrne-query-panel">
    <div class="cbrne-query__header">
      <div>
        <h5>结构化筛选与分页摘要</h5>
        <p>
          列表仅返回脱敏摘要与稳定引用；样本全文需走 Benchmark 详情入口（本切片不提供）。
          查询结果不提供 Activation Probe 或其它评测执行入口。
        </p>
      </div>
      <span class="cbrne-query__version">
        v{{ assetVersion || '—' }} · {{ shortRecordVersion }}
      </span>
    </div>

    <p class="cbrne-query__hit" data-testid="cbrne-query-hit">
      命中 {{ hasLoaded ? total : '—' }} / {{ assetSampleCountLabel }}
    </p>

    <section class="cbrne-query__filters">
      <el-select
        v-model="draft.label"
        clearable
        placeholder="参考标签"
        size="small"
        data-testid="cbrne-filter-label"
      >
        <el-option
          v-for="item in labelOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="draft.cbrne_category"
        clearable
        filterable
        placeholder="CBRNE 类别"
        size="small"
        data-testid="cbrne-filter-category"
      >
        <el-option
          v-for="item in categoryOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="draft.source"
        clearable
        filterable
        placeholder="来源"
        size="small"
        data-testid="cbrne-filter-source"
      >
        <el-option
          v-for="item in sourceOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="draft.exposure_tier"
        clearable
        placeholder="T1–T4"
        size="small"
        data-testid="cbrne-filter-tier"
      >
        <el-option
          v-for="item in tierOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-input-number
        v-model="draft.difficulty_min"
        :min="0"
        :max="20"
        controls-position="right"
        size="small"
        placeholder="难度下限"
        data-testid="cbrne-filter-difficulty-min"
      />
      <el-input-number
        v-model="draft.difficulty_max"
        :min="0"
        :max="20"
        controls-position="right"
        size="small"
        placeholder="难度上限"
        data-testid="cbrne-filter-difficulty-max"
      />
      <el-button size="small" type="primary" :loading="isLoading" @click="applyFilters">
        查询
      </el-button>
      <el-button size="small" :disabled="isLoading" @click="resetFilters">重置</el-button>
    </section>

    <el-alert
      v-if="errorMessage"
      type="warning"
      :title="errorMessage"
      :closable="false"
      show-icon
    />

    <el-empty
      v-if="!isLoading && !errorMessage && total === 0"
      description="当前筛选条件下没有样本。请放宽标签、类别、来源、T1–T4 或难度范围。"
      data-testid="cbrne-query-empty"
    />

    <template v-else>
      <el-table
        v-loading="isLoading"
        :data="samples"
        size="small"
        row-key="sample_id"
        class="cbrne-query__table"
        data-testid="cbrne-query-table"
      >
        <el-table-column prop="sample_id" label="样本 ID" min-width="120" />
        <el-table-column prop="label" label="标签" width="88" />
        <el-table-column prop="cbrne_category" label="类别" min-width="110" />
        <el-table-column prop="source" label="来源" min-width="110" />
        <el-table-column prop="exposure_tier" label="T1–T4" width="80" />
        <el-table-column prop="evaluator_relative_difficulty" label="评估器相对难度" width="120" />
        <el-table-column
          prop="text_excerpt"
          label="脱敏摘要"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column label="引用" min-width="160">
          <template #default="{ row }">
            <code class="cbrne-query__ref">
              {{ row.resource_ref.asset_id }}#{{ row.sample_id }}
            </code>
          </template>
        </el-table-column>
        <el-table-column label="样本资源" width="130">
          <template #default="{ row }">
            <RouterLink
              class="cbrne-query__sample-link"
              data-testid="cbrne-sample-resource-link"
              :to="benchmarkSamplePath(props.asset.asset_id, row.sample_id)"
            >
              打开样本地址
            </RouterLink>
          </template>
        </el-table-column>
      </el-table>

      <div class="cbrne-query__pager">
        <span data-testid="cbrne-query-summary">
          共 {{ total }} 条 · 第 {{ currentPage }} / {{ totalPages }} 页 · 资产版本
          {{ assetVersion || '—' }}
        </span>
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          data-testid="cbrne-query-pagination"
          @current-change="handlePageChange"
        />
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { queryCbrneAnomalySamples } from '@/api/benchmark'
import type {
  BenchmarkArtifactItem,
  BenchmarkCbrneQueryFilters,
  BenchmarkCbrneSampleSummaryItem,
} from '@/types'
import {
  CBRNE_EXPOSURE_TIER_OPTIONS,
  CBRNE_LABEL_OPTIONS,
  CBRNE_QUERY_PAGE_SIZE,
  buildCbrneQueryParams,
  cbrneDistributionContext,
  emptyCbrneQueryFilters,
  isMaskedCbrneExcerpt,
  optionsFromCountMap,
} from '@/utils/benchmark/cbrneQuery'
import { benchmarkSamplePath } from '@/utils/benchmark/benchmarkAssetRoute'

const props = defineProps<{
  asset: BenchmarkArtifactItem
}>()

const isLoading = ref(false)
const hasLoaded = ref(false)
const errorMessage = ref('')
const samples = ref<BenchmarkCbrneSampleSummaryItem[]>([])
const total = ref(0)
const offset = ref(0)
const pageSize = CBRNE_QUERY_PAGE_SIZE
const assetVersion = ref('')
const recordVersion = ref('')

const draft = reactive<BenchmarkCbrneQueryFilters>(emptyCbrneQueryFilters())
const applied = reactive<BenchmarkCbrneQueryFilters>(emptyCbrneQueryFilters())

const labelOptions = CBRNE_LABEL_OPTIONS
const tierOptions = CBRNE_EXPOSURE_TIER_OPTIONS

const assetDistributions = computed(() => cbrneDistributionContext(props.asset))
const categoryOptions = computed(() =>
  optionsFromCountMap(assetDistributions.value.cbrne_category_counts),
)
const sourceOptions = computed(() => optionsFromCountMap(assetDistributions.value.source_counts))

const currentPage = computed(() => Math.floor(offset.value / pageSize) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize) || 1))
const shortRecordVersion = computed(() => {
  const value = recordVersion.value
  if (!value) return 'record —'
  return value.length > 12 ? `${value.slice(0, 12)}…` : value
})

const assetSampleCountLabel = computed(() => {
  const value = assetDistributions.value.sample_count
  return typeof value === 'number' ? String(value) : '—'
})

async function loadPage() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const params = buildCbrneQueryParams(applied, offset.value, pageSize)
    const data = await queryCbrneAnomalySamples(props.asset.asset_id, params)
    samples.value = data.samples
    total.value = data.total
    assetVersion.value = data.asset_version
    recordVersion.value = data.record_version
    for (const item of data.samples) {
      if (!isMaskedCbrneExcerpt(item.text_excerpt)) {
        errorMessage.value = '列表摘要未按脱敏规则返回，已阻止展示。'
        samples.value = []
        break
      }
    }
  } catch (error) {
    samples.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : 'CBRNE 查询失败'
  } finally {
    hasLoaded.value = true
    isLoading.value = false
  }
}

function applyFilters() {
  Object.assign(applied, {
    label: draft.label || undefined,
    cbrne_category: draft.cbrne_category || undefined,
    source: draft.source || undefined,
    exposure_tier: draft.exposure_tier || undefined,
    difficulty_min: typeof draft.difficulty_min === 'number' ? draft.difficulty_min : undefined,
    difficulty_max: typeof draft.difficulty_max === 'number' ? draft.difficulty_max : undefined,
  })
  offset.value = 0
  void loadPage()
}

function resetFilters() {
  Object.assign(draft, emptyCbrneQueryFilters())
  Object.assign(applied, emptyCbrneQueryFilters())
  offset.value = 0
  void loadPage()
}

function handlePageChange(page: number) {
  offset.value = Math.max(0, (page - 1) * pageSize)
  void loadPage()
}

watch(
  () => props.asset.asset_id,
  () => {
    Object.assign(draft, emptyCbrneQueryFilters())
    Object.assign(applied, emptyCbrneQueryFilters())
    offset.value = 0
    hasLoaded.value = false
    total.value = 0
    void loadPage()
  },
)

onMounted(() => {
  void loadPage()
})
</script>

<style scoped>
.cbrne-query {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: grid;
  gap: 12px;
}

.cbrne-query__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.cbrne-query__header h5 {
  margin: 0 0 4px;
  font-size: 14px;
}

.cbrne-query__header p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.cbrne-query__version {
  flex: 0 0 auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.cbrne-query__hit {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 700;
}

.cbrne-query__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.cbrne-query__filters :deep(.el-select),
.cbrne-query__filters :deep(.el-input-number) {
  width: 140px;
}

.cbrne-query__table {
  width: 100%;
}

.cbrne-query__ref {
  font-size: 11px;
  word-break: break-all;
}

.cbrne-query__sample-link {
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}

.cbrne-query__sample-link:hover,
.cbrne-query__sample-link:focus-visible {
  text-decoration: underline;
}

.cbrne-query__pager {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
