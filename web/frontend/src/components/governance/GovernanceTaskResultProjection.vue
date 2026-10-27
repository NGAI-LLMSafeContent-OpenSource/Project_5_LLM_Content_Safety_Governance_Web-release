<template>
  <section
    v-if="result"
    class="governance-result-projection"
    :class="`is-${mode}`"
    :aria-label="resolvedTitle"
  >
    <h3 v-if="resolvedTitle" class="governance-result-projection__title">{{ resolvedTitle }}</h3>

    <details class="governance-result-projection__section" open>
      <summary>结论</summary>
      <div class="governance-result-projection__body">
        <div class="governance-result-projection__counts">
          <span class="governance-result-projection__chip is-consistent">
            一致：{{ result.summary.consistent_count }}
          </span>
          <span class="governance-result-projection__chip is-inconsistent">
            不一致：{{ result.summary.inconsistent_count }}
          </span>
          <span class="governance-result-projection__chip is-failed">
            失败：{{ result.summary.failed_count }}
          </span>
          <span class="governance-result-projection__chip">
            未执行：{{ result.summary.not_executed_count }}
          </span>
          <span v-if="result.partial" class="governance-result-projection__chip is-partial">
            部分结果
          </span>
        </div>
        <dl class="governance-result-projection__grid">
          <div class="governance-result-projection__field">
            <dt>任务状态</dt>
            <dd>{{ result.status || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>完成时间</dt>
            <dd>{{ formatGovernanceTime(result.completed_at) }}</dd>
          </div>
        </dl>
      </div>
    </details>

    <details class="governance-result-projection__section">
      <summary>冻结范围</summary>
      <div class="governance-result-projection__body">
        <dl class="governance-result-projection__grid">
          <div class="governance-result-projection__field">
            <dt>数据资产</dt>
            <dd>{{ result.asset_name || result.asset_id || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>资产标识</dt>
            <dd>{{ result.asset_id || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>样本数量</dt>
            <dd>{{ result.sample_count }}</dd>
          </div>
        </dl>
        <p v-if="filterEntries.length" class="governance-result-projection__subheading">筛选条件</p>
        <ul v-if="filterEntries.length" class="governance-result-projection__tags">
          <li v-for="entry in filterEntries" :key="entry.key">{{ entry.key }}：{{ entry.value }}</li>
        </ul>
        <p v-else class="governance-result-projection__empty-line">未附加筛选条件。</p>
      </div>
    </details>

    <details class="governance-result-projection__section">
      <summary>指标体系</summary>
      <div class="governance-result-projection__body">
        <dl class="governance-result-projection__grid">
          <div class="governance-result-projection__field">
            <dt>检测方式</dt>
            <dd>{{ result.method || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>能力版本</dt>
            <dd>{{ result.capability_version || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>结果结构</dt>
            <dd>{{ latestRun?.result_schema || '—' }}</dd>
          </div>
          <div class="governance-result-projection__field">
            <dt>执行器指纹</dt>
            <dd>{{ latestRun?.executor_fingerprint || '—' }}</dd>
          </div>
        </dl>
      </div>
    </details>

    <details class="governance-result-projection__section">
      <summary>证据（{{ result.samples.length }} 条）</summary>
      <div class="governance-result-projection__body">
        <p v-if="!result.samples.length" class="governance-result-projection__empty-line">
          本结果未附带样本证据。
        </p>
        <ol v-else class="governance-result-projection__samples">
          <li
            v-for="sample in result.samples"
            :key="sample.sample_id"
            class="governance-result-projection__sample"
          >
            <p class="governance-result-projection__sample-id">{{ sample.sample_id }}</p>
            <p
              v-if="sampleTextVisible"
              class="governance-result-projection__sample-text"
            >
              {{ sample.text }}
            </p>
            <div class="governance-result-projection__badges">
              <span
                v-if="sample.reference_label"
                class="governance-result-projection__label"
                :class="labelClass(sample.reference_label)"
              >
                参考标注：{{ formatRiskLabel(sample.reference_label) }}
              </span>
              <span
                v-if="sample.detected_label"
                class="governance-result-projection__label"
                :class="labelClass(sample.detected_label)"
              >
                本次检测：{{ formatRiskLabel(sample.detected_label) }}
              </span>
              <span class="governance-result-projection__chip" :class="`is-${sample.status}`">
                {{ sampleStatusDisplay(sample.status) }}
              </span>
              <span v-if="sample.source" class="governance-result-projection__chip">
                来源：{{ sample.source }}
              </span>
            </div>
            <p v-if="sample.reason" class="governance-result-projection__sample-reason">
              {{ sample.reason }}
            </p>
          </li>
        </ol>
      </div>
    </details>

    <details class="governance-result-projection__section">
      <summary>来源与运行历史</summary>
      <div class="governance-result-projection__body">
        <p v-if="!result.runs.length" class="governance-result-projection__empty-line">
          本结果未附带运行来源明细。
        </p>
        <ol v-else class="governance-result-projection__runs">
          <li v-for="run in result.runs" :key="run.run_id" class="governance-result-projection__run">
            <span class="governance-result-projection__run-attempt">第 {{ run.attempt }} 次</span>
            <span>{{ run.status || '—' }}</span>
            <span>{{ run.scope_selection || '—' }}</span>
            <span>{{ formatGovernanceTime(run.started_at) }}</span>
            <span class="governance-result-projection__run-fingerprint">
              {{ run.executor_fingerprint || '—' }}
            </span>
          </li>
        </ol>
        <ul v-if="sourceRefs.length" class="governance-result-projection__tags">
          <li v-for="ref in sourceRefs" :key="`${ref.ref_type}-${ref.ref_id}`">
            {{ ref.name || ref.ref_id }}（{{ ref.source_repo || '来源未知' }}）
          </li>
        </ul>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { GovernanceResultProjectionData } from '@/types'
import { formatGovernanceTime, formatRiskLabel, toFilterEntries } from '@/utils/governance-format'

const props = withDefaults(
  defineProps<{
    mode: 'executable' | 'review'
    result: GovernanceResultProjectionData | null
    showSampleText?: boolean
    title?: string
  }>(),
  {
    title: '治理任务结果',
  },
)

const resolvedTitle = computed(() => props.title?.trim() ?? '')

// 只读结果投影的样本文本开关：executable 默认展示样本原文；review 模式默认隐藏，
// 只有父级显式传入 showSampleText === true 才渲染（#65 §6，供 #66 评审页复用）。
const sampleTextVisible = computed(() => props.showSampleText ?? props.mode === 'executable')

const filterEntries = computed(() => toFilterEntries(props.result?.filters))

// 「指标体系」的 result_schema 与执行器指纹来自运行记录；取最近一次 attempt。
const latestRun = computed(() => {
  const runs = props.result?.runs ?? []
  return runs.length ? runs[runs.length - 1] : null
})

const sourceRefs = computed(() => props.result?.source_refs ?? [])

const SAMPLE_STATUS_DISPLAY: Record<string, string> = {
  consistent: '一致',
  inconsistent: '不一致',
  failed: '失败',
  not_executed: '未执行',
}

function sampleStatusDisplay(status: string) {
  return SAMPLE_STATUS_DISPLAY[status] ?? status
}

function labelClass(label: string) {
  return label === 'unsafe' ? 'is-risky' : 'is-safe'
}
</script>
