<template>
  <section class="guardrail-section" aria-labelledby="guardrail-disposal-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">04</p>
      <h2 id="guardrail-disposal-title">合规改写 / 放行</h2>
      <p class="guardrail-section__desc">展示本次 live 改写或放行结论，以及可追溯处置报告。</p>
    </header>

    <p class="disposal-notice">{{ LIVE_DISPOSAL_NOTICE }}</p>

    <div v-if="!sample" class="disposal-status">尚未运行本批</div>

    <div v-else class="disposal-body">
      <div class="disposal-compare">
        <article class="disposal-card">
          <h3>改写前</h3>
          <p>{{ sample.response || '—' }}</p>
        </article>
        <article class="disposal-card">
          <h3>改写后</h3>
          <p v-if="sample.disposition === 'pass'">本条判定安全，已放行。</p>
          <p v-else-if="sample.rewrite_status === 'error'">{{ sample.error || '改写失败' }}</p>
          <p v-else>{{ sample.edited_text || '等待改写' }}</p>
        </article>
      </div>

      <dl class="disposal-labels">
        <div>
          <dt>处置结论</dt>
          <dd>{{ sample.disposition || '—' }}</dd>
        </div>
        <div>
          <dt>改写后安全标签</dt>
          <dd>{{ sample.post_safety_label || '—' }}</dd>
        </div>
        <div>
          <dt>改写状态</dt>
          <dd>{{ sample.rewrite_status }}</dd>
        </div>
      </dl>

      <article class="disposal-report">
        <h3>处置报告</h3>
        <dl class="disposal-report__fields">
          <div>
            <dt>job_id</dt>
            <dd>{{ jobId || '—' }}</dd>
          </div>
          <div>
            <dt>来源</dt>
            <dd>live</dd>
          </div>
          <div>
            <dt>本批状态</dt>
            <dd>{{ jobStatus || '—' }}</dd>
          </div>
          <div>
            <dt>safe / unsafe / 失败</dt>
            <dd>{{ detectCounts.safe }} / {{ detectCounts.unsafe }} / {{ detectCounts.failed }}</dd>
          </div>
          <div>
            <dt>当前样本</dt>
            <dd>{{ sample.id }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { GuardrailLiveSample } from '@/api/output'
import { LIVE_DISPOSAL_NOTICE } from '@/composables/guardrail/useOutputGuardrailLive'

defineProps<{
  sample: GuardrailLiveSample | null
  jobId: string
  jobStatus: string
  detectCounts: { safe: number; unsafe: number; failed: number; pending: number }
}>()
</script>

<style scoped>
.guardrail-section {
  padding: 22px;
  border: 1px solid #dbe6f3;
  border-radius: 8px;
  background: #fff;
  scroll-margin-top: 24px;
}

.guardrail-section__header {
  margin-bottom: 14px;
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

.disposal-notice {
  margin: 0 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #155fa0;
  font-size: 13px;
  line-height: 1.6;
  background: #eef6ff;
}

.disposal-status {
  color: #486581;
  font-size: 14px;
}

.disposal-body {
  display: grid;
  gap: 16px;
}

.disposal-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.disposal-card,
.disposal-report {
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.disposal-card h3,
.disposal-report h3 {
  margin: 0 0 10px;
  color: #102a43;
  font-size: 15px;
}

.disposal-card p {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.disposal-labels,
.disposal-report__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 0;
}

.disposal-labels div,
.disposal-report__fields div {
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e3edf7;
}

.disposal-labels dt,
.disposal-report__fields dt {
  margin: 0 0 6px;
  color: #5b7088;
  font-size: 12px;
}

.disposal-labels dd,
.disposal-report__fields dd {
  margin: 0;
  color: #102a43;
  font-size: 14px;
  font-weight: 600;
  word-break: break-word;
}

@media (max-width: 900px) {
  .disposal-compare {
    grid-template-columns: 1fr;
  }
}
</style>
