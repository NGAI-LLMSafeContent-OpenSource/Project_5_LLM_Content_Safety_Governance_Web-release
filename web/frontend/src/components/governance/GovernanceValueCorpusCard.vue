<template>
  <div v-if="payload" class="value-corpus-card" aria-label="价值语料概览">
    <div v-if="!payload.available" class="value-corpus-card__empty">
      当前尚未导入可用的价值语料资产，无法展示语料构成。
    </div>
    <template v-else>
      <div class="value-corpus-card__stats">
        <div class="value-corpus-card__stat">
          <strong>{{ payload.sample_count }}</strong>
          <span>样本总数</span>
        </div>
        <div class="value-corpus-card__stat">
          <strong>{{ payload.group_count }}</strong>
          <span>价值三联组</span>
        </div>
        <div class="value-corpus-card__stat">
          <strong>{{ payload.asset_name || '—' }}</strong>
          <span>价值语料资产</span>
        </div>
      </div>
      <div v-if="qualityEntries.length" class="value-corpus-card__section">
        <h4>质量等级分布</h4>
        <ul>
          <li v-for="entry in qualityEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="primaryEntries.length" class="value-corpus-card__section">
        <h4>一级维度分布</h4>
        <ul>
          <li v-for="entry in primaryEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="secondaryEntries.length" class="value-corpus-card__section">
        <h4>二级维度分布</h4>
        <ul>
          <li v-for="entry in secondaryEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="sourceSummary" class="value-corpus-card__source">来源：{{ sourceSummary }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GovernanceSessionMessage, GovernanceValueCorpusOverviewPayload } from '@/types'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

function toEntries(distribution?: Record<string, number>) {
  return Object.entries(distribution ?? {}).map(([label, count]) => ({ label, count }))
}

const payload = computed<GovernanceValueCorpusOverviewPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'value_corpus_overview' || !raw) return null
  if (typeof raw.sample_count !== 'number' || typeof raw.group_count !== 'number') return null
  return raw as unknown as GovernanceValueCorpusOverviewPayload
})

const qualityEntries = computed(() => toEntries(payload.value?.quality_level_distribution))
const primaryEntries = computed(() => toEntries(payload.value?.primary_dimension_distribution))
const secondaryEntries = computed(() => toEntries(payload.value?.secondary_dimension_distribution))

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref) => [ref.source_repo, ref.source_commit].filter(Boolean).join('@'))
    .filter(Boolean)
    .join('、')
})
</script>
