<template>
  <div v-if="payload" class="system-record-detail" aria-label="系统预跑记录详情">
    <p class="system-record-detail__badge">系统预跑记录 · 非本次用户执行结果</p>
    <div v-if="payload.source_status !== 'ok'" class="system-record-detail__status" role="status">
      <strong>
        {{ payload.source_status === 'missing' ? '来源记录不存在' : '来源版本已变化' }}
      </strong>
      <span>{{ message.content }}</span>
    </div>
    <template v-if="payload.source_status !== 'missing'">
      <header class="system-record-detail__head">
        <h4>{{ payload.name || payload.record_id }}</h4>
        <p class="system-record-detail__id">{{ payload.record_id }}</p>
        <p class="system-record-detail__tags">
          <span class="system-record__chip">{{ payload.record_type_label }}</span>
          <span class="system-record__chip is-done">{{ payload.status_label }}</span>
          <span class="system-record__chip">版本：{{ payload.record_version || '未标注' }}</span>
          <span
            class="system-record__chip"
            :class="payload.asset_status === 'current' ? 'is-done' : ''"
          >
            {{ formatAssetVersion(payload.asset_version) }} ·
            {{ formatAssetStatus(payload.asset_status) }}
          </span>
        </p>
      </header>

      <section class="system-record-detail__section">
        <h5>数据集摘要</h5>
        <p class="system-record-detail__summary">{{ payload.sample_summary }}</p>
        <dl class="system-record-detail__facts">
          <div>
            <dt>样本总数</dt>
            <dd>{{ payload.dataset.sample_count }}</dd>
          </div>
          <div>
            <dt>安全样本</dt>
            <dd>{{ payload.dataset.safe_total }}</dd>
          </div>
          <div>
            <dt>风险样本</dt>
            <dd>{{ payload.dataset.risk_total }}</dd>
          </div>
          <div>
            <dt>分类体系</dt>
            <dd>{{ payload.dataset.taxonomy_schema || '—' }}</dd>
          </div>
          <div>
            <dt>评测对象版本</dt>
            <dd>{{ formatAssetVersion(payload.asset_version) }}</dd>
          </div>
          <div>
            <dt>版本状态</dt>
            <dd>{{ formatAssetStatus(payload.asset_status) }}</dd>
          </div>
        </dl>
        <div
          v-for="distribution in datasetDistributions"
          :key="distribution.label"
          class="system-record-detail__distribution"
        >
          <h6>{{ distribution.label }}</h6>
          <ul>
            <li v-for="entry in distribution.entries" :key="entry.label">
              <span>{{ entry.label }}</span>
              <strong>{{ entry.count }}</strong>
            </li>
          </ul>
        </div>
      </section>

      <section class="system-record-detail__section">
        <h5>模型结果与指标</h5>
        <p v-if="!payload.models.length" class="system-record-detail__note">
          该记录尚未导入可用的模型评测指标，仅展示数据集摘要。
        </p>
        <article
          v-for="model in payload.models"
          :key="model.run_id || model.model_id"
          class="system-record-model"
        >
          <div class="system-record-model__head">
            <strong>{{ model.display_name || model.model_name || model.model_id }}</strong>
            <span v-if="model.role" class="system-record__chip">{{ model.role }}</span>
            <span v-if="model.model_version" class="system-record__chip">
              {{ model.model_version }}
            </span>
          </div>
          <dl class="system-record-detail__facts">
            <div>
              <dt>评测时间</dt>
              <dd>{{ formatGovernanceTime(model.evaluated_at) }}</dd>
            </div>
            <div>
              <dt>预测样本数</dt>
              <dd>{{ model.predictions_count }}</dd>
            </div>
          </dl>
          <ul v-if="primaryMetricEntries(model).length" class="system-record-model__metrics">
            <li v-for="entry in primaryMetricEntries(model)" :key="entry.key">
              <span>{{ entry.label }}</span>
              <strong>{{ entry.value }}</strong>
            </li>
          </ul>
          <details
            v-if="supportingMetricEntries(model).length"
            class="system-record-detail__details"
          >
            <summary>支撑指标</summary>
            <ul>
              <li v-for="entry in supportingMetricEntries(model)" :key="entry.key">
                <span>{{ entry.label }}</span>
                <strong>{{ entry.value }}</strong>
              </li>
            </ul>
          </details>
          <details v-if="categoryMetricEntries(model).length" class="system-record-detail__details">
            <summary>分类别指标</summary>
            <ul>
              <li v-for="entry in categoryMetricEntries(model)" :key="entry.key">
                <span>{{ entry.key }}</span>
                <strong>{{ entry.value }}</strong>
              </li>
            </ul>
          </details>
        </article>
      </section>

      <section class="system-record-detail__section">
        <h5>来源版本</h5>
        <dl class="system-record-detail__facts">
          <div>
            <dt>来源仓库</dt>
            <dd>{{ payload.source_repo || '—' }}</dd>
          </div>
          <div>
            <dt>来源提交</dt>
            <dd>{{ payload.source_commit || '—' }}</dd>
          </div>
          <div>
            <dt>资产哈希</dt>
            <dd>{{ payload.asset_sha256 || '—' }}</dd>
          </div>
          <div>
            <dt>在线评测</dt>
            <dd>{{ payload.live_eval_enabled ? '已启用' : '未启用（预留）' }}</dd>
          </div>
        </dl>
      </section>

      <section
        v-if="payload.source_status === 'ok' && payload.review_supported"
        class="system-record-detail__review"
      >
        <h5>审阅任务</h5>
        <p class="system-record-detail__review-hint">
          冻结 {{ payload.asset_version || 'v6' }} 基准上的正式评测与 Base
          基线对照证据，生成可恢复的四维审阅报告；不重新运行模型。
        </p>
        <button
          type="button"
          class="system-record-detail__review-button"
          :disabled="reviewBusy"
          @click="createReviewTask"
        >
          {{ reviewBusy ? '正在创建审阅任务…' : '创建审阅任务' }}
        </button>
        <span v-if="reviewError" class="system-record-detail__review-error" role="alert">
          {{ reviewError }}
        </span>
      </section>
      <p
        v-else-if="payload.source_status === 'ok' && payload.review_unavailable_reason"
        class="system-record-detail__review-hint"
        role="status"
      >
        {{ payload.review_unavailable_reason }}
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import type {
  GovernanceSessionMessage,
  GovernanceSystemRecordDetailPayload,
  GovernanceSystemRecordModelResult,
} from '@/types'
import {
  formatAssetStatus,
  formatAssetVersion,
  formatGovernanceTime,
} from '@/utils/governance-format'
import { GOVERNANCE_RISK_REVIEW_ACTIONS } from '@/utils/governance-risk-review-actions'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceSystemRecordDetailPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_system_record_detail' || !raw) return null
  if (typeof raw.record_id !== 'string') return null
  return raw as unknown as GovernanceSystemRecordDetailPayload
})

