<template>
  <div
    class="risk-assess-split data-input-assess-split"
    :class="[isRiskMode ? 'is-risk-mode' : 'is-value-mode', { 'is-forming': isForming }]"
  >
    <div class="risk-assess-left-panel">
      <div class="risk-assess-section-label">训练语料统计（{{ displayTrackLabel }}）</div>
      <div class="risk-assess-stats-hint">{{ statsHint }}</div>

      <template v-if="isRiskMode">
        <div
          class="risk-summary-hero"
          :class="{ 'is-empty': !summaryReady, 'is-forming': isForming && summaryReady }"
        >
          <div class="risk-summary-hero__rate">{{ anomalyRateText }}</div>
          <div class="risk-summary-hero__label">异常率</div>
          <div class="risk-summary-hero__sub">
            异常 {{ animatedAbnormal }} / 检测 {{ animatedRiskTotal }}
          </div>
          <div class="risk-summary-hero__bar" aria-hidden="true">
            <span class="risk-summary-hero__bar-fill" :style="{ width: anomalyBarWidth }" />
          </div>
        </div>

        <div class="risk-summary-secondary">
          <div
            v-for="item in secondaryStats"
            :key="item.label"
            class="risk-stat-card risk-stat-card--secondary"
          >
            <div class="rsv">{{ item.val }}</div>
            <div class="rsl">{{ item.label }}</div>
          </div>
        </div>

        <div class="risk-summary-meta">{{ summaryMetaLine }}</div>
      </template>

      <template v-else>
        <div
          class="risk-summary-hero is-value"
          :class="{ 'is-empty': !valueSummaryReady, 'is-forming': isForming && valueSummaryReady }"
        >
          <div class="risk-summary-hero__rate">{{ improveRateText }}</div>
          <div class="risk-summary-hero__label">待提升占比</div>
          <div class="risk-summary-hero__sub">
            待提升 {{ animatedImprove }} / 总 {{ animatedValueTotal }}
          </div>
          <div class="risk-summary-hero__bar" aria-hidden="true">
            <span
              class="risk-summary-hero__bar-fill is-value"
              :style="{ width: improveBarWidth }"
            />
          </div>
        </div>
        <div class="risk-summary-secondary">
          <div
            v-for="item in valueSecondaryStats"
            :key="item.label"
            class="risk-stat-card risk-stat-card--secondary"
          >
            <div class="rsv">{{ item.val }}</div>
            <div class="rsl">{{ item.label }}</div>
          </div>
        </div>
        <div class="risk-summary-meta">{{ valueSummaryMetaLine }}</div>
      </template>
    </div>

    <div class="risk-assess-right-panel">
      <div v-if="isRiskMode" class="risk-right-switch">
        <button
          type="button"
          class="risk-right-switch__btn"
          :class="{ active: riskRightView === 'l1' }"
          @click="riskRightView = 'l1'"
        >
          L1 风险分布
        </button>
        <button
          type="button"
          class="risk-right-switch__btn"
          :class="{ active: riskRightView === 'l2' }"
          @click="riskRightView = 'l2'"
        >
          L2 细类占比
        </button>
      </div>

      <div class="risk-assess-section-label">
        {{
          isRiskMode
            ? riskRightView === 'l1'
              ? 'L1 风险分布（雷达）'
              : 'L2 细类占比（辅区）'
            : `维度${displayRadarTitle}（雷达）`
        }}
      </div>
      <div class="risk-assess-stats-hint">
        {{ isRiskMode ? riskRightHint : displayRadarHint }}
      </div>

      <div v-if="!isRiskMode" class="radar-indicator-selector">
        <span
          v-for="item in indicators"
          :key="item.id"
          class="radar-indicator-chip radar-indicator-chip--readonly"
          :class="{ active: item.enabled }"
        >
          <span class="radar-indicator-chip__dot" aria-hidden="true" />
          <span>{{ item.label || item.name }}</span>
        </span>
      </div>

      <template v-if="!isRiskMode || riskRightView === 'l1'">
        <div class="radar-panel" :class="{ 'radar-panel--l1': isRiskMode }">
          <span v-if="!isRiskMode && selectedIndicators.length === 0">
            当前治理标准体系暂无可展示的价值评测指标
          </span>
          <span v-else-if="isRiskMode && selectedRiskAxes.length === 0">
            当前治理标准体系暂无可展示的 L1 风险维度
          </span>
          <div v-else class="radar-chart-wrap" :class="{ 'radar-chart-wrap--l1': isRiskMode }">
            <svg
              :viewBox="isRiskMode ? '0 0 360 300' : '0 0 280 220'"
              class="radar-chart-svg"
              :aria-label="displayAriaLabel"
            >
              <g :transform="isRiskMode ? 'translate(180,145)' : 'translate(140,110)'">
                <polygon
                  v-for="(ring, idx) in radarRings"
                  :key="`ring-${idx}`"
                  :points="ring"
                  class="radar-ring"
                />
                <line
                  v-for="(axis, idx) in radarAxes"
                  :key="`axis-${idx}`"
                  :x1="0"
                  :y1="0"
                  :x2="axis.x"
                  :y2="axis.y"
                  class="radar-axis"
                />
                <polygon
                  :points="radarValuePolygon"
                  class="radar-value-area"
                  :class="{ 'is-growing': isForming }"
                  :style="{ fill: palette.area }"
                />
                <circle
                  v-for="(point, idx) in radarValuePoints"
                  :key="`pt-${idx}`"
                  :cx="point.x"
                  :cy="point.y"
                  r="3.5"
                  class="radar-value-dot"
                  :style="{ fill: palette.dot }"
                />
              </g>
              <g :transform="isRiskMode ? 'translate(180,145)' : 'translate(140,110)'">
                <text
                  v-for="(axis, idx) in radarAxes"
                  :key="`label-${idx}`"
                  :x="axis.lx"
                  :y="axis.ly"
                  class="radar-label"
                  :class="{ 'radar-label--l1': isRiskMode }"
                >
                  <tspan :x="axis.lx" dy="0">{{ axis.label }}</tspan>
                  <tspan v-if="axis.subLabel" :x="axis.lx" dy="14" class="radar-label-sub">
                    {{ axis.subLabel }}
                  </tspan>
                </text>
              </g>
            </svg>
          </div>
        </div>

        <ul v-if="isRiskMode" class="l1-radar-legend">
          <li v-for="item in l1LegendItems" :key="item.code">
            <span class="l1-radar-legend__code">{{ item.code }}</span>
            <span class="l1-radar-legend__name">{{ item.name }}</span>
            <span class="l1-radar-legend__score">{{ item.scoreText }}</span>
          </li>
        </ul>
      </template>

      <div v-else class="l2-aux-panel l2-aux-panel--switched" :class="{ 'is-forming': isForming }">
        <div v-if="l2ShareBars.length === 0" class="l2-aux-empty">
          暂无可展示的 L2 细类。请确认治理标准体系已有对应覆盖。
        </div>
        <div
          v-for="(item, index) in animatedL2ShareBars"
          :key="item.label"
          class="l2-aux-row"
          :style="{ '--l2-stagger': `${index * 55}ms` }"
        >
          <span class="l2-aux-name" :title="item.label">
            <small v-if="item.l1Code">{{ item.l1Code }}</small>
            {{ item.label }}
          </span>
          <div class="l2-aux-track">
            <span
              class="l2-aux-fill"
              :class="{ 'is-growing': isForming }"
              :style="{ width: item.width }"
            />
          </div>
          <span class="l2-aux-val">{{ item.count }} · {{ item.pct }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  emptyRiskAssessmentSummary,
  emptyValueAssessmentSummary,
  type RiskAssessmentSummary,
  type ValueAssessmentSummary,
} from '@/utils/inputMockData'
import { TOPIC2_L1_RADAR_AXES } from '@/utils/topic2HarmLabels'

