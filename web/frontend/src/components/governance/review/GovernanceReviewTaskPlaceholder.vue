<template>
  <!--
    Future #65 projection hook:
    Replace this placeholder with GovernanceTaskResultProjection (or equiv) using:
      :mode="'review'"
      :show-sample-text="showSampleText"
      :task="task"
    Do not invent a permanent demo result structure here.
  -->
  <section
    class="gov-review-placeholder"
    aria-label="任务结果（评审只读占位）"
    :data-projection-mode="mode"
    :data-show-sample-text="showSampleText ? 'true' : 'false'"
  >
    <header class="gov-review-placeholder__head">
      <h2>任务结论（fixture 占位）</h2>
      <p>
        只读 dump；#65 合入后以 mode=&apos;review&apos; / showSampleText 替换。不含确认、取消或重试。
      </p>
    </header>

    <dl class="gov-review-placeholder__kv">
      <div v-for="row in overviewRows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.value }}</dd>
      </div>
    </dl>

    <h3>汇总 counts</h3>
    <pre class="gov-review-placeholder__pre">{{ summaryJson }}</pre>

    <h3>范围 filters</h3>
    <pre class="gov-review-placeholder__pre">{{ filtersJson }}</pre>

    <h3>指标体系</h3>
    <dl class="gov-review-placeholder__kv">
      <div v-for="row in indicatorRows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.value }}</dd>
      </div>
    </dl>

    <h3>Provenance ids</h3>
    <pre class="gov-review-placeholder__pre">{{ provenanceJson }}</pre>

    <h3>样本摘录（受 showSampleText 约束）</h3>
    <p v-if="!showSampleText" class="gov-review-placeholder__note">
      样本原文默认隐藏；下列仅含 id / status / labels / digest。
    </p>
    <pre class="gov-review-placeholder__pre">{{ samplesJson }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type {
  GovernanceShareReviewResult,
  GovernanceShareReviewTask,
} from '@/types'

const props = defineProps<{
  task: GovernanceShareReviewTask
  showSampleText: boolean
}>()

/** Reserved for #65 projection props: mode='review' + showSampleText */
const mode = 'review' as const

const result = computed<GovernanceShareReviewResult | null>(() => {
  const raw = props.task.result
  if (!raw || typeof raw !== 'object') return null
  return raw as GovernanceShareReviewResult
})

function asDisplay(value: unknown): string {
  if (value == null || value === '') return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function pretty(value: unknown): string {
  try {
    return JSON.stringify(value ?? null, null, 2)
  } catch {
    return String(value)
  }
}

const overviewRows = computed(() => [
  { label: 'status', value: asDisplay(props.task.status || result.value?.status) },
  {
    label: 'capability',
    value: asDisplay(props.task.capability || result.value?.capability),
  },
  {
    label: 'finished_at / completed_at',
    value: asDisplay(
      props.task.finished_at || props.task.completed_at || result.value?.completed_at,
    ),
  },
  {
    label: 'sample_count',
    value: asDisplay(result.value?.sample_count),
  },
])

const indicatorRows = computed(() => {
  const runs = result.value?.runs
  const firstRun =
    Array.isArray(runs) && runs[0] && typeof runs[0] === 'object'
      ? (runs[0] as Record<string, unknown>)
      : null
  const capabilityVersion =
    props.task.capability_version ||
    (typeof firstRun?.capability_version === 'string' ? firstRun.capability_version : '')
  const resultSchema =
    typeof firstRun?.result_schema === 'string'
      ? firstRun.result_schema
      : typeof (result.value as Record<string, unknown> | null)?.result_schema === 'string'
        ? String((result.value as Record<string, unknown>).result_schema)
        : ''
  return [
    { label: 'method', value: asDisplay(result.value?.method) },
    { label: 'capability_version', value: asDisplay(capabilityVersion) },
    { label: 'result_schema', value: asDisplay(resultSchema) },
  ]
})

const summaryJson = computed(() => pretty(result.value?.summary ?? null))
const filtersJson = computed(() => pretty(result.value?.filters ?? null))

const provenanceJson = computed(() => {
  const runs = Array.isArray(result.value?.runs) ? result.value?.runs : []
  const sourceRefs = Array.isArray(result.value?.source_refs)
    ? result.value?.source_refs
    : []
  const runIds = runs
    .map((run) => {
      if (!run || typeof run !== 'object') return null
      const row = run as Record<string, unknown>
      return {
        run_id: row.run_id ?? null,
        attempt: row.attempt ?? null,
        capability_version: row.capability_version ?? null,
        executor_fingerprint: row.executor_fingerprint ?? null,
      }
    })
    .filter(Boolean)
  const refs = sourceRefs.map((ref) => {
    if (!ref || typeof ref !== 'object') return ref
    const row = ref as Record<string, unknown>
    return {
      ref_type: row.ref_type ?? row.kind ?? null,
      ref_id: row.ref_id ?? row.ref ?? null,
      name: row.name ?? row.label ?? null,
    }
  })
  return pretty({
    active_run_id: props.task.active_run_id ?? null,
    runs: runIds,
    source_refs: refs,
  })
})

const samplesJson = computed(() => {
  const samples = Array.isArray(result.value?.samples) ? result.value?.samples : []
  const rows = samples.map((sample, index) => {
    const row = sample && typeof sample === 'object' ? sample : {}
    const text =
      props.showSampleText && typeof row.text === 'string' ? row.text : undefined
    return {
      sample_id: row.sample_id ?? `sample-${index + 1}`,
      status: row.status ?? null,
      reference_label: row.reference_label ?? null,
      detected_label: row.detected_label ?? null,
      content_digest: row.content_digest ?? null,
      run_id: row.run_id ?? null,
      ...(text !== undefined ? { text } : {}),
    }
  })
  return pretty(rows)
})
</script>

<style scoped>
.gov-review-placeholder {
  display: grid;
  gap: 0.75rem;
  max-width: 56rem;
}

.gov-review-placeholder__head h2 {
  margin: 0;
  font-size: 1.15rem;
}

.gov-review-placeholder__head p {
  margin: 0.35rem 0 0;
  color: #5d6f66;
  font-size: 0.9rem;
}

.gov-review-placeholder h3 {
  margin: 0.5rem 0 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.gov-review-placeholder__kv {
  display: grid;
  gap: 0.45rem;
  margin: 0;
}

.gov-review-placeholder__kv dt {
  margin: 0;
  color: #5d6f66;
  font-size: 0.78rem;
}

.gov-review-placeholder__kv dd {
  margin: 0.1rem 0 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.88rem;
  word-break: break-word;
}

.gov-review-placeholder__pre {
  margin: 0;
  padding: 0.75rem 0.9rem;
  border: 1px solid #d5e0da;
  border-radius: 6px;
  background: #ffffff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.gov-review-placeholder__note {
  margin: 0;
  color: #5d6f66;
  font-size: 0.88rem;
}
</style>
