<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="82%"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @opened="loadSamples"
    @closed="handleClosed"
  >
    <div v-if="assetId" class="risk-sample-drawer">
      <section class="drawer-summary">
        <div>
          <h3>{{ assetNameLabel }}</h3>
          <p>
            样本详情展示全文、response 和 label_reason。缺失标注理由时显示“未提供标注理由”；
            理由与参考类别冲突时显示评测完整性告警。
          </p>
          <p class="drawer-identity">
            评测对象版本 {{ assetVersionLabel }} · 资产 {{ assetId }} · 内容哈希
            {{ assetSha256 || '—' }}
          </p>
        </div>
        <dl>
          <div>
            <dt>Safe</dt>
            <dd>{{ safeCount }}</dd>
          </div>
          <div>
            <dt>Low</dt>
            <dd>{{ levelCount('low') }}</dd>
          </div>
          <div>
            <dt>Medium</dt>
            <dd>{{ levelCount('medium') }}</dd>
          </div>
          <div>
            <dt>High</dt>
            <dd>{{ levelCount('high') }}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>{{ totalCount }}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{{ assetVersionLabel }}</dd>
          </div>
        </dl>
      </section>

      <section class="sample-toolbar">
        <el-segmented
          v-model="filters.risk_level_id"
          :options="levelOptions"
          @change="handleSearch"
        />
        <el-select
          v-model="filters.category"
          clearable
          filterable
          placeholder="风险大类"
          size="small"
          @change="handleSearch"
        >
          <el-option
            v-for="item in categoryOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="检索 prompt / response / label_reason"
          size="small"
          @keyup.enter="handleSearch"
        />
        <el-button size="small" type="primary" :loading="isLoading" @click="handleSearch">
          查询
        </el-button>
      </section>

      <el-alert
        v-if="errorMessage"
        type="warning"
        :title="errorMessage"
        :closable="false"
        show-icon
      />

      <section class="sample-layout">
        <div class="sample-table-wrap">
          <el-table
            v-loading="isLoading"
            :data="samples"
            height="520"
            size="small"
            row-key="sample_id"
            highlight-current-row
            @row-click="loadDetail"
          >
            <el-table-column prop="sample_id" label="ID" width="88" />
            <el-table-column prop="risk_level_id" label="Level" width="88">
              <template #default="{ row }">
                <el-tag :type="getRiskLevelTagType(row.risk_level_id)" size="small">
                  {{ row.risk_level_id }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="risk_category_code" label="类别" width="76" />
            <el-table-column
              prop="risk_sub_category"
              label="子类"
              min-width="150"
              show-overflow-tooltip
            />
            <el-table-column
              prop="prompt_preview"
              label="Prompt Preview"
              min-width="220"
              show-overflow-tooltip
            />
            <el-table-column
              prop="response_preview"
              label="Response Preview"
              min-width="240"
              show-overflow-tooltip
            />
            <el-table-column label="Label Reason" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.label_reason_preview || '未提供标注理由' }}
              </template>
            </el-table-column>
          </el-table>

          <div class="sample-pagination">
            <span>共 {{ total }} 条</span>
            <el-pagination
              background
              layout="prev, pager, next, sizes"
              :page-sizes="[10, 20, 50, 100]"
              :current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              @current-change="handlePageChange"
              @size-change="handlePageSizeChange"
            />
          </div>
        </div>

        <aside v-loading="isLoadingDetail" class="sample-detail">
          <div v-if="!selectedDetail" class="sample-detail__empty">
            <h4>样本详情</h4>
            <p>点击左侧样本查看完整 prompt、response 和 label_reason。</p>
          </div>

          <template v-else>
            <div class="sample-detail__overview">
              <div class="sample-detail__header">
                <div>
                  <h4>{{ selectedDetail.sample_id }}</h4>
                  <span>{{ selectedDetail.risk_category }}</span>
                </div>
                <el-tag :type="getRiskLevelTagType(selectedDetail.risk_level_id)" size="small">
                  {{ selectedDetail.risk_level_id }}
                </el-tag>
              </div>

              <dl class="detail-meta">
                <div class="detail-meta__item is-wide">
                  <dt>Risk Sub Category</dt>
                  <dd>{{ selectedDetail.risk_sub_category }}</dd>
                </div>
                <div class="detail-meta__item">
                  <dt>Safe Type</dt>
                  <dd>{{ selectedDetail.safe_type }}</dd>
                  <small>{{ selectedDetail.safe_mode }}</small>
                </div>
                <div class="detail-meta__item">
                  <dt>Source Index</dt>
                  <dd>{{ selectedDetail.source_index }}</dd>
                </div>
              </dl>

              <p
                v-if="selectedDetail.warning_note"
                class="detail-note"
                :title="selectedDetail.warning_note"
              >
                {{ selectedDetail.warning_note }}
              </p>
            </div>

            <div class="detail-block">
              <b>Prompt</b>
              <p>{{ selectedDetail.prompt }}</p>
            </div>
            <div class="detail-block">
              <b>Response</b>
              <p>{{ selectedDetail.response }}</p>
            </div>
            <div class="detail-block is-reason">
              <b>Label Reason</b>
              <p v-if="isLabelReasonMissing">未提供标注理由</p>
              <p v-else>{{ selectedDetail.label_reason }}</p>
            </div>
            <div
              v-if="selectedDetail.integrity_warnings?.length"
              class="integrity-warning"
              role="alert"
            >
              <b>评测完整性告警</b>
              <ul>
                <li v-for="warning in selectedDetail.integrity_warnings" :key="warning.code">
                  {{ warning.message }}
                </li>
              </ul>
              <p>该标注理由不进入自动治理解释。</p>
            </div>
          </template>
        </aside>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { getTopic3RiskSampleDetail, getTopic3RiskSamples } from '@/api/benchmark'
