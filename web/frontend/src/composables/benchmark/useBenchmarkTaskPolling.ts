import { onBeforeUnmount, ref, type Ref } from 'vue'
import { getBenchmarkTask, getBenchmarkTaskArtifacts, getBenchmarkTaskLogs } from '@/api/benchmark'
import {
  createBenchmarkTaskPollingController,
  type BenchmarkPollingController,
} from './benchmarkTaskPollingController'
import type { BenchmarkArtifactItem, BenchmarkTask, BenchmarkTaskLogItem } from '@/types'

export interface BenchmarkTaskPollingRefs {
  task: Ref<BenchmarkTask | null>
  logs: Ref<BenchmarkTaskLogItem[]>
  artifacts: Ref<BenchmarkArtifactItem[]>
  isPolling: Ref<boolean>
  errorMessage: Ref<string>
  currentTaskId: Ref<string>
}

export type BenchmarkTaskPolling = BenchmarkTaskPollingRefs & BenchmarkPollingController

function createBenchmarkTaskPollingRefs(): BenchmarkTaskPollingRefs {
  return {
    task: ref<BenchmarkTask | null>(null),
    logs: ref<BenchmarkTaskLogItem[]>([]),
    artifacts: ref<BenchmarkArtifactItem[]>([]),
    isPolling: ref(false),
    errorMessage: ref(''),
    currentTaskId: ref(''),
  }
}

export function useBenchmarkTaskPolling(
  refs: BenchmarkTaskPollingRefs = createBenchmarkTaskPollingRefs(),
): BenchmarkTaskPolling {
  const controller = createBenchmarkTaskPollingController({
    state: {
      get task() {
        return refs.task.value
      },
      set task(value) {
        refs.task.value = value
      },
      get logs() {
        return refs.logs.value
      },
      set logs(value) {
        refs.logs.value = value
      },
      get artifacts() {
        return refs.artifacts.value
      },
      set artifacts(value) {
        refs.artifacts.value = value
      },
      get isPolling() {
        return refs.isPolling.value
      },
      set isPolling(value) {
        refs.isPolling.value = value
      },
      get errorMessage() {
        return refs.errorMessage.value
      },
      set errorMessage(value) {
        refs.errorMessage.value = value
      },
      get currentTaskId() {
        return refs.currentTaskId.value
      },
      set currentTaskId(value) {
        refs.currentTaskId.value = value
      },
    },
    getTask: getBenchmarkTask,
    getLogs: getBenchmarkTaskLogs,
    getArtifacts: getBenchmarkTaskArtifacts,
  })

  onBeforeUnmount(controller.stopPolling)

  return {
    ...refs,
    startPolling: controller.startPolling,
    stopPolling: controller.stopPolling,
    resetPolling: controller.resetPolling,
    refreshArtifacts: controller.refreshArtifacts,
  }
}
