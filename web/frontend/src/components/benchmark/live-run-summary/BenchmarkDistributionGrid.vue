<template>
  <div class="distribution-grid">
    <article v-for="group in groups" :key="group.title">
      <el-tooltip v-if="group.tooltip" :content="group.tooltip" placement="top" :show-after="200">
        <b class="term-trigger">{{ group.title }}</b>
      </el-tooltip>
      <b v-else>{{ group.title }}</b>
      <span v-if="group.items.length === 0">-</span>
      <span v-for="entry in group.items" :key="entry.key">{{ entry.key }} {{ entry.value }}</span>
    </article>
  </div>
</template>

<script setup lang="ts">
import type { BenchmarkDistributionItem } from '@/utils/benchmarkLiveRunFormatters'

export interface BenchmarkDistributionGroup {
  title: string
  items: BenchmarkDistributionItem[]
  tooltip?: string
}

defineProps<{
  groups: BenchmarkDistributionGroup[]
}>()
</script>
