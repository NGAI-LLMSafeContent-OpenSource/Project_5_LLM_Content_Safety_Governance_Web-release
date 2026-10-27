<template>
  <main id="page-output" class="main-content page-wide">
    <div class="wizard-container">
      <!-- ===== Step Wizard Bar ===== -->
      <div class="wizard-flow">
        <div class="wizard-steps wizard-steps-shared wizard-steps--shared">
          <div
            class="wizard-step clickable"
            :class="{ active: currentStep === 1 }"
            @click="navigateToStep(1)"
          >
            <div class="wizard-step-num">1</div>
            <span>测试数据选择</span>
          </div>
        </div>

        <div class="wizard-parallel-wrap">
          <!-- Diversity Track -->
          <div
            class="wizard-track wizard-track--diversity"
            :class="{ 'wizard-track--inactive': isTrackInactive(OutputTrack.DIVERSITY) }"
          >
            <div class="track-title wizard-track-label">文化多样性</div>
            <div class="wizard-steps wizard-steps--track">
              <div
                v-for="s in diversityTrackSteps"
                :key="s.id"
                class="wizard-step clickable"
                :class="{ active: currentTrack === OutputTrack.DIVERSITY && currentStep === s.id }"
                @click="navigateToStep(s.id, OutputTrack.DIVERSITY)"
              >
                <div class="wizard-step-num">{{ s.icon }}</div>
                <span>{{ s.label }}</span>
              </div>
            </div>
          </div>

          <!-- Risk Track -->
          <div
            class="wizard-track wizard-track--risk"
            :class="{ 'wizard-track--inactive': isTrackInactive(OutputTrack.RISK) }"
          >
            <div class="track-title wizard-track-label">风险</div>
            <div class="wizard-steps wizard-steps--track">
              <div
                v-for="s in riskTrackSteps"
                :key="s.id"
                class="wizard-step clickable"
                :class="{ active: currentTrack === OutputTrack.RISK && currentStep === s.id }"
                @click="navigateToStep(s.id, OutputTrack.RISK)"
              >
                <div class="wizard-step-num">{{ s.icon }}</div>
                <span>{{ s.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Panel Body ===== -->
      <div class="wizard-body">
        <div
          v-for="panel in panels"
          :id="panel.id"
          :key="panel.id"
          class="wizard-panel output-stage-section"
          :class="{ active: isPanelActive(panel.step, panel.track) }"
        >
          <component :is="panel.component" />
          <div class="wizard-footer">
            <el-button
              v-for="btn in panel.footerButtons"
              :key="btn.label"
              :type="btn.type"
              @click="btn.action()"
            >
              {{ btn.label }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import OutputDatasetSelector from '@/components/output/step1-dataset/OutputDatasetSelector.vue'
import OutputDiversityFilter from '@/components/output/diversity/OutputDiversityFilter.vue'
import OutputRiskFilter from '@/components/output/risk/OutputRiskFilter.vue'
import OutputDiversityEval from '@/components/output/diversity/OutputDiversityEval.vue'
import OutputRiskEval from '@/components/output/risk/OutputRiskEval.vue'
import OutputDiversityAttribution from '@/components/output/diversity/OutputDiversityAttribution.vue'
import OutputRiskAttribution from '@/components/output/risk/OutputRiskAttribution.vue'
import OutputDiversityCorrection from '@/components/output/diversity/OutputDiversityCorrection.vue'
import OutputRiskCorrection from '@/components/output/risk/OutputRiskCorrection.vue'
import '@/assets/styles/wizard-shared.css'
import '@/assets/styles/output-wizard.css'
import '@/assets/styles/output-shared.css'
import { useOutputWizard } from '@/composables/output/useOutputWizard'
import { useToast } from '@/composables/common/useToast'
import { OutputTrack } from '@/types'

interface PanelFooterButton {
  label: string
  type?: 'primary' | 'default'
  action: () => void
}

interface PanelConfig {
  id: string
  step: number
  track?: OutputTrack
  component: Component
  footerButtons: PanelFooterButton[]
}

const {
  diversityTrackSteps,
  riskTrackSteps,
  currentStep,
  currentTrack,
  isPanelActive,
  isTrackInactive,
  navigateToStep,
  goToPrevStep,
  goToNextStep,
  finishOutput,
} = useOutputWizard()
const toast = useToast()

function exportReport() {
  // TODO: 对接后端导出 API，支持 CSV / PDF 格式
  toast.info('报告导出中...', '正在生成评估与修正报告，请稍候')
}

const panels: PanelConfig[] = [
  {
    id: 'output-step-1',
    step: 1,
    component: OutputDatasetSelector,
    footerButtons: [],
  },
  {
    id: 'output-step-2-diversity',
    step: 2,
    track: OutputTrack.DIVERSITY,
    component: OutputDiversityFilter,
    footerButtons: [
      { label: '← 上一步', action: goToPrevStep },
      { label: '下一步 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-2-risk',
    step: 2,
    track: OutputTrack.RISK,
    component: OutputRiskFilter,
    footerButtons: [
      { label: '← 上一步', action: goToPrevStep },
      { label: '下一步 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-3-diversity',
    step: 3,
    track: OutputTrack.DIVERSITY,
    component: OutputDiversityEval,
    footerButtons: [
      { label: '← 上一步', action: goToPrevStep },
      { label: '进入归因 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-3-risk',
    step: 3,
    track: OutputTrack.RISK,
    component: OutputRiskEval,
    footerButtons: [
      { label: '← 上一步', action: goToPrevStep },
      { label: '进入归因 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-4-diversity',
    step: 4,
    track: OutputTrack.DIVERSITY,
    component: OutputDiversityAttribution,
    footerButtons: [
      { label: '← 返回评估', action: goToPrevStep },
      { label: '进入生成 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-4-risk',
    step: 4,
    track: OutputTrack.RISK,
    component: OutputRiskAttribution,
    footerButtons: [
      { label: '← 返回评估', action: goToPrevStep },
      { label: '进入修正 →', type: 'primary', action: goToNextStep },
    ],
  },
  {
    id: 'output-step-5-diversity',
    step: 5,
    track: OutputTrack.DIVERSITY,
    component: OutputDiversityCorrection,
    footerButtons: [
      { label: '← 返回归因', action: goToPrevStep },
      { label: '导出多样性对齐清单（CSV）', action: exportReport },
      { label: '✓ 完成并保存', type: 'primary', action: finishOutput },
    ],
  },
  {
    id: 'output-step-5-risk',
    step: 5,
    track: OutputTrack.RISK,
    component: OutputRiskCorrection,
    footerButtons: [
      { label: '← 返回归因', action: goToPrevStep },
      { label: '导出风险修正清单（CSV）', action: exportReport },
      { label: '✓ 完成并保存', type: 'primary', action: finishOutput },
    ],
  },
]
</script>
