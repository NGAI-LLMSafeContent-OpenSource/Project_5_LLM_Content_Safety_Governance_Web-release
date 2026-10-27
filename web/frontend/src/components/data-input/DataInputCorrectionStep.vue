<template>
  <div>
    <h3>{{ isValueMode ? '价值修正' : '风险修正' }}</h3>

    <div class="data-input-stage-section" :class="{ 'is-forming': isForming }">
      <h4 class="data-input-stage-section__title">修正进度</h4>
      <div class="attrib-overview">
        <div class="risk-assess-section-label">处理工作台（{{ modeLabel }}）</div>
        <div class="risk-assess-stats-hint">{{ displayStatsHint }}</div>

        <div class="fix-progress-hero">
          <div class="fix-progress-hero__main">
            <div class="fix-progress-hero__rate">{{ progressOverview.doneRate }}</div>
            <div class="fix-progress-hero__label">已处理占比</div>
            <div class="fix-progress-hero__sub">
              已处理 {{ statusCounts.adopted + statusCounts.skipped }} / 待办池
              {{ progressOverview.pool }}
            </div>
            <div class="fix-progress-hero__bar" aria-hidden="true">
              <span
                class="fix-progress-hero__bar-fill"
                :style="{ width: progressOverview.barWidth }"
              />
            </div>
          </div>
          <div class="fix-status-strip fix-status-strip--hero">
            <div class="fix-status-chip">
              <strong>{{ statusCounts.pending }}</strong>
              <span>待处理</span>
            </div>
            <div class="fix-status-chip">
              <strong>{{ statusCounts.review }}</strong>
              <span>需复核</span>
            </div>
            <div class="fix-status-chip">
              <strong>{{ statusCounts.adopted }}</strong>
              <span>已采纳</span>
            </div>
            <div class="fix-status-chip">
              <strong>{{ statusCounts.skipped }}</strong>
              <span>已跳过</span>
            </div>
          </div>
        </div>

        <div v-if="!isValueMode && l1ShareBars.length" class="l1-mini-share">
          <div class="l1-mini-share__title">待修正样本 L1 分布（原因堆积，便于分批处理）</div>
          <div
            v-for="(item, index) in l1ShareBars"
            :key="item.code"
            class="l1-mini-share__row is-reveal"
            :style="{ animationDelay: `${index * 70 + 120}ms` }"
          >
            <span class="l1-mini-share__code">{{ item.code }}</span>
            <span class="l1-mini-share__name">{{ item.shortZh }}</span>
            <div class="l1-mini-share__track">
              <span class="l1-mini-share__fill" :style="{ width: item.width }" />
            </div>
            <span class="l1-mini-share__val">{{ item.count }} · {{ item.pct }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="data-input-stage-section data-input-stage-section--spaced">
      <h4 class="data-input-stage-section__title">个例展示 · 修正对照</h4>
      <p class="fix-stage-hint">
        {{
          isValueMode
            ? '左侧为待提升原文，右侧默认填入同组优档答案，可人工改写后采纳。完整证据链请在归因页查看。'
            : '本页为人工复核与改写：处置建议仅供参考，当前无自动 rewrite。完整证据链请在归因页查看。'
        }}
      </p>
      <div class="risk-table-toolbar risk-table-toolbar--spaced">
        <div class="risk-table-filters">
          <label class="filter-field" for="correction-preview-range">
            <span class="filter-field__label">预览范围</span>
            <select
              id="correction-preview-range"
              :value="previewRange"
              @change="onPreviewRangeChange"
            >
              <option value="all">全部修正样例</option>
              <option value="待处理">待处理</option>
              <option value="需复核">需复核</option>
              <option value="已采纳">已采纳</option>
              <option value="已跳过">已跳过</option>
            </select>
          </label>
          <template v-if="!isValueMode">
            <label class="filter-field" for="correction-l1-filter">
              <span class="filter-field__label">L1 类别</span>
              <select id="correction-l1-filter" v-model="filterL1">
                <option value="all">全部 L1</option>
                <option v-for="axis in enabledRiskL1Axes" :key="axis.code" :value="axis.code">
                  {{ axis.code }} {{ axis.shortZh }}
                </option>
              </select>
            </label>
          </template>
          <div class="filter-field filter-field--action">
            <span class="filter-field__label">&nbsp;</span>
            <button class="btn btn-secondary btn-sm" type="button" @click="exportCsv">
              导出 CSV
            </button>
          </div>
        </div>
      </div>

      <div
        v-for="(item, index) in pagedFixes"
        :key="item.id"
        class="fix-card-reveal"
        :style="{ animationDelay: `${Math.min(index, 6) * 70 + 320}ms` }"
      >
        <DataInputFixCard
          :item="item"
          :expanded="expandedFixId === item.id"
          :dirty="!!fixDirtyMap[item.id]"
          :summary-label="isValueMode ? '价值判定摘要' : '风险判定摘要'"
          :edit-title="'人工改写稿（可编辑）'"
          :suggest-title="isValueMode ? '优档对照稿' : '处置建议'"
          :apply-label="isValueMode ? '恢复优档对照' : '恢复处置建议'"
          :status-class="statusClass(item.status)"
          @toggle="$emit('toggle-fix', $event)"
          @update-suggest="onUpdateSuggest"
          @accept="$emit('mark-status', $event, '已采纳')"
          @apply-recommended="$emit('apply-recommended', $event)"
          @reset-original="$emit('reset-original', $event)"
          @mark-review="$emit('mark-status', $event, '需复核')"
          @skip="$emit('mark-status', $event, '已跳过')"
        />
      </div>

      <div v-if="displayFixes.length === 0" class="attribution-example-empty">
        {{
          (allFixes?.length || 0) === 0
            ? isValueMode
              ? '等待课题一评估写入待提升样本后，将在此生成修正项。'
              : '等待课题二识别出异常样本后，将在此生成修正项。'
            : '当前预览范围下暂无修正样例。'
        }}
        <button
          v-if="previewRange === '待处理' && (allFixes?.length || 0) > 0"
          type="button"
          class="empty-switch-link"
          @click="emit('update:preview-range', 'all')"
        >
          查看全部修正样例
        </button>
      </div>

      <div v-if="displayFixes.length > 0" class="case-pagination">
        <span class="case-pagination__summary">
          本页 {{ pagedFixes.length }} / 共 {{ displayFixes.length }} 条（每页 {{ pageSize }} 条）
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DataInputFixCard from '@/components/data-input/DataInputFixCard.vue'
import type {
  CorrectionPreviewRange,
  InputAssessmentRow,
  InputFixItem,
  InputStatItem,
  RiskAssessmentSummary,
  ValueAssessmentSummary,
} from '@/utils/inputMockData'
import { TOPIC2_L1_RADAR_AXES, extractL1Code, formatHarmCategoryL1 } from '@/utils/topic2HarmLabels'
import {
  scaleInt,
  scalePctText,
  scalePctWidth,
  useRevealProgress,
} from '@/composables/common/useRevealProgress'

const PAGE_SIZE = 4

const props = defineProps<{
  isValueMode: boolean
  modeLabel: string
  statsHint: string
  assessmentStats: InputStatItem[]
  assessmentRows?: InputAssessmentRow[]
  riskAssessmentSummary?: RiskAssessmentSummary | null
  valueAssessmentSummary?: ValueAssessmentSummary | null
  allFixes?: InputFixItem[]
  fixes: InputFixItem[]
  enabledL1Codes?: string[]
  previewRange: CorrectionPreviewRange
  expandedFixId: string
  fixDirtyMap: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:preview-range', value: CorrectionPreviewRange): void
  (e: 'toggle-fix', id: string): void
  (e: 'update-suggest', id: string, value: string): void
  (e: 'apply-recommended', id: string): void
  (e: 'reset-original', id: string): void
  (e: 'mark-status', id: string, status: InputFixItem['status']): void
}>()

const filterL1 = ref('all')
const currentPage = ref(1)
const pageSize = PAGE_SIZE

const displayStatsHint = computed(() =>
  props.isValueMode
    ? '本页统计处理进度：待处理 / 需复核 / 已采纳 / 已跳过。整体质量看评估页，原因分布看归因页。'
    : '本页统计处理进度：待处理 / 需复核 / 已采纳 / 已跳过。列表与 L1 分布基于治理标准体系组织。',
)

const sourceFixes = computed(() => props.allFixes ?? props.fixes)

const statusCountsRaw = computed(() => {
  const items = sourceFixes.value
  return {
    pending: items.filter((item) => item.status === '待处理').length,
    review: items.filter((item) => item.status === '需复核').length,
    adopted: items.filter((item) => item.status === '已采纳').length,
    skipped: items.filter((item) => item.status === '已跳过').length,
  }
})

const revealSignature = computed(
  () =>
    `${props.isValueMode ? 'v' : 'r'}:${sourceFixes.value.length}:${sourceFixes.value
      .slice(0, 12)
      .map((item) => item.id)
      .join(',')}`,
)

const { revealT, isForming } = useRevealProgress({
  durationMs: 1100,
  restartOn: revealSignature,
})

const displayFixes = computed(() => {
  if (props.isValueMode || filterL1.value === 'all') return props.fixes
  return props.fixes.filter((item) => fixL1Code(item) === filterL1.value)
})

const totalPages = computed(() => Math.max(1, Math.ceil(displayFixes.value.length / pageSize)))

const pagedFixes = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return displayFixes.value.slice(start, start + pageSize)
})

