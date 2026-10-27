<template>
  <div class="culture-review">
    <section
      id="guardrail-panel-ingest"
      class="guardrail-section"
      aria-labelledby="culture-ingest-title"
    >
      <header class="guardrail-section__header">
        <p class="guardrail-section__label">01</p>
        <h2 id="culture-ingest-title">模型回答接入</h2>
        <p class="guardrail-section__desc">
          接入 Project 3 文化场景候选回答，运行通用风险检测、文化评估与改写推荐。
        </p>
      </header>

      <div class="ingest-layout">
        <div>
          <p class="path-label">候选回答来源</p>
          <p class="path-value">{{ candidateSourceLabel }}</p>
        </div>

        <div class="run-panel">
          <div>
            <p class="path-label">运行条数</p>
            <div class="limit-group" role="group" aria-label="运行条数">
              <button
                v-for="item in limitOptions"
                :key="item"
                type="button"
                :class="['limit-button', { 'limit-button--active': item === limit }]"
                :disabled="busy"
                @click="emit('updateLimit', item)"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <button type="button" class="run-button" :disabled="busy" @click="emit('run')">
            {{ busy ? '运行中' : '运行文化批次' }}
          </button>
        </div>
      </div>

      <p v-if="busy" class="status-note">远程风险检测和文化评估运行中，limit=3 可能需要数分钟。</p>
      <p v-else-if="error" class="status-note status-note--error">{{ error }}</p>

      <dl class="meta-grid">
        <div>
          <dt>batch_id</dt>
          <dd>{{ batch?.batch_id || '尚未运行' }}</dd>
        </div>
        <div>
          <dt>model_id</dt>
          <dd>{{ modelId }}</dd>
        </div>
        <div>
          <dt>样本数</dt>
          <dd>{{ batch?.sample_count || 0 }}</dd>
        </div>
        <div>
          <dt>结果文件</dt>
          <dd>{{ batch?.results_path || '—' }}</dd>
        </div>
      </dl>
    </section>

    <section
      id="guardrail-panel-detect"
      class="guardrail-section"
      aria-labelledby="culture-detect-title"
    >
      <header class="guardrail-section__header">
        <p class="guardrail-section__label">02</p>
        <h2 id="culture-detect-title">通用风险检测</h2>
        <p class="guardrail-section__desc">展示 Topic 3 Benchmark 对候选回答的风险分类和证据。</p>
      </header>

      <div class="metric-grid">
        <article class="metric-box">
          <span>safe</span>
          <strong>{{ counts.safe }}</strong>
        </article>
        <article class="metric-box">
          <span>unsafe</span>
          <strong>{{ counts.unsafe }}</strong>
        </article>
        <article class="metric-box">
          <span>检测失败</span>
          <strong>{{ counts.detectError }}</strong>
        </article>
        <article class="metric-box">
          <span>fallback</span>
          <strong>{{ counts.fallback }}</strong>
        </article>
      </div>

      <div v-if="samples.length" class="review-layout">
        <aside class="sample-list" aria-label="样本列表">
          <button
            v-for="sample in samples"
            :key="sample.id"
            type="button"
            :class="['sample-row', { 'sample-row--active': sample.id === selectedSampleId }]"
            @click="emit('selectSample', sample.id)"
          >
            <span class="sample-row__title">
              #{{ sample.index }} {{ sample.scene?.implied_ethnic_group || '—' }}
            </span>
            <span class="sample-row__meta">
              {{ sample.pred_safe_type || '—' }} ·
              {{ cultureRiskLabel(sample.culture_assessment?.culture_risk_category) }}
            </span>
          </button>
        </aside>

        <article v-if="selectedSample" class="sample-detail">
          <div class="detail-header">
            <div>
              <h3>{{ selectedSample.scene?.implied_ethnic_group || '文化样本' }}</h3>
              <p>{{ selectedSample.id }}</p>
            </div>
            <span class="status-pill">
              {{ recommendationLabel(selectedSample.recommendation) }}
            </span>
          </div>

          <div class="field-grid">
            <div>
              <dt>安全判定</dt>
              <dd>{{ selectedSample.pred_safe_type || '—' }}</dd>
            </div>
            <div>
              <dt>风险等级</dt>
              <dd>{{ riskLevelLabel(selectedSample.pred_risk_level) }}</dd>
            </div>
            <div>
              <dt>风险类别</dt>
              <dd class="risk-category-list">
                <span
                  v-for="item in riskCategoryItems(
                    selectedSample.pred_category_code,
                    selectedSample.pred_category,
                  )"
                  :key="item.code || item.label"
                >
                  <strong v-if="item.code">{{ item.code }}</strong>
                  {{ item.label }}
                </span>
              </dd>
            </div>
            <div>
              <dt>文化结论</dt>
              <dd>
                {{ cultureRiskLabel(selectedSample.culture_assessment?.culture_risk_category) }}
              </dd>
            </div>
          </div>

          <div class="text-block">
            <h4>prompt</h4>
            <p>{{ selectedSample.prompt || '—' }}</p>
          </div>
          <div class="text-block">
            <h4>原始模型回答</h4>
            <p>{{ selectedSample.candidate_response || '—' }}</p>
          </div>
        </article>
      </div>
      <p v-else class="empty-state">尚未运行文化批次。</p>
    </section>

    <section
      id="guardrail-panel-culture"
      class="guardrail-section"
      aria-labelledby="culture-eval-title"
    >
      <header class="guardrail-section__header">
        <p class="guardrail-section__label">03</p>
        <h2 id="culture-eval-title">文化维度评估</h2>
        <p class="guardrail-section__desc">
          区分通用安全风险和文化回应不足，保留裁判理由供人工审阅。
        </p>
      </header>

      <div v-if="selectedSample" class="culture-grid">
        <article class="judge-box">
          <h3>文化对象识别</h3>
          <p class="judge-score">
            {{ selectedSample.culture_assessment?.ethnic_mention_judge?.score ?? '—' }}
          </p>
          <p>{{ selectedSample.culture_assessment?.ethnic_mention_judge?.reason || '—' }}</p>
        </article>
        <article class="judge-box">
          <h3>文化实质回应</h3>
          <p class="judge-score">
            {{ selectedSample.culture_assessment?.cultural_difference_judge?.score ?? '—' }}
          </p>
          <p>{{ selectedSample.culture_assessment?.cultural_difference_judge?.reason || '—' }}</p>
        </article>
      </div>
      <p v-else class="empty-state">选择样本后查看文化评估。</p>
    </section>

    <section
      id="guardrail-panel-correct"
      class="guardrail-section"
      aria-labelledby="culture-disposal-title"
    >
      <header class="guardrail-section__header">
        <p class="guardrail-section__label">04</p>
        <h2 id="culture-disposal-title">输出治理与推荐</h2>
        <p class="guardrail-section__desc">
          对比原始回答、文化改写和最终推荐回答，明确 fallback 场景。
        </p>
      </header>

      <div v-if="selectedSample" class="disposal-grid">
        <article class="text-block">
          <h4>文化改写</h4>
          <p>
            {{
              selectedSample.cultural_rewrite?.rewritten_response ||
              selectedSample.cultural_rewrite?.reason ||
              '—'
            }}
          </p>
        </article>
        <article class="text-block">
          <h4>最终推荐回答</h4>
          <p>{{ selectedSample.final_recommended_response || '—' }}</p>
        </article>
      </div>

      <dl v-if="selectedSample" class="meta-grid">
        <div>
          <dt>推荐策略</dt>
          <dd>{{ recommendationLabel(selectedSample.recommendation) }}</dd>
        </div>
        <div>
          <dt>通用改写状态</dt>
          <dd>{{ String(selectedSample.general_compliance_rewrite?.status || '—') }}</dd>
        </div>
        <div>
          <dt>文化改写状态</dt>
          <dd>{{ selectedSample.cultural_rewrite?.status || '—' }}</dd>
        </div>
        <div>
          <dt>剩余风险</dt>
          <dd>{{ selectedSample.cultural_rewrite?.remaining_risk || '—' }}</dd>
        </div>
      </dl>

      <article v-if="selectedSample?.cultural_rewrite?.rewrite_reason" class="rewrite-reason">
        <h3>改写原因</h3>
        <p>{{ selectedSample.cultural_rewrite.rewrite_reason }}</p>
        <ul v-if="selectedSample.cultural_rewrite.fixed_issues?.length">
          <li v-for="issue in selectedSample.cultural_rewrite.fixed_issues" :key="issue">
            {{ issue }}
          </li>
        </ul>
      </article>

      <p v-if="!selectedSample" class="empty-state">选择样本后查看治理结果。</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { CultureGuardrailBatchResponse, CultureGuardrailSample } from '@/api/output'
