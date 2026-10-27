<template>
  <main class="main-content page-wide">
    <div class="guardrail-page">
      <GuardrailSummaryFlow
        eyebrow="统一治理标准体系 · 输入侧落地"
        title="输入数据治理"
        subtitle="对训练语料进行风险识别与分流，输出可放行、需复核、需修正的数据资产。"
        governance-logic="共享治理标准体系，面向进入模型前的数据资产落地识别、分类、修正与追踪。"
        :steps="summarySteps"
        :dimension-tags="dimensionTags"
        :active-step-key="activeStepKey"
        legacy-link="/data-input"
        @select="onSelectStep"
      />

      <InputGuardrailIngest
        id="guardrail-panel-ingest"
        :packs="packs"
        :selected-pack-id="selectedPackId"
        :ingest-loading="ingestLoading"
        :ingest-error="ingestError"
        :running="running"
        :job-id="job?.job_id || ''"
        :job-status="job?.status || '未运行'"
        :mode="job?.mode || selectedPack?.mode || 'demo_adapter'"
        :risk-asset-name="riskAssetName"
        :risk-pair-count="riskPairCount"
        :risk-total="riskTotal"
        :category-summary="categorySummary"
        :sample-rows="sampleRows"
        @select-pack="selectPack"
        @run-live="runLive"
      />

      <InputGuardrailDetect
        id="guardrail-panel-detect"
        :loading="valueLoading"
        :error="valueError"
        :run-summary="runSummary"
        :disposition-summary="dispositionSummary"
        :samples="samples"
      />

      <InputGuardrailEvidence
        id="guardrail-panel-evidence"
        :loading="evidenceLoading"
        :error="evidenceError"
        :rows="unreleasedEvidenceRows"
        :selected-id="selectedEvidenceId"
        :detail="selectedEvidenceDetail"
        @select-row="selectEvidenceRow"
      />

      <InputGuardrailDisposal
        id="guardrail-panel-correct"
        :value-fix-items="valueFixItems"
        :risk-fix-items="riskFixItems"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GuardrailSummaryFlow from '@/components/guardrail/GuardrailSummaryFlow.vue'
import InputGuardrailDetect from '@/components/guardrail/InputGuardrailDetect.vue'
import InputGuardrailDisposal from '@/components/guardrail/InputGuardrailDisposal.vue'
import InputGuardrailEvidence from '@/components/guardrail/InputGuardrailEvidence.vue'
import InputGuardrailIngest from '@/components/guardrail/InputGuardrailIngest.vue'
import { useInputGuardrailLive } from '@/composables/guardrail/useInputGuardrailLive'

interface GuardrailSummaryStep {
  key: string
  title: string
  description: string
}

const summarySteps: GuardrailSummaryStep[] = [
  {
    key: 'ingest',
    title: '治理标准体系构建',
    description: '基于价值适配、异常风险、边界复核和血缘来源组织输入侧治理维度。',
  },
  {
    key: 'detect',
    title: '输入数据风险识别',
    description: '识别进入模型前的数据风险，并形成 pass、review、revise 分流结果。',
  },
  {
    key: 'evidence',
    title: '输入数据分类归因',
    description: '解释未放行样本的分类依据、风险证据和来源链路。',
  },
  {
    key: 'correct',
    title: '输入数据修正追踪',
    description: '汇总未放行语料的修正建议、复核动作和治理结果。',
  },
]

const dimensionTags = ['价值适配', '异常风险', '边界复核', '血缘来源']

const activeStepKey = ref('ingest')
const live = useInputGuardrailLive()
const {
  packs,
  selectedPackId,
  selectedPack,
  job,
  running,
  ingestLoading,
  ingestError,
  riskAssetName,
  riskPairCount,
  riskTotal,
  categorySummary,
  sampleRows,
  runSummary,
  dispositionSummary,
  samples,
  valueLoading,
  valueError,
  evidenceLoading,
  evidenceError,
  unreleasedEvidenceRows,
  selectedEvidenceId,
  selectedEvidenceDetail,
  valueFixItems,
  riskFixItems,
  selectPack,
  runLive,
  selectEvidenceRow,
} = live

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
