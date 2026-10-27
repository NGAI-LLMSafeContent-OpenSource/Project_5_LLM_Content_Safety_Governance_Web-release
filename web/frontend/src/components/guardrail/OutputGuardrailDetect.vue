<template>
  <section class="guardrail-section" aria-labelledby="guardrail-detect-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">02</p>
      <h2 id="guardrail-detect-title">输出内容风险识别</h2>
      <p class="guardrail-section__desc">本批 live 检测结果。文化多样性本轮不跑。</p>
    </header>

    <div class="detect-grid">
      <article class="detect-card">
        <h3>内容风险</h3>
        <template v-if="samples.length">
          <p class="detect-metric">unsafe {{ detectCounts.unsafe }}</p>
          <p class="detect-highlight">
            safe {{ detectCounts.safe }} · 失败 {{ detectCounts.failed }}
          </p>
        </template>
        <p v-else class="detect-empty">尚未运行本批</p>
      </article>

      <article class="detect-card">
        <h3>风险等级</h3>
        <template v-if="samples.length">
          <ul class="detect-levels">
            <li>
              <span>safe</span>
              <strong>{{ detectCounts.safe }}</strong>
            </li>
            <li>
              <span>unsafe</span>
              <strong>{{ detectCounts.unsafe }}</strong>
            </li>
            <li>
              <span>失败</span>
              <strong>{{ detectCounts.failed }}</strong>
            </li>
            <li>
              <span>进行中</span>
              <strong>{{ detectCounts.pending }}</strong>
            </li>
          </ul>
        </template>
        <p v-else class="detect-empty">尚未运行本批</p>
      </article>

      <article class="detect-card">
        <h3>文化多样性</h3>
        <p class="detect-empty">{{ CULTURE_IDLE_LABEL }}</p>
      </article>

      <article class="detect-card">
        <h3>多民族语言适配</h3>
        <p class="detect-empty">{{ CULTURE_IDLE_LABEL }}</p>
      </article>
    </div>

    <table v-if="samples.length" class="detect-table">
      <thead>
        <tr>
          <th>样本</th>
          <th>检测</th>
          <th>判定</th>
          <th>类别</th>
          <th>改写</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="sample in samples"
          :key="sample.id"
          :class="{ 'detect-table__row--active': sample.id === selectedSampleId }"
          @click="emit('selectSample', sample.id)"
        >
          <td>{{ sample.id }}</td>
          <td>{{ sample.detect_status }}</td>
          <td>{{ sample.pred_safe_type || '—' }}</td>
          <td>{{ sample.pred_category || sample.pred_category_code || '—' }}</td>
          <td>{{ sample.rewrite_status }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import type { GuardrailLiveSample } from '@/api/output'
import { CULTURE_IDLE_LABEL } from '@/composables/guardrail/useOutputGuardrailLive'

defineProps<{
  samples: GuardrailLiveSample[]
  selectedSampleId: string
  detectCounts: { safe: number; unsafe: number; failed: number; pending: number }
}>()

const emit = defineEmits<{
  selectSample: [sampleId: string]
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

.detect-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.detect-card {
  min-height: 120px;
  padding: 18px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.detect-card h3 {
  margin: 0 0 12px;
  color: #102a43;
  font-size: 16px;
}

.detect-metric {
  margin: 0 0 12px;
  color: #1565c0;
  font-size: 22px;
  font-weight: 700;
}

.detect-highlight {
  margin: 0;
  color: #486581;
  font-size: 14px;
  line-height: 1.6;
}

.detect-levels {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.detect-levels li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  color: #29445f;
  font-size: 13px;
  background: #fff;
}

.detect-levels strong {
  color: #102a43;
  font-size: 16px;
}

.detect-empty {
  margin: 0;
  color: #5b7088;
  font-size: 14px;
  line-height: 1.6;
}

.detect-table {
  width: 100%;
  margin-top: 16px;
  border-collapse: collapse;
  font-size: 13px;
}

.detect-table th,
.detect-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e3edf7;
  text-align: left;
  color: #29445f;
}

.detect-table tbody tr {
  cursor: pointer;
}

.detect-table__row--active {
  background: #eef6ff;
}

@media (max-width: 900px) {
  .detect-grid {
    grid-template-columns: 1fr;
  }
}
</style>
