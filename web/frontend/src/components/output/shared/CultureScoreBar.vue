<template>
  <div class="culture-score-bar" :class="`csb--${color}`">
    <span class="csb-label">{{ label }}</span>
    <div class="csb-track">
      <div class="csb-fill" :style="{ width: animatedWidth + '%' }"></div>
    </div>
    <span class="csb-value">{{ score }}{{ suffix }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    score: number
    color?: 'green' | 'blue' | 'amber' | 'purple'
    suffix?: string
  }>(),
  {
    color: 'green',
    suffix: '%',
  },
)

const animatedWidth = ref(0)

onMounted(() => {
  setTimeout(() => {
    animatedWidth.value = Math.min(props.score, 100)
  }, 100)
})
</script>

<style scoped>
.culture-score-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}

.csb-label {
  width: 80px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.csb-track {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.csb-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.csb--green .csb-fill {
  background: linear-gradient(90deg, #22c55e, #10b981);
}

.csb--blue .csb-fill {
  background: linear-gradient(90deg, #3b82f6, #6366f1);
}

.csb--amber .csb-fill {
  background: linear-gradient(90deg, #f59e0b, #ea580c);
}

.csb--purple .csb-fill {
  background: linear-gradient(90deg, #8b5cf6, #a855f7);
}

.csb-value {
  width: 36px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: right;
  flex-shrink: 0;
}
</style>
