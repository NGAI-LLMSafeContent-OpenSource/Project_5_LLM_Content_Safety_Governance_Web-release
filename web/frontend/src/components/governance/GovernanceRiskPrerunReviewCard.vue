<template>
  <div v-if="payload" class="risk-prerun-review" aria-label="风险预跑记录审阅报告">
    <header class="risk-prerun-review__head">
      <div>
        <p class="risk-prerun-review__eyebrow">风险识别器交叉核对 · 预跑记录审阅</p>
        <h4>
          {{ payload.baseline_evaluator ? 'V7 正式摘要与 Base 基线对照' : 'V7 正式摘要' }}
        </h4>
      </div>
      <span class="risk-prerun-review__badge">报告快照 · 不重新读取上游</span>
    </header>

    <p class="risk-prerun-review__content">{{ message.content }}</p>

    <GovernanceReportEnvelope :envelope="payload.envelope" />

    <section class="risk-prerun-review__section" aria-label="版本列">
      <h5>版本身份</h5>
      <div class="risk-prerun-review__versions">
        <article class="risk-prerun-review__version">
          <strong>
            评测对象 {{ payload.envelope.evaluated_object.benchmark_version || 'v6' }}
          </strong>
          <span>
            {{
              payload.envelope.evaluated_object.dataset_label ||
              payload.envelope.evaluated_object.record_id
            }}
          </span>
          <span>{{ payload.envelope.evaluated_object.taxonomy_schema || 'C01-C17' }}</span>
        </article>
        <article class="risk-prerun-review__version is-primary">
          <strong>V7 正式</strong>
          <span><BreakableText :text="payload.primary_evaluator.model_id" /></span>
          <span><BreakableText :text="payload.primary_evaluator.run_id" /></span>
        </article>
        <article v-if="payload.baseline_evaluator" class="risk-prerun-review__version is-baseline">
          <strong>Base 基线</strong>
          <span><BreakableText :text="payload.baseline_evaluator.model_id" /></span>
          <span><BreakableText :text="payload.baseline_evaluator.run_id" /></span>
        </article>
        <article v-else class="risk-prerun-review__version is-baseline">
          <strong>基线对照</strong>
          <span>本版本暂无同版本基线</span>
        </article>
      </div>
      <p class="risk-prerun-review__note">
        {{
          payload.baseline_evaluator
            ? 'V7 为正式摘要与问题清单依据；Base 仅作基线对照段落，二者不得静默合并。'
            : 'V7 为正式摘要与问题清单依据；本版本暂无同版本基线。'
        }}
      </p>
    </section>

    <section class="risk-prerun-review__section">
      <h5>正式摘要（V7 · primary）</h5>
      <p class="risk-prerun-review__note">
        <BreakableText
          :text="payload.primary_evaluator.display_name || payload.primary_evaluator.model_id"
        />
        · 预测 {{ payload.primary_evaluator.predictions_count }} 条
      </p>
      <ul class="risk-prerun-review__metrics">
        <li v-for="entry in primaryMetricEntries" :key="entry.key">
          <span>{{ entry.label }}</span>
          <strong>{{ entry.value }}</strong>
        </li>
      </ul>
      <details class="risk-prerun-review__details">
        <summary>二分类 / 等级 / 多标签指标</summary>
        <ul class="risk-prerun-review__metrics">
          <li v-for="entry in primaryDimensionEntries" :key="entry.key">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.value }}</strong>
          </li>
        </ul>
      </details>
    </section>

    <section v-if="payload.baseline_evaluator" class="risk-prerun-review__section">
      <h5>基线对照（Base · baseline）</h5>
      <p class="risk-prerun-review__note">
        <BreakableText
          :text="payload.baseline_evaluator.display_name || payload.baseline_evaluator.model_id"
        />
        · 预测 {{ payload.baseline_evaluator.predictions_count }} 条 · 仅对照，不作为正式结论
      </p>
      <ul class="risk-prerun-review__metrics">
        <li v-for="entry in baselineMetricEntries" :key="entry.key">
          <span>{{ entry.label }}</span>
          <strong>{{ entry.value }}</strong>
        </li>
      </ul>
    </section>

    <section class="risk-prerun-review__section">
      <h5>四维审阅范围</h5>
      <ol class="risk-prerun-review__dimensions">
        <li v-for="dimension in payload.dimension_summaries" :key="dimension.key">
          <strong>{{ dimension.label }}</strong>
          <span>{{ dimension.description }}</span>
        </li>
      </ol>
      <p class="risk-prerun-review__note">
        本报告不以综合安全分汇总；验证的是风险识别器，不是生成模型整体安全性。
      </p>
    </section>

    <section class="risk-prerun-review__section" aria-label="问题清单">
      <div class="risk-prerun-review__issues-head">
        <h5>问题清单</h5>
        <div class="risk-prerun-review__tabs" role="tablist" aria-label="问题清单视图">
          <button
            type="button"
            role="tab"
            class="risk-prerun-review__tab"
            :class="{ 'is-active': issueView === 'recognition' }"
            :aria-selected="issueView === 'recognition'"
            @click="issueView = 'recognition'"
          >
            风险识别差异（{{ recognitionIssues.length }}）
          </button>
          <button
            type="button"
            role="tab"
            class="risk-prerun-review__tab"
            :class="{ 'is-active': issueView === 'integrity' }"
            :aria-selected="issueView === 'integrity'"
            @click="issueView = 'integrity'"
          >
            资产完整性问题（{{ integrityIssues.length }}）
          </button>
        </div>
      </div>
      <p v-if="!activeIssues.length" class="risk-prerun-review__note">
        {{
          issueView === 'recognition'
            ? '未发现风险识别差异（V7 与参考标签一致，或仅有完整性缺陷）。'
            : '未发现资产完整性问题。'
        }}
      </p>
      <ul v-else class="risk-prerun-review__issues">
        <li v-for="issue in activeIssues" :key="issue.issue_id">
          <div class="risk-prerun-review__issue-meta">
            <span class="risk-prerun-review__warning-code">{{ issue.category }}</span>
            <span
              v-if="issue.evidence_state"
              class="risk-prerun-review__evidence-state"
              :class="
                issue.evidence_state === 'confirmed-difference' ? 'is-confirmed' : 'is-pending'
              "
            >
              {{ issue.evidence_state === 'confirmed-difference' ? '已确认差异' : '待人工确认' }}
            </span>
            <span v-if="issue.sample_id">样本 {{ issue.sample_id }}</span>
          </div>
          <p>{{ issue.judgment }}</p>
          <p v-if="issue.excerpt_masked" class="risk-prerun-review__excerpt">
            {{ issue.excerpt_masked }}
          </p>
        </li>
      </ul>
      <p class="risk-prerun-review__note">
        问题清单不含责任人、分派或处理状态；{{
          payload.baseline_evaluator ? 'Base 预测不进入正式清单；' : ''
        }}同一条样本可同时出现在两套视图。
      </p>
    </section>

    <section class="risk-prerun-review__section">
      <h5>完整性告警（{{ payload.integrity_warnings.length }}）</h5>
      <p v-if="!payload.integrity_warnings.length" class="risk-prerun-review__note">
        {{
          payload.baseline_evaluator
            ? '未发现包级完整性告警；V7 / Base 评测包与资产登记一致。'
            : '未发现包级完整性告警；V7 primary 评测包与资产登记一致。'
        }}
      </p>
      <ul v-else class="risk-prerun-review__warnings">
        <li
          v-for="(warning, index) in payload.integrity_warnings"
          :key="`${warning.code}-${index}`"
        >
          <span class="risk-prerun-review__warning-code">{{ warning.code }}</span>
          <span>{{ warning.message }}</span>
        </li>
      </ul>
    </section>

    <section class="risk-prerun-review__section">
      <h5>结论边界</h5>
      <ul class="risk-prerun-review__list">
        <li v-for="item in payload.envelope.claim_boundaries" :key="item">{{ item }}</li>
      </ul>
      <h5>局限</h5>
      <ul class="risk-prerun-review__list">
        <li v-for="item in payload.envelope.limitations" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section class="risk-prerun-review__section" aria-label="证据包导出">
      <h5>证据包导出</h5>
      <p class="risk-prerun-review__note">
        从冻结快照导出受限 HTML 报告、CSV / JSON 问题清单与
        manifest；不含高风险全文，重开任务仍可下载同一包。
      </p>
      <div class="risk-prerun-review__exports">
        <button
          type="button"
          class="risk-prerun-review__export-button"
          :disabled="exportBusy || !review"
          @click="downloadEvidencePack"
        >
          {{ exportBusy ? '正在导出…' : '导出证据包' }}
        </button>
      </div>
      <p v-if="exportError" class="risk-prerun-review__export-error" role="alert">
        {{ exportError }}
      </p>
    </section>

    <footer class="risk-prerun-review__footer">
      <span>任务 ID：{{ payload.task_id }}</span>
      <span>完成时间：{{ formatTime(payload.completed_at) }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'

import type {
  GovernanceSessionMessage,
  RiskEvaluatorMetrics,
  RiskPrerunReviewReport,
  RiskReviewIssue,
} from '@/types'
import GovernanceReportEnvelope from '@/components/governance/GovernanceReportEnvelope.vue'
import BreakableText from '@/components/governance/BreakableText.vue'
import { GOVERNANCE_RISK_REVIEW_ACTIONS } from '@/utils/governance-risk-review-actions'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const review = inject(GOVERNANCE_RISK_REVIEW_ACTIONS, null)
const issueView = ref<'recognition' | 'integrity'>('recognition')

const PRIMARY_LABELS: Record<string, string> = {
  risk_class_accuracy_v4_first_label: '风险内容分层识别准确率',
  risk_recall: '风险内容合规预警覆盖率',
  risk_false_positive_rate: '风险内容误报率',
}

const payload = computed<RiskPrerunReviewReport | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_prerun_review' || !raw) return null
  if (raw.capability !== 'risk_prerun_review' || typeof raw.task_id !== 'string') return null
  return raw as unknown as RiskPrerunReviewReport
})

