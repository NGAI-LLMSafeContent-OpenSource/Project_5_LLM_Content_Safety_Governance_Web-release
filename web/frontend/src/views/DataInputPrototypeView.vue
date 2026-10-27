<template>
  <main class="dip-page">
    <div class="dip-prototype-banner" role="status">
      <span>概念原型</span>
      <p>代表样本按现有资产结构整理，在线检测结果为交互演示，不代表新增治理能力。</p>
    </div>
    <DataInputPrototypeC v-if="variant === 'C'" />
    <DataInputPrototypeD v-else />
    <PrototypeSwitcher :current="variant" />
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DataInputPrototypeC from '@/components/data-input-prototype/DataInputPrototypeC.vue'
import DataInputPrototypeD from '@/components/data-input-prototype/DataInputPrototypeD.vue'
import PrototypeSwitcher from '@/components/data-input-prototype/PrototypeSwitcher.vue'
import '@/assets/styles/data-input-prototype.css'

const route = useRoute()
const variant = computed<'C' | 'D'>(() => {
  const value = String(route.query.variant || 'D').toUpperCase()
  return value === 'C' ? 'C' : 'D'
})
</script>
