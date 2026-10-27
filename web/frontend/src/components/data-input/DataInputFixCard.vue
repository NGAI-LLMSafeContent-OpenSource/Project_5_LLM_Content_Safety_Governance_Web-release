<template>
  <article
    class="fix-card"
    :class="[
      isRiskItem ? 'is-risk' : 'is-value',
      { 'is-focused': focused, 'is-expanded': expanded },
    ]"
    :data-fix-id="item.id"
  >
    <header class="fix-card__head">
      <div class="fix-card__id">
        <strong>{{ item.title }}</strong>
        <span class="status-badge" :class="statusClass">{{ item.status }}</span>
        <span v-if="l1Code" class="fix-pill">{{ l1Code }}</span>
        <span v-if="item.detectMethod" class="fix-pill is-method">
          {{ methodLabel(item.detectMethod) }}
        </span>
        <span v-if="item.contractStatus === 'pending_topic2_contract'" class="fix-pill is-warn">
          仅人工复核
        </span>
        <span v-else-if="item.note" class="fix-pill">{{ item.note }}</span>
        <span v-if="dirty" class="fix-dirty-tag">已编辑未保存</span>
      </div>
      <button class="btn btn-primary btn-sm" type="button" @click="$emit('toggle', item.id)">
        {{ expanded ? '收起编辑' : '打开修改' }}
      </button>
    </header>

    <p class="fix-why-line">{{ whyLine }}</p>

    <div class="fix-compare">
      <section class="fix-compare__col">
        <h5 class="fix-compare__title">原文</h5>
        <p class="fix-compare__text">{{ item.original || '—' }}</p>
      </section>
      <section class="fix-compare__col is-suggest">
        <h5 class="fix-compare__title">{{ suggestTitle }}</h5>
        <p class="fix-compare__text">
          {{ item.suggest || item.recommended || item.action || '—' }}
        </p>
      </section>
    </div>

    <div class="fix-card-actions">
      <button class="btn btn-success btn-sm" type="button" @click="$emit('accept', item.id)">
        采纳
      </button>
      <button
        class="btn btn-secondary btn-sm"
        type="button"
        @click="$emit('apply-recommended', item.id)"
      >
        {{ applyLabel }}
      </button>
      <button class="btn btn-warning btn-sm" type="button" @click="$emit('mark-review', item.id)">
        标记复核
      </button>
      <button class="btn btn-secondary btn-sm" type="button" @click="$emit('skip', item.id)">
        跳过
      </button>
      <button
        class="btn btn-secondary btn-sm fix-detail-toggle"
        type="button"
        @click="showDetail = !showDetail"
      >
        {{ showDetail ? '收起归因摘要' : '查看归因摘要' }}
      </button>
    </div>

    <div v-if="showDetail" class="fix-detail-fold">
      <div class="fix-detail-fold__grid">
        <div>
          <span class="fix-kv__label">{{ isRiskItem ? 'L1 / 血缘' : '问题片段' }}</span>
          <template v-if="isRiskItem">
            <div>
              {{ formatHarmCategoryL1(item.riskCategoryL1) || l1Code || '未返回 L1' }}
              · {{ item.lineageNodeLabel || '未绑定血缘' }}
            </div>
          </template>
          <ul v-else-if="item.issueSpans?.length" class="fix-issue-spans">
            <li v-for="(issue, index) in item.issueSpans" :key="`${item.id}-issue-${index}`">
              <strong>{{ issue.type || '问题片段' }}</strong>
              <span v-if="issue.span">「{{ issue.span }}」</span>
            </li>
          </ul>
          <p v-else class="fix-muted">{{ summaryLabel }}</p>
        </div>
        <div>
          <span class="fix-kv__label">归因步骤</span>
          <ol v-if="steps.length" class="fix-timeline-compact">
            <li v-for="(step, index) in steps.slice(0, 4)" :key="`${item.id}-step-${index}`">
              <strong>{{ step.title }}</strong>
              ：{{ step.detail || '—' }}
            </li>
          </ol>
          <p v-else class="fix-muted">完整证据请到归因页查看</p>
        </div>
      </div>
    </div>

    <div v-if="expanded" class="fix-edit-panel">
      <div class="fix-edit-title">{{ editTitle }}</div>
      <textarea
        class="correction-suggest"
        rows="4"
        :value="item.suggest"
        @input="onSuggestInput"
      ></textarea>
      <div class="sample-correct-actions">
        <button class="btn btn-success" type="button" @click="$emit('accept', item.id)">
          采纳本稿
        </button>
        <button
          class="btn btn-secondary"
          type="button"
          @click="$emit('apply-recommended', item.id)"
        >
          {{ applyLabel }}
        </button>
        <button class="btn btn-secondary" type="button" @click="$emit('reset-original', item.id)">
          恢复原文
        </button>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { InputFixItem } from '@/utils/inputMockData'
import { extractL1Code, formatHarmCategoryL1 } from '@/utils/topic2HarmLabels'

