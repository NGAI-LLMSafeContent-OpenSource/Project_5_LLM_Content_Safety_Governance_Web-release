<template>
  <section class="guardrail-section" aria-labelledby="guardrail-ingest-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">01</p>
      <h2 id="guardrail-ingest-title">模型回答接入</h2>
      <p class="guardrail-section__desc">选择预置的小批量模型回答，点运行后当场检测与改写。</p>
    </header>

    <div class="guardrail-section__body">
      <label class="ingest-select-label" for="guardrail-pack-select">预置包</label>
      <select
        id="guardrail-pack-select"
        class="ingest-select"
        :value="selectedPackId"
        :disabled="jobBusy || packsLoading || !packs.length"
        @change="onPackChange"
      >
        <option v-if="!packs.length" value="" disabled>暂无可用预置包</option>
        <option v-for="item in packs" :key="item.pack_id" :value="item.pack_id">
          {{ item.title }} · {{ item.sample_count }} 条
        </option>
      </select>

      <p v-if="packsLoading" class="ingest-status">加载预置包…</p>
      <p v-else-if="packsError" class="ingest-status ingest-status--error">{{ packsError }}</p>
      <p v-else-if="jobError" class="ingest-status ingest-status--error">{{ jobError }}</p>

      <div class="ingest-actions">
        <button
          type="button"
          class="ingest-run"
          :disabled="jobBusy || !selectedPackId"
          @click="emit('run')"
        >
          运行本批
        </button>
        <p v-if="jobBusy" class="ingest-status">本批运行中…</p>
      </div>

      <dl v-if="selectedPack" class="ingest-meta">
        <div>
          <dt>pack_id</dt>
          <dd>{{ selectedPack.pack_id }}</dd>
        </div>
        <div>
          <dt>条数</dt>
          <dd>{{ selectedPack.sample_count }}</dd>
        </div>
        <div>
          <dt>model_id</dt>
          <dd>{{ selectedPack.model_id || '—' }}</dd>
        </div>
        <div>
          <dt>job_id</dt>
          <dd>{{ jobId || '尚未运行' }}</dd>
        </div>
        <div>
          <dt>来源</dt>
          <dd>{{ jobId ? 'live' : '—' }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { GuardrailDemoPack } from '@/api/output'

defineProps<{
  packs: GuardrailDemoPack[]
  selectedPackId: string
  selectedPack: GuardrailDemoPack | null
  packsLoading: boolean
  packsError: string
  jobId: string
  jobError: string
  jobBusy: boolean
}>()

const emit = defineEmits<{
  selectPack: [packId: string]
  run: []
}>()

function onPackChange(event: Event) {
  emit('selectPack', (event.target as HTMLSelectElement).value)
}
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
  margin-bottom: 18px;
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

.ingest-select-label {
  display: block;
  margin-bottom: 8px;
  color: #29445f;
  font-size: 13px;
  font-weight: 600;
}

.ingest-select {
  width: 100%;
  max-width: 720px;
  padding: 10px 12px;
  border: 1px solid #b7c9dd;
  border-radius: 8px;
  color: #102a43;
  font-size: 14px;
  background: #fff;
}

.ingest-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.ingest-run {
  padding: 8px 16px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  background: #1565c0;
  cursor: pointer;
}

.ingest-run:disabled {
  cursor: not-allowed;
  background: #90caf9;
}

.ingest-status {
  margin: 12px 0 0;
  color: #486581;
  font-size: 14px;
}

.ingest-status--error {
  color: #b71c1c;
}

.ingest-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 18px 0 0;
}

.ingest-meta div {
  padding: 12px;
  border-radius: 8px;
  background: #f2f7fc;
}

.ingest-meta dt {
  margin: 0 0 6px;
  color: #5b7088;
  font-size: 12px;
}

.ingest-meta dd {
  margin: 0;
  color: #102a43;
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
}
</style>