import type { BenchmarkTopic3RiskSampleDetail, BenchmarkTopic3RiskSampleItem } from '@/types'

const props = defineProps<{
  modelValue: boolean
  assetId: string | null
  assetName?: string
  assetVersion?: string | null
  assetSha256?: string
  sampleCount?: number | null
  riskLevelDistribution?: Record<string, number>
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const samples = ref<BenchmarkTopic3RiskSampleItem[]>([])
const selectedDetail = ref<BenchmarkTopic3RiskSampleDetail | null>(null)
const isLoading = ref(false)
const isLoadingDetail = ref(false)
const errorMessage = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const samplesRequestSeq = ref(0)
const detailRequestSeq = ref(0)
const filters = reactive({
  risk_level_id: '',
  category: '',
  keyword: '',
})

const levelOptions = [
  { label: '全部', value: '' },
  { label: 'Safe', value: 'safe' },
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
]

const categoryOptions = Array.from({ length: 17 }, (_, index) => {
  const value = `C${String(index + 1).padStart(2, '0')}`
  return { label: value, value }
})

const drawerTitle = computed(() =>
  props.assetId ? `样本详情：${assetNameLabel.value}` : '样本详情',
)
const assetNameLabel = computed(() => props.assetName || '课题三风险 Benchmark')
const assetVersionLabel = computed(() => props.assetVersion || '未登记')
const totalCount = computed(() => (typeof props.sampleCount === 'number' ? props.sampleCount : '—'))
const safeCount = computed(() => levelCount('safe'))

const isLabelReasonMissing = computed(() => {
  const detail = selectedDetail.value
  if (!detail) return false
  if (detail.label_reason_status) {
    return detail.label_reason_status !== '已提供'
  }
  return !detail.label_reason?.trim()
})

watch(
  () => props.assetId,
  () => {
    samplesRequestSeq.value += 1
    detailRequestSeq.value += 1
    samples.value = []
    selectedDetail.value = null
    total.value = 0
    currentPage.value = 1
    errorMessage.value = ''
    resetFilters()
  },
)

function levelCount(level: string) {
  const value = props.riskLevelDistribution?.[level]
  return typeof value === 'number' ? value : '—'
}

function getRiskLevelTagType(level: string) {
  if (level === 'safe') {
    return 'success'
  }
  if (level === 'low') {
    return 'warning'
  }
  if (level === 'medium') {
    return 'primary'
  }
  return 'danger'
}

function responseMatchesSelectedAsset(assetId?: string, assetSha256?: string) {
  if (!props.assetId || assetId !== props.assetId) return false
  if (props.assetSha256 && assetSha256 !== props.assetSha256) return false
  return true
}

async function loadSamples() {
  if (!props.assetId) {
    return
  }
  const requestSeq = ++samplesRequestSeq.value
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic3RiskSamples(props.assetId, {
      risk_level_id: filters.risk_level_id || undefined,
      category: filters.category || undefined,
      keyword: filters.keyword.trim() || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })
    if (requestSeq !== samplesRequestSeq.value) {
      return
    }
    if (!responseMatchesSelectedAsset(response.asset_id, response.asset_sha256)) {
      errorMessage.value = '样本结果与所选资产标识或内容哈希不一致，已停止展示以避免跨版本拼接。'
      samples.value = []
      total.value = 0
      return
    }
    samples.value = response.samples
    total.value = response.total
    if (
      selectedDetail.value &&
      !samples.value.some((item) => item.sample_id === selectedDetail.value?.sample_id)
    ) {
      selectedDetail.value = null
    }
  } catch (error) {
    if (requestSeq !== samplesRequestSeq.value) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '动态风险样本读取失败'
    samples.value = []
    total.value = 0
  } finally {
    if (requestSeq === samplesRequestSeq.value) {
      isLoading.value = false
    }
  }
}

