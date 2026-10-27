<template>
  <div v-if="payload" class="cultural-record-detail" aria-label="文化多样性系统预跑记录详情">
    <p class="cultural-record-detail__badge">系统预跑记录 · 非本次用户执行结果</p>
    <div v-if="payload.source_status !== 'ok'" class="cultural-record-detail__status" role="status">
      <strong>
        {{ payload.source_status === 'missing' ? '来源记录不存在' : '来源版本已变化' }}
      </strong>
      <span>{{ message.content }}</span>
    </div>
    <template v-if="payload.source_status !== 'missing'">
      <header class="cultural-record-detail__head">
        <h4>{{ payload.name || payload.record_id }}</h4>
        <p class="cultural-record-detail__id">{{ payload.record_id }}</p>
        <p class="cultural-record-detail__tags">
          <span class="cultural-record__chip">{{ payload.record_type_label }}</span>
          <span class="cultural-record__chip is-done">{{ payload.status_label }}</span>
          <span class="cultural-record__chip">版本：{{ payload.record_version || '未标注' }}</span>
        </p>
      </header>

      <section class="cultural-record-detail__section">
        <h5>数据集摘要</h5>
        <p class="cultural-record-detail__summary">{{ payload.sample_summary }}</p>
        <dl class="cultural-record-detail__facts">
          <div>
            <dt>样本总数</dt>
            <dd>{{ payload.dataset.sample_count }}</dd>
          </div>
          <div>
            <dt>审校通过</dt>
            <dd>{{ payload.dataset.review_passed_count }}</dd>
          </div>
          <div>
            <dt>审校通过率</dt>
            <dd>{{ formatMetricRate(payload.dataset.review_passed_rate) }}</dd>
          </div>
          <div>
            <dt>质量门禁</dt>
            <dd>{{ payload.dataset.quality_gate_overall || '—' }}</dd>
          </div>
        </dl>
        <div
          v-for="distribution in datasetDistributions"
          :key="distribution.label"
          class="cultural-record-detail__distribution"
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

      <section class="cultural-record-detail__section">
        <h5>样本预览</h5>
        <p v-if="!payload.samples.length" class="cultural-record-detail__note">
          该记录未提供可展示的样本预览，仅展示数据集分布摘要。
        </p>
        <ul v-else class="cultural-record-detail__samples">
          <li
            v-for="sample in payload.samples"
            :key="sample.sample_id"
            class="cultural-record-sample"
          >
            <div class="cultural-record-sample__head">
              <strong>{{ sample.sample_id || '样本' }}</strong>
              <span v-if="sample.difficulty_level" class="cultural-record__chip">
                {{ sample.difficulty_level }}
              </span>
              <span v-if="sample.ethnic_group" class="cultural-record__chip">
                {{ sample.ethnic_group }}
              </span>
              <span v-if="sample.background_type" class="cultural-record__chip">
                {{ sample.background_type }}
              </span>
              <span v-if="sample.query_type" class="cultural-record__chip">
                {{ sample.query_type }}
              </span>
            </div>
            <p class="cultural-record-sample__prompt">{{ sample.prompt_preview || '暂无预览' }}</p>
          </li>
        </ul>
      </section>

      <section class="cultural-record-detail__section">
        <h5>来源版本</h5>
        <dl class="cultural-record-detail__facts">
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
        </dl>
      </section>

      <section
        v-if="payload.source_status === 'ok' && payload.review_supported"
        class="cultural-record-detail__review"
      >
        <h5>审阅任务</h5>
        <p class="cultural-record-detail__review-hint">
          冻结同一批语料及 Direct / 3-Agent / Judge 证据，生成可恢复的审阅报告；不重新运行模型。
        </p>
        <button
          type="button"
          class="cultural-record-detail__review-button"
          :disabled="reviewBusy"
          @click="createReviewTask"
        >
          {{ reviewBusy ? '正在创建审阅任务…' : '创建审阅任务' }}
        </button>
        <span v-if="reviewError" class="cultural-record-detail__review-error" role="alert">
          {{ reviewError }}
        </span>
      </section>
      <p
        v-else-if="payload.source_status === 'ok' && payload.review_unavailable_reason"
        class="cultural-record-detail__review-hint"
        role="status"
      >
        {{ payload.review_unavailable_reason }}
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import type { GovernanceCulturalRecordDetailPayload, GovernanceSessionMessage } from '@/types'
import { GOVERNANCE_CULTURAL_REVIEW_ACTIONS } from '@/utils/governance-cultural-review-actions'
import { formatMetricRate } from '@/utils/governance-format'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceCulturalRecordDetailPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cultural_system_record_detail' || !raw) return null
  if (typeof raw.record_id !== 'string') return null
  return raw as unknown as GovernanceCulturalRecordDetailPayload
})

const review = inject(GOVERNANCE_CULTURAL_REVIEW_ACTIONS, null)

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

// The dedicated endpoint replaces a natural-language instruction: clicking the
// button calls the injected action directly, so browsing or rendering a detail
// card can never create a `cultural_prerun_review` task by accident.
function createReviewTask() {
  const current = payload.value
  if (!current || !review || !current.review_supported) return
  review.create(current.record_id, current.record_version)
}

const datasetDistributions = computed(() => {
  const dataset = payload.value?.dataset
  if (!dataset) return []
  return [
    { label: '语境难度分布', distribution: dataset.difficulty_distribution },
    { label: '民族分布', distribution: dataset.ethnic_distribution },
    { label: '背景类型分布', distribution: dataset.background_type_distribution },
    { label: '问题类型分布', distribution: dataset.query_type_distribution },
    { label: '人格分布', distribution: dataset.persona_distribution },
    { label: '丢弃计数', distribution: dataset.discard_counts },
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
</script>
