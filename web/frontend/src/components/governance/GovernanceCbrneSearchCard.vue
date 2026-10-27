<template>
  <div
    v-if="payload"
    class="cbrne-gov-card"
    data-testid="cbrne-search-card"
    aria-label="CBRNE 摘要查询"
  >
    <div v-if="!payload.available || payload.total === 0" class="cbrne-gov-card__empty">
      {{ message.content }}
    </div>
    <template v-else>
      <p class="cbrne-gov-card__badge">脱敏摘要 · 无全文 · 无评测执行</p>
      <div class="cbrne-gov-card__summary">
        {{ message.content }}
      </div>
      <p class="cbrne-gov-card__meta">
        资产 {{ payload.asset_id }} v{{ payload.asset_version || '—' }} · 命中 {{ payload.total }}
      </p>
      <div v-if="filterEntries.length" class="cbrne-gov-card__filters">
        <span v-for="entry in filterEntries" :key="entry.key" class="cbrne-gov-card__filter">
          {{ entry.key }}：{{ entry.label }}
        </span>
      </div>
      <ol class="cbrne-gov-card__list">
        <li
          v-for="sample in payload.samples"
          :key="sample.sample_id"
          class="cbrne-gov-card__item"
          data-testid="cbrne-search-sample"
        >
          <div class="cbrne-gov-card__head">
            <strong>{{ sample.sample_id }}</strong>
            <span class="cbrne-gov-card__chip">{{ sample.label }}</span>
            <span class="cbrne-gov-card__chip">{{ sample.cbrne_category }}</span>
            <span class="cbrne-gov-card__chip">{{ sample.exposure_tier }}</span>
          </div>
          <p class="cbrne-gov-card__excerpt">{{ sample.text_excerpt }}</p>
          <RouterLink
            class="cbrne-gov-card__link"
            data-testid="cbrne-benchmark-sample-link"
            :to="
              sample.benchmark_href ||
              cbrneSampleBenchmarkHref(payload.asset_id || '', sample.sample_id)
            "
            target="_blank"
            rel="noopener noreferrer"
          >
            在 Benchmark 查看样本
          </RouterLink>
        </li>
      </ol>
      <div v-if="canLoadMore" class="cbrne-gov-card__more" data-testid="cbrne-search-pagination">
        <span>
          第 {{ payload.offset + 1 }}–{{ payload.offset + payload.samples.length }} 条 / 共
          {{ payload.total }} 条
        </span>
        <button type="button" class="cbrne-gov-card__more-button" @click="$emit('load-more')">
          加载更多
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { GovernanceCbrneSearchPayload, GovernanceSessionMessage } from '@/types'
import { cbrneSampleBenchmarkHref } from '@/utils/governance-cbrne-links'

const props = defineProps<{
  message: GovernanceSessionMessage
  isLast?: boolean
}>()

defineEmits<{
  (event: 'load-more'): void
}>()

const FILTER_LABELS: Record<string, string> = {
  asset_id: '资产',
  label: '标签',
  cbrne_category: '类别',
  source: '来源',
  exposure_tier: 'T1–T4',
  difficulty_min: '难度下限',
  difficulty_max: '难度上限',
}

const payload = computed<GovernanceCbrneSearchPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cbrne_dataset_search' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceCbrneSearchPayload
})

const canLoadMore = computed(() => {
  const value = payload.value
  if (!value || !props.isLast) return false
  return value.offset + value.samples.length < value.total
})

const filterEntries = computed(() =>
  Object.entries(payload.value?.filters ?? {}).map(([key, value]) => ({
    key: FILTER_LABELS[key] ?? key,
    label: String(value),
  })),
)
</script>
