<template>
  <div class="lineage-summary-grid">
    <div v-for="item in summaryItems" :key="item.label" class="lineage-summary-card">
      <div class="ls-val" :class="item.valueClass">{{ item.value }}</div>
      <div class="ls-label">{{ item.label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { InputLineageSummary } from '@/stores/input'

const props = defineProps<{
  summary: InputLineageSummary
  lineageCorpusSource?: 'value' | 'risk' | 'topic4_static'
}>()

function formatCount(value: number) {
  return Number(value || 0).toLocaleString('zh-CN')
}

const summaryItems = computed(() => [
  {
    value: formatCount(props.summary.totalNodes),
    label: '实体节点',
  },
  {
    value: formatCount(props.summary.totalEdges),
    label: '关系边',
  },
  {
    value: formatCount(props.summary.riskyNodes),
    label: props.lineageCorpusSource === 'value' ? '待提升节点' : '风险节点',
  },
  {
    value: String(props.summary.chunkCount),
    label: 'Chunk 数',
    valueClass: 'lineage-build-time',
  },
])
</script>
