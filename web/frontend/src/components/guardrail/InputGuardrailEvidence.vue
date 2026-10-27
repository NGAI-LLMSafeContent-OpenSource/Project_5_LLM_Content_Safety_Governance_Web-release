<template>
  <section class="guardrail-section" aria-labelledby="guardrail-evidence-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">03</p>
      <h2 id="guardrail-evidence-title">证据归因</h2>
      <p class="guardrail-section__desc">
        解释本次未放行语料的分流原因，正常 pass 样本不在这里展开。
      </p>
    </header>

    <p v-if="loading" class="detect-empty">加载证据...</p>
    <p v-else-if="error" class="detect-empty">{{ error }}</p>
    <div v-else class="evidence-body">
      <p class="evidence-summary">
        本区解释 {{ rows.length }} 条未放行语料的分流原因：{{ reviewCount }} 条 review，{{
          reviseCount
        }}
        条 revise。
      </p>

      <div class="evidence-layout">
        <el-table
          class="evidence-table"
          :data="rows"
          border
          size="small"
          highlight-current-row
          :row-class-name="rowClassName"
          @row-click="onRowClick"
        >
          <el-table-column prop="id" label="ID" width="190" show-overflow-tooltip />
          <el-table-column label="价值评估" width="160">
            <template #default="{ row }">
              <div class="eval-cell">
                <el-tag :type="valueLevelTagType(row.valueLevel)" size="small">
                  {{ row.valueLevel || '未测' }}
                </el-tag>
                <span v-if="row.valueDim" class="eval-cell__dim">{{ row.valueDim }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="风险评估" width="160">
            <template #default="{ row }">
              <div class="eval-cell">
                <el-tag :type="riskStatusTagType(row.riskStatus)" size="small">
                  {{ row.riskStatus || '未测' }}
                </el-tag>
                <span
                  class="eval-cell__dim"
                  :class="{ 'eval-cell__dim--muted': row.riskL1 === '未命中' }"
                >
                  {{ row.riskL1 }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="处置" width="96">
            <template #default="{ row }">
              <el-tooltip v-if="row.dispositionHelp" :content="row.dispositionHelp" placement="top">
                <el-tag :type="dispositionTagType(row.disposition)" size="small">
                  {{ row.disposition }}
                </el-tag>
              </el-tooltip>
              <el-tag v-else :type="dispositionTagType(row.disposition)" size="small">
                {{ row.disposition }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="derivation" label="推导说明" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="derivation-text">{{ row.derivation || '—' }}</span>
            </template>
          </el-table-column>
        </el-table>

        <article v-if="detail" class="evidence-detail">
          <div class="evidence-detail__titlebar">
            <div>
              <h3>归因详情</h3>
              <p>{{ detail.id }}</p>
            </div>
            <el-tooltip
              v-if="detail.dispositionHelp"
              :content="detail.dispositionHelp"
              placement="top"
            >
              <el-tag :type="dispositionTagType(detail.disposition)" size="small">
                {{ detail.disposition }}
              </el-tag>
            </el-tooltip>
          </div>

          <section class="detail-block">
            <h4>触发文本</h4>
            <p>{{ detail.triggerText }}</p>
          </section>

          <div class="basis-columns">
            <section
              class="basis-block"
              :class="{
                'basis-block--value-trigger': isValueTrigger(detail),
                'basis-block--muted': !isValueTrigger(detail) && !detail.valueBasis.notApplicable,
              }"
            >
              <div class="basis-block__header">
                <h4>价值依据</h4>
                <span class="basis-block__source">课题一</span>
                <span
                  v-if="
                    !detail.valueBasis.notApplicable &&
                    detail.valueBasis.qualityLevel !== '未测' &&
                    detail.valueBasis.qualityLevel !== '—'
                  "
                  class="basis-block__badge"
                >
                  课题一预跑资产
                </span>
              </div>
              <template v-if="detail.valueBasis.notApplicable">
                <p class="basis-block__na">{{ detail.valueBasis.reason }}</p>
              </template>
              <template v-else>
                <dl class="basis-dl">
                  <dt>一级维</dt>
                  <dd>{{ detail.valueBasis.primaryDim }}</dd>
                  <dt>二级维</dt>
                  <dd>{{ detail.valueBasis.secondaryDim }}</dd>
                  <dt>档位</dt>
                  <dd>
                    <el-tag :type="valueLevelTagType(detail.valueBasis.qualityLevel)" size="small">
                      {{ detail.valueBasis.qualityLevel }}
                    </el-tag>
                  </dd>
                </dl>
                <p v-if="detail.valueBasis.reason" class="basis-block__reason">
                  {{ detail.valueBasis.reason }}
                </p>
              </template>
            </section>

            <section
              class="basis-block"
              :class="{
                'basis-block--risk-trigger': isRiskTrigger(detail),
                'basis-block--muted': detail.riskBasis.notTriggered,
              }"
            >
              <div class="basis-block__header">
                <h4>风险依据</h4>
                <span class="basis-block__source">课题二</span>
              </div>
              <dl class="basis-dl">
                <dt>状态</dt>
                <dd>
                  <el-tag :type="riskStatusTagType(detail.riskBasis.riskStatus)" size="small">
                    {{ detail.riskBasis.riskStatus }}
                  </el-tag>
                </dd>
                <dt>L1</dt>
                <dd :class="{ 'text-muted': detail.riskBasis.notTriggered }">
                  {{ detail.riskBasis.l1 || 'L1-1～L1-4 均未命中' }}
                </dd>
                <template v-if="detail.riskBasis.l2">
                  <dt>L2</dt>
                  <dd>{{ detail.riskBasis.l2 }}</dd>
                </template>
              </dl>
              <ul v-if="detail.riskBasis.evidenceItems.length" class="basis-evidence-list">
                <li v-for="item in detail.riskBasis.evidenceItems" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>

          <section v-if="detail.derivationRule" class="detail-block detail-block--derivation">
            <h4>推导规则</h4>
            <p class="derivation-rule">
              {{ detail.derivationRule }}
            </p>
          </section>

          <section class="detail-block">
            <h4>建议动作</h4>
            <p>{{ detail.suggestion }}</p>
          </section>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  UnreleasedEvidenceDetail,
  UnreleasedEvidenceRow,
} from '@/composables/guardrail/inputGuardrailDemoMap'

