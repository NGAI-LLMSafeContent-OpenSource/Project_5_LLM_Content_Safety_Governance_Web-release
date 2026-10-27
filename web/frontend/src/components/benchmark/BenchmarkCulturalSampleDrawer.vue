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
    <div v-if="asset" class="cultural-sample-drawer">
      <section class="drawer-summary">
        <div>
          <h3>{{ asset.name }}</h3>
          <p>{{ sampleIntro }}</p>
        </div>
        <dl>
          <div>
            <dt>Total</dt>
            <dd>{{ getManifestNumber('sample_count') }}</dd>
          </div>
          <div>
            <dt>Review Passed</dt>
            <dd>{{ getManifestNumber('review_passed_count') }}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{{ asset.source_mode }}</dd>
          </div>
          <div>
            <dt>Model Eval</dt>
            <dd>{{ getManifestString('model_eval_status') }}</dd>
          </div>
        </dl>
      </section>

      <section class="sample-toolbar">
        <el-select
          v-model="filters.ethnic_group"
          clearable
          placeholder="民族"
          size="small"
          @change="handleSearch"
        >
          <el-option v-for="item in ethnicOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select
          v-model="filters.difficulty_level"
          clearable
          placeholder="难度"
          size="small"
          @change="handleSearch"
        >
          <el-option v-for="item in difficultyOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="检索 prompt / 期望答案 / review"
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
            <el-table-column prop="sample_id" label="ID" width="140" />
            <el-table-column prop="ethnic_group" label="民族" width="90" />
            <el-table-column prop="difficulty_level" label="难度" width="80" />
            <el-table-column prop="background_type" label="背景类型" width="96" />
            <el-table-column prop="persona" label="人设" width="120" show-overflow-tooltip />
            <el-table-column prop="query_type" label="问法" width="96" />
            <el-table-column
              prop="prompt_preview"
              label="Prompt Preview"
              min-width="260"
              show-overflow-tooltip
            />
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
            <p>点击左侧样本查看完整背景、问题、标准答案和 rubric。</p>
          </div>

          <template v-else>
            <div class="sample-detail__overview">
              <div class="sample-detail__header">
                <div>
                  <h4>{{ selectedDetail.sample_id }}</h4>
                  <span>
                    {{ selectedDetail.ethnic_group }} · {{ selectedDetail.difficulty_level }}
                  </span>
                </div>
                <el-tag size="small">{{ selectedDetail.background_type }}</el-tag>
              </div>
              <dl class="detail-meta">
                <div class="detail-meta__item">
                  <dt>Persona</dt>
                  <dd>{{ selectedDetail.persona }}</dd>
                </div>
                <div class="detail-meta__item">
                  <dt>Query Type</dt>
                  <dd>{{ selectedDetail.query_type }}</dd>
                </div>
                <div class="detail-meta__item">
                  <dt>Review</dt>
                  <dd>{{ selectedDetail.review.overall_passed ? 'passed' : 'failed' }}</dd>
                  <small>score {{ selectedDetail.review.cultural_accuracy ?? '-' }}</small>
                </div>
              </dl>
            </div>

            <div class="detail-block">
              <b>Background</b>
              <p>{{ selectedDetail.background }}</p>
            </div>
            <div class="detail-block">
              <b>User Query</b>
              <p>{{ selectedDetail.user_query }}</p>
            </div>
            <div class="detail-block">
              <b>Expected Answer</b>
              <p>{{ selectedDetail.expected_answer }}</p>
            </div>
            <div class="detail-block">
              <b>Knowledge Points</b>
              <ul>
                <li v-for="(item, index) in selectedDetail.cultural_knowledge_points" :key="index">
                  {{ item }}
                </li>
              </ul>
            </div>
            <div class="detail-block">
              <b>Rubric Must-have</b>
              <ul>
                <li v-for="(item, index) in selectedDetail.rubric.must_have" :key="`m-${index}`">
                  {{ item }}
                </li>
              </ul>
            </div>
            <div class="detail-block is-reason">
              <b>Rubric Penalty</b>
              <ul>
                <li v-for="(item, index) in selectedDetail.rubric.penalty" :key="`p-${index}`">
                  {{ item }}
                </li>
              </ul>
            </div>
            <div class="detail-block is-reason">
              <b>Review Reason</b>
              <p>{{ selectedDetail.review.reason || '-' }}</p>
            </div>
          </template>
        </aside>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { getTopic3CulturalSampleDetail, getTopic3CulturalSamples } from '@/api/benchmark'
