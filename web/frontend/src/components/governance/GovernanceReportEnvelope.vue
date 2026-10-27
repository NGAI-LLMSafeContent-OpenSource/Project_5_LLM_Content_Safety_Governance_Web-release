<template>
  <section class="report-envelope" aria-label="报告证据外壳">
    <div class="report-envelope__statuses">
      <div v-for="status in statuses" :key="status.key" class="report-envelope__status">
        <span class="report-envelope__status-name">{{ status.name }}</span>
        <span class="report-envelope__status-chip" :class="statusChipClass(status.value.code)">
          {{ status.value.label || status.value.code }}
        </span>
        <span v-if="status.value.detail" class="report-envelope__status-detail">
          {{ status.value.detail }}
        </span>
      </div>
    </div>

    <div class="report-envelope__grid">
      <section class="report-envelope__block">
        <h6>评测对象</h6>
        <dl v-if="hasEvaluatedObject" class="report-envelope__facts">
          <div>
            <dt>资产</dt>
            <dd>
              <BreakableText :text="evaluated.name || evaluated.asset_id || '—'" />
            </dd>
          </div>
          <div>
            <dt>资产 ID</dt>
            <dd class="report-envelope__mono">
              <BreakableText :text="evaluated.asset_id || '—'" />
            </dd>
          </div>
          <div v-if="evaluated.filename">
            <dt>文件</dt>
            <dd><BreakableText :text="evaluated.filename" /></dd>
          </div>
          <div>
            <dt>样本数</dt>
            <dd>{{ evaluated.sample_count ?? '—' }}</dd>
          </div>
          <div v-if="evaluated.disclosure_level">
            <dt>披露级别</dt>
            <dd>{{ evaluated.disclosure_level }}</dd>
          </div>
          <div v-if="evaluated.content_sha256">
            <dt>内容摘要</dt>
            <dd class="report-envelope__mono">
              {{ truncateHash(String(evaluated.content_sha256)) }}
            </dd>
          </div>
        </dl>
        <dl v-else class="report-envelope__facts">
          <div>
            <dt>记录</dt>
            <dd>
              <BreakableText :text="evaluated.record_name || evaluated.record_id || '—'" />
            </dd>
          </div>
          <div>
            <dt>记录 ID</dt>
            <dd class="report-envelope__mono">
              <BreakableText :text="evaluated.record_id || '—'" />
            </dd>
          </div>
          <div>
            <dt>记录版本</dt>
            <dd>{{ evaluated.record_version || '—' }}</dd>
          </div>
          <div>
            <dt>数据集</dt>
            <dd>
              <BreakableText :text="evaluated.dataset_label || evaluated.dataset_id || '—'" />
            </dd>
          </div>
          <div>
            <dt>样本数</dt>
            <dd>{{ evaluated.sample_count }}</dd>
          </div>
          <div v-if="evaluated.benchmark_version">
            <dt>基准版本</dt>
            <dd>{{ evaluated.benchmark_version }}</dd>
          </div>
        </dl>
      </section>

      <section class="report-envelope__block">
        <h6>来源身份</h6>
        <dl class="report-envelope__facts">
          <div v-if="source.source_repo || !hasEvaluatedObject">
            <dt>来源仓库</dt>
            <dd><BreakableText :text="source.source_repo || '—'" /></dd>
          </div>
          <div v-if="source.source_commit || !hasEvaluatedObject">
            <dt>来源提交</dt>
            <dd>{{ source.source_commit || '—' }}</dd>
          </div>
          <div>
            <dt>资产哈希</dt>
            <dd class="report-envelope__mono">
              {{ source.asset_sha256 ? truncateHash(String(source.asset_sha256)) : '—' }}
            </dd>
          </div>
          <div v-if="source.static_view_id">
            <dt>静态视图</dt>
            <dd><BreakableText :text="source.static_view_id || '—'" /></dd>
          </div>
          <div v-if="source.benchmark_version">
            <dt>基准版本</dt>
            <dd>{{ source.benchmark_version }}</dd>
          </div>
          <div v-if="source.disclosure_level">
            <dt>披露级别</dt>
            <dd>{{ source.disclosure_level }}</dd>
          </div>
          <div v-if="source.source_message">
            <dt>来源说明</dt>
            <dd>{{ source.source_message }}</dd>
          </div>
          <div v-if="source.licence_message">
            <dt>许可说明</dt>
            <dd>{{ source.licence_message }}</dd>
          </div>
        </dl>
        <ul v-if="source.evidence_files?.length" class="report-envelope__evidence">
          <li v-for="file in source.evidence_files" :key="`${file.role}:${file.path}`">
            <span class="report-envelope__evidence-role">
              <BreakableText :text="file.role" />
            </span>
            <code><BreakableText :text="file.path" /></code>
          </li>
        </ul>
      </section>

      <section class="report-envelope__block">
        <h6>运行身份</h6>
        <dl v-if="isMethodRun" class="report-envelope__facts">
          <div>
            <dt>方式</dt>
            <dd><BreakableText :text="methodRun.method || '—'" /></dd>
          </div>
          <div>
            <dt>能力</dt>
            <dd><BreakableText :text="methodRun.capability || '—'" /></dd>
          </div>
          <div>
            <dt>部分完成</dt>
            <dd>{{ methodRun.partial ? '是' : '否' }}</dd>
          </div>
        </dl>
        <dl v-else-if="isRiskRun" class="report-envelope__facts">
          <div>
            <dt>基准</dt>
            <dd>{{ riskRun.benchmark_version || 'v6' }}</dd>
          </div>
          <div>
            <dt>V7 正式（primary）</dt>
            <dd>
              <BreakableText
                :text="`${riskRun.primary.run_id || '—'} · ${riskRun.primary.model_id || '—'}`"
              />
            </dd>
          </div>
          <div>
            <dt>Base 基线（baseline）</dt>
            <dd>
              <BreakableText
                :text="`${riskRun.baseline.run_id || '—'} · ${riskRun.baseline.model_id || '—'}`"
              />
            </dd>
          </div>
        </dl>
        <dl v-else class="report-envelope__facts">
          <div>
            <dt>Direct</dt>
            <dd>
              <BreakableText
                :text="`${culturalRun.direct.run_id || '—'} · ${culturalRun.direct.model || '—'}`"
              />
            </dd>
          </div>
          <div>
            <dt>3-Agent</dt>
            <dd><BreakableText :text="culturalRun.three_agent.run_id || '—'" /></dd>
          </div>
          <div>
            <dt>3-Agent 流水线</dt>
            <dd class="report-envelope__mono">
              <BreakableText :text="culturalRun.three_agent.pipeline || '—'" />
            </dd>
          </div>
          <div>
            <dt>Judge · 民族识别</dt>
            <dd><BreakableText :text="culturalRun.judge.ethnic_recognition_model || '—'" /></dd>
          </div>
          <div>
            <dt>Judge · 文化特异性</dt>
            <dd><BreakableText :text="culturalRun.judge.cultural_specificity_model || '—'" /></dd>
          </div>
          <div>
            <dt>Judge 范围</dt>
            <dd>{{ judgeScope }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import BreakableText from '@/components/governance/BreakableText.vue'
import type {
  CulturalPrerunReviewEnvelope,
  GovernanceReportEnvelope,
  GovernanceReportStatus,
  RiskPrerunReviewEnvelope,
} from '@/types'

const props = defineProps<{
  envelope: GovernanceReportEnvelope | CulturalPrerunReviewEnvelope | RiskPrerunReviewEnvelope
}>()

interface StatusEntry {
  key: string
  name: string
  value: GovernanceReportStatus
}

// The four statuses are independent facts: the review task completing never
// rewrites the evaluation-run, integrity or delivery-readiness statuses.
const statuses = computed<StatusEntry[]>(() => [
  { key: 'evaluation_run_status', name: '评测运行', value: props.envelope.evaluation_run_status },
  { key: 'integrity_status', name: '完整性', value: props.envelope.integrity_status },
  { key: 'delivery_readiness', name: '交付就绪', value: props.envelope.delivery_readiness },
  { key: 'review_task_status', name: '审阅任务', value: props.envelope.review_task_status },
])

const POSITIVE_STATUS_CODES = new Set(['passed', 'completed', 'ready', 'ok', 'internal_only'])
const WARNING_STATUS_CODES = new Set([
  'warning',
  'not_ready',
  'partial',
  'changed',
  'completed_partial',
])

function statusChipClass(code: string) {
  if (POSITIVE_STATUS_CODES.has(code)) return 'is-positive'
  if (WARNING_STATUS_CODES.has(code)) return 'is-warning'
  return 'is-neutral'
}

function truncateHash(value: string) {
  return value.length > 16 ? `${value.slice(0, 16)}…` : value
}

type EvaluatedView = {
  record_id?: string
  record_name?: string
  record_version?: string
  dataset_id?: string
  dataset_label?: string
  sample_count?: number
  benchmark_version?: string
  asset_id?: string
  name?: string
  filename?: string
  content_sha256?: string
  disclosure_level?: string
}
type SourceView = {
  source_repo?: string
  source_commit?: string
  asset_sha256?: string
  static_view_id?: string
  benchmark_version?: string
  disclosure_level?: string
  source_message?: string
  licence_message?: string
  evidence_files?: { role: string; path: string }[]
}

const evaluated = computed(() => props.envelope.evaluated_object as unknown as EvaluatedView)
const source = computed(() => props.envelope.source_identity as unknown as SourceView)

const hasEvaluatedObject = computed(() =>
  Boolean(evaluated.value.asset_id || evaluated.value.disclosure_level),
)

const isRiskRun = computed(() => {
  const run = props.envelope.run_identity as unknown as Record<string, unknown>
  return Boolean(run && 'primary' in run && 'baseline' in run && !('direct' in run))
})

// A direct capability run (the input-risk re-detection report): identity is
// carried as method + capability rather than the cultural primary/baseline pair.
const isMethodRun = computed(() => {
  const run = props.envelope.run_identity as unknown as Record<string, unknown>
  return Boolean(
    run && 'method' in run && 'capability' in run && !('primary' in run) && !('direct' in run),
  )
})

const methodRun = computed(
  () =>
    props.envelope.run_identity as unknown as {
      method?: string
      capability?: string
      partial?: boolean
    },
)
const riskRun = computed(
  () => props.envelope.run_identity as unknown as RiskPrerunReviewEnvelope['run_identity'],
)
const culturalRun = computed(
  () => props.envelope.run_identity as unknown as CulturalPrerunReviewEnvelope['run_identity'],
)
const judgeScope = computed(() => {
  if (isRiskRun.value || isMethodRun.value) return '—'
  return culturalRun.value.judge.scope.join('、') || '—'
})
</script>
