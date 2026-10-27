<template>
  <section class="guardrail-section" aria-labelledby="guardrail-detect-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">02</p>
      <h2 id="guardrail-detect-title">输入数据风险识别</h2>
      <p class="guardrail-section__desc">
        展示本次 live run 跑完后的分流结果：哪些语料放行，哪些进入复核，哪些需要修正。
      </p>
    </header>

    <p v-if="loading" class="detect-empty">运行或加载检测结果…</p>
    <p v-else-if="error" class="detect-empty">{{ error }}</p>
    <p v-else-if="!runSummary.total" class="detect-empty">运行后显示本批语料分流结果</p>

    <div v-else class="detect-grid">
      <article class="detect-card">
        <h3>完成</h3>
        <p class="detect-source">{{ runSummary.status }}</p>
        <p class="detect-metric">{{ runSummary.done }} / {{ runSummary.total }}</p>
        <p v-if="runSummary.jobId" class="detect-highlight">job {{ runSummary.jobId }}</p>
      </article>

      <article class="detect-card">
        <h3>pass</h3>
        <p class="detect-source">放行</p>
        <p class="detect-metric">{{ runSummary.pass }} 条</p>
        <p class="detect-highlight">可进入候选入库或低风险抽检</p>
      </article>

      <article class="detect-card">
        <h3>review</h3>
        <p class="detect-source">复核</p>
        <p class="detect-metric">{{ runSummary.review }} 条</p>
        <p class="detect-highlight">风险、边界或质量语义需要人工确认</p>
      </article>

      <article class="detect-card">
        <h3>revise</h3>
        <p class="detect-source">修正</p>
        <p class="detect-metric">{{ runSummary.revise }} 条</p>
        <p class="detect-highlight">先修正事实或价值表达，再复核</p>
      </article>
    </div>

    <div v-if="sampleAssessmentRows.length" class="assessment-panel">
      <h3>样本评估体系</h3>
      <p class="assessment-hint">
        每条语料的课题一价值评估与课题二风险识别结果，处置由两套评估推导。
      </p>
      <el-table :data="sampleAssessmentRows" border size="small" class="assessment-table">
        <el-table-column prop="id" label="ID" width="160" show-overflow-tooltip />
        <el-table-column label="课题一 价值体系" min-width="220">
          <template #default="{ row }">
            <template v-if="row.valuePrimary">
              <span class="dim-tag dim-tag--value">{{ row.valuePrimary }}</span>
              <span v-if="row.valueSecondary" class="dim-sub">{{ row.valueSecondary }}</span>
              <el-tag
                :type="
                  row.valueLevel === 'high'
                    ? 'success'
                    : row.valueLevel === 'medium'
                      ? 'warning'
                      : 'danger'
                "
                size="small"
                class="level-tag"
              >
                {{ row.valueLevel }}
              </el-tag>
            </template>
            <span v-else class="dim-na">未评</span>
          </template>
        </el-table-column>
        <el-table-column label="课题二 风险体系" min-width="200">
          <template #default="{ row }">
            <template v-if="row.riskL1">
              <span class="dim-tag dim-tag--risk">{{ row.riskL1 }}</span>
              <el-tag
                :type="
                  row.riskAbnormal ? 'danger' : row.riskStatus === '待复核' ? 'warning' : 'info'
                "
                size="small"
                class="level-tag"
              >
                {{ row.riskAbnormal ? '异常' : row.riskStatus || '安全' }}
              </el-tag>
            </template>
            <span v-else class="dim-na">未评</span>
          </template>
        </el-table-column>
        <el-table-column label="处置" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.disposition === 'pass'
                  ? 'success'
                  : row.disposition === 'revise'
                    ? 'danger'
                    : 'warning'
              "
              size="small"
            >
              {{ row.disposition || '—' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="derivedReason"
          label="推导说明"
          min-width="200"
          show-overflow-tooltip
        />
      </el-table>
    </div>

    <div v-if="dispositionSummary.length" class="distribution-panel">
      <h3>治理结果分布</h3>
      <el-table :data="dispositionSummary" border size="small">
        <el-table-column prop="category" label="类型" min-width="150" show-overflow-tooltip />
        <el-table-column prop="sampleCount" label="样本数" width="90" />
        <el-table-column prop="pass" label="pass" width="80" />
        <el-table-column prop="review" label="review" width="90" />
        <el-table-column prop="revise" label="revise" width="90" />
        <el-table-column prop="note" label="说明" min-width="260" show-overflow-tooltip />
      </el-table>
    </div>

    <p class="detect-notice">
      以下结果来自本次输入数据治理运行，不是预跑静态拼接。每条样本保留来源资产、来源样本 ID
      与最小血缘链，用于后续证据归因和草稿保存。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { InputGuardrailLiveSample } from '@/api/dataInput'
import { deriveAssessmentReason } from '@/composables/guardrail/deriveAssessmentReason'
import type {
  DispositionCategoryRow,
  RunDispositionSummary,
} from '@/composables/guardrail/inputGuardrailDemoMap'
import { formatHarmCategoryL1 } from '@/utils/topic2HarmLabels'

const props = defineProps<{
  loading: boolean
  error: string
  runSummary: RunDispositionSummary
  dispositionSummary: DispositionCategoryRow[]
  samples: InputGuardrailLiveSample[]
}>()

interface AssessmentRow {
  id: string
  valuePrimary: string
  valueSecondary: string
  valueLevel: string
  riskL1: string
  riskAbnormal: boolean
  riskStatus: string
  disposition: string
  derivedReason: string
}

const sampleAssessmentRows = computed<AssessmentRow[]>(() =>
  props.samples.map((s) => {
    const vd = s.value_dimension
    const rr = s.risk_result as Record<string, unknown>
    const row: AssessmentRow = {
      id: s.id,
      valuePrimary: vd?.primary || '',
      valueSecondary: vd?.secondary || '',
      valueLevel:
        vd?.quality_level ||
        ((s.value_result as Record<string, unknown>)?.quality_level as string) ||
        '',
      riskL1: formatHarmCategoryL1(rr?.category_l1 as string),
      riskAbnormal: Boolean(rr?.is_abnormal),
      riskStatus: String(rr?.status || ''),
      disposition: s.disposition || s.expected_disposition || '',
      derivedReason: '',
    }
    row.derivedReason = deriveAssessmentReason(row)
    return row
  }),
)
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  margin: 0 0 8px;
  color: #102a43;
  font-size: 16px;
}

.detect-source {
  margin: 0 0 12px;
  color: #5b7088;
  font-size: 12px;
  line-height: 1.5;
}

.detect-metric {
  margin: 0 0 12px;
  color: #1565c0;
  font-size: 22px;
  font-weight: 700;
}

.detect-highlight {
  margin: 0 0 8px;
  color: #486581;
  font-size: 14px;
  line-height: 1.6;
}

.detect-highlight:last-child {
  margin-bottom: 0;
}

.detect-empty {
  margin: 0;
  color: #5b7088;
  font-size: 14px;
  line-height: 1.6;
}

.detect-notice {
  margin: 16px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  color: #155fa0;
  font-size: 13px;
  line-height: 1.6;
  background: #eef6ff;
}

.assessment-panel {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #fff;
}

.assessment-panel h3 {
  margin: 0 0 6px;
  color: #102a43;
  font-size: 15px;
}

.assessment-hint {
  margin: 0 0 12px;
  color: #5b7088;
  font-size: 13px;
  line-height: 1.6;
}

.assessment-table {
  font-size: 13px;
}

.dim-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  margin-right: 4px;
}

.dim-tag--value {
  background: #e8f4fd;
  color: #1565c0;
}

.dim-tag--risk {
  background: #fdecea;
  color: #c0392b;
}

.dim-sub {
  font-size: 12px;
  color: #5b7088;
  margin-right: 4px;
}

.dim-na {
  color: #aab8c9;
  font-size: 12px;
}

.level-tag {
  margin-left: 2px;
}

.distribution-panel {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #fff;
}

.distribution-panel h3 {
  margin: 0 0 12px;
  color: #102a43;
  font-size: 15px;
}

@media (max-width: 900px) {
  .detect-grid {
    grid-template-columns: 1fr;
  }
}
</style>
