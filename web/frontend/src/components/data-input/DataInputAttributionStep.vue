<template>
  <h3>{{ isValueMode ? '价值归因' : '风险归因' }}</h3>

  <DataInputServiceStatusCard
    v-if="isValueMode && valueAttributionStatus"
    title="课题一 value_qa 价值归因"
    :status="valueAttributionStatus"
    :badges="valueAttributionBadges"
    connected-label="已载入"
    disconnected-label="等待资产"
    tone="blue"
  />

  <DataInputServiceStatusCard
    v-if="!isValueMode && riskAttributionStatus"
    title="课题二风险归因"
    :status="riskAttributionStatus"
    :badges="riskAttributionBadges"
    action-label="重新生成风险归因"
    loading-label="生成中..."
    connected-label="已生成"
    disconnected-label="等待识别结果"
    tone="red"
    button-class="btn-primary"
    @action="$emit('load-risk-attribution')"
  />

  <div class="data-input-stage-section" :class="{ 'is-forming': isForming }">
    <h4 class="data-input-stage-section__title">原因分布</h4>
    <div class="attrib-overview">
      <div class="risk-assess-section-label">归因口径（{{ modeLabel }}）</div>
      <div class="risk-assess-stats-hint">{{ displayStatsHint }}</div>
      <p class="attr-stage-context">{{ causeContextLine }}</p>

      <div class="risk-summary-secondary">
        <div
          v-for="item in causeSecondary"
          :key="item.label"
          class="risk-stat-card risk-stat-card--secondary"
        >
          <div class="rsv">{{ item.val }}</div>
          <div class="rsl">{{ item.label }}</div>
        </div>
      </div>

      <div v-if="!isValueMode" class="l1-mini-share">
        <div class="l1-mini-share__title">异常样本 L1-1～L1-4 原因占比</div>
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

      <div v-else class="dim-share">
        <div class="dim-share__title">
          {{
            (enabledScienceNames?.length || 0) > 0
              ? '待提升样本 · 治理维度分布（二级评测维度）'
              : '待提升样本 · 治理维度分布'
          }}
        </div>
        <div v-if="valueDimensionBars.length === 0" class="attr-empty-inline">
          暂无待提升维度统计（请确认治理标准体系已有相关覆盖）
        </div>
        <div
          v-for="(item, index) in valueDimensionBars"
          :key="item.label"
          class="dim-share__row is-reveal"
          :style="{ animationDelay: `${index * 70 + 120}ms` }"
        >
          <span class="dim-share__name" :title="item.label">{{ item.label }}</span>
          <div class="dim-share__track">
            <span class="dim-share__fill" :style="{ width: item.width }" />
          </div>
          <span class="dim-share__val">{{ item.count }} · {{ item.pct }}</span>
        </div>
      </div>
    </div>
  </div>

  <div class="data-input-stage-section data-input-stage-section--spaced">
    <h4 class="data-input-stage-section__title">个例展示 · 归因证据</h4>
    <p class="attr-stage-hint">
      本页聚焦「为什么」：点选左侧样本，右侧查看证据、问题片段、血缘与归因链。判定清单见评估页，修正对照见修正页。
    </p>

    <div class="risk-table-toolbar">
      <div class="risk-table-filters">
        <template v-if="!isValueMode">
          <label class="filter-field" for="attr-case-verdict">
            <span class="filter-field__label">判定</span>
            <select id="attr-case-verdict" v-model="caseFilterVerdict">
              <option value="all">全部</option>
              <option value="abnormal">异常</option>
              <option value="safe">安全</option>
            </select>
          </label>
          <label class="filter-field" for="attr-case-l1">
            <span class="filter-field__label">L1 类别</span>
            <select id="attr-case-l1" v-model="caseFilterL1">
              <option value="all">全部 L1</option>
              <option v-for="axis in enabledRiskL1Axes" :key="axis.code" :value="axis.code">
                {{ axis.code }} {{ axis.shortZh }}
              </option>
            </select>
          </label>
        </template>
        <label v-else class="filter-field" for="attr-case-value-filter">
          <span class="filter-field__label">筛选</span>
          <select id="attr-case-value-filter" v-model="previewRange">
            <option value="all">全部档位</option>
            <option value="优">优</option>
            <option value="良">良</option>
            <option value="待提升">待提升</option>
          </select>
        </label>
      </div>
    </div>

    <div v-if="caseFilteredRows.length === 0" class="attribution-example-empty">
      当前筛选下暂无可展示个例。请先载入对应轨道的归因模块。
    </div>

    <div v-else class="attr-master-detail">
      <aside class="attr-case-list" aria-label="归因样本列表">
        <button
          v-for="(row, index) in pagedCaseRows"
          :key="`list-${row.id}`"
          type="button"
          class="attr-case-list__item is-reveal"
          :class="{
            'is-selected': focusedCaseId === row.id,
            'is-high': !isValueMode && rowIsAbnormal(row),
            'is-improve': isValueMode && row.status === '待提升',
          }"
          :style="{ animationDelay: `${Math.min(index, 8) * 55 + 280}ms` }"
          @click="focusCase(row.id)"
        >
          <div class="attr-case-list__top">
            <code class="eval-id">{{ row.id }}</code>
            <span
              class="risk-status-badge"
              :class="
                isValueMode ? valueBadgeClass(row) : rowIsAbnormal(row) ? 'is-high' : 'is-low'
              "
            >
              {{ overallDisplay(row) }}
            </span>
          </div>
          <div class="attr-case-list__meta">
            <template v-if="!isValueMode">
              <span class="attr-meta-chip">{{ rowL1Code(row) || '未返回 L1' }}</span>
              <span class="attr-meta-score">{{ row.score }}</span>
            </template>
            <template v-else>
              <span class="attr-meta-chip">{{ row.dimension || row.topic || '价值样本' }}</span>
              <span class="attr-meta-score is-value">{{ row.score }}</span>
            </template>
          </div>
          <p class="attr-case-list__snippet">{{ row.snippet || '—' }}</p>
        </button>

        <div v-if="caseFilteredRows.length > 0" class="case-pagination case-pagination--compact">
          <span class="case-pagination__summary">{{ caseFilteredRows.length }} 条</span>
          <div class="case-pagination__controls">
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              :disabled="currentCasePage <= 1"
              @click="currentCasePage -= 1"
            >
              上页
            </button>
            <span class="case-pagination__page">{{ currentCasePage }}/{{ caseTotalPages }}</span>
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              :disabled="currentCasePage >= caseTotalPages"
              @click="currentCasePage += 1"
            >
              下页
            </button>
          </div>
        </div>
      </aside>

      <div v-if="focusedCase" class="attr-case-detail">
        <header class="attr-case-detail__head">
          <div>
            <code class="eval-id">{{ focusedCase.id }}</code>
            <span
              class="risk-status-badge"
              :class="
                isValueMode
                  ? valueBadgeClass(focusedCase)
                  : rowIsAbnormal(focusedCase)
                    ? 'is-high'
                    : 'is-low'
              "
            >
              {{ overallDisplay(focusedCase) }}
            </span>
            <span v-if="!isValueMode && rowL1Code(focusedCase)" class="risk-pill is-l1">
              {{ rowL1Code(focusedCase) }}
            </span>
            <span v-if="focusedCase.detectMethod" class="risk-pill is-method">
              {{ methodLabel(focusedCase.detectMethod) }}
            </span>
          </div>
          <div class="attr-case-detail__score" :class="isValueMode ? 'is-value' : ''">
            <span class="eval-score-label">{{ isValueMode ? '价值分' : '风险分' }}</span>
            <strong>{{ focusedCase.score }}</strong>
          </div>
        </header>

        <p class="attr-case-detail__snippet">
          <span class="eval-snippet-label">原文</span>
          {{ focusedCase.snippet || '—' }}
        </p>

        <div class="attr-evidence-stack">
          <section class="attr-evidence-block">
            <h5>{{ isValueMode ? '价值依据' : '判定依据' }}</h5>
            <div v-if="!isValueMode" class="risk-attr-kv risk-attr-kv--grid">
              <div>
                <span class="risk-attr-kv__label">L1</span>
                <div class="risk-attr-kv__value">
                  {{
                    formatHarmCategoryL1(focusedCase.riskCategoryL1) ||
                    rowL1Code(focusedCase) ||
                    '未返回 L1'
                  }}
                </div>
              </div>
              <div>
                <span class="risk-attr-kv__label">L2</span>
                <div class="risk-attr-kv__value">
                  {{ formatHarmCategoryL2(focusedCase.riskCategoryL2) || '—' }}
                </div>
              </div>
              <div>
                <span class="risk-attr-kv__label">血缘</span>
                <div class="risk-attr-kv__value">
                  {{ focusedCase.lineageNodeLabel || focusedCase.lineageNodeId || '未绑定' }}
                </div>
              </div>
              <div>
                <span class="risk-attr-kv__label">方法</span>
                <div class="risk-attr-kv__value">
                  {{ methodLabel(focusedCase.detectMethod || '') || '—' }}
                </div>
              </div>
            </div>
            <div v-else>
              <p class="attr-meta-line">{{ valueMetaText(focusedCase) }}</p>
              <ul v-if="focusedCase.issueSpans?.length" class="attribution-issue-spans">
                <li
                  v-for="(issue, index) in focusedCase.issueSpans"
                  :key="`${focusedCase.id}-issue-${index}`"
                >
                  <strong>{{ issue.type || 'issue' }}</strong>
                  ：{{ issue.span || issue.sentence || '未提供片段' }}
                </li>
              </ul>
              <p v-else class="eval-empty">暂无问题片段标注</p>
            </div>
          </section>

          <section class="attr-evidence-block">
            <h5>归因链</h5>
            <ol v-if="attributionSteps(focusedCase).length" class="attr-timeline">
              <li
                v-for="(step, index) in attributionSteps(focusedCase)"
                :key="`${focusedCase.id}-step-${index}`"
              >
                <span class="attr-timeline__index">{{ index + 1 }}</span>
                <div class="attr-timeline__body">
                  <div class="attr-timeline__title">{{ step.title }}</div>
                  <div class="attr-timeline__detail">{{ step.detail || '—' }}</div>
                </div>
              </li>
            </ol>
            <p v-else class="eval-empty">
              {{ isValueMode ? attributionText(focusedCase) : '暂无结构化归因步骤' }}
            </p>
          </section>

          <section v-if="!isValueMode" class="attr-evidence-block">
            <h5>证据明细</h5>
            <ul v-if="focusedCase.findings?.length" class="risk-attr-findings">
              <li
                v-for="(finding, index) in focusedCase.findings"
                :key="`${focusedCase.id}-f-${index}`"
              >
                <strong>{{ finding.label || finding.riskType || '证据' }}</strong>
                <span v-if="finding.keyword">· {{ finding.keyword }}</span>
                <span v-if="finding.evidence" class="eval-empty">— {{ finding.evidence }}</span>
              </li>
            </ul>
            <p v-else class="eval-empty">
              {{
                focusedCase.detectMethod === 'activation_probe'
                  ? 'neuron 以 L1 路由为主要证据，详见归因链。'
                  : '暂无关键词命中明细'
              }}
            </p>
          </section>
        </div>

        <p v-if="focusedCase.note" class="risk-attr-note">{{ focusedCase.note }}</p>
      </div>

      <div v-else class="attr-case-detail attr-case-detail--empty">
        <strong>选择左侧样本</strong>
        <span>右侧将展示证据链、血缘与问题片段。</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DataInputServiceStatusCard from '@/components/data-input/DataInputServiceStatusCard.vue'
