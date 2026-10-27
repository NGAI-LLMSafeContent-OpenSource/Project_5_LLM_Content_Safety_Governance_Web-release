<template>
  <div>
    <h3>{{ isValueMode ? '价值评估' : '风险评估' }}</h3>

    <DataInputServiceStatusCard
      v-if="isValueMode && topic1Status"
      title="课题一 value_qa 价值评测资产"
      :status="topic1Status"
      :badges="topic1Badges"
      connected-label="已接入"
      disconnected-label="等待资产"
      tone="blue"
    />

    <template v-if="!isValueMode && topic2Status">
      <p class="risk-assess-hint">
        默认先展示风险侧静态预跑标签（original_label / L1）；需要时再选择 neuron / keyword
        进行实时识别。
      </p>
      <div class="topic2-method-switch">
        <label for="topic2-risk-method">实时识别方法</label>
        <select
          id="topic2-risk-method"
          :value="topic2Method"
          :disabled="topic2Status.loading"
          @change="onMethodChange"
        >
          <option value="activation_probe">neuron</option>
          <option value="keyword">keyword</option>
        </select>
      </div>
      <el-alert
        v-if="topic2ServiceWarning"
        class="topic2-health-alert"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>{{ topic2ServiceWarning.title }}</template>
        <p>{{ topic2ServiceWarning.message }}</p>
        <p v-if="topic2ServiceWarning.action">{{ topic2ServiceWarning.action }}</p>
      </el-alert>
      <DataInputServiceStatusCard
        :title="topic2CardTitle"
        :status="topic2Status"
        :badges="topic2Badges"
        action-label="开始实时识别"
        loading-label="任务运行中..."
        secondary-action-label="取消任务"
        :secondary-action-enabled="topic2Status.cancellable"
        connected-label="已连接"
        disconnected-label="未连接"
        :tone="topic2CardTone"
        button-class="btn-primary"
        :show-technical-details="topic2ShowTechnicalDetails"
        @action="$emit('run-topic2-keyword')"
        @secondary-action="$emit('cancel-topic2-risk-scan')"
      />
    </template>

    <DataInputAssessmentPanel
      :mode-label="modeLabel"
      :track-mode="trackMode"
      :radar-title-suffix="radarTitleSuffix"
      :stats-hint="statsHint"
      :assessment-stats="assessmentStats"
      :risk-assessment-summary="riskAssessmentSummary"
      :value-assessment-summary="valueAssessmentSummary"
      :indicators="indicators"
      :selected-indicators="selectedIndicators"
      :radar-scores="radarScores"
      :aria-label="chartAriaLabel"
      :palette="palette"
      :l2-share-bars="l2ShareBars"
      @toggle-indicator="$emit('toggle-radar-indicator', $event)"
    />
    <DataInputEvaluationSection :track-mode="trackMode" :assessment-rows="assessmentRows" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataInputAssessmentPanel from '@/components/data-input/DataInputAssessmentPanel.vue'
import DataInputEvaluationSection from '@/components/data-input/DataInputEvaluationSection.vue'
import DataInputServiceStatusCard from '@/components/data-input/DataInputServiceStatusCard.vue'
import type { DataInputTrack } from '@/utils/dataInputConfig'
import type { RadarIndicatorItem } from '@/stores/standard'
import type { AttributionModuleStatus, Topic2FilterGuardStatus } from '@/stores/input'
import type {
  InputAssessmentRow,
  RiskAssessmentSummary,
  ValueAssessmentSummary,
} from '@/utils/inputMockData'

const props = defineProps<{
  isValueMode: boolean
  trackMode: DataInputTrack
  modeLabel: string
  radarTitleSuffix: string
  statsHint: string
  assessmentStats: Array<{ val: string; label: string }>
  riskAssessmentSummary?: RiskAssessmentSummary | null
  valueAssessmentSummary?: ValueAssessmentSummary | null
  indicators: RadarIndicatorItem[]
  selectedIndicators: string[]
  radarScores: Record<string, number>
  chartAriaLabel: string
  palette: { area: string; dot: string }
  assessmentRows: InputAssessmentRow[]
  l2ShareBars?: Array<{
    label: string
    l1Code: string
    count: number
    pct: string
    width: string
  }>
  topic2Status?: Topic2FilterGuardStatus
  topic2Method?: 'activation_probe' | 'keyword'
  topic1Status?: AttributionModuleStatus
}>()

const emit = defineEmits<{
  (e: 'toggle-radar-indicator', id: string): void
  (e: 'run-topic2-keyword'): void
  (e: 'cancel-topic2-risk-scan'): void
  (e: 'update-topic2-method', method: 'activation_probe' | 'keyword'): void
}>()

const topic1Badges = computed(() => {
  if (!props.topic1Status) return []
  const badges: string[] = []
  if (props.topic1Status.assetId) badges.push(props.topic1Status.assetId)
  if (props.topic1Status.total > 0) badges.push(`${props.topic1Status.total} 条`)
  return badges
})

const topic2CardTitle = computed(() =>
  props.topic2Method === 'keyword' ? '课题二 keyword 异常识别' : '课题二 neuron 异常识别',
)

const topic2CardTone = computed(() =>
  props.topic2Status?.checked && !props.topic2Status.connected ? 'red' : 'blue',
)

const topic2ShowTechnicalDetails = computed(
  () => Boolean(props.topic2Status?.checked) && !props.topic2Status?.connected,
)

const topic2ServiceWarning = computed(() => {
  const status = props.topic2Status
  if (!status?.checked || status.connected || status.loading) return null
  return {
    title: `${topic2CardTitle.value} 未连接`,
    message: status.blockingReason || status.message,
    action: status.nextAction,
  }
})

const topic2Badges = computed(() => {
  if (!props.topic2Status) return []
  const methodKey = props.topic2Status.method || props.topic2Method || 'activation_probe'
  const methodLabel = methodKey === 'keyword' ? 'keyword' : 'neuron'
  const badges = [`method=${methodLabel}`]
  if (props.topic2Status.taskStatus && props.topic2Status.taskStatus !== 'idle') {
    badges.push(`任务 ${props.topic2Status.progress}%`)
  }
  if (props.topic2Status.total > 0) {
    badges.push(`${props.topic2Status.total} 条 / 异常 ${props.topic2Status.abnormalCount} 条`)
  }
  return badges
})

function onMethodChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value === 'keyword' || value === 'activation_probe') {
    emit('update-topic2-method', value)
  }
}
</script>

<style scoped>
.risk-assess-hint {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff8f6;
  border: 1px solid #f0d2c8;
  color: #6d3b32;
  font-size: 13px;
  line-height: 1.45;
}

.topic2-method-switch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 12px;
}

.topic2-method-switch label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.topic2-method-switch select {
  min-width: 280px;
  border: 1px solid var(--border-color, #d9d9d9);
  border-radius: 8px;
  padding: 6px 10px;
  background: #fff;
  font-size: 13px;
}

.topic2-health-alert {
  margin: 0 0 12px;
}

.topic2-health-alert p {
  margin: 4px 0 0;
  line-height: 1.45;
}
</style>
