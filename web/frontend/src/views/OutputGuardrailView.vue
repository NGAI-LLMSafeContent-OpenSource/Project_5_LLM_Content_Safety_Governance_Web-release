<template>
  <main class="main-content page-wide">
    <div class="guardrail-page">
      <GuardrailSummaryFlow
        eyebrow="统一治理标准体系 · 输出侧落地"
        title="输出内容治理"
        subtitle="对文化场景下的模型回答进行通用风险识别、文化维度评估与改写推荐。"
        governance-logic="共享治理标准体系，面向模型生成后的内容结果落地识别、分类、修正与追踪。"
        :steps="summarySteps"
        :dimension-tags="dimensionTags"
        :active-step-key="activeStepKey"
        legacy-link="/output"
        @select="onSelectStep"
      />

      <OutputCultureGuardrailReview
        :batch="batch"
        :status="status"
        :error="error"
        :busy="busy"
        :limit="limit"
        :model-id="modelId"
        :candidate-source-label="candidateSourceLabel"
        :samples="samples"
        :selected-sample-id="selectedSampleId"
        :selected-sample="selectedSample"
        :counts="counts"
        @run="runBatch"
        @select-sample="selectSample"
        @update-limit="updateLimit"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GuardrailSummaryFlow from '@/components/guardrail/GuardrailSummaryFlow.vue'
import OutputCultureGuardrailReview from '@/components/guardrail/OutputCultureGuardrailReview.vue'
import { useOutputCultureGuardrailBatch } from '@/composables/guardrail/useOutputCultureGuardrailBatch'

interface GuardrailSummaryStep {
  key: string
  title: string
  description: string
}

const summarySteps: GuardrailSummaryStep[] = [
  {
    key: 'ingest',
    title: '治理标准体系构建',
    description: '基于内容风险、风险等级、文化多样性和多民族语言适配组织输出侧治理维度。',
  },
  {
    key: 'detect',
    title: '输出内容风险识别',
    description: '识别模型生成内容中的通用风险、等级和类别。',
  },
  {
    key: 'culture',
    title: '输出内容分类归因',
    description: '解释文化对象识别、实质回应和风险证据之间的分类依据。',
  },
  {
    key: 'correct',
    title: '输出内容修正追踪',
    description: '对比改写结果，沉淀最终推荐、修正动作和治理结果。',
  },
]

const dimensionTags = ['内容风险', '风险等级', '文化多样性', '多民族语言适配']

const {
  status,
  error,
  batch,
  busy,
  limit,
  candidateSourceLabel,
  modelId,
  samples,
  selectedSampleId,
  selectedSample,
  counts,
  runBatch,
  selectSample,
} = useOutputCultureGuardrailBatch()

const activeStepKey = ref('ingest')

function updateLimit(nextLimit: number) {
  limit.value = nextLimit
}

function onSelectStep(key: string) {
  activeStepKey.value = key
  document.getElementById(`guardrail-panel-${key}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
</script>

<style scoped>
.guardrail-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 28px 24px 48px;
}

@media (max-width: 720px) {
  .guardrail-page {
    padding: 20px 16px 36px;
  }
}
</style>
