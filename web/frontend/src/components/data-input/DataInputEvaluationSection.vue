<template>
  <div class="data-input-stage-section data-input-stage-section--spaced">
    <h4 class="data-input-stage-section__title">个例展示 · 评估结果</h4>
    <p class="eval-stage-hint">
      本页聚焦「判得怎样」：判定 / 档位、分数与摘要。证据链与修正处置分别在归因、修正页展开。
    </p>

    <div v-if="assessmentRows.length === 0" class="data-input-empty-state">
      <strong>{{ emptyTitle }}</strong>
      <span>{{ emptyHint }}</span>
    </div>

    <template v-else>
      <div v-if="trackMode === 'risk'" class="risk-level-legend">
        <span class="risk-level-legend__title">判定公示</span>
        <span class="risk-legend-item is-high">
          <i></i>
          异常
        </span>
        <span class="risk-legend-item is-low">
          <i></i>
          安全
        </span>
      </div>

      <div class="risk-table-toolbar">
        <div class="risk-table-filters">
          <template v-if="trackMode === 'risk'">
            <label class="filter-field" for="risk-eval-verdict">
              <span class="filter-field__label">判定</span>
              <select id="risk-eval-verdict" v-model="filterVerdict">
                <option value="all">全部</option>
                <option value="abnormal">异常</option>
                <option value="safe">安全</option>
              </select>
            </label>
            <label class="filter-field" for="risk-eval-l1">
              <span class="filter-field__label">L1 类别</span>
              <select id="risk-eval-l1" v-model="filterL1">
                <option value="all">全部 L1</option>
                <option v-for="axis in l1FilterOptions" :key="axis.code" :value="axis.code">
                  {{ axis.code }} {{ axis.shortZh }}
                </option>
              </select>
            </label>
          </template>
          <label v-else class="filter-field" :for="`${trackMode}-eval-filter`">
            <span class="filter-field__label">筛选</span>
            <select :id="`${trackMode}-eval-filter`" v-model="filterStatus">
              <option value="all">全部档位</option>
              <option v-for="option in valueStatusOptions" :key="option" :value="option">
                {{ option }}
              </option>
            </select>
          </label>
          <label class="filter-field" :for="`${trackMode}-eval-sort`">
            <span class="filter-field__label">排序</span>
            <select :id="`${trackMode}-eval-sort`" v-model="sortMode">
              <option value="score-desc">
                {{ trackMode === 'value' ? '价值分（高到低）' : '风险分（高到低）' }}
              </option>
              <option value="score-asc">
                {{ trackMode === 'value' ? '价值分（低到高）' : '风险分（低到高）' }}
              </option>
              <option value="id-asc">数据点 ID（字母序）</option>
            </select>
          </label>
        </div>
      </div>

      <div class="eval-result-grid">
        <article
          v-for="(row, index) in pagedRows"
          :key="row.id"
          class="eval-result-card is-reveal"
          :class="trackMode === 'risk' ? riskVerdictClass(row) : valueToneClass(row)"
          :style="{ animationDelay: `${Math.min(index, 8) * 55 + 280}ms` }"
        >
          <header class="eval-result-card__head">
            <div class="eval-result-card__id">
              <code class="eval-id">{{ row.id }}</code>
              <span
                v-if="trackMode === 'risk'"
                class="risk-status-badge"
                :class="riskVerdictClass(row)"
              >
                {{ verdictLabel(row) }}
              </span>
              <span v-else class="badge" :class="badgeClass(row.status)">{{ row.status }}</span>
              <span v-if="trackMode === 'risk' && rowL1Code(row)" class="risk-pill is-l1-id">
                {{ rowL1Code(row) }}
              </span>
              <span v-else-if="row.dimension" class="risk-pill is-dim">{{ row.dimension }}</span>
              <span v-if="row.detectMethod" class="risk-pill is-method">
                {{ methodLabel(row.detectMethod) }}
              </span>
            </div>
            <div class="eval-result-card__score" :class="trackMode === 'value' ? 'is-value' : ''">
              <span class="eval-score-label">
                {{ trackMode === 'value' ? '价值分' : '风险分' }}
              </span>
              <strong>{{ row.score }}</strong>
            </div>
          </header>

          <div class="eval-result-card__meta">
            <template v-if="trackMode === 'risk'">
              <span class="eval-meta-chip">
                {{ formatHarmCategoryL1(row.riskCategoryL1) || rowL1Code(row) || '未返回 L1' }}
              </span>
              <span v-if="row.riskCategoryL2" class="eval-meta-chip is-l2">
                {{ formatHarmCategoryL2(row.riskCategoryL2) }}
              </span>
            </template>
            <template v-else>
              <span class="eval-meta-chip">{{ row.topic || row.dimension || '价值样本' }}</span>
              <span v-if="row.qualityLevel" class="eval-meta-chip is-l2">
                {{ row.qualityLevel }}
              </span>
            </template>
          </div>

          <p class="eval-result-card__snippet">
            <span class="eval-snippet-label">原文</span>
            {{ row.snippet || '—' }}
          </p>
        </article>
      </div>

      <div v-if="filteredRows.length === 0" class="risk-sample-empty">当前筛选条件下暂无样例</div>

      <div v-if="filteredRows.length > 0" class="case-pagination">
        <span class="case-pagination__summary">
          共 {{ filteredRows.length }} 条，每页 {{ pageSize }} 条
        </span>
        <div class="case-pagination__controls">
          <button
            type="button"
            class="btn btn-secondary btn-sm"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          >
            上一页
          </button>
          <span class="case-pagination__page">{{ currentPage }} / {{ totalPages }}</span>
          <button
            type="button"
            class="btn btn-secondary btn-sm"
            :disabled="currentPage >= totalPages"
            @click="currentPage += 1"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { InputAssessmentRow } from '@/utils/inputMockData'
