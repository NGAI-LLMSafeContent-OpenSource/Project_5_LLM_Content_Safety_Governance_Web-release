<template>
  <div
    v-if="run || notice"
    class="risk-rescan-result-card"
    aria-label="输入风险语料在线二次检测结果"
  >
    <template v-if="run">
      <header class="risk-rescan-result-card__head">
        <div>
          <p class="risk-rescan-result-card__eyebrow">{{ assetDisplayName }}</p>
          <h4>{{ incomplete ? '在线二次检测报告（未完整完成）' : '在线二次检测报告' }}</h4>
        </div>
        <span class="risk-rescan-result-card__badge">不计算准确率 · 参考标注非 ground truth</span>
      </header>

      <p class="risk-rescan-result-card__content">{{ message.content }}</p>
      <p v-if="incomplete" class="risk-rescan-result-card__note" role="status">
        本报告不是完整检测完成记录；失败或未执行样本不得计入准确率。
      </p>

      <GovernanceReportEnvelope v-if="run.envelope" :envelope="run.envelope" />

      <section class="risk-rescan-result-card__section" aria-label="检测身份">
        <h5>检测身份</h5>
        <dl class="risk-rescan-result-card__facts">
          <div>
            <dt>评测对象</dt>
            <dd>{{ evaluationObject.name || run.asset_name || '—' }}</dd>
          </div>
          <div>
            <dt>资产版本（内容摘要）</dt>
            <dd class="risk-rescan-result-card__mono">{{ truncatedSha || '—' }}</dd>
          </div>
          <div>
            <dt>校验器身份</dt>
            <dd>{{ evaluatorLabel }}</dd>
          </div>
          <div>
            <dt>执行器身份</dt>
            <dd>{{ executorLabel }}</dd>
          </div>
          <div>
            <dt>冻结条数</dt>
            <dd>{{ run.sample_count }}</dd>
          </div>
        </dl>
      </section>

      <section class="risk-rescan-result-card__section" aria-label="执行进度">
        <h5>执行进度（进度计数，不是准确率）</h5>
        <dl class="risk-rescan-result-card__facts">
          <div>
            <dt>已执行</dt>
            <dd>{{ executionSummary.executed_count }}</dd>
          </div>
          <div>
            <dt>失败</dt>
            <dd>{{ executionSummary.failed_count }}</dd>
          </div>
          <div>
            <dt>未执行</dt>
            <dd>{{ executionSummary.not_executed_count }}</dd>
          </div>
        </dl>
      </section>

      <section class="risk-rescan-result-card__section" aria-label="问题清单">
        <div class="risk-rescan-result-card__issues-head">
          <h5>问题清单（两个视图）</h5>
          <div class="risk-rescan-result-card__tabs" role="tablist" aria-label="问题清单视图">
            <button
              type="button"
              role="tab"
              class="risk-rescan-result-card__tab"
              :class="{ 'is-active': issueView === 'risk_hit' }"
              :aria-selected="issueView === 'risk_hit'"
              @click="issueView = 'risk_hit'"
            >
              风险命中（{{ riskHitIssues.length }}）
            </button>
            <button
              type="button"
              role="tab"
              class="risk-rescan-result-card__tab"
              :class="{ 'is-active': issueView === 'reference_label_disagreement' }"
              :aria-selected="issueView === 'reference_label_disagreement'"
              @click="issueView = 'reference_label_disagreement'"
            >
              参考标注分歧（{{ disagreementIssues.length }}）
            </button>
          </div>
        </div>
        <p v-if="!activeIssues.length" class="risk-rescan-result-card__note">
          {{
            issueView === 'risk_hit'
              ? `未发现风险命中（${evaluatorLabel} 未判定 unsafe）。`
              : '未发现与参考标注的分歧。'
          }}
        </p>
        <ul v-else class="risk-rescan-result-card__issues">
          <li v-for="issue in activeIssues" :key="issue.issue_id">
            <div class="risk-rescan-result-card__issue-meta">
              <span class="risk-rescan-result-card__warning-code">{{ issue.category }}</span>
              <span v-if="issue.sample_id">样本 {{ issue.sample_id }}</span>
              <span v-if="issue.reference_label">
                参考 {{ formatRiskLabel(issue.reference_label) }}
              </span>
              <span v-if="issue.detected_label">
                检出 {{ formatRiskLabel(issue.detected_label) }}
              </span>
            </div>
            <p>{{ issue.judgment }}</p>
          </li>
        </ul>
        <p class="risk-rescan-result-card__note">
          参考标注为只读事实，本次检测结果并列展示，不回写原始标注。清单条数不是准确率或一致率。
        </p>
      </section>

      <section
        v-if="run.disclosure_limits?.length || run.integrity_facts?.length"
        class="risk-rescan-result-card__section"
      >
        <h5 v-if="run.disclosure_limits?.length">披露限制</h5>
        <ul v-if="run.disclosure_limits?.length" class="risk-rescan-result-card__list">
          <li v-for="item in run.disclosure_limits" :key="item">{{ item }}</li>
        </ul>
        <h5 v-if="run.integrity_facts?.length">完整性事实</h5>
        <ul v-if="run.integrity_facts?.length" class="risk-rescan-result-card__list">
          <li v-for="item in run.integrity_facts" :key="item">{{ item }}</li>
        </ul>
      </section>

      <section v-if="run.envelope" class="risk-rescan-result-card__section">
        <h5>结论边界</h5>
        <ul class="risk-rescan-result-card__list">
          <li v-for="item in run.envelope.claim_boundaries" :key="item">{{ item }}</li>
        </ul>
        <h5>局限</h5>
        <ul class="risk-rescan-result-card__list">
          <li v-for="item in run.envelope.limitations" :key="item">{{ item }}</li>
        </ul>
      </section>

      <footer class="risk-rescan-result-card__footer">
        <span>任务 ID：{{ run.task_id }}</span>
        <span>检索条件：{{ filterSummary }}</span>
        <span>完成时间：{{ formatTime(run.completed_at) }}</span>
      </footer>

      <div v-if="exportable" class="risk-rescan-result-card__actions">
        <button
          type="button"
          class="risk-rescan-result-card__button"
          :disabled="exportBusy"
          @click="downloadEvidencePack"
        >
          {{ exportBusy ? '正在导出…' : '导出证据包' }}
        </button>
        <span v-if="exportError" class="risk-rescan-result-card__error" role="alert">
          {{ exportError }}
        </span>
      </div>
    </template>

    <template v-else-if="notice">
      <div class="risk-rescan-result-card__notice" :class="`is-${notice.status}`">
        <p>{{ message.content }}</p>
        <p class="risk-rescan-result-card__notice-reason">{{ notice.reason }}</p>
        <button
          v-if="retryable"
          type="button"
          class="risk-rescan-result-card__button"
          :disabled="inFlight"
          @click="rescan?.retry(notice.task_id)"
        >
          {{ retryBusy ? '正在创建重试任务…' : '重试（创建关联新任务）' }}
        </button>
        <span v-if="error" class="risk-rescan-result-card__error" role="alert">
          {{ error }}
        </span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'

