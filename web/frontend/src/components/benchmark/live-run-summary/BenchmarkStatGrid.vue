<template>
  <div class="event-stat-grid">
    <article v-for="item in items" :key="item.label">
      <el-tooltip v-if="item.tooltip" :content="item.tooltip" placement="top" :show-after="200">
        <span class="term-trigger">{{ item.label }}</span>
      </el-tooltip>
      <span v-else>{{ item.label }}</span>
      <strong>{{ item.value }}</strong>
    </article>
  </div>
</template>

<script setup lang="ts">
export interface BenchmarkStatGridItem {
  label: string
  value: string | number
  tooltip?: string
}

defineProps<{
  items: BenchmarkStatGridItem[]
}>()
</script>