import {
  TOPIC2_L1_RADAR_AXES,
  extractL1Code,
  formatHarmCategoryL1,
  formatHarmCategoryL2,
} from '@/utils/topic2HarmLabels'

const PAGE_SIZE = 6

const props = defineProps<{
  trackMode: 'value' | 'risk'
  assessmentRows: InputAssessmentRow[]
}>()

const filterStatus = ref('all')
const filterVerdict = ref<'all' | 'abnormal' | 'safe'>('all')
const filterL1 = ref('all')
const sortMode = ref<'score-desc' | 'score-asc' | 'id-asc'>('score-desc')
const currentPage = ref(1)
const pageSize = PAGE_SIZE

const valueStatusOptions = ['优', '良', '待提升']
const l1FilterOptions = TOPIC2_L1_RADAR_AXES
const emptyTitle = computed(() =>
  props.trackMode === 'risk' ? '等待课题二识别结果' : '等待课题一评估样本',
)
const emptyHint = computed(() =>
  props.trackMode === 'risk'
    ? '进入本页后会自动启动识别；完成后在此展示异常 / 安全个例。'
    : '进入本页后会自动载入 value_qa 样本；完成后在此展示优 / 良 / 待提升个例。',
)

const filteredRows = computed(() => {
  let rows = [...props.assessmentRows]

  if (props.trackMode === 'risk') {
    if (filterVerdict.value === 'abnormal') {
      rows = rows.filter((row) => rowIsAbnormal(row))
    } else if (filterVerdict.value === 'safe') {
      rows = rows.filter((row) => !rowIsAbnormal(row))
    }
    if (filterL1.value !== 'all') {
      rows = rows.filter((row) => rowL1Code(row) === filterL1.value)
    }
  } else if (filterStatus.value !== 'all') {
    rows = rows.filter((row) => row.status === filterStatus.value)
  }

  return rows.sort((a, b) => {
    if (sortMode.value === 'id-asc') return a.id.localeCompare(b.id)
    const aScore = Number(a.score)
    const bScore = Number(b.score)
    return sortMode.value === 'score-asc' ? aScore - bScore : bScore - aScore
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)))

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredRows.value.slice(start, start + pageSize)
})

function rowIsAbnormal(row: InputAssessmentRow) {
  if (row.isAbnormal !== undefined) return Boolean(row.isAbnormal)
  return row.status === '异常' || row.status === '高风险' || row.status === '中风险'
}

function rowL1Code(row: InputAssessmentRow) {
  return extractL1Code(row.predictedL1Id) || extractL1Code(row.riskCategoryL1)
}

function verdictLabel(row: InputAssessmentRow) {
  return rowIsAbnormal(row) ? '异常' : '安全'
}

function riskVerdictClass(row: InputAssessmentRow) {
  return rowIsAbnormal(row) ? 'is-high' : 'is-low'
}

function valueToneClass(row: InputAssessmentRow) {
  if (row.status === '待提升') return 'is-improve'
  if (row.status === '优') return 'is-good'
  return 'is-mid'
}

function badgeClass(status: string) {
  const map: Record<string, string> = {
    优: 'badge-green',
    良: 'badge-blue',
    待提升: 'badge-orange',
  }
  return map[status] ?? 'badge-blue'
}

function methodLabel(method: string) {
  if (method === 'activation_probe') return 'neuron'
  if (method === 'keyword') return 'keyword'
  return method
}