import {
  cultureRiskLabel,
  recommendationLabel,
  riskCategoryItems,
  riskLevelLabel,
} from '@/composables/guardrail/useOutputCultureGuardrailBatch'

defineProps<{
  batch: CultureGuardrailBatchResponse | null
  status: string
  error: string
  busy: boolean
  limit: number
  modelId: string
  candidateSourceLabel: string
  samples: CultureGuardrailSample[]
  selectedSampleId: string
  selectedSample: CultureGuardrailSample | null
  counts: {
    total: number
    safe: number
    unsafe: number
    detectError: number
    culturePass: number
    cultureFail: number
    fallback: number
  }
}>()

const emit = defineEmits<{
  run: []
  selectSample: [sampleId: string]
  updateLimit: [limit: number]
}>()

const limitOptions = [1, 3, 10]
</script>

<style scoped>
.culture-review {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

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

.guardrail-section__desc,
.empty-state,
.status-note {
  margin: 0;
  color: #52677f;
  font-size: 14px;
  line-height: 1.7;
}

.status-note {
  margin-top: 14px;
}

.status-note--error {
  color: #b71c1c;
}

.ingest-layout,
.run-panel,
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ingest-layout {
  align-items: stretch;
}

.run-panel {
  flex: 0 0 280px;
  align-items: center;
}

.path-label {
  margin: 0 0 8px;
  color: #5b7088;
  font-size: 12px;
  font-weight: 600;
}

.path-value {
  margin: 0;
  color: #102a43;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-all;
}

.limit-group {
  display: flex;
  gap: 6px;
}

.limit-button,
.run-button,
.sample-row {
  border: 1px solid #b7c9dd;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.limit-button {
  min-width: 42px;
  min-height: 34px;
  color: #29445f;
  font-weight: 700;
}

.limit-button--active,
.run-button {
  border-color: #1565c0;
  color: #fff;
  background: #1565c0;
}

.run-button {
  min-height: 38px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 700;
}

.limit-button:disabled,
.run-button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.meta-grid,
.field-grid,
.metric-grid,
.culture-grid,
.disposal-grid {
  display: grid;
  gap: 12px;
}

.meta-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin: 18px 0 0;
}

