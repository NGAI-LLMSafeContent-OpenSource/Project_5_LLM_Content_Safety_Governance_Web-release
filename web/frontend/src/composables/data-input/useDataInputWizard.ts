import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useInputStore } from '@/stores/input'
import { scrollToPageTop } from '@/utils/scroll'
import {
  nextDataInputStepButtonLabels,
  riskTrackStepLabels,
  valueTrackStepLabels,
  type DataInputTrack,
} from '@/utils/dataInputConfig'

export function useDataInputWizard() {
  const inputStore = useInputStore()
  const { activeDataInputStep, currentTrack: currentDataInputTrack } = storeToRefs(inputStore)
  const nextStepButtonLabel = computed(
    () => nextDataInputStepButtonLabels[activeDataInputStep.value] ?? '下一步',
  )

  function goToSharedStep(targetStep: number) {
    inputStore.setActiveDataInputStep(targetStep)
    scrollToPageTop()
  }

  function activateTrackStep(targetTrack: DataInputTrack, targetStep: number) {
    inputStore.setCurrentTrack(targetTrack)
    inputStore.setActiveDataInputStep(targetStep)
    scrollToPageTop()
  }

  function goToPreviousStep() {
    if (activeDataInputStep.value <= 1) return
    inputStore.setActiveDataInputStep(activeDataInputStep.value - 1)
    scrollToPageTop()
  }

  function goToNextStep() {
    if (activeDataInputStep.value >= 6) return
    inputStore.setActiveDataInputStep(activeDataInputStep.value + 1)
    scrollToPageTop()
  }

  return {
    activeDataInputStep,
    currentDataInputTrack,
    valueTrackStepLabels,
    riskTrackStepLabels,
    nextStepButtonLabel,
    goToSharedStep,
    activateTrackStep,
    goToPreviousStep,
    goToNextStep,
  }
}
