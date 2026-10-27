<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="88%"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @closed="handleClosed"
  >
    <div v-if="asset" class="valueqa-drawer">
      <section class="drawer-summary">
        <div>
          <h3>{{ asset.name }}</h3>
          <p>
            左侧按三档对照组展示 preview，右侧展示同组高 / 中 / 低完整问题、回答和质检追踪信息。
          </p>
        </div>
        <dl>
          <div>
            <dt>样本数</dt>
            <dd>{{ getManifestNumber('sample_count') }}</dd>
          </div>
          <div>
            <dt>三档对照组</dt>
            <dd>{{ groupCount }}</dd>
          </div>
          <div>
            <dt>人工抽检</dt>
            <dd>{{ getQcImportLabel() }}</dd>
          </div>
        </dl>
      </section>

      <section class="sample-toolbar">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="关键词"
          size="small"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-input
          v-model="filters.topic"
          clearable
          placeholder="topic"
          size="small"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-input
          v-model="filters.primaryDimension"
          clearable
          placeholder="primary dimension"
          size="small"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-input
          v-model="filters.secondaryDimension"
          clearable
          placeholder="secondary dimension"
          size="small"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-segmented
          v-model="filters.qcStatus"
          :options="qcStatusOptions"
          @change="handleSearch"
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
            :data="groups"
            height="520"
            size="small"
            row-key="group_id"
            highlight-current-row
            @row-click="selectGroup"
          >
            <el-table-column prop="topic" label="Topic" width="150" show-overflow-tooltip />
            <el-table-column
              prop="secondary_dimension"
              label="Dimension"
              width="180"
              show-overflow-tooltip
            />
            <el-table-column label="high preview" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.levels.high?.answer_preview || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="medium preview" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.levels.medium?.answer_preview || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="low preview" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.levels.low?.answer_preview || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="人工抽检" width="120">
              <template #default="{ row }">
                <el-tag :type="row.qc_status === 'qc_sampled' ? 'success' : 'info'" size="small">
                  {{ getGroupQcLabel(row.qc_status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="sample-pagination">
            <span>共 {{ total }} 组</span>
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
            <h4>高 / 中 / 低三档详情</h4>
            <p>点击左侧对照组，查看同组高 / 中 / 低三档的问题、回答和质检信息。</p>
          </div>
          <template v-else>
            <div class="sample-detail__header">
              <div>
                <h4>
                  {{ selectedDetail.topic || selectedDetail.secondary_dimension || '三档对照组' }}
                </h4>
                <span>{{ selectedDetail.secondary_dimension || '-' }}</span>
              </div>
              <el-tag
                :type="selectedDetail.qc_status === 'qc_sampled' ? 'success' : 'info'"
                size="small"
              >
                {{ getGroupQcLabel(selectedDetail.qc_status) }}
              </el-tag>
            </div>

            <dl class="detail-meta">
              <div>
                <dt>Primary</dt>
                <dd>{{ selectedDetail.primary_dimension || '-' }}</dd>
              </div>
              <div>
                <dt>Secondary</dt>
                <dd>{{ selectedDetail.secondary_dimension || '-' }}</dd>
              </div>
              <div>
                <dt>Group</dt>
                <dd>{{ getReadableGroupLabel(selectedDetail) }}</dd>
              </div>
              <div class="detail-meta__id">
                <dt>组 ID</dt>
                <dd class="mono">{{ selectedDetail.group_id }}</dd>
              </div>
            </dl>

            <div class="level-samples">
              <article
                v-for="level in qualityLevels"
                :key="level"
                class="level-card"
                :class="{ 'has-trace-mismatch': isTraceMismatch(selectedDetail.levels[level]) }"
              >
                <div class="level-card__header">
                  <div>
                    <h5>{{ levelLabelMap[level] }}</h5>
                    <span class="mono">{{ selectedDetail.levels[level]?.sample_id || '-' }}</span>
                  </div>
                  <div class="level-card__tags">
                    <el-tag
                      :type="
                        selectedDetail.levels[level]?.qc_status === 'qc_sampled'
                          ? 'success'
                          : 'info'
                      "
                      size="small"
                    >
                      {{ getGroupQcLabel(selectedDetail.levels[level]?.qc_status) }}
                    </el-tag>
                    <el-tag
                      v-if="hasTraceRecheck(selectedDetail.levels[level])"
                      :type="getTraceMatchType(selectedDetail.levels[level])"
                      size="small"
                    >
                      {{ getTraceMatchLabel(selectedDetail.levels[level]) }}
                    </el-tag>
                  </div>
                </div>
                <div class="level-card__meta">
                  <span>Prompt {{ selectedDetail.levels[level]?.prompt_snapshot || '-' }}</span>
                  <span>
                    漏标数 {{ selectedDetail.levels[level]?.missing_annotation_count ?? 0 }}
                  </span>
                  <span v-if="selectedDetail.levels[level]?.trace_predicted_level">
                    复判 {{ selectedDetail.levels[level]?.trace_predicted_level }}
                  </span>
                  <span v-if="selectedDetail.levels[level]?.trace_issue_count">
                    复判问题 {{ selectedDetail.levels[level]?.trace_issue_count }}
                  </span>
                  <span v-if="selectedDetail.levels[level]?.manual_marked_at">人工标注</span>
                </div>
                <b>问题</b>
                <p>{{ selectedDetail.levels[level]?.question || '-' }}</p>
                <b>回答</b>
                <p>{{ selectedDetail.levels[level]?.answer || '-' }}</p>
                <div v-if="hasTraceRecheck(selectedDetail.levels[level])" class="recheck-panel">
                  <div class="recheck-panel__head">
                    <b>复判结果</b>
                    <span>{{ getTraceIssueCountLabel(selectedDetail.levels[level]) }}</span>
                  </div>
                  <dl class="recheck-fields">
                    <div>
                      <dt>原始档位</dt>
                      <dd>{{ selectedDetail.levels[level]?.quality_level || '-' }}</dd>
                    </div>
                    <div>
                      <dt>复判档位</dt>
                      <dd>{{ selectedDetail.levels[level]?.trace_predicted_level || '-' }}</dd>
                    </div>
                    <div>
                      <dt>一致性</dt>
                      <dd>{{ getTraceMatchLabel(selectedDetail.levels[level]) }}</dd>
                    </div>
                    <div>
                      <dt>复判问题数</dt>
                      <dd>{{ getTraceIssueCount(selectedDetail.levels[level]) }}</dd>
                    </div>
                  </dl>
                  <div
                    v-if="getTraceIssues(selectedDetail.levels[level]).length > 0"
                    class="trace-issues"
                  >
                    <article
                      v-for="(issue, issueIndex) in getTraceIssues(selectedDetail.levels[level])"
                      :key="issueIndex"
                      class="trace-issue"
                    >
                      <span class="trace-issue__type">{{ getTraceIssueType(issue) }}</span>
                      <p v-if="getTraceIssueSpan(issue)">
                        <b>片段</b>
                        {{ getTraceIssueSpan(issue) }}
                      </p>
                      <p v-if="getTraceIssueReason(issue)">
                        <b>原因</b>
                        {{ getTraceIssueReason(issue) }}
                      </p>
                    </article>
                  </div>
                  <p v-else class="trace-empty">当前复判未返回可展示的问题片段。</p>
                </div>
                <details
                  v-if="hasSourceReference(selectedDetail.levels[level]?.source_reference)"
                  class="source-reference"
                >
                  <summary>Source reference</summary>
                  <pre>{{
                    formatSourceReference(selectedDetail.levels[level]?.source_reference)
                  }}</pre>
                </details>
              </article>
            </div>
          </template>
        </aside>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { getTopic1ValueQaGroupDetail, getTopic1ValueQaGroups } from '@/api/benchmark'
import type {
  BenchmarkArtifactItem,
  BenchmarkTopic1ValueQaGroupDetail,
  BenchmarkTopic1ValueQaGroupItem,
  BenchmarkTopic1ValueQaLevelDetail,
  BenchmarkTopic1ValueQaTraceIssue,
} from '@/types'

const props = defineProps<{
  modelValue: boolean
  asset: BenchmarkArtifactItem | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const groups = ref<BenchmarkTopic1ValueQaGroupItem[]>([])
const selectedDetail = ref<BenchmarkTopic1ValueQaGroupDetail | null>(null)
const total = ref(0)
const pageSize = ref(20)
const currentPage = ref(1)
const isLoading = ref(false)
const isLoadingDetail = ref(false)
const errorMessage = ref('')
const groupsRequestSeq = ref(0)
const detailRequestSeq = ref(0)
const qualityLevels = ['high', 'medium', 'low'] as const
type ValueQaLevelSample = BenchmarkTopic1ValueQaLevelDetail | undefined
const levelLabelMap = {
  high: 'HIGH 高质量回答',
  medium: 'MEDIUM 中等质量回答',
  low: 'LOW 低质量回答',
} as const

const filters = reactive<{
  keyword: string
  topic: string
  primaryDimension: string
  secondaryDimension: string
  qcStatus: '' | 'not_sampled' | 'qc_sampled'
}>({
  keyword: '',
  topic: '',
  primaryDimension: '',
  secondaryDimension: '',
  qcStatus: '',
})

const qcStatusOptions = [
  { label: '全部抽检状态', value: '' },
  { label: '人工抽检覆盖', value: 'qc_sampled' },
  { label: '未抽检', value: 'not_sampled' },
]

const drawerTitle = computed(() => {
  return props.asset
    ? `课题一 value_qa 三档样本 · ${props.asset.asset_id}`
    : '课题一 value_qa 三档样本'
})
const groupCount = computed(() => {
  return getManifestNumber('group_count') || total.value
})

watch(
  () => props.asset?.asset_id,
  () => {
    groupsRequestSeq.value += 1
    detailRequestSeq.value += 1
    groups.value = []
    selectedDetail.value = null
    total.value = 0
    currentPage.value = 1
    errorMessage.value = ''
  },
)

watch(
  [() => props.modelValue, () => props.asset?.asset_id],
  ([visible, assetId]) => {
    if (visible && assetId) {
      void loadGroups()
    }
  },
  { flush: 'post' },
)

async function loadGroups() {
  if (!props.asset) {
    return
  }
  const requestSeq = ++groupsRequestSeq.value
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic1ValueQaGroups(props.asset.asset_id, {
      keyword: filters.keyword || undefined,
      topic: filters.topic || undefined,
      primary_dimension: filters.primaryDimension || undefined,
      secondary_dimension: filters.secondaryDimension || undefined,
      qc_status: filters.qcStatus || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })
    if (requestSeq !== groupsRequestSeq.value) {
      return
    }
    groups.value = response.groups
    total.value = response.total
    if (response.groups[0]) {
      void loadDetail(response.groups[0])
    } else {
      selectedDetail.value = null
    }
  } catch (error) {
    if (requestSeq !== groupsRequestSeq.value) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '三档样本读取失败'
    groups.value = []
    selectedDetail.value = null
    total.value = 0
  } finally {
    if (requestSeq === groupsRequestSeq.value) {
      isLoading.value = false
    }
  }
}

async function loadDetail(group: BenchmarkTopic1ValueQaGroupItem) {
  if (!props.asset) {
    return
  }
  const requestSeq = ++detailRequestSeq.value
  isLoadingDetail.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic1ValueQaGroupDetail(props.asset.asset_id, group.group_id)
    if (requestSeq !== detailRequestSeq.value) {
      return
    }
    selectedDetail.value = response
  } catch (error) {
    if (requestSeq !== detailRequestSeq.value) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '三档详情读取失败'
  } finally {
    if (requestSeq === detailRequestSeq.value) {
      isLoadingDetail.value = false
    }
  }
}

function handleSearch() {
  currentPage.value = 1
  selectedDetail.value = null
  void loadGroups()
}

function handlePageChange(page: number) {
  currentPage.value = page
  void loadGroups()
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  void loadGroups()
}

function selectGroup(group: BenchmarkTopic1ValueQaGroupItem) {
  void loadDetail(group)
}

function handleClosed() {
  groupsRequestSeq.value += 1
  detailRequestSeq.value += 1
  groups.value = []
  selectedDetail.value = null
  errorMessage.value = ''
  isLoading.value = false
  isLoadingDetail.value = false
}

function getManifestString(key: string) {
  const value = props.asset?.manifest[key]
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '-'
}

function getQcImportLabel() {
  return getManifestString('qc_status') === 'imported'
    ? '人工抽检状态已导入'
    : getManifestString('qc_status')
}

function getGroupQcLabel(value?: string) {
  return value === 'qc_sampled' ? '人工抽检覆盖' : '未抽检'
}

function getReadableGroupLabel(group: BenchmarkTopic1ValueQaGroupDetail) {
  return [group.topic, group.secondary_dimension].filter(Boolean).join(' / ') || '-'
}

function hasSourceReference(value?: Record<string, unknown>) {
  return Boolean(value && Object.keys(value).length > 0)
}

function formatSourceReference(value?: Record<string, unknown>) {
  if (!value) {
    return ''
  }
  return JSON.stringify(value, null, 2)
}

function hasTraceRecheck(sample: ValueQaLevelSample) {
  return Boolean(
    sample?.trace_predicted_level ||
    sample?.trace_true_label ||
    sample?.trace_match_status ||
    getTraceIssueCount(sample) > 0,
  )
}

function isTraceMismatch(sample: ValueQaLevelSample) {
  if (!sample) {
    return false
  }
  if (sample.trace_is_consistent === false || sample.trace_match_status === 'mismatched') {
    return true
  }
  if (sample.trace_predicted_level && sample.quality_level) {
    return sample.trace_predicted_level !== sample.quality_level
  }
  return false
}

function getTraceMatchType(sample: ValueQaLevelSample) {
  if (!hasTraceRecheck(sample)) {
    return 'info'
  }
  return isTraceMismatch(sample) ? 'danger' : 'success'
}

function getTraceMatchLabel(sample: ValueQaLevelSample) {
  if (!hasTraceRecheck(sample)) {
    return '未复判'
  }
  return isTraceMismatch(sample) ? '复判不一致' : '复判一致'
}

function getTraceIssueCount(sample: ValueQaLevelSample) {
  if (typeof sample?.trace_issue_count === 'number') {
    return sample.trace_issue_count
  }
  return getTraceIssues(sample).length
}

function getTraceIssueCountLabel(sample: ValueQaLevelSample) {
  return `复判问题 ${getTraceIssueCount(sample)}`
}

function getTraceIssues(sample: ValueQaLevelSample) {
  return Array.isArray(sample?.trace_low_issue_spans) ? sample.trace_low_issue_spans : []
}

function getTraceIssueType(issue: BenchmarkTopic1ValueQaTraceIssue) {
  return (
    stringifyTraceIssueField(issue.type) || stringifyTraceIssueField(issue.issue_type) || 'issue'
  )
}

function getTraceIssueSpan(issue: BenchmarkTopic1ValueQaTraceIssue) {
  return stringifyTraceIssueField(issue.span)
}

function getTraceIssueReason(issue: BenchmarkTopic1ValueQaTraceIssue) {
  return stringifyTraceIssueField(issue.reason) || stringifyTraceIssueField(issue.rationale)
}

function stringifyTraceIssueField(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function getManifestNumber(key: string) {
  const value = props.asset?.manifest[key]
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}
</script>

<style scoped>
.valueqa-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.drawer-summary h3 {
  margin: 0;
  color: var(--text-primary);
}

.drawer-summary p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.drawer-summary dl,
.detail-meta {
  display: grid;
  gap: 10px;
  margin: 0;
}

.drawer-summary dl {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.detail-meta {
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.sample-toolbar .el-input {
  width: 180px;
}

.sample-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(380px, 0.9fr);
  gap: 14px;
}

.sample-table-wrap,
.sample-detail {
  min-width: 0;
}

.sample-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.sample-detail {
  display: flex;
  min-height: 520px;
  max-height: 590px;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
  padding: 14px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.sample-detail__empty {
  color: var(--text-secondary);
}

.sample-detail__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.sample-detail__header h4 {
  margin: 0;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.sample-detail__header span {
  color: var(--text-muted);
  font-size: 12px;
}

.level-samples {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.level-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.level-card.has-trace-mismatch {
  border-color: rgba(211, 47, 47, 0.32);
  background: #fffafa;
}

.level-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.level-card__tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.level-card h5 {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  text-transform: uppercase;
}

.level-card__header > div {
  min-width: 0;
}

.level-card__header .mono {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.level-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.level-card__meta span {
  padding: 2px 6px;
  border-radius: 4px;
  background: #eef4fb;
  color: var(--text-secondary);
  font-size: 11px;
}

.level-card b {
  color: var(--text-muted);
  font-size: 12px;
}

.level-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.recheck-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(0, 121, 107, 0.16);
  border-radius: 8px;
  background: #fff;
}

.recheck-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.recheck-panel__head span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.recheck-fields {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.recheck-fields div {
  min-width: 0;
  padding: 8px;
  border-radius: 6px;
  background: #f8fbff;
}

.recheck-fields dt {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}

.recheck-fields dd {
  margin: 3px 0 0;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 800;
}

.trace-issues {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trace-issue {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 8px;
  border-radius: 6px;
  background: #f7fcfb;
}

.trace-issue__type {
  align-self: flex-start;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(0, 121, 107, 0.1);
  color: #00796b;
  font-size: 11px;
  font-weight: 800;
}

.trace-issue p {
  display: flex;
  gap: 6px;
}

.trace-issue p b {
  flex: 0 0 auto;
}

.trace-empty {
  color: var(--text-muted);
}

.source-reference {
  color: var(--text-secondary);
  font-size: 12px;
}

.source-reference summary {
  cursor: pointer;
  color: var(--text-primary);
  font-weight: 700;
}

.source-reference pre {
  max-height: 160px;
  overflow: auto;
  margin: 8px 0 0;
  padding: 8px;
  border: 1px solid #dbe5f1;
  border-radius: 6px;
  background: #fff;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
}

@media (max-width: 1100px) {
  .sample-layout {
    grid-template-columns: 1fr;
  }

  .detail-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .recheck-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