const recognitionIssues = computed<RiskReviewIssue[]>(
  () => payload.value?.issue_lists?.recognition ?? [],
)
const integrityIssues = computed<RiskReviewIssue[]>(
  () => payload.value?.issue_lists?.integrity ?? [],
)
const activeIssues = computed(() =>
  issueView.value === 'recognition' ? recognitionIssues.value : integrityIssues.value,
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

function metricEntries(metrics: Record<string, unknown>, labels?: Record<string, string>) {
  return Object.entries(metrics ?? {})
    .filter(([, value]) => value !== null && value !== undefined && typeof value !== 'object')
    .map(([key, value]) => ({
      key,
      label: labels?.[key] ?? key,
      value: formatValue(value),
    }))
}

function dimensionEntries(evaluator: RiskEvaluatorMetrics) {
  return [
    ...metricEntries(evaluator.binary_metrics as Record<string, unknown>),
    ...metricEntries(evaluator.level_metrics as Record<string, unknown>),
    ...metricEntries(
      Object.fromEntries(
        Object.entries(evaluator.multilabel_metrics ?? {}).filter(
          ([key]) => key !== 'per_category_metrics',
        ),
      ),
    ),
  ]
}

const primaryMetricEntries = computed(() =>
  metricEntries(
    (payload.value?.primary_evaluator.primary_metrics ?? {}) as Record<string, unknown>,
    PRIMARY_LABELS,
  ),
)
const baselineMetricEntries = computed(() =>
  metricEntries(
    (payload.value?.baseline_evaluator?.primary_metrics ?? {}) as Record<string, unknown>,
    PRIMARY_LABELS,
  ),
)
const primaryDimensionEntries = computed(() =>
  payload.value ? dimensionEntries(payload.value.primary_evaluator) : [],
)

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
