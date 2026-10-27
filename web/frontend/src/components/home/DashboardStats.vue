<template>
  <section class="dashboard-stats">
    <article v-for="item in items" :key="item.id" class="stat-card" :class="item.theme">
      <div class="stat-card-header">
        <div class="stat-card-title">{{ item.title }}</div>
        <div class="stat-card-icon">{{ item.icon }}</div>
      </div>
      <div class="stat-card-value">{{ item.value }}</div>
      <div class="stat-card-change" :class="item.trend === 'up' ? 'up' : 'down'">
        <span>{{ item.trend === 'up' ? '↑' : '↓' }} {{ item.change }}{{ item.unit }}</span>
        <span>较上月</span>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
export interface StatItem {
  id: string
  title: string
  icon: string
  value: string | number
  change: number
  unit: string
  trend: 'up' | 'down'
  theme?: string
}

defineProps<{
  items: StatItem[]
}>()
</script>
