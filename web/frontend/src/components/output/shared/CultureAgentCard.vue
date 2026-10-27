<template>
  <div class="culture-agent-card" :class="statusClass">
    <div class="cac-head">
      <span class="cac-index">{{ index }}</span>
      <span class="cac-title">{{ title }}</span>
      <span class="cac-status-tag">{{ statusLabel }}</span>
      <span v-if="time" class="cac-time">{{ time }}</span>
    </div>

    <div v-if="input" class="cac-section">
      <div class="cac-label">输入</div>
      <div class="cac-input-text">{{ input }}</div>
    </div>

    <div v-if="reasoning" class="cac-section">
      <div class="cac-label">推理过程</div>
      <div class="cac-reasoning">{{ reasoning }}</div>
    </div>

    <div v-if="knowledge" class="cac-section">
      <div class="cac-label">检索知识</div>
      <div class="cac-knowledge">{{ knowledge }}</div>
    </div>

    <div v-if="top3 && top3.length > 0" class="cac-section">
      <div class="cac-label">Top-3 结果</div>
      <div class="cac-top3-list">
        <span v-for="(item, i) in top3" :key="i" class="cac-top3-item">{{ item }}</span>
      </div>
    </div>

    <div v-if="result" class="cac-section">
      <div class="cac-label">输出结果</div>
      <div class="cac-result">{{ result }}</div>
    </div>

    <div v-if="status === 'running'" class="cac-spinner">
      <span class="cac-dot"></span>
      <span>运行中…</span>
    </div>

    <div v-if="status === 'error'" class="cac-error">
      {{ errorMsg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  index: number
  title: string
  status: 'pending' | 'running' | 'done' | 'error'
  input?: string
  reasoning?: string
  knowledge?: string
  top3?: string[]
  result?: string
  time?: string
  errorMsg?: string
}>()

const statusClass = computed(() => `cac--${props.status}`)

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    done: '已完成',
    error: '失败',
  }
  return map[props.status] ?? '等待中'
})
</script>

<style scoped>
.culture-agent-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  background: var(--bg-primary);
  transition:
    border-color 0.3s,
    box-shadow 0.3s;
}

.cac--running {
  border-color: #6366f1;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.12);
}

.cac--done {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.03);
}

.cac--error {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.04);
}

.cac-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.cac-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--bg-secondary);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
}

.cac--running .cac-index {
  background: #6366f1;
  color: #fff;
}

.cac--done .cac-index {
  background: #22c55e;
  color: #fff;
}

.cac-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.cac-status-tag {
  margin-left: auto;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.cac--done .cac-status-tag {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.cac--error .cac-status-tag {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.cac-time {
  font-size: 10px;
  color: var(--text-muted);
}

.cac-section {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}

.cac-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.cac-input-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

.cac-reasoning {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.cac-knowledge {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: 6px;
  border-left: 3px solid #6366f1;
}

.cac-top3-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.cac-top3-item {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.cac-result {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.7;
}

.cac-spinner {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 12px;
  color: #6366f1;
}

.cac-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6366f1;
  animation: cac-pulse 1.2s ease-in-out infinite;
}

@keyframes cac-pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.cac-error {
  margin-top: 10px;
  font-size: 12px;
  color: #ef4444;
  padding: 8px;
  background: rgba(239, 68, 68, 0.06);
  border-radius: 6px;
}
</style>
