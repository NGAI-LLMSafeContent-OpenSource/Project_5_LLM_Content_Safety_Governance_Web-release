<template>
  <dl class="summary-fields">
    <div v-for="item in items" :key="item.key">
      <dt>
        <el-tooltip v-if="item.tooltip" :content="item.tooltip" placement="top" :show-after="200">
          <span class="term-trigger">{{ item.label }}</span>
        </el-tooltip>
        <span v-else>{{ item.label }}</span>
      </dt>
      <dd :class="{ mono: item.mono }">{{ item.value }}</dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
export interface BenchmarkFieldGridItem {
  key: string
  label: string
  value: string | number
  mono?: boolean
  tooltip?: string
}

defineProps<{
  items: BenchmarkFieldGridItem[]
}>()
</script>
