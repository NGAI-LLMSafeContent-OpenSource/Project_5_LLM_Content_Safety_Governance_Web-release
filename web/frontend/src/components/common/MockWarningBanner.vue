<template>
  <div
    v-if="source === 'mock' || source === 'error' || source === 'unavailable'"
    class="mock-warning-banner"
  >
    <span class="mock-warning-icon">⚠️</span>
    <span class="mock-warning-text">
      {{ reason || '后端接口异常' }}，当前展示为
      <strong>模拟数据</strong>
      。详见
      <code>Project_3_Risk_Hierarchical_Classification_Benchmark/app.py</code>
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  source: string
  reason: string
}>()
</script>

<style scoped>
.mock-warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
  background: #fff8e1;
  border: 1px solid #ffc107;
  border-radius: 8px;
  font-size: 13px;
  color: #5d4037;
  line-height: 1.6;
}
.mock-warning-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}
.mock-warning-text strong {
  color: #e65100;
}
.mock-warning-text code {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
}
</style>