interface RadarIndicatorItem {
  id: string
  name: string
  label?: string
  enabled: boolean
}

interface RadarAxisView {
  label: string
  subLabel?: string
  scoreKey: string
  x: number
  y: number
  lx: number
  ly: number
}

const props = defineProps<{
  modeLabel?: string
  trackLabel?: string
  radarTitleSuffix?: string
  statsHint: string
  radarHint?: string
  assessmentStats: Array<{ val: string; label: string }>
  riskAssessmentSummary?: RiskAssessmentSummary | null
  valueAssessmentSummary?: ValueAssessmentSummary | null
  indicators: RadarIndicatorItem[]
  selectedIndicators: string[]
  radarScores: Record<string, number>
  palette: { area: string; dot: string }
  ariaLabel?: string
  trackMode?: 'value' | 'risk'
  l2ShareBars?: Array<{
    label: string
    l1Code: string
    count: number
    pct: string
    width: string
  }>
}>()

const REVEAL_MS = 1200
const revealT = ref(0)
let revealRaf = 0
let revealStart = 0
const riskRightView = ref<'l1' | 'l2'>('l1')

const displayTrackLabel = computed(() => props.trackLabel ?? props.modeLabel ?? '')
const isRiskMode = computed(
  () => props.trackMode === 'risk' || displayTrackLabel.value.includes('风险'),
)
const l2ShareBars = computed(() => props.l2ShareBars || [])
const animatedL2ShareBars = computed(() => {
  const t = revealT.value
  return l2ShareBars.value.map((item) => {
    const targetPct = Number.parseFloat(String(item.pct).replace('%', '')) || 0
    const shownPct = Math.round(targetPct * t)
    const shownCount = Math.round(item.count * t)
    return {
      ...item,
      count: shownCount,
      pct: `${shownPct}%`,
      width: `${Math.min(Math.max(targetPct * t, 0), 100)}%`,
    }
  })
})
const riskRightHint = computed(() =>
  riskRightView.value === 'l1'
    ? '基于治理标准体系中的 L1 维度展示；可切换到 L2 查看细类占比。'
    : '基于治理标准体系中的 L2 细类展示；条占比 = 该 L2 异常数 / 异常总数。',
)
const displaySummary = computed(() => props.riskAssessmentSummary ?? emptyRiskAssessmentSummary())
const displayValueSummary = computed(
  () => props.valueAssessmentSummary ?? emptyValueAssessmentSummary(),
)
const summaryReady = computed(() => displaySummary.value.ready)
const valueSummaryReady = computed(() => displayValueSummary.value.ready)
const isForming = computed(() => revealT.value < 0.999)