import { levelShortLabel } from '@/utils/outputHelpers'
import type { AttributionModuleStatus } from '@/stores/input'
import type { ValueAssessmentSummary } from '@/utils/inputMockData'
import {
  TOPIC2_L1_RADAR_AXES,
  extractL1Code,
  formatHarmCategoryL1,
  formatHarmCategoryL2,
} from '@/utils/topic2HarmLabels'
import { formatValueQaPrimaryDimension } from '@/stores/standard'
import {
  scaleInt,
  scalePctText,
  scalePctWidth,
  useRevealProgress,
} from '@/composables/common/useRevealProgress'

interface AssessmentRow {
  id: string
  score: string
  status: string
  snippet: string
  suggestion: string
  summary?: string
  lineageNodeId?: string
  lineageNodeLabel?: string
  riskCategoryL1?: string
  riskCategoryL2?: string
  predictedL1Id?: string
  detectMethod?: string
  action?: string
  isAbnormal?: boolean
  evidenceChain?: string[]
  attributionSteps?: Array<{ title: string; detail: string }>
  note?: string
  findings?: Array<{ keyword: string; evidence: string; riskType: string; label?: string }>
  issueSpans?: Array<{ type: string; sentence: string; span: string }>
  dimension?: string
  topic?: string
  trueLabel?: string
  predictedLabel?: string
}

