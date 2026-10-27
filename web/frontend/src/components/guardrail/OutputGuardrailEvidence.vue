<template>
  <section class="guardrail-section" aria-labelledby="guardrail-evidence-title">
    <header class="guardrail-section__header">
      <div class="guardrail-section__heading-row">
        <div>
          <p class="guardrail-section__label">03</p>
          <h2 id="guardrail-evidence-title">风险解释与定位</h2>
          <p class="guardrail-section__desc">展示本次推理给出的类别与证据，默认第一条 unsafe。</p>
        </div>
        <span class="evidence-badge">本次推理</span>
      </div>
    </header>

    <div v-if="!sample" class="evidence-status">
      {{ emptyLabel }}
    </div>

    <div v-else class="evidence-body">
      <article class="evidence-text-card">
        <h3>回答全文</h3>
        <p class="evidence-fulltext">{{ sample.response || '—' }}</p>
      </article>

      <div class="evidence-meta-grid">
        <article class="evidence-meta-card">
          <h3>检测状态</h3>
          <p>{{ sample.detect_status }}</p>
        </article>
        <article class="evidence-meta-card">
          <h3>安全判定</h3>
          <p>{{ sample.pred_safe_type || '—' }}</p>
        </article>
        <article class="evidence-meta-card">
          <h3>风险等级</h3>
          <p>{{ sample.pred_risk_level || '—' }}</p>
        </article>
        <article class="evidence-meta-card">
          <h3>预测类别</h3>
          <p>{{ sample.pred_category || sample.pred_category_code || '—' }}</p>
        </article>
        <article class="evidence-meta-card">
          <h3>风险证据</h3>
          <ul v-if="evidenceItems.length" class="evidence-signal-list">
            <li v-for="item in evidenceItems" :key="item">{{ item }}</li>
          </ul>
          <p v-else>—</p>
        </article>
        <article class="evidence-meta-card">
          <h3>失败原因</h3>
          <p>{{ sample.error || '—' }}</p>
        </article>
      </div>

      <button type="button" class="evidence-next" @click="emit('showNextEvidence')">下一条</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GuardrailLiveSample } from '@/api/output'

const props = defineProps<{
  sample: GuardrailLiveSample | null
  emptyLabel: string
  evidenceItems: string[]
}>()

const emit = defineEmits<{
  showNextEvidence: []
}>()

const evidenceItems = computed(() => props.evidenceItems)
</script>

<style scoped>
.guardrail-section {
  padding: 22px;
  border: 1px solid #dbe6f3;
  border-radius: 8px;
  background: #fff;
  scroll-margin-top: 24px;
}

.guardrail-section__heading-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.guardrail-section__label {
  margin: 0 0 10px;
  color: #1565c0;
  font-size: 13px;
  font-weight: 700;
}

.guardrail-section h2 {
  margin: 0 0 8px;
  color: #102a43;
  font-size: 20px;
  line-height: 1.35;
}

.guardrail-section__desc {
  margin: 0;
  color: #52677f;
  font-size: 14px;
  line-height: 1.7;
}

.evidence-badge {
  flex: 0 0 auto;
  padding: 6px 12px;
  border: 1px solid #c9dcf0;
  border-radius: 999px;
  color: #155fa0;
  font-size: 12px;
  font-weight: 600;
  background: #eef6ff;
}

.evidence-status {
  margin-top: 8px;
  color: #486581;
  font-size: 14px;
}

.evidence-body {
  display: grid;
  gap: 16px;
}

.evidence-text-card,
.evidence-meta-card {
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.evidence-text-card h3,
.evidence-meta-card h3 {
  margin: 0 0 10px;
  color: #102a43;
  font-size: 15px;
}

.evidence-fulltext,
.evidence-meta-card p {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.evidence-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.evidence-signal-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.evidence-signal-list li {
  color: #29445f;
  font-size: 13px;
}

.evidence-next {
  justify-self: start;
  padding: 8px 14px;
  border: 1px solid #b7c9dd;
  border-radius: 8px;
  color: #155fa0;
  font-size: 14px;
  font-weight: 600;
  background: #fff;
  cursor: pointer;
}

.evidence-next:hover {
  border-color: #1565c0;
  color: #0d47a1;
}

@media (max-width: 900px) {
  .guardrail-section__heading-row {
    display: block;
  }

  .evidence-badge {
    display: inline-flex;
    margin-top: 12px;
  }

  .evidence-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