const props = defineProps<{
  item: InputFixItem
  expanded: boolean
  dirty: boolean
  summaryLabel: string
  editTitle: string
  statusClass: string
  suggestTitle?: string
  applyLabel?: string
  focused?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'update-suggest', id: string, value: string): void
  (e: 'accept', id: string): void
  (e: 'apply-recommended', id: string): void
  (e: 'reset-original', id: string): void
  (e: 'mark-review', id: string): void
  (e: 'skip', id: string): void
}>()

const showDetail = ref(false)

const isRiskItem = computed(
  () =>
    Boolean(props.item.detectMethod) ||
    Boolean(props.item.riskCategoryL1) ||
    Boolean(props.item.predictedL1Id),
)
const l1Code = computed(
  () => extractL1Code(props.item.predictedL1Id) || extractL1Code(props.item.riskCategoryL1),
)

const suggestTitle = computed(
  () => props.suggestTitle || (isRiskItem.value ? '处置建议' : '优档对照稿'),
)
const applyLabel = computed(
  () => props.applyLabel || (isRiskItem.value ? '恢复处置建议' : '恢复优档对照'),
)

const whyLine = computed(() => {
  if (isRiskItem.value) {
    const l1 = formatHarmCategoryL1(props.item.riskCategoryL1) || l1Code.value || '未分类'
    return `为何需改：识别为异常 · ${l1}（需人工改写，无自动 rewrite）`
  }
  if (props.item.action) {
    return `为何需改：${props.item.action}`
  }
  if (props.item.issueSpans?.length) {
    return `为何需改：待提升 · ${props.item.issueSpans[0]?.type || '价值问题片段'}`
  }
  return `为何需改：${props.summaryLabel || '待提升样本'}`
})

const steps = computed(() => {
  if (props.item.attributionSteps?.length) return props.item.attributionSteps
  if (!props.item.evidenceChain?.length) return []
  return props.item.evidenceChain.slice(0, 4).map((item) => {
    const split = item.split('：')
    if (split.length >= 2) {
      return { title: split[0], detail: split.slice(1).join('：') }
    }
    return { title: '证据', detail: item }
  })
})

function onSuggestInput(event: Event) {
  emit('update-suggest', props.item.id, (event.target as HTMLTextAreaElement).value)
}

function methodLabel(method: string) {
  if (method === 'activation_probe') return 'neuron'
  if (method === 'keyword') return 'keyword'
  return method
}
</script>

<style scoped>
.fix-card {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  padding: 14px 16px;
  background: #fff;
  margin-bottom: 12px;
}

.fix-card.is-risk {
  box-shadow: inset 3px 0 0 #1565c0;
}

.fix-card.is-value {
  box-shadow: inset 3px 0 0 #e6a23c;
}

.fix-card.is-focused {
  outline: 2px solid #1565c0;
  outline-offset: 1px;
}

.fix-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.fix-card__id {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.fix-card__id strong {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  background: #eef2f7;
  color: #334e68;
  font-size: 13px;
  font-weight: 700;
}

.fix-pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  background: #e0f2fe;
  color: #0369a1;
  white-space: nowrap;
}

.fix-pill.is-method {
  background: #f3e8ff;
  color: #6b21a8;
}

.fix-pill.is-warn {
  background: #fff7e6;
  color: #b26a00;
}

.fix-dirty-tag {
  font-size: 11px;
  color: #b26a00;
  white-space: nowrap;
}

.fix-why-line {
  margin: 0 0 10px;
  padding: 6px 10px;
  border-radius: 8px;
  background: #f1f5f9;
  font-size: 12px;
  color: #475569;
  line-height: 1.45;
}

.fix-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}

.fix-compare__col {
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: #f8fafc;
  overflow: hidden;
  min-width: 0;
}

.fix-compare__col.is-suggest {
  background: #fffaf0;
  border-color: #f5d08a;
}

.fix-compare__title {
  margin: 0;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  background: #e2e8f0;
  border-bottom: 1px solid #d8e2ee;
  white-space: nowrap;
}

.fix-compare__col.is-suggest .fix-compare__title {
  color: #b45309;
  background: #fef3c7;
  border-bottom-color: #f5d08a;
}

.fix-compare__text {
  margin: 0;
  padding: 10px;
  font-size: 13px;
  line-height: 1.55;
  color: #1a2a44;
  max-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
}

.fix-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.fix-detail-toggle {
  margin-left: auto;
}

.fix-detail-fold {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed #d8e2ee;
  border-radius: 10px;
  background: #f8fbff;
}

.fix-detail-fold__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  font-size: 13px;
  color: #1a2a44;
}

.fix-kv__label {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #6b86a5;
}

.fix-issue-spans,
.fix-timeline-compact {
  margin: 0;
  padding-left: 16px;
  line-height: 1.5;
}

.fix-muted {
  margin: 0;
  color: #8a9bb0;
  font-size: 12px;
}

.fix-edit-panel {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e8eef6;
}

.fix-edit-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #1a2a44;
}

.correction-suggest {
  width: 100%;
  margin-bottom: 10px;
}

.sample-correct-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 900px) {
  .fix-compare,
  .fix-detail-fold__grid {
    grid-template-columns: 1fr;
  }

  .fix-detail-toggle {
    margin-left: 0;
  }
}
</style>
