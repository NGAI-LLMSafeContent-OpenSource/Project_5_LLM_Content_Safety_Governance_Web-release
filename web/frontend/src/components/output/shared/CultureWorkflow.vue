<template>
  <div class="culture-workflow">
    <div class="cw-agents">
      <CultureAgentCard
        v-for="(step, i) in localSteps"
        :key="i"
        :index="i + 1"
        :title="step.name"
        :status="step.status"
        :input="getStepInput(i)"
        :reasoning="getStepReasoning(i)"
        :knowledge="getStepKnowledge(i)"
        :top3="getStepTop3(i)"
        :result="getStepResult(i)"
        :time="getStepTime(i)"
        :error-msg="step.status === 'error' ? step.detail : ''"
      />
    </div>

    <div v-if="scores" class="cw-scores">
      <CultureScoreBar label="文化贴切度" :score="scores.culture" color="green" />
      <CultureScoreBar label="语义相似度" :score="scores.semantic" color="blue" />
      <CultureScoreBar label="信息完整性" :score="scores.integrity" color="amber" />
      <CultureScoreBar label="综合评分" :score="scores.culture" color="purple" suffix="分" />
    </div>

    <div v-if="errorAnalysis" class="cw-errors">
      <h4 class="cw-error-title">错误分析与修正建议</h4>
      <div class="cw-error-block cw-error-wrong">
        <span class="cw-error-tag">错误示例</span>
        <p>{{ errorAnalysis.wrongExample }}</p>
      </div>
      <div class="cw-error-block cw-error-fix">
        <span class="cw-error-tag">修正建议</span>
        <p>{{ errorAnalysis.fixSuggestion }}</p>
      </div>
      <div v-if="errorAnalysis.improveItems?.length" class="cw-improve">
        <span class="cw-error-tag">改进方向</span>
        <ul>
          <li v-for="(item, i) in errorAnalysis.improveItems" :key="i">{{ item }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CultureAgentCard from './CultureAgentCard.vue'
import CultureScoreBar from './CultureScoreBar.vue'
import type { InferProgressStep, CultureAnalyzeResult } from '@/types'

const props = defineProps<{
  steps: InferProgressStep[]
  result: CultureAnalyzeResult | null
}>()

const localSteps = computed(() =>
  props.steps.length > 0
    ? props.steps
    : [
        { name: '文化识别', status: 'pending' as const, detail: '' },
        { name: '知识检索', status: 'pending' as const, detail: '' },
        { name: '自适应生成', status: 'pending' as const, detail: '' },
        { name: '评分与纠偏', status: 'pending' as const, detail: '' },
      ],
)

function getStepInput(i: number): string {
  if (!props.result || i > 0) return ''
  return props.result.text ?? ''
}

function getStepReasoning(i: number): string {
  if (!props.result) return ''
  if (i === 0) return (props.result.reasoning ?? []).join('\n')
  return ''
}

function getStepKnowledge(i: number): string {
  if (!props.result || i !== 1) return ''
  return props.result.knowledge ?? ''
}

function getStepTop3(i: number): string[] {
  if (!props.result || i !== 1) return []
  return props.result.top3 ?? []
}

function getStepResult(i: number): string {
  if (!props.result) return ''
  if (i === 0) return `识别为${props.result.ethnic}，置信度${props.result.confidence}%`
  if (i === 2) return props.result.generated ?? ''
  if (i === 3)
    return `综合评分${props.result.scores?.total}分 (文化${props.result.scores?.culture} 语义${props.result.scores?.semantic} 完整性${props.result.scores?.integrity})`
  return ''
}

function getStepTime(_i: number): string {
  return ''
}

const scores = computed(() => props.result?.scores ?? null)
const errorAnalysis = computed(() => props.result?.errors ?? null)
</script>

<style scoped>
.culture-workflow {
  margin-top: 12px;
}

.cw-agents {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cw-scores {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-primary);
}

.cw-errors {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-primary);
}

.cw-error-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.cw-error-block {
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.cw-error-wrong {
  background: rgba(239, 68, 68, 0.06);
  border-left: 3px solid #ef4444;
}

.cw-error-fix {
  background: rgba(34, 197, 94, 0.06);
  border-left: 3px solid #22c55e;
}

.cw-error-tag {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 4px;
  display: block;
}

.cw-error-wrong .cw-error-tag {
  color: #ef4444;
}
.cw-error-fix .cw-error-tag {
  color: #22c55e;
}

.cw-error-block p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.cw-improve {
  padding: 10px;
  border-radius: 6px;
  background: var(--bg-secondary);
}

.cw-improve ul {
  margin: 4px 0 0;
  padding-left: 18px;
}

.cw-improve li {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