watch(
  () => props.trackMode,
  () => {
    filterStatus.value = 'all'
    filterVerdict.value = 'all'
    filterL1.value = 'all'
    sortMode.value = 'score-desc'
    currentPage.value = 1
  },
)

watch([filterStatus, filterVerdict, filterL1, sortMode, () => props.assessmentRows], () => {
  currentPage.value = 1
})

watch(totalPages, (pages) => {
  if (currentPage.value > pages) currentPage.value = pages
})
</script>

<style scoped>
.data-input-stage-section--spaced {
  margin-top: 8px;
}

.eval-stage-hint {
  margin: 0 0 14px;
  font-size: 12px;
  line-height: 1.5;
  color: #66788c;
}

.risk-level-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  margin: 0 0 14px;
  padding: 8px 12px;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: #f8fbff;
}

.risk-level-legend__title {
  font-size: 12px;
  font-weight: 700;
  color: #4a6380;
}

.risk-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #334e68;
}

.risk-legend-item i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.risk-legend-item.is-high i {
  background: #1565c0;
}
.risk-legend-item.is-low i {
  background: #2e7d32;
}

.risk-table-toolbar {
  margin-bottom: 14px;
}

.risk-table-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: flex-end;
  width: 100%;
}

.risk-table-filters .filter-field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  flex: 0 0 auto;
  min-width: 148px;
  margin: 0;
  font-size: 12px;
  color: #5c7188;
}

.risk-table-filters .filter-field__label {
  display: block;
  line-height: 1.2;
  white-space: nowrap;
  font-weight: 600;
}

.risk-table-filters .filter-field select {
  width: auto;
  min-width: 148px;
  max-width: 220px;
  border: 1px solid #d8e2ee;
  border-radius: 6px;
  background: #fff;
  padding: 6px 10px;
  font-size: 12px;
  line-height: 1.3;
}

.eval-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.eval-result-card {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  min-height: 0;
}

.eval-result-card.is-reveal {
  animation: eval-card-reveal 0.42s ease both;
}

@keyframes eval-card-reveal {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.eval-result-card.is-high {
  box-shadow: inset 3px 0 0 #1565c0;
  border-color: #90caf9;
  background: #f7faff;
}

.eval-result-card.is-low {
  box-shadow: inset 3px 0 0 #2e7d32;
  border-color: #b7dfb9;
  background: #f5fbf5;
}

.eval-result-card.is-improve {
  box-shadow: inset 3px 0 0 #e6a23c;
  border-color: #f5d08a;
  background: #fffaf0;
}

.eval-result-card.is-good {
  box-shadow: inset 3px 0 0 #2e7d32;
  border-color: #b7dfb9;
  background: #f5fbf5;
}

.eval-result-card.is-mid {
  box-shadow: inset 3px 0 0 #1565c0;
  border-color: #90caf9;
  background: #f7faff;
}

.eval-result-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.eval-result-card__id {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.eval-id {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 6px;
  background: #eef2f7;
  color: #334e68;
  font-size: 12px;
  font-weight: 700;
}

.eval-result-card__score {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: #1565c0;
  white-space: nowrap;
}

.eval-result-card__score.is-value {
  background: rgba(230, 162, 60, 0.14);
  color: #b45309;
}

.eval-score-label {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
}

.eval-result-card__score strong {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.eval-result-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.eval-meta-chip {
  display: inline-flex;
  max-width: 100%;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef4fb;
  color: #1565c0;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
}

.eval-meta-chip.is-l2 {
  background: #f3e8ff;
  color: #6b21a8;
}

.eval-result-card__snippet {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid #90a4ae;
  background: #f8fafc;
  font-size: 13px;
  line-height: 1.55;
  color: #1a2a44;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.eval-snippet-label {
  display: inline-block;
  margin-right: 6px;
  padding: 0 5px;
  border-radius: 4px;
  background: #e2e8f0;
  color: #475569;
  font-size: 10px;
  font-weight: 700;
  vertical-align: 1px;
}

.risk-status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.risk-status-badge.is-high {
  background: rgba(21, 101, 192, 0.12);
  color: #1565c0;
}

.risk-status-badge.is-low {
  background: rgba(46, 125, 50, 0.12);
  color: #2e7d32;
}

.risk-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.risk-pill.is-method {
  background: #f3e8ff;
  color: #6b21a8;
}

.risk-pill.is-l1-id {
  background: #e0f2fe;
  color: #0369a1;
}

.risk-pill.is-dim {
  background: #ecfdf5;
  color: #047857;
}

.risk-sample-empty {
  padding: 20px;
  text-align: center;
  color: #66788c;
  font-size: 13px;
}

@media (max-width: 900px) {
  .eval-result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
