<template>
  <div v-if="payload" class="risk-corpus-card" aria-label="风险语料概览">
    <div v-if="!payload.available" class="risk-corpus-card__empty">{{ message.content }}</div>
    <template v-else>
      <div class="risk-corpus-card__stats">
        <div class="risk-corpus-card__stat">
          <strong>{{ payload.sample_count }}</strong>
          <span>样本总数</span>
        </div>
        <div class="risk-corpus-card__stat">
          <strong>{{ riskyCount }}</strong>
          <span>不安全样本</span>
        </div>
        <div class="risk-corpus-card__stat">
          <strong>{{ payload.asset_name || '—' }}</strong>
          <span>风险语料资产</span>
        </div>
      </div>
      <div v-if="referenceLabelEntries.length" class="risk-corpus-card__section">
        <h4>参考标注分布</h4>
        <ul>
          <li v-for="entry in referenceLabelEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="l1Entries.length" class="risk-corpus-card__section">
        <h4>一级风险分类分布</h4>
        <ul>
          <li v-for="entry in l1Entries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="l2Entries.length" class="risk-corpus-card__section">
        <h4>二级风险分类分布</h4>
        <ul>
          <li v-for="entry in l2Entries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="sourceEntries.length" class="risk-corpus-card__section">
        <h4>来源分布</h4>
        <ul>
          <li v-for="entry in sourceEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="sourceSummary" class="risk-corpus-card__source">来源：{{ sourceSummary }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GovernanceRiskCorpusOverviewPayload, GovernanceSessionMessage } from '@/types'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const LABEL_DISPLAY: Record<string, string> = { safe: '安全', unsafe: '不安全' }

function toEntries(distribution?: Record<string, number>) {
  return Object.entries(distribution ?? {}).map(([label, count]) => ({ label, count }))
}

const payload = computed<GovernanceRiskCorpusOverviewPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_corpus_overview' || !raw) return null
  if (typeof raw.sample_count !== 'number') return null
  return raw as unknown as GovernanceRiskCorpusOverviewPayload
})

const riskyCount = computed(() => payload.value?.reference_label_distribution?.['unsafe'] ?? 0)

const referenceLabelEntries = computed(() =>
  toEntries(payload.value?.reference_label_distribution).map((entry) => ({
    label: LABEL_DISPLAY[entry.label] ?? entry.label,
    count: entry.count,
  })),
)
const l1Entries = computed(() => toEntries(payload.value?.harm_category_L1_distribution))
const l2Entries = computed(() => toEntries(payload.value?.harm_category_L2_distribution))
const sourceEntries = computed(() => toEntries(payload.value?.source_distribution))

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref) => {
      const revision = [ref.source_repo, ref.source_commit].filter(Boolean).join('@')
      return revision || ref.name || ref.ref_id
    })
    .filter(Boolean)
    .join('、')
})
</script>