const dataSignature = computed(() => {
  const scores = Object.keys(props.radarScores)
    .sort()
    .map((key) => `${key}:${Number(props.radarScores[key] ?? 0).toFixed(3)}`)
    .join('|')
  const l2Sig = l2ShareBars.value.map((item) => `${item.label}:${item.count}:${item.pct}`).join('|')
  if (isRiskMode.value) {
    const s = displaySummary.value
    return `risk:${s.ready}:${s.total}:${s.abnormal}:${s.anomalyRate}:${scores}:${l2Sig}`
  }
  const s = displayValueSummary.value
  return `value:${s.ready}:${s.total}:${s.improve}:${s.improveRate}:${scores}:${props.selectedIndicators.join(',')}`
})

const anomalyRateText = computed(() => {
  if (!summaryReady.value) return '—'
  return `${Math.round(displaySummary.value.anomalyRate * 100 * revealT.value)}%`
})
const improveRateText = computed(() => {
  if (!valueSummaryReady.value) return '—'
  return `${Math.round(displayValueSummary.value.improveRate * 100 * revealT.value)}%`
})
const anomalyBarWidth = computed(() => {
  if (!summaryReady.value) return '0%'
  const pct = Math.min(Math.max(displaySummary.value.anomalyRate * 100 * revealT.value, 0), 100)
  return `${pct}%`
})
const improveBarWidth = computed(() => {
  if (!valueSummaryReady.value) return '0%'
  const pct = Math.min(
    Math.max(displayValueSummary.value.improveRate * 100 * revealT.value, 0),
    100,
  )
  return `${pct}%`
})

const animatedAbnormal = computed(() => Math.round(displaySummary.value.abnormal * revealT.value))
const animatedRiskTotal = computed(() => Math.round(displaySummary.value.total * revealT.value))
const animatedImprove = computed(() =>
  Math.round(displayValueSummary.value.improve * revealT.value),
)
const animatedValueTotal = computed(() =>
  Math.round(displayValueSummary.value.total * revealT.value),
)

const secondaryStats = computed(() => [
  { val: String(Math.round(displaySummary.value.total * revealT.value)), label: '检测条数' },
  { val: String(Math.round(displaySummary.value.normal * revealT.value)), label: '安全样本' },
  { val: String(Math.round(displaySummary.value.highRisk * revealT.value)), label: '异常条数' },
])
const valueSecondaryStats = computed(() => [
  {
    val: String(Math.round(displayValueSummary.value.total * revealT.value)),
    label: '总数据条数',
  },
  {
    val: String(Math.round(displayValueSummary.value.excellent * revealT.value)),
    label: '优档条数',
  },
  {
    val: String(Math.round(displayValueSummary.value.good * revealT.value)),
    label: '良档条数',
  },
])
const summaryMetaLine = computed(() => {
  if (!summaryReady.value) {
    return '进入本页后将自动写入异常率与样本构成。'
  }
  if (isForming.value) {
    return '正在汇总异常率与样本构成…'
  }
  const method = displaySummary.value.methodLabel || '课题二'
  const covered = displaySummary.value.l1Covered
  const total = displaySummary.value.total
  return `方法：${method} · L1 覆盖 ${covered}/${total}`
})
const valueSummaryMetaLine = computed(() => {
  if (!valueSummaryReady.value) {
    return '进入本页后将自动写入待提升占比与档位构成。'
  }
  if (isForming.value) {
    return '正在汇总待提升占比与档位构成…'
  }
  return `待提升 ${displayValueSummary.value.improve} · 优 ${displayValueSummary.value.excellent} · 良 ${displayValueSummary.value.good}`
})
const displayAriaLabel = computed(() =>
  isRiskMode.value
    ? '课题二 L1 风险治理维度分布雷达图'
    : (props.ariaLabel ?? `${displayTrackLabel.value}评估雷达图`),
)
const displayRadarTitle = computed(
  () =>
    props.radarTitleSuffix ?? (displayTrackLabel.value.includes('价值') ? '价值达成' : '风险分布'),
)
const displayRadarHint = computed(() => {
  if (props.radarHint) return props.radarHint
  if (isRiskMode.value) {
    return '基于治理标准体系中的 L1 维度展示；下方辅区展示 L2 细类占比。'
  }
  return '雷达轴对应治理标准体系中的价值二级评测维度；上方一级维度用于组织样本范围。'
})