const review = inject(GOVERNANCE_RISK_REVIEW_ACTIONS, null)

const reviewBusy = computed(() => {
  const recordId = payload.value?.record_id
  return Boolean(recordId) && review?.busyRecordId === recordId
})

const reviewError = computed(() => {
  const actions = review
  const recordId = payload.value?.record_id
  if (!actions || !recordId || actions.errorRecordId !== recordId) return ''
  return actions.error
})

// Dedicated endpoint only: browsing or rendering this detail card never creates
// a `risk_prerun_review` task by accident.
function createReviewTask() {
  const current = payload.value
  if (!current || !review || !current.review_supported) return
  review.create(current.record_id, current.record_version)
}

const metricLabels = computed(() => {
  const map: Record<string, string> = {}
  for (const metric of payload.value?.primary_metrics ?? []) {
    if (metric.key) map[metric.key] = metric.display_name || metric.key
  }
  return map
})

const datasetDistributions = computed(() => {
  const dataset = payload.value?.dataset
  if (!dataset) return []
  return [
    { label: '风险等级分布', distribution: dataset.risk_level_distribution },
    { label: '风险分类分布', distribution: dataset.category_distribution },
    { label: '语言分布', distribution: dataset.language_distribution },
    { label: '文化分布', distribution: dataset.culture_distribution },
  ]
    .map(({ label, distribution }) => ({
      label,
      entries: Object.entries(distribution ?? {}).map(([key, count]) => ({
        label: key,
        count,
      })),
    }))
    .filter((group) => group.entries.length > 0)
})

function primaryMetricEntries(model: GovernanceSystemRecordModelResult) {
  return Object.entries(model.primary_metrics ?? {}).map(([key, value]) => ({
    key,
    label: metricLabels.value[key] ?? key,
    value: formatValue(value),
  }))
}

function supportingMetricEntries(model: GovernanceSystemRecordModelResult) {
  return Object.entries(model.supporting_metrics ?? {})
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => ({ key, label: key, value: formatValue(value) }))
}

function categoryMetricEntries(model: GovernanceSystemRecordModelResult) {
  return Object.entries(model.per_category_metrics ?? {}).map(([key, value]) => ({
    key,
    label: key,
    value: formatValue(value),
  }))
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return String(Number.isInteger(value) ? value : value.toFixed(4))
  if (typeof value === 'string') return value
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${key}=${formatValue(nested)}`)
      .join('，')
  }
  return String(value)
}
</script>
