<template>
  <div class="step-indicator">
    <button
      v-for="step in steps"
      :key="getStepKey(step)"
      type="button"
      class="step-item"
      :class="{
        active: getStepKey(step) === activeStep,
        clickable: canJumpTo(getStepKey(step)),
        disabled: !canJumpTo(getStepKey(step)),
      }"
      :aria-disabled="!canJumpTo(getStepKey(step))"
      @click="handleStepClick(getStepKey(step))"
    >
      <div class="step-number">{{ getStepNumber(step) }}</div>
      <div class="step-label">{{ step.label }}</div>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface StepItem {
  id?: number
  key?: number
  number?: number
  label: string
}

const props = defineProps<{
  steps: StepItem[]
  modelValue?: number
  current?: number
  maxUnlockedStep?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
  (e: 'step-click', value: number): void
  (e: 'blocked-click', value: number): void
}>()

const activeStep = computed(() => props.modelValue ?? props.current ?? 1)
const maxUnlockedStep = computed(() => props.maxUnlockedStep ?? Number.POSITIVE_INFINITY)

function getStepKey(step: StepItem) {
  return step.key ?? step.id ?? 1
}

function getStepNumber(step: StepItem) {
  return step.number ?? getStepKey(step)
}

function canJumpTo(stepKey: number) {
  return stepKey <= maxUnlockedStep.value
}

function handleStepClick(stepKey: number) {
  if (!canJumpTo(stepKey)) {
    emit('blocked-click', stepKey)
    return
  }
  emit('update:modelValue', stepKey)
  emit('step-click', stepKey)
}
</script>
