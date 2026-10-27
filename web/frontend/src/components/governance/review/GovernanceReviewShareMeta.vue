<template>
  <section class="gov-review-meta" aria-label="分享元信息">
    <dl>
      <div>
        <dt>任务</dt>
        <dd>{{ taskId }}</dd>
      </div>
      <div>
        <dt>有效期至</dt>
        <dd>{{ formatGovernanceTime(expiresAt) }}</dd>
      </div>
      <div>
        <dt>样本原文</dt>
        <dd>{{ showSampleText ? '已授权展示' : '默认隐藏' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { formatGovernanceTime } from '@/utils/governance-format'

defineProps<{
  taskId: string
  expiresAt: string
  showSampleText: boolean
}>()
</script>

<style scoped>
.gov-review-meta {
  max-width: 56rem;
  margin-bottom: 1.25rem;
  padding: 1rem 1.15rem;
  border: 1px solid #d5e0da;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
}

.gov-review-meta dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.85rem 1.25rem;
  margin: 0;
}

.gov-review-meta dt {
  margin: 0;
  color: #5d6f66;
  font-size: 0.8rem;
}

.gov-review-meta dd {
  margin: 0.2rem 0 0;
  font-weight: 600;
  word-break: break-all;
}
</style>
