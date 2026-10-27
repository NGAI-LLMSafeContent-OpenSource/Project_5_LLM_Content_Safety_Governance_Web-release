<template>
  <main class="main-content page-wide">
    <div id="page-definition" class="page active">
      <div class="definition-container">
        <div class="definition-tabs">
          <button
            v-for="tab in definitionTabs"
            :key="tab.key"
            type="button"
            class="definition-tab"
            :class="{ active: activeTab === tab.key }"
            @click="switchTab(tab.key)"
          >
            <span class="definition-tab-icon">{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <div class="definition-tab-content active">
          <StepIndicator
            :model-value="activeStep"
            :steps="definitionStepItems"
            :max-unlocked-step="maxUnlockedStep"
            @update:model-value="handleStepIndicatorUpdate"
            @blocked-click="showBlockedStepHint"
          />

          <div class="step-content">
            <DefinitionInputStep
              v-if="activeStep === STEP_INPUT"
              :config="activeTabConfig"
              :state="activeTabFormState"
              :mining-state="activeMiningState"
              :format-timestamp="formatMiningTimestamp"
              @update:state="updateActiveTabFormState"
              @next="startMiningForActiveTab"
              @view-history="viewHistoryMiningTask"
              @refresh-history="refreshActiveMiningHistory"
            />

            <DefinitionMiningStep
              v-if="activeStep === STEP_MINING"
              :config="activeTabConfig"
              :form-state="activeTabFormState"
              :mining-state="activeMiningState"
              :predefined-standards="activeTabConfig.standards"
              :candidate-standards="activeStandards"
              @refresh-task="refreshActiveMiningTask"
              @adopt-candidate="adoptCandidate"
              @reject-candidate="rejectCandidate"
              @update-candidate="updateCandidate"
              @next="goToStep(STEP_MINDMAP)"
            />

            <DefinitionMindmapStep
              v-if="activeStep === STEP_MINDMAP"
              :root-title="activeTabConfig.rootTitle"
              :branches="activeBranches"
              :can-save-to-history="canSaveCurrentMiningToHistory"
              :saved-to-history="activeMiningState.savedToHistory"
              :saving-disabled="activeMiningState.loading || activeMiningState.savedToHistory"
              @save-history="() => saveCurrentMiningToHistory()"
            />
          </div>
        </div>
      </div>
    </div>

    <DefinitionHistoryViewer
      :open="historyViewer.open"
      :title="historyViewer.title"
      :subtitle="historyViewer.subtitle"
      :root-title="historyViewer.rootTitle"
      :loading="historyViewer.loading"
      :error="historyViewer.error"
      :branches="historyViewer.branches"
      @close="closeHistoryViewer"
    />
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DefinitionHistoryViewer from '@/components/definition/DefinitionHistoryViewer.vue'
import DefinitionInputStep from '@/components/definition/DefinitionInputStep.vue'
import DefinitionMiningStep from '@/components/definition/DefinitionMiningStep.vue'
import DefinitionMindmapStep from '@/components/definition/DefinitionMindmapStep.vue'
import { useDefinitionWorkflow } from '@/composables/definition/useDefinitionWorkflow'
import { definitionStepItems, definitionTabs } from '@/utils/definitionConfig'

const {
  activeTab,
  activeStep,
  maxUnlockedStep,
  activeTabConfig,
  activeTabFormState,
  activeMiningState,
  activeStandards,
  activeBranches,
  switchTab,
  showBlockedStepHint,
  goToStep,
  handleStepIndicatorUpdate,
  updateActiveTabFormState,
  startMiningForActiveTab,
  refreshActiveMiningTask,
  viewHistoryMiningTask,
  refreshActiveMiningHistory,
  closeHistoryViewer,
  saveCurrentMiningToHistory,
  formatMiningTimestamp,
  adoptCandidate,
  rejectCandidate,
  updateCandidate,
  historyViewer,
} = useDefinitionWorkflow()

const STEP_INPUT = 1
const STEP_MINING = 2
const STEP_MINDMAP = 3

const canSaveCurrentMiningToHistory = computed(
  () => Boolean(activeMiningState.value.taskId) && activeMiningState.value.status === 'completed',
)
</script>