.field-grid,
.metric-grid {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.culture-grid,
.disposal-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.meta-grid div,
.field-grid div,
.metric-box,
.judge-box,
.text-block,
.rewrite-reason {
  padding: 14px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.meta-grid dt,
.field-grid dt {
  margin: 0 0 6px;
  color: #5b7088;
  font-size: 12px;
}

.meta-grid dd,
.field-grid dd {
  margin: 0;
  color: #102a43;
  font-size: 14px;
  font-weight: 700;
  word-break: break-word;
}

.risk-category-list {
  display: grid;
  gap: 6px;
}

.risk-category-list span {
  line-height: 1.45;
}

.risk-category-list strong {
  margin-right: 6px;
  color: #1565c0;
}

.metric-box span {
  display: block;
  margin-bottom: 8px;
  color: #5b7088;
  font-size: 12px;
}

.metric-box strong {
  color: #1565c0;
  font-size: 24px;
}

.review-layout {
  display: grid;
  grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.sample-list {
  display: grid;
  gap: 8px;
}

.sample-row {
  width: 100%;
  padding: 12px;
  text-align: left;
}

.sample-row--active {
  border-color: #1565c0;
  background: #eef6ff;
}

.sample-row__title,
.sample-row__meta {
  display: block;
}

.sample-row__title {
  color: #102a43;
  font-size: 14px;
  font-weight: 700;
}

.sample-row__meta {
  margin-top: 6px;
  color: #5b7088;
  font-size: 12px;
  line-height: 1.5;
}

.sample-detail {
  display: grid;
  gap: 14px;
}

.detail-header h3,
.judge-box h3,
.text-block h4,
.rewrite-reason h3 {
  margin: 0 0 8px;
  color: #102a43;
  font-size: 15px;
}

.detail-header p,
.judge-box p,
.text-block p,
.rewrite-reason p {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.status-pill {
  flex: 0 0 auto;
  max-width: 220px;
  padding: 7px 10px;
  border-radius: 8px;
  color: #155fa0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  background: #eef6ff;
}

.judge-score {
  margin-bottom: 8px !important;
  color: #1565c0 !important;
  font-size: 22px !important;
  font-weight: 800;
}

.rewrite-reason {
  margin-top: 12px;
}

.rewrite-reason ul {
  margin: 10px 0 0;
  padding-left: 20px;
  color: #29445f;
  font-size: 14px;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .ingest-layout,
  .run-panel,
  .detail-header {
    flex-direction: column;
  }

  .run-panel {
    flex-basis: auto;
    align-items: flex-start;
  }

  .review-layout,
  .culture-grid,
  .disposal-grid {
    grid-template-columns: 1fr;
  }
}
</style>