const CASE_PAGE_SIZE = 8

const props = defineProps<{
  isValueMode: boolean
  modeLabel: string
  statsHint: string
  assessmentStats: Array<{ val: string; label: string }>
  assessmentRows: AssessmentRow[]
  valueAssessmentSummary?: ValueAssessmentSummary | null
  valueAttributionStatus?: AttributionModuleStatus
  riskAttributionStatus?: AttributionModuleStatus
  enabledL1Codes?: string[]
  enabledValuePrimaries?: string[]
  enabledScienceNames?: string[]
}>()

defineEmits<{
  (e: 'load-risk-attribution'): void
}>()

const previewRange = ref('待提升')
const caseFilterVerdict = ref<'all' | 'abnormal' | 'safe'>('abnormal')
const caseFilterL1 = ref('all')
const currentCasePage = ref(1)
const casePageSize = CASE_PAGE_SIZE
const focusedCaseId = ref('')

const revealSignature = computed(
  () =>
    `${props.isValueMode ? 'v' : 'r'}:${props.assessmentRows.length}:${props.assessmentRows
      .slice(0, 12)
      .map((row) => row.id)
      .join(',')}`,
)

const { revealT, isForming } = useRevealProgress({
  durationMs: 1100,
  restartOn: revealSignature,
})

const displayStatsHint = computed(() =>
  props.isValueMode
    ? '本页展示治理标准体系下的待提升原因分布与证据链；维度口径与输入数据治理标准一致。'
    : '本页展示治理标准体系下的 L1 / L2 异常原因分布与证据链；口径与评估辅区一致。',
)