const props = defineProps<{
  loading: boolean
  error: string
  rows: UnreleasedEvidenceRow[]
  selectedId: string
  detail: UnreleasedEvidenceDetail | null
}>()

const emit = defineEmits<{
  selectRow: [id: string]
}>()

const reviewCount = computed(() => props.rows.filter((row) => row.disposition === 'review').length)
const reviseCount = computed(() => props.rows.filter((row) => row.disposition === 'revise').length)

function onRowClick(row: UnreleasedEvidenceRow) {
  emit('selectRow', row.id)
}

function rowClassName({ row }: { row: UnreleasedEvidenceRow }) {
  return row.id === props.selectedId ? 'is-selected-evidence-row' : ''
}

function dispositionTagType(disposition: string) {
  if (disposition === 'pass') return 'success'
  if (disposition === 'review') return 'warning'
  if (disposition === 'revise') return 'danger'
  return 'info'
}

function valueLevelTagType(level: string) {
  if (level === 'high') return 'success'
  if (level === 'medium') return 'warning'
  if (level === 'low') return 'danger'
  return 'info'
}

function riskStatusTagType(status: string) {
  if (status === '安全') return 'success'
  if (status === '异常') return 'danger'
  if (status === '待复核') return 'warning'
  return 'info'
}

function isValueTrigger(d: UnreleasedEvidenceDetail): boolean {
  return d.disposition === 'revise' || d.valueBasis.qualityLevel === 'low'
}