const selectedRiskAxes = computed(() => {
  const enabled = new Set(
    props.selectedIndicators
      .map((name) => String(name || '').trim())
      .filter((name) => name.startsWith('L1-')),
  )
  if (enabled.size === 0) {
    props.indicators.forEach((item) => {
      if (item.enabled && String(item.name || '').startsWith('L1-')) {
        enabled.add(item.name)
      }
    })
  }
  return TOPIC2_L1_RADAR_AXES.filter((axis) => enabled.has(axis.code))
})

const radarAxes = computed<RadarAxisView[]>(() => {
  if (isRiskMode.value) {
    const axes = selectedRiskAxes.value
    const count = Math.max(axes.length, 1)
    const radius = 96
    const labelRadius = 118
    return axes.map((axis, index) => {
      const angle = -Math.PI / 2 + (index * Math.PI * 2) / count
      return {
        label: axis.code,
        subLabel: axis.shortZh,
        scoreKey: axis.code,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        lx: Math.cos(angle) * labelRadius,
        ly: Math.sin(angle) * labelRadius + (Math.sin(angle) > 0.2 ? 2 : -2),
      }
    })
  }

  const labels = props.selectedIndicators.slice(0, 6)
  if (labels.length === 0) return []
  const count = labels.length
  return labels.map((label, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / count
    const indicator = props.indicators.find((item) => item.name === label)
    return {
      label: indicator?.label || label,
      scoreKey: label,
      x: Math.cos(angle) * 82,
      y: Math.sin(angle) * 82,
      lx: Math.cos(angle) * 104,
      ly: Math.sin(angle) * 104 + 4,
    }
  })
})

const radarRings = computed(() =>
  [0.25, 0.5, 0.75, 1].map((radius) => buildPolygon(radarAxes.value, radius)),
)

const radarValuePoints = computed(() =>
  radarAxes.value.map((axis) => {
    const score = Math.max(0, Math.min(props.radarScores[axis.scoreKey] ?? 0, 1)) * revealT.value
    return {
      x: axis.x * score,
      y: axis.y * score,
    }
  }),
)

const radarValuePolygon = computed(() =>
  radarValuePoints.value.map((point) => `${point.x},${point.y}`).join(' '),
)

const l1LegendItems = computed(() =>
  selectedRiskAxes.value.map((axis) => {
    const score = Math.max(0, Math.min(props.radarScores[axis.code] ?? 0, 1)) * revealT.value
    return {
      code: axis.code,
      name: axis.fullZh,
      scoreText: `${(score * 100).toFixed(0)}%`,
    }
  }),
)

function easeOutCubic(t: number) {
  return 1 - (1 - t) ** 3
}

function stopReveal() {
  if (revealRaf) {
    cancelAnimationFrame(revealRaf)
    revealRaf = 0
  }
}

function startReveal() {
  stopReveal()
  revealT.value = 0
  revealStart = 0
  const tick = (now: number) => {
    if (!revealStart) revealStart = now
    const raw = Math.min(1, (now - revealStart) / REVEAL_MS)
    revealT.value = easeOutCubic(raw)
    if (raw < 1) {
      revealRaf = requestAnimationFrame(tick)
      return
    }
    revealT.value = 1
    revealRaf = 0
  }
  revealRaf = requestAnimationFrame(tick)
}

function buildPolygon(axes: Array<{ x: number; y: number }>, radiusRatio: number) {
  return axes.map((axis) => `${axis.x * radiusRatio},${axis.y * radiusRatio}`).join(' ')
}