const causeContextLine = computed(() => {
  const t = revealT.value
  if (props.isValueMode) {
    const improve = props.assessmentRows.filter((row) => row.status === '待提升').length
    return `上下文：待提升 ${scaleInt(improve, t)} / 总 ${scaleInt(props.assessmentRows.length, t)}（点选样本查看证据）`
  }
  const abnormal = props.assessmentRows.filter((row) => rowIsAbnormal(row)).length
  return `上下文：异常 ${scaleInt(abnormal, t)} / 检测 ${scaleInt(props.assessmentRows.length, t)}（点选样本查看证据）`
})

const causeSecondary = computed(() => {
  const rows = props.assessmentRows
  const t = revealT.value
  if (!props.isValueMode) {
    const abnormal = rows.filter((row) => rowIsAbnormal(row))
    const withLineage = abnormal.filter(
      (row) => Boolean(row.lineageNodeId?.trim()) || Boolean(row.lineageNodeLabel?.trim()),
    ).length
    const withEvidence = abnormal.filter(
      (row) => Boolean(row.findings?.length) || Boolean(row.evidenceChain?.length),
    ).length
    const method =
      rows.find((row) => row.detectMethod)?.detectMethod === 'activation_probe'
        ? 'neuron'
        : rows.find((row) => row.detectMethod)?.detectMethod === 'keyword'
          ? 'keyword'
          : '—'
    return [
      { val: String(scaleInt(abnormal.length, t)), label: '异常样本' },
      { val: String(scaleInt(withEvidence, t)), label: '有证据明细' },
      { val: String(scaleInt(withLineage, t)), label: '已绑血缘' },
      { val: method, label: '主识别方法' },
    ]
  }
  const improve = rows.filter((row) => row.status === '待提升')
  const withSpans = improve.filter((row) => Boolean(row.issueSpans?.length)).length
  const withSteps = improve.filter(
    (row) => Boolean(row.attributionSteps?.length) || Boolean(row.evidenceChain?.length),
  ).length
  const dims = new Set(improve.map((row) => row.dimension || row.topic || '').filter(Boolean))
  return [
    { val: String(scaleInt(improve.length, t)), label: '待提升样本' },
    { val: String(scaleInt(withSpans, t)), label: '有问题片段' },
    { val: String(scaleInt(withSteps, t)), label: '有归因步骤' },
    { val: String(scaleInt(dims.size, t)), label: '涉及维度数' },
  ]
})

const valueDimensionBars = computed(() => {
  const improve = props.assessmentRows.filter((row) => row.status === '待提升')
  const enabledScience = props.enabledScienceNames || []
  const enabledPrimaries = props.enabledValuePrimaries || []
  const useScience = enabledScience.length > 0
  const axisKeys = useScience ? enabledScience : enabledPrimaries
  const counts = new Map<string, number>()

  improve.forEach((row) => {
    const raw = String(row.dimension || row.topic || '').trim()
    const parts = raw
      .split(/\s*\/\s*/)
      .map((part) => part.trim())
      .filter(Boolean)
    const primary = parts[0] || ''
    const secondary = parts.length >= 2 ? parts[parts.length - 1] : parts[0] || ''
    const key = useScience ? secondary || primary || '未标注维度' : primary || '未标注维度'
    if (axisKeys.length > 0) {
      const matched = axisKeys.some(
        (name) =>
          key === name ||
          formatValueQaPrimaryDimension(key) === formatValueQaPrimaryDimension(name),
      )
      if (!matched) return
    }
    const label = useScience ? key : formatValueQaPrimaryDimension(key) || key
    counts.set(label, (counts.get(label) || 0) + 1)
  })

  if (axisKeys.length > 0) {
    axisKeys.forEach((name) => {
      const label = useScience ? name : formatValueQaPrimaryDimension(name) || name
      if (!counts.has(label)) counts.set(label, 0)
    })
  }

  const countedImprove = Array.from(counts.values()).reduce((sum, n) => sum + n, 0)
  const denom = Math.max(countedImprove, 1)
  const t = revealT.value
  return Array.from(counts.entries())
    .map(([label, count]) => {
      const ratio = count / denom
      return {
        label,
        rawCount: count,
        count: scaleInt(count, t),
        pct: count === 0 ? '0%' : scalePctText(ratio, t),
        width: scalePctWidth(ratio, t),
      }
    })
    .sort((a, b) => b.rawCount - a.rawCount)
    .slice(0, 8)
})

const enabledRiskL1Axes = computed(() => {
  const enabled = new Set((props.enabledL1Codes || []).filter((code) => code.startsWith('L1-')))
  if (enabled.size === 0) return TOPIC2_L1_RADAR_AXES
  return TOPIC2_L1_RADAR_AXES.filter((axis) => enabled.has(axis.code))
})

