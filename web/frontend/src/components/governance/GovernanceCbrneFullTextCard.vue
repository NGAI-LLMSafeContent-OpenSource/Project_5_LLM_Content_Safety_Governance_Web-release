<template>
  <div
    v-if="payload"
    class="cbrne-gov-card"
    data-testid="cbrne-full-text-card"
    aria-label="CBRNE 全文披露说明"
  >
    <p class="cbrne-gov-card__badge">全文不进治理消息</p>
    <p class="cbrne-gov-card__summary">{{ message.content }}</p>
    <p class="cbrne-gov-card__meta">
      披露策略：{{ payload.disclosure }} · 样本 {{ payload.sample_id || '—' }}
    </p>
    <RouterLink
      v-if="payload.benchmark_href"
      class="cbrne-gov-card__link"
      data-testid="cbrne-benchmark-sample-link"
      :to="payload.benchmark_href"
      target="_blank"
      rel="noopener noreferrer"
    >
      在 Benchmark 查看样本
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { GovernanceCbrneFullTextPayload, GovernanceSessionMessage } from '@/types'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceCbrneFullTextPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cbrne_dataset_full_text' || !raw) return null
  return raw as unknown as GovernanceCbrneFullTextPayload
})
</script>