onMounted(() => {
  startReveal()
})

watch(dataSignature, () => {
  startReveal()
})

watch(riskRightView, (view) => {
  if (view === 'l2') startReveal()
})

onBeforeUnmount(() => {
  stopReveal()
})
</script>

<style scoped>
.risk-assess-split.is-risk-mode {
  align-items: start;
}

.risk-assess-split.is-forming .risk-assess-left-panel {
  animation: assess-panel-in 0.45s ease both;
}

.risk-assess-split.is-forming .risk-assess-right-panel {
  animation: assess-panel-in 0.45s ease 0.12s both;
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

.risk-assess-left-panel,
.risk-assess-right-panel {
  min-height: 0;
}

.risk-summary-hero {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 16px 18px 14px;
  background: linear-gradient(180deg, #fff8f7 0%, #ffffff 70%);
  margin-bottom: 12px;
}

.risk-summary-hero.is-empty {
  background: #f8fafc;
}

.risk-summary-hero.is-forming .risk-summary-hero__rate {
  text-shadow: 0 0 0 transparent;
}

.risk-summary-hero__rate {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: #c62828;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
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
  font-variant-numeric: tabular-nums;
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  line-height: 1.1;
  color: #1a2a44;
  font-variant-numeric: tabular-nums;
}

.risk-stat-card--secondary .rsl {
  margin-top: 4px;
  font-size: 11px;
  color: #5f7186;
}

.risk-summary-meta {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #5f7186;
}

.radar-value-area {
  opacity: 0.55;
  transition: opacity 0.2s ease;
}

.radar-value-area.is-growing {
  opacity: 0.7;
}

.radar-panel--l1 {
  height: auto;
  min-height: 280px;
  padding: 4px 0 0;
}

.radar-chart-wrap--l1 {
  width: 100%;
  max-width: 380px;
  margin: 0 auto;
}

.radar-label--l1 {
  font-size: 11px;
  font-weight: 700;
  fill: #1a2a44;
}

.radar-label-sub {
  font-size: 10px;
  font-weight: 500;
  fill: #5f7186;
}

.l1-radar-legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.l1-radar-legend li {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  background: #f8fbff;
  font-size: 12px;
  line-height: 1.3;
}

.l1-radar-legend__code {
  font-weight: 800;
  color: #1565c0;
}

.l1-radar-legend__name {
  color: #334e68;
}

.l1-radar-legend__score {
  font-weight: 700;
  color: #c62828;
  font-variant-numeric: tabular-nums;
}

.l2-aux-panel {
  margin-top: 4px;
}

.l2-aux-panel--switched {
  min-height: 220px;
}

.risk-right-switch {
  display: inline-flex;
  gap: 4px;
  margin-bottom: 10px;
  padding: 3px;
  border-radius: 10px;
  background: #eef3f8;
}

.risk-right-switch__btn {
  border: none;
  background: transparent;
  color: #5f7186;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  line-height: 1.2;
}

.risk-right-switch__btn.active {
  background: #fff;
  color: #1565c0;
  box-shadow: 0 1px 2px rgba(21, 101, 192, 0.12);
}

.l2-aux-empty {
  margin-top: 8px;
  padding: 10px 12px;
  border: 1px dashed #cbd8e7;
  border-radius: 8px;
  color: #6b86a5;
  font-size: 12px;
}

.l2-aux-row {
  display: grid;
  grid-template-columns: minmax(96px, 1.2fr) minmax(80px, 1.6fr) auto;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
  opacity: 1;
  transform: translateY(0);
}

.l2-aux-panel.is-forming .l2-aux-row {
  animation: l2-row-in 0.42s ease both;
  animation-delay: var(--l2-stagger, 0ms);
}

.l2-aux-name {
  font-size: 12px;
  color: #334e68;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.l2-aux-name small {
  display: inline-block;
  margin-right: 6px;
  color: #1565c0;
  font-weight: 700;
}

.l2-aux-track {
  height: 8px;
  border-radius: 999px;
  background: #e8eef5;
  overflow: hidden;
}

.l2-aux-fill {
  display: block;
  height: 100%;
  width: 0;
  border-radius: inherit;
  background: linear-gradient(90deg, #ef9a9a, #c62828);
  transform-origin: left center;
  transition: width 0.05s linear;
}

.l2-aux-fill.is-growing {
  box-shadow: 0 0 0 1px rgba(198, 40, 40, 0.08);
}

.l2-aux-val {
  font-size: 11px;
  font-weight: 700;
  color: #5f7186;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

@keyframes assess-panel-in {
  from {
    opacity: 0.35;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes l2-row-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
