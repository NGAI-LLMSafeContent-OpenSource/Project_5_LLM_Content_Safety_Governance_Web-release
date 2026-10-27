<template>
  <div v-if="payload" class="cultural-prerun-review" aria-label="文化预跑记录审阅报告">
    <header class="cultural-prerun-review__head">
      <div>
        <p class="cultural-prerun-review__eyebrow">文化生成方法对比 · 预跑记录审阅</p>
        <h4>Direct vs 3-Agent 来源指标对比</h4>
      </div>
      <span class="cultural-prerun-review__badge">报告快照 · 不重新读取上游</span>
    </header>

    <p class="cultural-prerun-review__content">{{ message.content }}</p>

    <GovernanceReportEnvelope :envelope="payload.envelope" />

    <section class="cultural-prerun-review__section">
      <h5>来源指标对比</h5>
      <table class="cultural-prerun-review__metrics">
        <thead>
          <tr>
            <th scope="col">方法</th>
            <th scope="col">民族识别</th>
            <th scope="col">文化特异性</th>
            <th scope="col">综合通过</th>
            <th scope="col">综合百分比</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="metric in payload.source_metrics" :key="metric.method">
            <th scope="row">{{ metric.label }}</th>
            <td>{{ formatMetricRate(metric.ethnic_recognition_rate) }}</td>
            <td>{{ formatMetricRate(metric.cultural_specificity_rate) }}</td>
            <td>{{ metric.composite_pass_count }} / {{ metric.total_samples }}</td>
            <td class="cultural-prerun-review__percentage">{{ metric.composite_percentage }}%</td>
          </tr>
        </tbody>
      </table>
      <p class="cultural-prerun-review__note">
        综合百分比为上游评测原始值，原样展示；完整性检查只追加告警，不重算或改写。
      </p>
    </section>

    <section class="cultural-prerun-review__section">
      <h5>3-Agent 协作阶段</h5>
      <ol class="cultural-prerun-review__stages">
        <li v-for="stage in payload.three_agent_stages" :key="stage.key">
          <strong>{{ stage.label }}</strong>
          <span>{{ stage.description }}</span>
        </li>
      </ol>
      <p class="cultural-prerun-review__note">
        3-Agent 表示文化识别、知识检索、回答生成三个协作阶段，不是三个评估器。
      </p>
    </section>

    <section class="cultural-prerun-review__section" aria-label="问题清单">
      <div class="cultural-prerun-review__issue-head">
        <h5>问题清单</h5>
        <div class="cultural-prerun-review__tabs" role="tablist" aria-label="问题清单视图">
          <button
            type="button"
            role="tab"
            class="cultural-prerun-review__tab"
            :class="{ 'is-active': issueView === 'content' }"
            :aria-selected="issueView === 'content'"
            @click="issueView = 'content'"
          >
            内容问题（{{ contentIssues.length }}）
          </button>
          <button
            type="button"
            role="tab"
            class="cultural-prerun-review__tab"
            :class="{ 'is-active': issueView === 'integrity' }"
            :aria-selected="issueView === 'integrity'"
            @click="issueView = 'integrity'"
          >
            评测完整性问题（{{ integrityIssues.length }}）
          </button>
        </div>
      </div>
      <p v-if="!activeIssues.length" class="cultural-prerun-review__note">
        {{
          issueView === 'content'
            ? '未发现内容问题（Judge 判定为通过或仅有完整性缺陷）。'
            : '未发现评测完整性问题。'
        }}
      </p>
      <ul v-else class="cultural-prerun-review__issues">
        <li v-for="issue in activeIssues" :key="issue.issue_id">
          <div class="cultural-prerun-review__issue-meta">
            <span class="cultural-prerun-review__warning-code">{{ issue.category }}</span>
            <span v-if="issue.sample_id">样本 {{ issue.sample_id }}</span>
            <span v-if="issue.method">{{ issue.method }}</span>
          </div>
          <p>{{ issue.judgment }}</p>
        </li>
      </ul>
      <p class="cultural-prerun-review__note">
        问题清单不含责任人、分派或处理状态；完整性问题不通过改分消除。
      </p>
    </section>

    <section class="cultural-prerun-review__section">
      <h5>完整性告警（{{ payload.integrity_warnings.length }}）</h5>
      <p v-if="!payload.integrity_warnings.length" class="cultural-prerun-review__note">
        未发现完整性告警，语料与 Direct / 3-Agent / Judge 证据集合一致。
      </p>
      <ul v-else class="cultural-prerun-review__warnings">
        <li
          v-for="(warning, index) in payload.integrity_warnings"
          :key="`${warning.code}-${index}`"
        >
          <span class="cultural-prerun-review__warning-code">{{ warning.code }}</span>
          <span>{{ warning.message }}</span>
        </li>
      </ul>
      <p class="cultural-prerun-review__note">
        冻结样本数：{{ payload.frozen_evidence.sample_count }} 条；告警不触发重新判分。
      </p>
    </section>

    <section class="cultural-prerun-review__section">
      <h5>结论边界</h5>
      <ul class="cultural-prerun-review__list">
        <li v-for="item in payload.envelope.claim_boundaries" :key="item">{{ item }}</li>
      </ul>
      <h5>局限</h5>
      <ul class="cultural-prerun-review__list">
        <li v-for="item in payload.envelope.limitations" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section class="cultural-prerun-review__section" aria-label="证据包导出">
      <h5>证据包导出</h5>
      <p class="cultural-prerun-review__note">
        从冻结快照导出可打印报告、CSV / JSON 问题清单与 manifest；重开任务仍可下载同一包。
      </p>
      <div class="cultural-prerun-review__exports">
        <button
          type="button"
          class="cultural-prerun-review__export-button"
          :disabled="exportBusy"
          @click="downloadEvidencePack"
        >
          {{ exportBusy ? '正在导出…' : '导出证据包' }}
        </button>
      </div>
      <p v-if="exportError" class="cultural-record-detail__review-error" role="alert">
        {{ exportError }}
      </p>
    </section>

    <footer class="cultural-prerun-review__footer">
      <span>任务 ID：{{ payload.task_id }}</span>
      <span>完成时间：{{ formatTime(payload.completed_at) }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'

import type {
  CulturalReviewIssue,
  CulturalPrerunReviewReport,
  GovernanceSessionMessage,
} from '@/types'
import GovernanceReportEnvelope from '@/components/governance/GovernanceReportEnvelope.vue'
import { GOVERNANCE_CULTURAL_REVIEW_ACTIONS } from '@/utils/governance-cultural-review-actions'
import { formatMetricRate } from '@/utils/governance-format'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const review = inject(GOVERNANCE_CULTURAL_REVIEW_ACTIONS, null)
const issueView = ref<'content' | 'integrity'>('content')

// The report renders only from the persisted message payload (#88 constraint 6):
// refreshing or reopening the session never re-reads the upstream benchmark.
const payload = computed<CulturalPrerunReviewReport | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cultural_prerun_review' || !raw) return null
  if (raw.capability !== 'cultural_prerun_review' || typeof raw.task_id !== 'string') return null
  return raw as unknown as CulturalPrerunReviewReport
})

const contentIssues = computed<CulturalReviewIssue[]>(
  () => payload.value?.issue_lists?.content ?? [],
)
const integrityIssues = computed<CulturalReviewIssue[]>(
  () => payload.value?.issue_lists?.integrity ?? [],
)
const activeIssues = computed(() =>
  issueView.value === 'content' ? contentIssues.value : integrityIssues.value,
)

const exportBusy = computed(() => {
  const taskId = payload.value?.task_id
  return Boolean(taskId) && review?.exportBusyTaskId === taskId
})

const exportError = computed(() => {
  const taskId = payload.value?.task_id
  if (!review || !taskId || review.exportErrorTaskId !== taskId) return ''
  return review.exportError
})

function formatTime(value: string) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

function downloadEvidencePack() {
  const current = payload.value
  if (!current || !review) return
  review.downloadEvidencePack(current.task_id)
}
</script>