import type {
  GovernanceRiskRescanNoticePayload,
  GovernanceRiskRescanRunPayload,
  GovernanceSessionMessage,
  RiskRescanIssue,
} from '@/types'
import { GOVERNANCE_RESCAN_ACTIONS } from '@/utils/governance-rescan-actions'
import { formatRiskLabel, formatRiskRescanEvaluator } from '@/utils/governance-format'
import GovernanceReportEnvelope from '@/components/governance/GovernanceReportEnvelope.vue'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const rescan = inject(GOVERNANCE_RESCAN_ACTIONS, null)
const issueView = ref<'risk_hit' | 'reference_label_disagreement'>('risk_hit')

const run = computed<GovernanceRiskRescanRunPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_corpus_rescan' || !raw) return null
  if (raw.phase !== 'result') return null
  return raw as unknown as GovernanceRiskRescanRunPayload
})

const notice = computed<GovernanceRiskRescanNoticePayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_corpus_rescan' || !raw) return null
  if (raw.phase !== 'failed' && raw.phase !== 'cancelled') return null
  return raw as unknown as GovernanceRiskRescanNoticePayload
})

const taskId = computed(() => run.value?.task_id ?? notice.value?.task_id ?? '')

const evaluationObject = computed(() => run.value?.evaluation_object ?? {})

// The display name is owned by the backend (`RISK_STATIC_ASSET_DISPLAY_NAME`),
// which stamps it on both the preview and the result; the card must not keep a
// second copy of the canonical string.
const assetDisplayName = computed(
  () => run.value?.asset_name || evaluationObject.value.name || '输入风险静态验证语料',
)

const truncatedSha = computed(() => {
  const sha = String(evaluationObject.value.content_sha256 || '')
  if (!sha) return ''
  return sha.length > 16 ? `${sha.slice(0, 16)}…` : sha
})

const executionSummary = computed(
  () =>
    run.value?.execution_summary ?? {
      executed_count: 0,
      failed_count: 0,
      not_executed_count: 0,
    },
)

const riskHitIssues = computed<RiskRescanIssue[]>(() => run.value?.issue_lists?.risk_hit ?? [])
const disagreementIssues = computed<RiskRescanIssue[]>(
  () => run.value?.issue_lists?.reference_label_disagreement ?? [],
)
const activeIssues = computed(() =>
  issueView.value === 'risk_hit' ? riskHitIssues.value : disagreementIssues.value,
)

const incomplete = computed(
  () => Boolean(run.value) && (run.value?.partial === true || run.value?.status !== 'completed'),
)

const evaluatorLabel = computed(() =>
  formatRiskRescanEvaluator(run.value?.evaluator || run.value?.method || ''),
)

const executorLabel = computed(() => {
  const identity = run.value?.executor_identity
  if (!identity) return '—'
  const parts = [identity.agent_id, identity.source_commit, identity.reproduce_command].filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  )
  return parts.length ? parts.join(' · ') : '—'
})

const filterSummary = computed(() => {
  const filters = run.value?.filters
  if (!filters || !Object.keys(filters).length) return '无筛选（全量）'
  return Object.entries(filters)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join('、')
})

const retryable = computed(() =>
  notice.value ? ['failed', 'cancelled', 'timeout'].includes(notice.value.status) : false,
)

const exportable = computed(
  () => run.value?.status === 'completed' && run.value?.export_available === true,
)

const exportBusy = computed(
  () => Boolean(taskId.value) && rescan?.exportBusyTaskId === taskId.value,
)

const exportError = computed(() => {
  const actions = rescan
  const id = taskId.value
  if (!actions || !id || actions.exportErrorTaskId !== id) return ''
  return actions.exportError
})

function downloadEvidencePack() {
  const id = taskId.value
  if (id && exportable.value) rescan?.downloadRiskRescanEvidencePack(id)
}

const inFlight = computed(() => Boolean(taskId.value) && rescan?.busyTaskId === taskId.value)

const retryBusy = computed(() => inFlight.value && rescan?.busyAction === 'retry')

const error = computed(() => {
  const actions = rescan
  const id = taskId.value
  if (!actions || !id || actions.errorTaskId !== id) return ''
  return actions.error
})

function formatTime(value: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>
