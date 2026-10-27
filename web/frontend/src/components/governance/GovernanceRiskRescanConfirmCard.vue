<template>
  <div v-if="payload" class="risk-rescan-confirm-card" aria-label="输入风险语料在线二次检测确认">
    <p class="risk-rescan-confirm-card__title">输入风险语料在线二次检测</p>
    <div class="risk-rescan-confirm-card__summary">
      {{ message.content }}
      <span v-if="sourceSummary" class="risk-rescan-confirm-card__source">
        来源引用：{{ sourceSummary }}
      </span>
    </div>

    <div v-if="filterEntries.length" class="risk-rescan-confirm-card__filters">
      <span
        v-for="entry in filterEntries"
        :key="entry.key"
        class="risk-rescan-confirm-card__filter"
      >
        {{ entry.key }}：{{ entry.label }}
      </span>
    </div>

    <div class="risk-rescan-confirm-card__count">
      <span>数据来源：{{ payload.asset_name || '数据来源未标注' }}</span>
      <span>
        实际检测条数：{{ payload.sample_count }} 条
        <template v-if="payload.capped">
          （匹配 {{ payload.total_matched }} 条，超过单次 30 条上限，已冻结前
          {{ payload.sample_count }} 条）
        </template>
      </span>
      <span class="risk-rescan-confirm-card__evaluator">
        校验器：{{ evaluatorLabel }}（未指定时使用服务端默认校验器）
      </span>
      <span v-if="payload.export_requested" class="risk-rescan-confirm-card__export-hint">
        已完成导出偏好：完成后结果将提供证据包下载入口
      </span>
      <span v-if="payload.parent_task_id" class="risk-rescan-confirm-card__retry-hint">
        重试任务（原任务 {{ payload.parent_task_id.slice(0, 8) }}… 保留原状态与原因）
      </span>
    </div>

    <ol class="risk-rescan-confirm-card__samples">
      <li
        v-for="sample in payload.samples"
        :key="sample.sample_id"
        class="risk-rescan-confirm-card__sample"
      >
        <p class="risk-rescan-confirm-card__sample-text">{{ sample.text }}</p>
        <div class="risk-rescan-confirm-card__sample-badges">
          <span
            class="risk-rescan-confirm-card__label"
            :class="sample.reference_label === 'unsafe' ? 'is-risky' : 'is-safe'"
          >
            参考标注：{{ formatRiskLabel(sample.reference_label) }}
          </span>
          <span class="risk-rescan-confirm-card__chip">{{ sample.sample_id }}</span>
          <span v-if="sample.harm_category_L1" class="risk-rescan-confirm-card__chip">
            {{ sample.harm_category_L1 }}
          </span>
          <span class="risk-rescan-confirm-card__chip">来源：{{ sample.source }}</span>
        </div>
      </li>
    </ol>

    <div class="risk-rescan-confirm-card__actions">
      <template v-if="awaiting">
        <button
          type="button"
          class="risk-rescan-confirm-card__button is-confirm"
          :disabled="inFlight"
          @click="rescan?.confirm(payload.task_id)"
        >
          {{ confirmBusy ? '正在执行检测…' : '确认执行在线二次检测' }}
        </button>
        <button
          type="button"
          class="risk-rescan-confirm-card__button is-cancel"
          :disabled="inFlight"
          @click="rescan?.cancel(payload.task_id)"
        >
          {{ cancelBusy ? '正在取消…' : '取消' }}
        </button>
      </template>
      <span v-else class="risk-rescan-confirm-card__state">{{ statusLabel }}</span>
      <span v-if="error" class="risk-rescan-confirm-card__error" role="alert">
        {{ error }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'

import type {
  GovernanceRiskRescanPreviewPayload,
  GovernanceSessionMessage,
  GovernanceSourceRef,
} from '@/types'
import { formatRiskLabel, formatRiskRescanEvaluator } from '@/utils/governance-format'
import { GOVERNANCE_RESCAN_ACTIONS } from '@/utils/governance-rescan-actions'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const FILTER_LABELS: Record<string, string> = {
  keyword: '关键词',
  reference_label: '参考标注',
  source: '来源',
  harm_category_L1: '一级分类',
  harm_category_L2: '二级分类',
}

const STATUS_LABELS: Record<string, string> = {
  loading: '正在核对任务状态…',
  queued: '已确认，等待执行队列领取…',
  running: '该任务正在执行',
  cancelling: '正在取消执行…',
  completed: '该任务已完成，结果见下方消息',
  completed_partial: '该任务部分完成，结果见下方消息',
  cancelled: '该任务已取消，未产生检测调用',
  failed: '该任务已失败，可在结果通知中重试',
  timeout: '该任务已超时，可在结果通知中重试',
  awaiting_confirmation: '该任务待确认',
}

const rescan = inject(GOVERNANCE_RESCAN_ACTIONS, null)

const payload = computed<GovernanceRiskRescanPreviewPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_corpus_rescan' || !raw) return null
  if (raw.phase !== 'preview' || typeof raw.task_id !== 'string') return null
  return raw as unknown as GovernanceRiskRescanPreviewPayload
})

// Only the server-confirmed status may enable the paid action. The snapshot's
// own status is deliberately NOT a fallback: after a refresh it is stale, and
// inviting a confirm on an already-cancelled/failed task would be wrong (the
// server would reject it with a 409, but the UI must not offer it).
const taskStatus = computed(() => {
  const taskId = payload.value?.task_id
  if (!taskId) return 'loading'
  return rescan?.statuses[taskId] ?? 'loading'
})

const awaiting = computed(() => taskStatus.value === 'awaiting_confirmation')

const inFlight = computed(
  () => Boolean(payload.value) && rescan?.busyTaskId === payload.value?.task_id,
)

const confirmBusy = computed(() => inFlight.value && rescan?.busyAction === 'confirm')

const cancelBusy = computed(() => inFlight.value && rescan?.busyAction === 'cancel')

const error = computed(() => {
  const actions = rescan
  const taskId = payload.value?.task_id
  if (!actions || !taskId || actions.errorTaskId !== taskId) return ''
  return actions.error
})

const statusLabel = computed(() => STATUS_LABELS[taskStatus.value] ?? '该任务状态未知，请刷新页面')

const evaluatorLabel = computed(() =>
  payload.value?.evaluator
    ? formatRiskRescanEvaluator(payload.value.evaluator)
    : 'Activation Probe',
)

const filterEntries = computed(() =>
  Object.entries(payload.value?.filters ?? {}).map(([key, value]) => ({
    key: FILTER_LABELS[key] ?? key,
    label: key === 'reference_label' ? formatRiskLabel(String(value)) : String(value),
  })),
)

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref: GovernanceSourceRef) => {
      const revision = [ref.source_repo, ref.source_commit].filter(Boolean).join('@')
      return revision || ref.name || ref.ref_id
    })
    .filter(Boolean)
    .join('、')
})
</script>