const l1ShareBars = computed(() => {
  const abnormalRows = props.assessmentRows.filter((row) => rowIsAbnormal(row))
  const denom = Math.max(abnormalRows.length, 1)
  const t = revealT.value
  return enabledRiskL1Axes.value.map((axis) => {
    const count = abnormalRows.filter((row) => rowL1Code(row) === axis.code).length
    const ratio = count / denom
    return {
      code: axis.code,
      shortZh: axis.shortZh,
      count: scaleInt(count, t),
      pct: abnormalRows.length === 0 ? '0%' : scalePctText(ratio, t),
      width: scalePctWidth(ratio, t),
    }
  })
})

const caseFilteredRows = computed(() => {
  if (props.isValueMode) {
    if (previewRange.value === 'all') return props.assessmentRows
    return props.assessmentRows.filter((row) => row.status === previewRange.value)
  }
  let rows = [...props.assessmentRows]
  if (caseFilterVerdict.value === 'abnormal') {
    rows = rows.filter((row) => rowIsAbnormal(row))
  } else if (caseFilterVerdict.value === 'safe') {
    rows = rows.filter((row) => !rowIsAbnormal(row))
  }
  if (caseFilterL1.value !== 'all') {
    rows = rows.filter((row) => rowL1Code(row) === caseFilterL1.value)
  }
  return rows
})

const caseTotalPages = computed(() =>
  Math.max(1, Math.ceil(caseFilteredRows.value.length / casePageSize)),
)

const pagedCaseRows = computed(() => {
  const start = (currentCasePage.value - 1) * casePageSize
  return caseFilteredRows.value.slice(start, start + casePageSize)
})

const focusedCase = computed(
  () =>
    caseFilteredRows.value.find((row) => row.id === focusedCaseId.value) ||
    pagedCaseRows.value[0] ||
    null,
)

const valueAttributionBadges = computed(() => {
  const status = props.valueAttributionStatus
  if (!status) return []
  const badges = [status.source || 'topic1_value_qa']
  if (status.assetName) badges.push(status.assetName)
  if (status.total > 0) badges.push(`${status.total} 条`)
  return badges
})

const riskAttributionBadges = computed(() => {
  const status = props.riskAttributionStatus
  if (!status) return []
  const badges = [formatRiskAttributionSource(status.source)]
  if (status.assetName) badges.push(status.assetName)
  if (status.total > 0) badges.push(`${status.total} 条`)
  return badges
})

function formatRiskAttributionSource(source = '') {
  const normalized = source.trim().toLowerCase()
  if (normalized.includes('activation')) return 'topic2_activation_probe'
  if (normalized.includes('prerun')) return 'topic2_prerun_snapshot'
  if (normalized.includes('filterguard') || normalized.includes('keyword')) {
    return 'topic2_filterguard'
  }
  return normalized || 'topic2_activation_probe'
}

function rowIsAbnormal(row: AssessmentRow) {
  if (row.isAbnormal !== undefined) return Boolean(row.isAbnormal)
  return row.status === '异常' || row.status === '高风险' || row.status === '中风险'
}

function rowL1Code(row: AssessmentRow) {
  return extractL1Code(row.predictedL1Id) || extractL1Code(row.riskCategoryL1)
}

function statusToLevel(
  status: string,
): 'HIGH' | 'MEDIUM' | 'LOW' | 'excellent' | 'good' | 'needsImprovement' {
  if (props.isValueMode) {
    if (status === '优') return 'excellent'
    if (status === '良') return 'good'
    return 'needsImprovement'
  }
  if (status === '异常' || status === '高风险' || status === '中风险') return 'HIGH'
  return 'LOW'
}

function overallLevel(row: AssessmentRow) {
  if (!props.isValueMode) return rowIsAbnormal(row) ? 'HIGH' : 'LOW'
  return statusToLevel(row.status)
}

function overallDisplay(row: AssessmentRow) {
  if (!props.isValueMode) return rowIsAbnormal(row) ? '异常' : '安全'
  return levelShortLabel(overallLevel(row))
}

function valueBadgeClass(row: AssessmentRow) {
  if (row.status === '待提升') return 'is-improve'
  if (row.status === '优') return 'is-low'
  return 'is-high'
}

function attributionSteps(row: AssessmentRow) {
  if (row.attributionSteps?.length) return row.attributionSteps
  if (!row.evidenceChain?.length) return []
  return row.evidenceChain.map((item) => {
    const split = item.split('：')
    if (split.length >= 2) {
      return { title: split[0], detail: split.slice(1).join('：') }
    }
    return { title: '证据', detail: item }
  })
}

function attributionText(row: AssessmentRow) {
  if (row.summary) return row.summary
  return `价值归因链路：标准维度匹配 -> 综合评分 ${row.score} -> 当前档位 ${row.status}。`
}

function methodLabel(method: string) {
  if (method === 'activation_probe') return 'neuron'
  if (method === 'keyword') return 'keyword'
  return method
}

