<template>
  <div
    v-if="payload"
    class="cbrne-gov-card"
    data-testid="cbrne-overview-card"
    aria-label="CBRNE 资产总览"
  >
    <div v-if="!payload.available" class="cbrne-gov-card__empty">{{ message.content }}</div>
    <template v-else>
      <p class="cbrne-gov-card__badge">只读登记事实 · 非评测执行</p>
      <div class="cbrne-gov-card__stats">
        <div class="cbrne-gov-card__stat">
          <strong>{{ payload.sample_count }}</strong>
          <span>样本总数</span>
        </div>
        <div class="cbrne-gov-card__stat">
          <strong>v{{ payload.asset_version || '—' }}</strong>
          <span>资产版本</span>
        </div>
        <div class="cbrne-gov-card__stat">
          <strong>{{ payload.is_current ? '当前' : '历史' }}</strong>
          <span>版本指针</span>
        </div>
      </div>
      <p class="cbrne-gov-card__meta">{{ payload.asset_id }} · record {{ shortVersion }}</p>
      <div v-if="labelEntries.length" class="cbrne-gov-card__section">
        <h4>标签分布</h4>
        <ul>
          <li v-for="entry in labelEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="categoryEntries.length" class="cbrne-gov-card__section">
        <h4>CBRNE 类别分布</h4>
        <ul>
          <li v-for="entry in categoryEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="sourceEntries.length" class="cbrne-gov-card__section">
        <h4>来源</h4>
        <ul>
          <li v-for="entry in sourceEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="tierEntries.length" class="cbrne-gov-card__section">
        <h4>T1–T4</h4>
        <ul>
          <li v-for="entry in tierEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <div v-if="difficultyEntries.length" class="cbrne-gov-card__section">
        <h4>评估器相对难度</h4>
        <ul>
          <li v-for="entry in difficultyEntries" :key="entry.label">
            <span>{{ entry.label }}</span>
            <strong>{{ entry.count }}</strong>
          </li>
        </ul>
      </div>
      <RouterLink
        class="cbrne-gov-card__link"
        data-testid="cbrne-benchmark-asset-link"
        :to="payload.benchmark_href || cbrneAssetBenchmarkHref(payload.asset_id || '')"
        target="_blank"
        rel="noopener noreferrer"
      >
        在 Benchmark 查看资产
      </RouterLink>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { GovernanceCbrneOverviewPayload, GovernanceSessionMessage } from '@/types'
import { cbrneAssetBenchmarkHref } from '@/utils/governance-cbrne-links'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceCbrneOverviewPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cbrne_dataset_overview' || !raw) return null
  if (typeof raw.sample_count !== 'number') return null
  return raw as unknown as GovernanceCbrneOverviewPayload
})

const shortVersion = computed(() => {
  const value = payload.value?.record_version || ''
  return value.length > 12 ? `${value.slice(0, 12)}…` : value || '—'
})

function toEntries(distribution?: Record<string, number>) {
  return Object.entries(distribution ?? {}).map(([label, count]) => ({ label, count }))
}

const labelEntries = computed(() => toEntries(payload.value?.label_counts))
const categoryEntries = computed(() => toEntries(payload.value?.cbrne_category_counts))
const sourceEntries = computed(() => toEntries(payload.value?.source_counts))
const tierEntries = computed(() => toEntries(payload.value?.exposure_tier_counts))
const difficultyEntries = computed(() =>
  toEntries(payload.value?.evaluator_relative_difficulty_counts),
)
</script>