import type {
  BenchmarkArtifactItem,
  BenchmarkTopic3CulturalSampleDetail,
  BenchmarkTopic3CulturalSampleItem,
} from '@/types'

const props = defineProps<{
  modelValue: boolean
  asset: BenchmarkArtifactItem | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const samples = ref<BenchmarkTopic3CulturalSampleItem[]>([])
const selectedDetail = ref<BenchmarkTopic3CulturalSampleDetail | null>(null)
const isLoading = ref(false)
const isLoadingDetail = ref(false)
const errorMessage = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const samplesRequestSeq = ref(0)
const detailRequestSeq = ref(0)
const filters = reactive({
  ethnic_group: '',
  difficulty_level: '',
  keyword: '',
})

const ethnicOptions = ['回族', '蒙古族', '维吾尔族', '藏族']
const difficultyOptions = ['L1', 'L2', 'L3']

const drawerTitle = computed(() => (props.asset ? `样本详情：${props.asset.name}` : '样本详情'))
const sampleIntro = computed(() =>
  props.asset?.source_mode === 'live_run'
    ? '该资产来自课题三文化多样性语料现场生成，包含背景、用户问题、标准答案、rubric 与文化审核结果。'
    : '该资产来自课题三文化多样性语料预跑批次，包含背景、用户问题、标准答案、rubric 与文化审核结果。',
)

watch(
  () => props.asset?.asset_id,
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

function getManifestNumber(key: string) {
  const value = props.asset?.manifest[key]
  return typeof value === 'number' ? value : '-'
}

function getManifestString(key: string) {
  const value = props.asset?.manifest[key]
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  return '-'
}

async function loadSamples() {
  if (!props.asset) {
    return
  }
  const requestSeq = ++samplesRequestSeq.value
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic3CulturalSamples(props.asset.asset_id, {
      ethnic_group: filters.ethnic_group || undefined,
      difficulty_level: filters.difficulty_level || undefined,
      keyword: filters.keyword.trim() || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })
    if (requestSeq !== samplesRequestSeq.value) {
      return
    }
    samples.value = response.samples
    total.value = response.total
  } catch (error) {
    if (requestSeq !== samplesRequestSeq.value) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '文化样本读取失败'
    samples.value = []
    total.value = 0
  } finally {
    if (requestSeq === samplesRequestSeq.value) {
      isLoading.value = false
    }
  }
}

async function loadDetail(row: BenchmarkTopic3CulturalSampleItem) {
  if (!props.asset) {
    return
  }
  const requestSeq = ++detailRequestSeq.value
  isLoadingDetail.value = true
  try {
    const response = await getTopic3CulturalSampleDetail(props.asset.asset_id, row.sample_id)
    if (requestSeq !== detailRequestSeq.value) {
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
  filters.ethnic_group = ''
  filters.difficulty_level = ''
  filters.keyword = ''
}
</script>

<style scoped>
.cultural-sample-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.drawer-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 500px);
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

.drawer-summary dl,
.detail-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
}

.sample-toolbar {
  display: grid;
  grid-template-columns: 150px 120px minmax(220px, 1fr) auto;
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

.sample-detail__empty p {
  margin: 8px 0 0;
  color: var(--text-secondary);
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

.sample-detail__header h4 {
  margin: 0;
}

.sample-detail__header span {
  display: inline-block;
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.detail-meta small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
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

.detail-block p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.detail-block ul {
  margin: 0;
  padding-left: 16px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.detail-block.is-reason {
  background: #fffaf2;
}

@media (max-width: 1100px) {
  .drawer-summary,
  .sample-layout {
    grid-template-columns: 1fr;
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