function valueMetaText(row: AssessmentRow) {
  const parts = [
    row.topic ? `主题：${row.topic}` : '',
    row.dimension ? `维度：${row.dimension}` : '',
    row.predictedLabel ? `复判：${row.predictedLabel}` : '',
    row.trueLabel ? `对照：${row.trueLabel}` : '',
  ].filter(Boolean)
  return parts.join(' · ') || '价值档位与维度证据'
}

function focusCase(rowId: string) {
  focusedCaseId.value = rowId
}

watch(
  () => props.isValueMode,
  (isValue) => {
    previewRange.value = isValue ? '待提升' : 'all'
    caseFilterVerdict.value = isValue ? 'all' : 'abnormal'
    caseFilterL1.value = 'all'
    currentCasePage.value = 1
    focusedCaseId.value = ''
  },
)

watch([previewRange, caseFilterVerdict, caseFilterL1, () => props.assessmentRows], () => {
  currentCasePage.value = 1
})

watch(caseTotalPages, (pages) => {
  if (currentCasePage.value > pages) currentCasePage.value = pages
})

watch(
  pagedCaseRows,
  (rows) => {
    if (!rows.length) {
      focusedCaseId.value = ''
      return
    }
    if (!rows.some((row) => row.id === focusedCaseId.value)) {
      focusedCaseId.value = rows[0].id
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.data-input-stage-section.is-forming .attrib-overview {
  animation: attr-panel-in 0.4s ease both;
}

.l1-mini-share__row.is-reveal,
.dim-share__row.is-reveal,
.attr-case-list__item.is-reveal {
  animation: attr-row-reveal 0.4s ease both;
}

.risk-stat-card--secondary .rsv,
.attr-stage-context,
.l1-mini-share__val,
.dim-share__val {
  font-variant-numeric: tabular-nums;
}

@keyframes attr-panel-in {
  from {
    opacity: 0.4;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes attr-row-reveal {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.risk-level-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  margin: 0 0 14px;
  padding: 10px 14px;
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

.attrib-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-summary-hero {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 16px 18px 14px;
  background: linear-gradient(180deg, #fff8f7 0%, #ffffff 70%);
}

.risk-summary-hero.is-empty {
  background: #f8fafc;
}

.risk-summary-hero__rate {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: #c62828;
}

.risk-summary-hero.is-empty .risk-summary-hero__rate {
  color: #90a4ae;
}

.risk-summary-hero__label {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #1a2a44;
}

.risk-summary-hero__sub {
  margin-top: 4px;
  font-size: 12px;
  color: #5f7186;
}

.risk-summary-hero__bar {
  margin-top: 12px;
  height: 6px;
  border-radius: 999px;
  background: #e8eef5;
  overflow: hidden;
}

.risk-summary-hero__bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ef9a9a, #c62828);
}

.risk-summary-secondary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.risk-stat-card--secondary {
  min-height: 64px;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: #fff;
  text-align: center;
}

.risk-stat-card--secondary .rsv {
  font-size: 18px;
  font-weight: 800;
  color: #1a2a44;
}

.risk-stat-card--secondary .rsl {
  margin-top: 4px;
  font-size: 11px;
  color: #5f7186;
}

.risk-summary-meta {
  font-size: 12px;
  color: #5f7186;
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

.cds-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--text-secondary, #5c7188);
  font-size: 12px;
}

.cds-legend mark {
  margin-right: 4px;
  border-radius: 4px;
  padding: 1px 6px;
  font-style: normal;
  font-weight: 700;
}

.rh-high {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.rh-med {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.rh-low {
  background: rgba(63, 185, 129, 0.1);
  color: #3fb981;
}

.preview-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary, #5c7188);
  font-size: 12px;
}

.preview-tools select {
  min-width: 160px;
  border: 1px solid #d8e2ee;
  border-radius: 6px;
  background: #fff;
  padding: 4px 8px;
  font-size: 12px;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e1eaf4;
  border-radius: 10px;
  background: #fff;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.preview-table th {
  text-align: left;
  padding: 10px 12px;
  color: #6a7d91;
  font-weight: 600;
  font-size: 11px;
  white-space: nowrap;
  border-bottom: 2px solid #d8e2ee;
  background: #f8fbff;
}

.preview-table td {
  padding: 12px;
  border-bottom: 1px solid #e8eef6;
  color: #4c657e;
  vertical-align: middle;
}

.preview-table tbody tr:last-child td {
  border-bottom: none;
}

.preview-row.is-clickable {
  cursor: pointer;
}

.preview-row.is-clickable:hover {
  background: #f5f9ff;
}

.preview-row.is-selected {
  background: #eef5ff;
}

.risk-attr-card.is-focused,
.attribution-example-card.is-focused {
  outline: 2px solid #1565c0;
  outline-offset: 2px;
}

.risk-summary-hero.is-value {
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 70%);
}

.risk-summary-hero.is-value .risk-summary-hero__rate {
  color: #1565c0;
}

.risk-summary-hero__bar-fill.is-value {
  background: linear-gradient(90deg, #90caf9, #1565c0);
}

.preview-table code {
  color: #2f435a;
  font-size: 12px;
}

.snippet {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lineage-cell {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.l1-cell {
  font-weight: 700;
  color: #1565c0;
}

.eval-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.eval-tag.green {
  background: rgba(63, 185, 129, 0.14);
  color: #15803d;
}

.eval-tag.orange {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

.eval-tag.red {
  background: rgba(239, 68, 68, 0.14);
  color: #dc2626;
}

.eval-empty {
  color: #94a3b8;
}

.attribution-example-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-attr-card {
  border: 1px solid #d8e2ee;
  border-radius: 14px;
  padding: 16px 18px;
  background: #fff;
}

.risk-attr-card.is-high {
  border-color: #90caf9;
  box-shadow: inset 4px 0 0 #1565c0;
  background: linear-gradient(180deg, #f7faff 0%, #fff 36%);
}

.risk-attr-card.is-low {
  border-color: #b7dfb9;
  box-shadow: inset 4px 0 0 #2e7d32;
  background: linear-gradient(180deg, #f5fbf5 0%, #fff 36%);
}

.risk-attr-card__head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e8eef6;
}

.risk-attr-card__id {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.risk-attr-card__score {
  font-size: 13px;
  font-weight: 700;
  color: #4a6380;
}

.risk-status-badge {
  display: inline-flex;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
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
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
}

.risk-pill.is-l1,
.risk-pill.is-method {
  background: #eef4fb;
  color: #1565c0;
}

.risk-attr-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.risk-attr-section {
  border: 1px solid #e1eaf4;
  border-radius: 12px;
  background: #f8fbff;
  overflow: hidden;
  min-height: 100%;
}

.risk-attr-section--chain,
.risk-attr-section--action {
  grid-column: 1 / -1;
}

.risk-attr-section--action {
  background: #fff;
}

.risk-attr-section__title {
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
  color: #1565c0;
  background: #eef4fb;
  border-bottom: 1px solid #d8e2ee;
}

.risk-attr-card.is-high .risk-attr-section__title {
  color: #1565c0;
  background: #eef4fb;
  border-bottom-color: #d8e2ee;
}

.risk-attr-card.is-low .risk-attr-section__title {
  color: #2e7d32;
  background: #eef8ef;
  border-bottom-color: #cfe5d1;
}

.risk-attr-section__body {
  padding: 12px;
}

.risk-attr-snippet,
.risk-attr-action {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #1a2a44;
}

.risk-attr-action {
  font-weight: 600;
}

.risk-attr-kv {
  display: grid;
  gap: 10px;
  font-size: 13px;
  color: #1a2a44;
}

.risk-attr-kv__label {
  display: block;
  margin-bottom: 2px;
  font-size: 11px;
  font-weight: 700;
  color: #6b86a5;
}

.attr-timeline {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0;
}

.attr-timeline li {
  position: relative;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 0 0 14px 0;
}

.attr-timeline li:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 13px;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: #d0dceb;
}

.attr-timeline li:last-child {
  padding-bottom: 0;
}

.attr-timeline__index {
  position: relative;
  z-index: 1;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #1565c0;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

.attr-timeline__body {
  min-width: 0;
  padding-top: 2px;
}

.attr-timeline__title {
  font-size: 13px;
  font-weight: 700;
  color: #1a2a44;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attr-timeline__detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #4a6380;
  word-break: break-word;
}

.risk-attr-findings {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.55;
  color: #4a6380;
}

.risk-attr-note {
  margin: 12px 0 0;
  font-size: 11px;
  line-height: 1.45;
  color: #90a4ae;
}

.attribution-example-card {
  border: 1px solid #e1eaf4;
  border-radius: 10px;
  background: #fff;
  padding: 14px 16px;
}

.attribution-example-title {
  font-weight: 700;
  color: #2f435a;
  margin-bottom: 8px;
}

.attribution-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-bottom: 8px;
  color: #6a7d91;
  font-size: 12px;
}

.attribution-meta-row span {
  background: #f5f8fc;
  border-radius: 999px;
  padding: 2px 10px;
}

.attribution-example-text {
  color: #4c657e;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 8px;
}

.attribution-issue-spans {
  margin: 0 0 10px;
  padding-left: 18px;
  color: #9a3412;
  font-size: 12px;
  line-height: 1.55;
}

.attribution-example-result {
  color: #334155;
  font-size: 13px;
  line-height: 1.55;
}

.attribution-example-empty {
  border: 1px dashed #d8e2ee;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  color: #6a7d91;
  font-size: 13px;
}

.risk-sample-empty {
  text-align: center;
  color: #6a7d91;
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

.case-pagination--compact {
  margin-top: 10px;
  padding-top: 10px;
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

.attr-stage-context,
.attr-stage-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #66788c;
}

.attr-empty-inline {
  font-size: 12px;
  color: #8a9bb0;
}

.attr-master-detail {
  display: grid;
  grid-template-columns: minmax(260px, 0.9fr) minmax(0, 1.4fr);
  gap: 14px;
  align-items: start;
}

.attr-case-list {
  display: grid;
  gap: 8px;
  max-height: 720px;
  overflow: auto;
  padding-right: 2px;
}

.attr-case-list__item {
  display: grid;
  gap: 6px;
  width: 100%;
  text-align: left;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  cursor: pointer;
  font: inherit;
}

.attr-case-list__item.is-high {
  box-shadow: inset 3px 0 0 #1565c0;
}

.attr-case-list__item.is-improve {
  box-shadow: inset 3px 0 0 #e6a23c;
}

.attr-case-list__item.is-selected {
  border-color: #90caf9;
  background: #f7faff;
  outline: 2px solid rgba(21, 101, 192, 0.2);
}

.attr-case-list__top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.attr-case-list__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #66788c;
}

.attr-meta-chip {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.attr-meta-score {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: #1565c0;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.attr-meta-score.is-value {
  background: rgba(230, 162, 60, 0.14);
  color: #b45309;
}

.attr-case-list__snippet {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #1a2a44;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.attr-case-detail {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 14px 16px;
  background: #fff;
  min-height: 420px;
}

.attr-case-detail--empty {
  display: grid;
  place-content: center;
  gap: 6px;
  text-align: center;
  color: #66788c;
}

.attr-case-detail__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e8eef6;
}

.attr-case-detail__head > div:first-child {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.attr-case-detail__score {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: #1565c0;
  white-space: nowrap;
}

.attr-case-detail__score.is-value {
  background: rgba(230, 162, 60, 0.14);
  color: #b45309;
}

.attr-case-detail__score .eval-score-label {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
}

.attr-case-detail__score strong {
  font-size: 15px;
  font-weight: 800;
}

.attr-case-detail__snippet {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid #90a4ae;
  background: #f8fafc;
  font-size: 13px;
  line-height: 1.55;
  color: #1a2a44;
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
  white-space: nowrap;
}

.risk-status-badge.is-improve {
  background: rgba(230, 162, 60, 0.16);
  color: #b45309;
}

.risk-pill {
  white-space: nowrap;
}

.risk-pill.is-l1 {
  background: #e0f2fe;
  color: #0369a1;
}

.risk-pill.is-method {
  background: #f3e8ff;
  color: #6b21a8;
}

.attr-evidence-stack {
  display: grid;
  gap: 12px;
}

.attr-evidence-block {
  border: 1px solid #e1eaf4;
  border-radius: 10px;
  background: #f8fbff;
  padding: 12px 14px;
  min-width: 0;
}

.attr-evidence-block h5 {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 700;
  color: #1565c0;
  white-space: nowrap;
}

.risk-attr-kv--grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.risk-attr-kv__value {
  font-size: 13px;
  line-height: 1.45;
  color: #1a2a44;
  word-break: break-word;
}

.attr-meta-line {
  margin: 0 0 8px;
  font-size: 12px;
  color: #66788c;
}

.l1-mini-share__fill.is-value {
  background: linear-gradient(90deg, #f5d08a, #e6a23c);
}

.dim-share {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fffaf3;
}

.dim-share__title {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  color: #b45309;
}

.dim-share__row {
  display: grid;
  grid-template-columns: minmax(96px, 160px) 1fr auto;
  gap: 10px;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
}

.dim-share__name {
  color: #7c2d12;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dim-share__track {
  height: 8px;
  border-radius: 999px;
  background: #f3e8d8;
  overflow: hidden;
}

.dim-share__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #f5d08a, #e6a23c);
}

.dim-share__val {
  min-width: 72px;
  text-align: right;
  color: #9a3412;
  font-weight: 600;
  white-space: nowrap;
}

.l1-mini-share__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.case-pagination--compact {
  margin-top: 4px;
  padding-top: 8px;
}

@media (max-width: 860px) {
  .risk-attr-grid,
  .attr-master-detail,
  .risk-summary-secondary,
  .risk-attr-kv--grid {
    grid-template-columns: 1fr;
  }

  .dim-share__row {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      'name val'
      'track track';
  }

  .dim-share__name {
    grid-area: name;
  }

  .dim-share__track {
    grid-area: track;
  }

  .dim-share__val {
    grid-area: val;
  }

  .l1-mini-share__row {
    grid-template-columns: 44px 1fr;
    grid-template-areas:
      'code name'
      'track track'
      'val val';
  }

  .l1-mini-share__code {
    grid-area: code;
  }

  .l1-mini-share__name {
    grid-area: name;
  }

  .l1-mini-share__track {
    grid-area: track;
  }

  .l1-mini-share__val {
    grid-area: val;
    text-align: left;
  }
}
</style>
