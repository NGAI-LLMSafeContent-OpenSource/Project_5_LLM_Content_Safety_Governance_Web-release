<template>
  <main class="main-content page-wide">
    <div id="page-data-input" class="page active">
      <div class="wizard-container">
        <div class="wizard-flow">
          <div class="wizard-steps wizard-steps-shared wizard-steps--shared">
            <div
              class="wizard-step clickable"
              :class="{ active: isSharedStepActive(STEP_DATASET) }"
              @click="goToSharedStep(STEP_DATASET)"
            >
              <div class="wizard-step-num">1</div>
              <div>训练语料构建</div>
            </div>
            <div
              class="wizard-step clickable"
              :class="{ active: isSharedStepActive(STEP_LINEAGE) }"
              @click="goToSharedStep(STEP_LINEAGE)"
            >
              <div class="wizard-step-num">2</div>
              <div>血缘图谱生成</div>
            </div>
          </div>

          <div class="wizard-parallel-wrap data-input-parallel-stack">
            <div
              class="wizard-track wizard-track--value data-input-track-panel data-input-track-panel--value"
              :class="{
                'is-track-muted':
                  activeDataInputStep >= STEP_SCREENING && currentDataInputTrack !== 'value',
              }"
            >
              <div class="track-title wizard-track-label">价值</div>
              <div class="wizard-steps">
                <div
                  v-for="stepNumber in trackStepNumbers"
                  :key="`v-${stepNumber}`"
                  class="wizard-step clickable"
                  :class="{ active: isTrackStepActive('value', stepNumber) }"
                  @click="activateTrackStep('value', stepNumber)"
                >
                  <div class="wizard-step-num">{{ stepNumber }}</div>
                  <div>{{ valueTrackStepLabels[stepNumber] }}</div>
                </div>
              </div>
            </div>
            <div
              class="wizard-track wizard-track--risk data-input-track-panel data-input-track-panel--risk"
              :class="{
                'is-track-muted':
                  activeDataInputStep >= STEP_SCREENING && currentDataInputTrack !== 'risk',
              }"
            >
              <div class="track-title wizard-track-label">风险</div>
              <div class="wizard-steps">
                <div
                  v-for="stepNumber in trackStepNumbers"
                  :key="`r-${stepNumber}`"
                  class="wizard-step clickable"
                  :class="{ active: isTrackStepActive('risk', stepNumber) }"
                  @click="activateTrackStep('risk', stepNumber)"
                >
                  <div class="wizard-step-num">{{ stepNumber }}</div>
                  <div>{{ riskTrackStepLabels[stepNumber] }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="wizard-body">
          <DataInputCorpusContextBar
            v-if="activeDataInputStep === STEP_LINEAGE"
            :title="corpusContext.title"
            :description="corpusContext.description"
            :chips="corpusContext.chips"
          />

          <div
            v-if="activeDataInputStep === STEP_DATASET"
            class="wizard-panel active data-input-stage-section"
          >
            <DataInputStepOne
              v-model:dataset-form="datasetForm"
              :custom-corpus-track="customCorpusTrack"
              :uploaded-files="uploadedFiles"
              :is-dragging-files="isDraggingFiles"
              :upload-parse-loading="uploadParseLoading"
              :corpus-catalog="corpusCatalog"
              :corpus-catalog-loading="corpusCatalogLoading"
              :corpus-catalog-message="corpusCatalogMessage"
              :value-selected-corpus="valueSelectedCorpus"
              :risk-selected-corpus="riskSelectedCorpus"
              :corpus-select-loading="corpusSelectLoading"
              :topic1-tool-catalog="topic1ToolCatalog"
              :topic1-tool-catalog-loading="topic1ToolCatalogLoading"
              :topic1-tool-catalog-error="topic1ToolCatalogError"
              :status-cards="stepOneStatusCards"
              @drag-state="handleDatasetDragState"
              @file-select="handleDatasetFileSelect"
              @file-drop="handleDatasetFileDrop"
              @remove-file="handleRemoveUploadedFile"
              @update:custom-corpus-track="handleCustomCorpusTrackChange"
              @refresh-corpus-catalog="loadInputCorpusCatalog"
              @select-corpus="handleSelectCorpus"
              @clear-value-corpus="clearValueSelectedInputCorpus"
              @clear-risk-corpus="clearRiskSelectedInputCorpus"
              @refresh-topic1-tools="loadTopic1CorpusTools"
            />
          </div>

          <div
            v-else-if="activeDataInputStep === STEP_LINEAGE"
            class="wizard-panel active data-input-stage-section"
          >
            <DataInputLineageStep
              :nodes="lineageNodes"
              :edges="lineageEdges"
              :summary="lineageSummary"
              :topic4-status="topic4LineageStatus"
              :workflow-stages="topic4WorkflowStages"
              :annotation-count="topic4Annotations.length"
              :cleaning-action-count="topic4CleaningActions.length"
              :report-summary="topic4ReportSummary"
              :selected-node="selectedLineageNode"
              :selected-node-id="selectedLineageNodeId"
              :lineage-corpus-source="lineageCorpusSource"
              :value-corpus-ready="Boolean(valueSelectedCorpus)"
              :risk-corpus-ready="Boolean(riskSelectedCorpus)"
              @update:selected-node-id="selectLineageNode"
              @change-lineage-source="setLineageCorpusSourceAndRebuild"
            />
          </div>

          <div
            v-else-if="activeDataInputStep === STEP_SCREENING"
            class="wizard-panel active data-input-stage-section"
            :class="
              currentTrackModel.isValueMode
                ? 'data-input-stage-section--value'
                : 'data-input-stage-section--risk'
            "
          >
            <DataInputScreeningStep
              :is-value-mode="currentTrackModel.isValueMode"
              :primary-standards="currentTrackModel.primaryStandards"
              :science-standards="currentTrackModel.scienceStandards"
              :custom-rules="currentTrackModel.customRules"
              :new-rule="currentTrackModel.newRule"
              :value-threshold-excellent="valueThresholdExcellent"
              :value-threshold-good="valueThresholdGood"
              :risk-threshold-high="riskThresholdHigh"
              :risk-threshold-mid="riskThresholdMid"
              :risk-threshold-low="riskThresholdLow"
              :topic1-status="topic1ValueQaAssetStatus"
              :risk-screening-status="riskScreeningStatus"
              @toggle-standard="togglePrimaryStandardForCurrentTrack"
              @toggle-science-standard="toggleScienceStandardForCurrentTrack"
              @add-rule="addCustomRuleForCurrentTrack"
              @remove-rule="removeCustomRuleForCurrentTrack"
              @update:new-rule="updateCustomRuleDraftForCurrentTrack"
              @update:value-threshold-excellent="updateValueExcellentThreshold"
              @update:value-threshold-good="updateValueGoodThreshold"
              @update:risk-threshold-high="updateRiskHighThreshold"
              @update:risk-threshold-mid="updateRiskMidThreshold"
              @update:risk-threshold-low="updateRiskLowThreshold"
            />
          </div>

          <div
            v-else-if="activeDataInputStep === STEP_ASSESSMENT"
            class="wizard-panel active data-input-stage-section"
            :class="
              currentTrackModel.isValueMode
                ? 'data-input-stage-section--value'
                : 'data-input-stage-section--risk'
            "
          >
            <DataInputAssessmentStep
              :is-value-mode="currentTrackModel.isValueMode"
              :track-mode="currentDataInputTrack"
              :mode-label="currentTrackModel.modeLabel"
              :radar-title-suffix="currentTrackModel.radarTitleSuffix"
              :stats-hint="currentTrackModel.statsHint"
              :assessment-stats="currentTrackModel.assessmentStats"
              :risk-assessment-summary="currentTrackModel.riskAssessmentSummary"
              :value-assessment-summary="currentTrackModel.valueAssessmentSummary"
              :indicators="currentTrackModel.radarIndicators"
              :selected-indicators="currentTrackModel.selectedRadarIndicators"
              :radar-scores="currentTrackModel.displayRadarScores"
              :chart-aria-label="currentTrackModel.radarAriaLabel"
              :palette="currentTrackModel.radarPalette"
              :l2-share-bars="currentTrackModel.riskL2ShareBars"
              :assessment-rows="currentTrackModel.assessmentRows"
              :topic2-status="topic2FilterGuardStatus"
              :topic2-method="topic2RiskDetectMethod"
              :topic1-status="topic1ValueQaAssetStatus"
              @toggle-radar-indicator="toggleRadarIndicatorForCurrentTrack"
              @run-topic2-keyword="runTopic2KeywordForRiskSamples"
              @cancel-topic2-risk-scan="cancelTopic2RiskScanForRiskSamples"
              @update-topic2-method="setTopic2RiskDetectMethod"
            />
          </div>

          <div
            v-else-if="activeDataInputStep === STEP_ATTRIBUTION"
            class="wizard-panel active data-input-stage-section"
            :class="
              currentTrackModel.isValueMode
                ? 'data-input-stage-section--value'
                : 'data-input-stage-section--risk'
            "
          >
            <DataInputAttributionStep
              :is-value-mode="currentTrackModel.isValueMode"
              :mode-label="currentTrackModel.modeLabel"
              :stats-hint="currentTrackModel.statsHint"
              :assessment-stats="currentTrackModel.assessmentStats"
              :assessment-rows="currentTrackModel.assessmentRows"
              :value-assessment-summary="currentTrackModel.valueAssessmentSummary"
              :value-attribution-status="valueAttributionStatus"
              :risk-attribution-status="riskAttributionStatus"
              :enabled-l1-codes="currentTrackModel.enabledL1Codes"
              :enabled-value-primaries="currentTrackModel.enabledValuePrimaries"
              :enabled-science-names="currentTrackModel.enabledScienceNames"
              @load-risk-attribution="loadRiskAttributionSamples"
            />
          </div>

          <div
            v-else-if="activeDataInputStep === STEP_CORRECTION"
            class="wizard-panel active data-input-stage-section"
            :class="
              currentTrackModel.isValueMode
                ? 'data-input-stage-section--value'
                : 'data-input-stage-section--risk'
            "
          >
            <DataInputCorrectionStep
              :is-value-mode="currentTrackModel.isValueMode"
              :mode-label="currentTrackModel.modeLabel"
              :stats-hint="currentTrackModel.statsHint"
              :assessment-stats="currentTrackModel.assessmentStats"
              :assessment-rows="currentTrackModel.assessmentRows"
              :risk-assessment-summary="currentTrackModel.riskAssessmentSummary"
              :value-assessment-summary="currentTrackModel.valueAssessmentSummary"
              :all-fixes="currentFixes"
              :fixes="filteredFixes"
              :enabled-l1-codes="currentTrackModel.enabledL1Codes"
              :preview-range="correctionPreviewRange"
              :expanded-fix-id="expandedFixId"
              :fix-dirty-map="fixDirtyMap"
              @update:preview-range="updateCorrectionPreviewRange"
              @toggle-fix="toggleFixExpansion"
              @update-suggest="updateSuggestedFixTextForCurrentTrack"
              @apply-recommended="applyRecommendedFixForCurrentTrack"
              @reset-original="resetFixTextForCurrentTrack"
              @mark-status="markFixStatusForCurrentTrack"
            />
          </div>
        </div>

        <div class="data-input-wizard-footer">
          <button
            v-if="activeDataInputStep > STEP_DATASET"
            class="btn btn-secondary data-input-wizard-footer__prev"
            @click="goToPreviousStep"
          >
            上一步
          </button>

          <div
            v-if="activeDataInputStep === STEP_LINEAGE"
            class="data-input-wizard-footer__track-choices"
          >
            <button
              class="btn btn-secondary data-input-wizard-footer__track-btn data-input-wizard-footer__track-btn--value"
              type="button"
              :disabled="!trackEntryAvailability.value"
              @click="activateTrackStep('value', STEP_SCREENING)"
            >
              进入价值 · 治理标准体系
            </button>
            <button
              class="btn btn-primary data-input-wizard-footer__track-btn data-input-wizard-footer__track-btn--risk"
              type="button"
              :disabled="!trackEntryAvailability.risk"
              @click="activateTrackStep('risk', STEP_SCREENING)"
            >
              进入风险 · 治理标准体系
            </button>
          </div>

          <button
            v-else-if="activeDataInputStep === STEP_CORRECTION"
            class="btn btn-primary data-input-wizard-footer__next"
            type="button"
            :disabled="inputWorkflowSaving"
            @click="finishInputWorkflowAndReturnHome"
          >
            {{ inputWorkflowSaving ? '保存中...' : '完成并保存' }}
          </button>

          <button
            v-else-if="activeDataInputStep < STEP_CORRECTION"
            class="btn btn-primary data-input-wizard-footer__next"
            @click="goToNextStep"
          >
            {{ nextStepButtonLabel }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { useDataInputPage } from '@/composables/data-input/useDataInputPage'
import DataInputStepOne from '@/components/data-input/DataInputStepOne.vue'
import DataInputLineageStep from '@/components/data-input/DataInputLineageStep.vue'
import DataInputScreeningStep from '@/components/data-input/DataInputScreeningStep.vue'
import DataInputAssessmentStep from '@/components/data-input/DataInputAssessmentStep.vue'
import DataInputAttributionStep from '@/components/data-input/DataInputAttributionStep.vue'
import DataInputCorrectionStep from '@/components/data-input/DataInputCorrectionStep.vue'
import DataInputCorpusContextBar from '@/components/data-input/DataInputCorpusContextBar.vue'

const {
  datasetForm,
  customCorpusTrack,
  uploadedFiles,
  isDraggingFiles,
  uploadParseLoading,
  corpusCatalog,
  corpusCatalogLoading,
  corpusCatalogMessage,
  topic1ToolCatalog,
  topic1ToolCatalogLoading,
  topic1ToolCatalogError,
  valueSelectedCorpus,
  riskSelectedCorpus,
  lineageCorpusSource,
  corpusSelectLoading,
  corpusContext,
  stepOneStatusCards,
  trackEntryAvailability,
  inputWorkflowSaving,
  riskScreeningStatus,
  valueThresholdExcellent,
  valueThresholdGood,
  riskThresholdHigh,
  riskThresholdMid,
  riskThresholdLow,
  lineageNodes,
  lineageEdges,
  topic4WorkflowStages,
  topic4Annotations,
  topic4CleaningActions,
  topic4ReportSummary,
  lineageSummary,
  topic4LineageStatus,
  topic2FilterGuardStatus,
  topic2RiskDetectMethod,
  topic1ValueQaAssetStatus,
  valueAttributionStatus,
  riskAttributionStatus,
  selectedLineageNodeId,
  selectedLineageNode,
  expandedFixId,
  fixDirtyMap,
  correctionPreviewRange,
  filteredFixes,
  currentFixes,
  activeDataInputStep,
  currentDataInputTrack,
  valueTrackStepLabels,
  riskTrackStepLabels,
  nextStepButtonLabel,
  goToSharedStep,
  activateTrackStep,
  goToPreviousStep,
  goToNextStep,
  isSharedStepActive,
  isTrackStepActive,
  currentTrackModel,
  togglePrimaryStandardForCurrentTrack,
  toggleScienceStandardForCurrentTrack,
  addCustomRuleForCurrentTrack,
  removeCustomRuleForCurrentTrack,
  updateCustomRuleDraftForCurrentTrack,
  updateValueExcellentThreshold,
  updateValueGoodThreshold,
  updateRiskHighThreshold,
  updateRiskMidThreshold,
  updateRiskLowThreshold,
  toggleRadarIndicatorForCurrentTrack,
  selectLineageNode,
  runTopic2KeywordForRiskSamples,
  cancelTopic2RiskScanForRiskSamples,
  loadRiskAttributionSamples,
  setTopic2RiskDetectMethod,
  setDatasetFileDragState,
  appendSelectedDatasetFiles,
  appendDroppedDatasetFiles,
  loadInputCorpusCatalog,
  loadTopic1CorpusTools,
  selectInputCorpusAsset,
  clearValueSelectedInputCorpus,
  clearRiskSelectedInputCorpus,
  setLineageCorpusSourceAndRebuild,
  updateCustomCorpusTrack: updateCustomCorpusTrackBase,
  updateCorrectionPreviewRange,
  toggleFixExpansion,
  updateSuggestedFixTextForCurrentTrack,
  applyRecommendedFixForCurrentTrack,
  resetFixTextForCurrentTrack,
  markFixStatusForCurrentTrack,
  finishInputWorkflowAndReturnHome,
  removeUploadedFile,
} = useDataInputPage()

const STEP_DATASET = 1
const STEP_LINEAGE = 2
const STEP_SCREENING = 3
const STEP_ASSESSMENT = 4
const STEP_ATTRIBUTION = 5
const STEP_CORRECTION = 6
const trackStepNumbers = [STEP_SCREENING, STEP_ASSESSMENT, STEP_ATTRIBUTION, STEP_CORRECTION]

function handleDatasetDragState(...args: unknown[]) {
  setDatasetFileDragState(Boolean(args[0]))
}

function handleDatasetFileSelect(...args: unknown[]) {
  appendSelectedDatasetFiles(args[0] as Event)
}

function handleDatasetFileDrop(...args: unknown[]) {
  appendDroppedDatasetFiles(args[0] as DragEvent)
}

function handleRemoveUploadedFile(...args: unknown[]) {
  const fileId = String(args[0] || '')
  if (fileId) removeUploadedFile(fileId)
}

function handleCustomCorpusTrackChange(...args: unknown[]) {
  const track = args[0]
  if (track === 'value' || track === 'risk') updateCustomCorpusTrackBase(track)
}

function handleSelectCorpus(...args: unknown[]) {
  const payload = args[0] as { assetId: string; kind: string }
  if (payload?.assetId) void selectInputCorpusAsset(payload)
}
</script>