function isRiskTrigger(d: UnreleasedEvidenceDetail): boolean {
  return !d.riskBasis.notTriggered && d.riskBasis.riskStatus !== '安全'
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

.detect-empty {
  margin: 0;
  color: #5b7088;
  font-size: 14px;
  line-height: 1.6;
}

.evidence-body {
  display: grid;
  gap: 14px;
}

.evidence-summary {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.7;
}

.evidence-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 16px;
  align-items: start;
}

.evidence-table {
  width: 100%;
}

.evidence-table :deep(.el-table__row) {
  cursor: pointer;
}

.evidence-table :deep(.is-selected-evidence-row td) {
  background: #eef6ff;
}

.eval-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.eval-cell__dim {
  color: #29445f;
  font-size: 12px;
  line-height: 1.4;
}

.eval-cell__dim--muted {
  color: #9aafbf;
}

.derivation-text {
  color: #3d5a73;
  font-size: 12px;
}

/* detail panel */
.evidence-detail {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #f7fbff;
}

.evidence-detail__titlebar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.evidence-detail h3 {
  margin: 0 0 4px;
  color: #102a43;
  font-size: 16px;
  line-height: 1.4;
}

.evidence-detail__titlebar p {
  margin: 0;
  color: #60758f;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.detail-block {
  display: grid;
  gap: 8px;
}

.detail-block h4 {
  margin: 0;
  color: #102a43;
  font-size: 13px;
  line-height: 1.5;
}

.detail-block p {
  margin: 0;
  color: #29445f;
  font-size: 14px;
  line-height: 1.7;
}

.detail-block ul {
  display: grid;
  gap: 7px;
  margin: 0;
  padding-left: 18px;
  color: #29445f;
  font-size: 13px;
  line-height: 1.6;
}

/* basis columns */
.basis-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.basis-block {
  padding: 12px;
  border: 1px solid #d8e4f0;
  border-radius: 6px;
  background: #fafafa;
  display: grid;
  gap: 8px;
}

.basis-block--value-trigger {
  background: #f0f7ff;
  border-color: #b3d4f5;
}

.basis-block--risk-trigger {
  background: #fff8f0;
  border-color: #f5cfa0;
}

.basis-block--muted {
  opacity: 0.65;
}

.basis-block__header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.basis-block__header h4 {
  margin: 0;
  color: #102a43;
  font-size: 13px;
  font-weight: 600;
}

.basis-block__source {
  font-size: 11px;
  color: #60758f;
  background: #e8eef5;
  border-radius: 3px;
  padding: 1px 5px;
}

.basis-block__badge {
  margin-left: auto;
  font-size: 10px;
  color: #1565c0;
  background: #dbeafe;
  border-radius: 3px;
  padding: 1px 5px;
}

.basis-block__na {
  margin: 0;
  color: #60758f;
  font-size: 12px;
  line-height: 1.6;
  font-style: italic;
}

.basis-dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 10px;
  margin: 0;
}

.basis-dl dt {
  color: #60758f;
  font-size: 12px;
  line-height: 1.6;
}

.basis-dl dd {
  margin: 0;
  color: #29445f;
  font-size: 12px;
  line-height: 1.6;
}

.text-muted {
  color: #9aafbf;
}

.basis-block__reason {
  margin: 0;
  color: #29445f;
  font-size: 12px;
  line-height: 1.6;
}

.basis-evidence-list {
  margin: 0;
  padding-left: 16px;
  display: grid;
  gap: 4px;
}

.basis-evidence-list li {
  color: #3d5a73;
  font-size: 12px;
  line-height: 1.5;
}

.detail-block--derivation {
  background: #f4f8fe;
  border: 1px solid #cce0f5;
  border-radius: 6px;
  padding: 10px 12px;
}

.derivation-rule {
  margin: 0;
  color: #1565c0;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .evidence-layout {
    grid-template-columns: 1fr;
  }

  .basis-columns {
    grid-template-columns: 1fr;
  }
}
</style>