const statusCounts = computed(() => {
  const t = revealT.value
  const raw = statusCountsRaw.value
  return {
    pending: scaleInt(raw.pending, t),
    review: scaleInt(raw.review, t),
    adopted: scaleInt(raw.adopted, t),
    skipped: scaleInt(raw.skipped, t),
  }
})

const progressOverview = computed(() => {
  const pool = sourceFixes.value.length
  const done = statusCountsRaw.value.adopted + statusCountsRaw.value.skipped
  const rate = pool > 0 ? done / pool : 0
  const t = revealT.value
  return {
    pool: scaleInt(pool, t),
    doneRate: pool > 0 ? scalePctText(rate, t) : '—',
    barWidth: scalePctWidth(rate, t),
  }
})

const enabledRiskL1Axes = computed(() => {
  const enabled = new Set((props.enabledL1Codes || []).filter((code) => code.startsWith('L1-')))
  if (enabled.size === 0) return TOPIC2_L1_RADAR_AXES
  return TOPIC2_L1_RADAR_AXES.filter((axis) => enabled.has(axis.code))
})

const l1ShareBars = computed(() => {
  const items = sourceFixes.value.filter(
    (item) => item.status !== '已采纳' && item.status !== '已跳过',
  )
  const denom = Math.max(items.length, 1)
  const t = revealT.value
  return enabledRiskL1Axes.value
    .map((axis) => {
      const count = items.filter((item) => fixL1Code(item) === axis.code).length
      const ratio = count / denom
      return {
        code: axis.code,
        shortZh: axis.shortZh,
        rawCount: count,
        count: scaleInt(count, t),
        pct: items.length === 0 ? '0%' : scalePctText(ratio, t),
        width: scalePctWidth(ratio, t),
      }
    })
    .filter((item) => item.rawCount > 0)
})

