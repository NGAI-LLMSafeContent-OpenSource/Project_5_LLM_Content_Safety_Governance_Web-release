import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export type BenchmarkUiView = 'standard' | 'expert'

export type BenchmarkExpertQuery = {
  tab?: string
  agent?: string
  task?: string
}

function readViewQuery(raw: unknown): BenchmarkUiView {
  const value = Array.isArray(raw) ? raw[0] : raw
  return value === 'expert' ? 'expert' : 'standard'
}

export function useBenchmarkViewMode() {
  const route = useRoute()
  const router = useRouter()

  const view = computed<BenchmarkUiView>(() => readViewQuery(route.query.view))
  const isExpert = computed(() => view.value === 'expert')
  const isStandard = computed(() => view.value === 'standard')

  function goExpert(payload?: BenchmarkExpertQuery) {
    const nextQuery = { ...route.query }
    delete nextQuery.tab
    delete nextQuery.agent
    delete nextQuery.task
    nextQuery.view = 'expert'
    if (payload?.tab) {
      nextQuery.tab = payload.tab
    }
    if (payload?.agent) {
      nextQuery.agent = payload.agent
    }
    if (payload?.task) {
      nextQuery.task = payload.task
    }
    void router.replace({ query: nextQuery })
  }

  function goStandard() {
    const nextQuery = { ...route.query }
    delete nextQuery.view
    delete nextQuery.tab
    delete nextQuery.agent
    delete nextQuery.task
    void router.replace({ query: nextQuery })
  }

  return {
    view,
    isExpert,
    isStandard,
    goExpert,
    goStandard,
  }
}