async function loadDetail(row: BenchmarkTopic3RiskSampleItem) {
  if (!props.assetId) {
    return
  }
  const requestSeq = ++detailRequestSeq.value
  isLoadingDetail.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic3RiskSampleDetail(props.assetId, row.sample_id)
    if (requestSeq !== detailRequestSeq.value) {
      return
    }
    if (!responseMatchesSelectedAsset(response.asset_id, response.asset_sha256)) {
      selectedDetail.value = null
      errorMessage.value = '样本详情与所选资产标识或内容哈希不一致，已停止展示以避免跨版本拼接。'
      return
    }
    selectedDetail.value = response
  } catch (error) {
    if (requestSeq !== detailRequestSeq.value) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '样本详情读取失败'
  } finally {
    if (requestSeq === detailRequestSeq.value) {
      isLoadingDetail.value = false
    }
  }
}

function handleSearch() {
  currentPage.value = 1
  selectedDetail.value = null
  void loadSamples()
}

function handlePageChange(page: number) {
  currentPage.value = page
  void loadSamples()
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  void loadSamples()
}

function handleClosed() {
  samplesRequestSeq.value += 1
  detailRequestSeq.value += 1
  selectedDetail.value = null
  errorMessage.value = ''
  isLoading.value = false
  isLoadingDetail.value = false
}

function resetFilters() {
  filters.risk_level_id = ''
  filters.category = ''
  filters.keyword = ''
}
</script>

<style scoped>
.risk-sample-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.drawer-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: 16px;
  padding: 16px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.drawer-summary h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
}

.drawer-summary p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.drawer-identity {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow-wrap: anywhere;
}

.integrity-warning {
  padding: 10px 12px;
  border: 1px solid #ffe1ad;
  border-radius: 8px;
  background: #fff7e8;
  color: #8a5a11;
  font-size: 12px;
  line-height: 1.6;
}

.integrity-warning b {
  color: #8a5a11;
}

.integrity-warning ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.integrity-warning p {
  margin: 6px 0 0;
}

.drawer-summary dl,
.detail-meta {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.drawer-summary dt,
.detail-meta dt {
  color: var(--text-muted);
  font-size: 12px;
}

.drawer-summary dd,
.detail-meta dd {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.sample-toolbar {
  display: grid;
  grid-template-columns: 320px 160px minmax(220px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.sample-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.8fr);
  gap: 16px;
  min-height: 560px;
}

.sample-table-wrap,
.sample-detail {
  min-width: 0;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.sample-table-wrap {
  overflow: hidden;
}

.sample-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.sample-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 590px;
  overflow: auto;
  padding: 16px;
}

.sample-detail__empty {
  color: var(--text-secondary);
}

.sample-detail__empty h4,
.sample-detail__header h4 {
  margin: 0;
  color: var(--text-primary);
}

.sample-detail__empty p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
}

.sample-detail__overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e7eef7;
}

.sample-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.sample-detail__header span {
  display: inline-block;
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.detail-meta {
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) minmax(72px, 0.55fr);
  gap: 10px;
}

.detail-meta__item {
  min-width: 0;
}

.detail-meta__item.is-wide dd {
  white-space: normal;
}

.detail-meta small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.detail-note {
  display: -webkit-box;
  margin: 0;
  padding: 9px 10px;
  overflow: hidden;
  color: #8a5a11;
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
  background: #fff7e8;
  border: 1px solid #ffe1ad;
  border-radius: 6px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 8px;
  background: #f8fbff;
}

.detail-block b {
  color: var(--text-primary);
  font-size: 13px;
}

.detail-block p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.detail-block.is-reason {
  background: #fffaf2;
}

@media (max-width: 1100px) {
  .drawer-summary,
  .sample-layout {
    grid-template-columns: 1fr;
  }

  .sample-toolbar {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .drawer-summary dl,
  .detail-meta,
  .sample-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