function fixL1Code(item: InputFixItem) {
  return extractL1Code(item.predictedL1Id) || extractL1Code(item.riskCategoryL1)
}

function onPreviewRangeChange(event: Event) {
  emit('update:preview-range', (event.target as HTMLSelectElement).value as CorrectionPreviewRange)
}

function onUpdateSuggest(id: string, value: string) {
  emit('update-suggest', id, value)
}

function statusClass(status: InputFixItem['status']) {
  if (status === '待处理') return 'status-pending'
  if (status === '需复核') return 'status-review'
  if (status === '已跳过') return 'status-skipped'
  return 'status-adopt'
}

function csvEscape(value: string) {
  const text = String(value ?? '').replace(/"/g, '""')
  return `"${text}"`
}

function exportCsv() {
  const rows = sourceFixes.value
  const header = props.isValueMode
    ? ['id', 'sample_id', 'status', 'original', 'suggest', 'issue_spans']
    : ['id', 'sample_id', 'status', 'l1', 'method', 'lineage', 'original', 'suggest', 'action']
  const lines = [header.join(',')]
  rows.forEach((item) => {
    if (props.isValueMode) {
      lines.push(
        [
          csvEscape(item.id),
          csvEscape(item.sampleId || ''),
          csvEscape(item.status),
          csvEscape(item.original),
          csvEscape(item.suggest),
          csvEscape(
            (item.issueSpans || [])
              .map((issue) => `${issue.type}:${issue.span || issue.sentence || ''}`)
              .join(' | '),
          ),
        ].join(','),
      )
      return
    }
    lines.push(
      [
        csvEscape(item.id),
        csvEscape(item.sampleId || ''),
        csvEscape(item.status),
        csvEscape(formatHarmCategoryL1(item.riskCategoryL1) || fixL1Code(item) || ''),
        csvEscape(item.detectMethod || ''),
        csvEscape(item.lineageNodeLabel || ''),
        csvEscape(item.original),
        csvEscape(item.suggest),
        csvEscape(item.action || ''),
      ].join(','),
    )
  })
  const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = props.isValueMode
    ? `value-correction-export-${Date.now()}.csv`
    : `risk-correction-export-${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

watch(
  () => props.isValueMode,
  () => {
    filterL1.value = 'all'
    currentPage.value = 1
  },
)

watch([() => props.fixes, () => props.previewRange, filterL1], () => {
  currentPage.value = 1
})

watch(totalPages, (pages) => {
  if (currentPage.value > pages) currentPage.value = pages
})
</script>

<style scoped>
.data-input-stage-section.is-forming .attrib-overview {
  animation: fix-panel-in 0.4s ease both;
}

.l1-mini-share__row.is-reveal,
.fix-card-reveal {
  animation: fix-row-reveal 0.42s ease both;
}

.fix-progress-hero__rate,
.fix-progress-hero__sub,
.fix-status-strip,
.l1-mini-share__val {
  font-variant-numeric: tabular-nums;
}

@keyframes fix-panel-in {
  from {
    opacity: 0.4;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fix-row-reveal {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.attrib-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fix-stage-hint {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #66788c;
}

.fix-progress-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.85fr);
  gap: 12px;
  align-items: stretch;
}

.fix-progress-hero__main {
  border: 2px solid #c5d5ea;
  border-radius: 12px;
  padding: 14px 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 0;
}

.fix-progress-hero__rate {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
  color: #1565c0;
}

.fix-progress-hero__label {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #1a2a44;
}

.fix-progress-hero__sub {
  margin-top: 4px;
  font-size: 12px;
  color: #5f7186;
}

.fix-progress-hero__bar {
  margin-top: 12px;
  height: 6px;
  border-radius: 999px;
  background: #e8eef5;
  overflow: hidden;
}

.fix-progress-hero__bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #90caf9, #1565c0);
}

.fix-status-strip--hero {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: stretch;
  gap: 10px;
  width: 100%;
  height: 100%;
  min-width: 0;
  border: 2px solid #c5d5ea;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  box-sizing: border-box;
}

.fix-status-chip {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
  height: auto;
  padding: 10px 8px;
  border: 2px solid #c5d5ea;
  border-radius: 10px;
  background: #fff;
  text-align: center;
  box-sizing: border-box;
}

.fix-status-chip strong {
  font-size: 20px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: #1a2a44;
}

.fix-status-chip span {
  font-size: 12px;
  font-weight: 650;
  color: #5f7186;
}

@media (max-width: 900px) {
  .fix-progress-hero {
    grid-template-columns: 1fr;
  }

  .fix-status-strip--hero {
    height: auto;
    min-height: 72px;
  }

  .fix-status-chip {
    height: auto;
    min-height: 64px;
  }
}

.l1-mini-share {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 12px 14px;
  background: #f8fbff;
}

.l1-mini-share__title {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  color: #4a6380;
}

.l1-mini-share__row {
  display: grid;
  grid-template-columns: 48px minmax(96px, 120px) 1fr auto;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
}

.l1-mini-share__code {
  font-weight: 800;
  color: #1565c0;
}

.l1-mini-share__name {
  color: #334e68;
}

.l1-mini-share__track {
  height: 8px;
  border-radius: 999px;
  background: #e8eef5;
  overflow: hidden;
}

.l1-mini-share__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #90caf9, #1565c0);
}

.l1-mini-share__val {
  min-width: 72px;
  text-align: right;
  color: #5f7186;
  font-weight: 600;
}

.fix-status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #4a6380;
}

.risk-table-toolbar--spaced {
  margin-bottom: 16px;
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

.risk-table-filters .filter-field--action {
  min-width: auto;
}

.attribution-example-empty {
  border: 1px dashed #d8e2ee;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  color: #6a7d91;
  font-size: 13px;
}

.empty-switch-link {
  display: inline-block;
  margin-left: 8px;
  border: none;
  background: transparent;
  color: #1565c0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.case-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.case-pagination__summary {
  font-size: 13px;
  color: #6a7d91;
}

.case-pagination__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.case-pagination__page {
  min-width: 64px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .fix-progress-hero {
    grid-template-columns: 1fr;
  }
}
</style>
