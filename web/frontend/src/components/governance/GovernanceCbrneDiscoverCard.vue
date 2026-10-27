<template>
  <div
    v-if="payload"
    class="cbrne-gov-card"
    data-testid="cbrne-discover-card"
    aria-label="CBRNE 资产发现"
  >
    <div v-if="!payload.available || payload.total === 0" class="cbrne-gov-card__empty">
      {{ message.content }}
    </div>
    <template v-else>
      <p class="cbrne-gov-card__badge">只读登记事实 · 非评测执行</p>
      <ol class="cbrne-gov-card__list">
        <li v-for="record in payload.records" :key="record.asset_id" class="cbrne-gov-card__item">
          <div class="cbrne-gov-card__head">
            <strong>{{ record.asset_name || record.asset_id }}</strong>
            <span v-if="record.is_current" class="cbrne-gov-card__chip is-current">当前</span>
            <span class="cbrne-gov-card__chip">v{{ record.asset_version || '—' }}</span>
          </div>
          <p class="cbrne-gov-card__meta">
            {{ record.asset_id }} · 样本 {{ record.sample_count }} ·
            {{ record.source_repo || '未标注来源' }}
          </p>
          <RouterLink
            class="cbrne-gov-card__link"
            data-testid="cbrne-benchmark-asset-link"
            :to="record.benchmark_href || cbrneAssetBenchmarkHref(record.asset_id)"
            target="_blank"
            rel="noopener noreferrer"
          >
            在 Benchmark 查看资产
          </RouterLink>
        </li>
      </ol>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { GovernanceCbrneDiscoverPayload, GovernanceSessionMessage } from '@/types'
import { cbrneAssetBenchmarkHref } from '@/utils/governance-cbrne-links'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceCbrneDiscoverPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cbrne_dataset_discover' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceCbrneDiscoverPayload
})
</script>
