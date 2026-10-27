<template>
  <section class="guardrail-section" aria-labelledby="guardrail-ingest-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">01</p>
      <h2 id="guardrail-ingest-title">语料接入</h2>
      <p class="guardrail-section__desc">
        选择 5-10 条本地可追溯演示语料，点击运行后生成本次输入数据治理 job。
      </p>
    </header>

    <div class="guardrail-section__body">
      <label class="ingest-label" for="guardrail-value-select">选择演示批次</label>
      <div class="ingest-control-row">
        <select
          id="guardrail-value-select"
          class="ingest-select"
          :value="selectedPackId"
          :disabled="ingestLoading || !packs.length"
          @change="onPackChange"
        >
          <option v-if="!packs.length" value="" disabled>暂无可用演示批次</option>
          <option v-for="item in packs" :key="item.pack_id" :value="item.pack_id">
            {{ item.title }} · {{ item.sample_count }} 条
          </option>
        </select>
        <button
          class="run-button"
          type="button"
          :disabled="ingestLoading || !selectedPackId"
          @click="emit('runLive')"
        >
          {{ running ? '运行中...' : '启动风险识别' }}
        </button>
      </div>
      <p class="ingest-badge">现场演示批次 · 实时运行</p>

      <p v-if="ingestLoading" class="ingest-status">准备或执行风险识别…</p>
      <p v-else-if="ingestError" class="ingest-status ingest-status--error">{{ ingestError }}</p>
      <p v-if="jobId" class="ingest-status">本次运行 {{ jobId }} · {{ jobStatus }}</p>

      <dl class="ingest-meta">
        <div>
          <dt>语料包</dt>
          <dd>{{ riskAssetName || '—' }}</dd>
        </div>
        <div>
          <dt>模式</dt>
          <dd>{{ mode || 'demo_adapter' }}</dd>
        </div>
        <div>
          <dt>风险复核 / 总样本</dt>
          <dd>{{ riskPairCount }} / {{ riskTotal }}</dd>
        </div>
      </dl>

      <div v-if="categorySummary.length" class="corpus-summary">
        <div class="corpus-summary__head">
          <h3>本批语料构成</h3>
          <p>按演示语义展示 10 条样本的来源类别；处置值保持英文，悬停可查看含义。</p>
        </div>
        <div class="category-grid">
          <article v-for="item in categorySummary" :key="item.category" class="category-card">
            <div>
              <b>{{ item.category }}</b>
              <p>{{ item.note }}</p>
            </div>
            <strong>{{ item.count }}</strong>
            <div class="category-tags">
              <el-tooltip
                v-for="disposition in item.dispositions"
                :key="`${item.category}-${disposition}`"
                :content="dispositionHelp(disposition)"
                placement="top"
                :show-after="200"
              >
                <el-tag :type="dispositionTagType(disposition)" size="small">
                  {{ disposition }}
                </el-tag>
              </el-tooltip>
            </div>
          </article>
        </div>

        <el-collapse class="sample-collapse">
          <el-collapse-item title="查看 10 条语料明细" name="samples">
            <el-table :data="sampleRows" border size="small" empty-text="运行后显示语料明细">
              <el-table-column prop="id" label="ID" width="190" show-overflow-tooltip />
              <el-table-column prop="category" label="类型" width="140" show-overflow-tooltip />
              <el-table-column
                prop="sourceTopic"
                label="来源课题"
                width="160"
                show-overflow-tooltip
              />
              <el-table-column prop="sourceLabel" label="上游标签" width="100" />
              <el-table-column label="预期处置" width="110">
                <template #default="{ row }">
                  <el-tooltip
                    :content="row.dispositionHelp || dispositionHelp(row.expectedDisposition)"
                    placement="top"
                    :show-after="200"
                  >
                    <el-tag :type="dispositionTagType(row.expectedDisposition)" size="small">
                      {{ row.expectedDisposition || '—' }}
                    </el-tag>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column
                prop="snippet"
                label="文本摘要"
                min-width="260"
                show-overflow-tooltip
              />
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { InputGuardrailDemoPack } from '@/api/dataInput'
import type {
  DemoCategorySummary,
  DemoSampleRow,
} from '@/composables/guardrail/inputGuardrailDemoMap'

defineProps<{
  packs: InputGuardrailDemoPack[]
  selectedPackId: string
  ingestLoading: boolean
  ingestError: string
  running: boolean
  jobId: string
  jobStatus: string
  mode: string
  riskAssetName: string
  riskPairCount: number
  riskTotal: number
  categorySummary: DemoCategorySummary[]
  sampleRows: DemoSampleRow[]
}>()

const emit = defineEmits<{
  selectPack: [packId: string]
  runLive: []
}>()

function onPackChange(event: Event) {
  emit('selectPack', (event.target as HTMLSelectElement).value)
}

function dispositionHelp(disposition: string): string {
  if (disposition === 'pass') return '语料质量和风险状态基本可接受，可以进入候选入库或低风险抽检。'
  if (disposition === 'review')
    return '语料存在风险、边界意图、信息不足或需要确认的地方，先交给人工复核。'
  if (disposition === 'revise') return '语料明显低质、事实错配或价值表达有问题，需要修正后再复核。'
  return '暂无处置说明。'
}

function dispositionTagType(disposition: string): 'success' | 'warning' | 'danger' | 'info' {
  if (disposition === 'pass') return 'success'
  if (disposition === 'review') return 'warning'
  if (disposition === 'revise') return 'danger'
  return 'info'
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

.ingest-label {
  display: block;
  margin-bottom: 8px;
  color: #29445f;
  font-size: 13px;
  font-weight: 600;
}

.ingest-control-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
}

.ingest-select {
  flex: 1 1 360px;
  width: 100%;
  max-width: 720px;
  padding: 10px 12px;
  border: 1px solid #b7c9dd;
  border-radius: 8px;
  color: #102a43;
  font-size: 14px;
  background: #fff;
}

.run-button {
  flex: 0 0 auto;
  padding: 10px 14px;
  border: 1px solid #1565c0;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  background: #1565c0;
  cursor: pointer;
}

.run-button:disabled {
  border-color: #b7c9dd;
  color: #6b7f94;
  background: #e8f0f8;
  cursor: not-allowed;
}

.ingest-badge {
  display: inline-block;
  margin: 10px 0 0;
  padding: 4px 10px;
  border: 1px solid #c9dcf0;
  border-radius: 999px;
  color: #155fa0;
  font-size: 12px;
  font-weight: 600;
  background: #eef6ff;
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

.corpus-summary {
  margin-top: 18px;
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.corpus-summary__head {
  margin-bottom: 14px;
}

.corpus-summary h3 {
  margin: 0 0 10px;
  color: #102a43;
  font-size: 15px;
}

.corpus-summary__head p {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.6;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.category-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 14px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #fff;
}

.category-card b {
  display: block;
  margin-bottom: 6px;
  color: #102a43;
  font-size: 14px;
}

.category-card p {
  margin: 0;
  color: #5b7088;
  font-size: 12px;
  line-height: 1.55;
}

.category-card > strong {
  color: #1565c0;
  font-size: 24px;
  line-height: 1;
}

.category-tags {
  display: flex;
  flex-wrap: wrap;
  grid-column: 1 / -1;
  gap: 6px;
}

.sample-collapse {
  margin-top: 14px;
  border-top: 1px solid #d8e4f0;
  border-bottom: 0;
}

.sample-collapse :deep(.el-collapse-item__header) {
  color: #155fa0;
  font-weight: 700;
  background: transparent;
}

.sample-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
}

.sample-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}
</style>
