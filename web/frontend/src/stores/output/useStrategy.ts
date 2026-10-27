import { ref } from 'vue'
import type { StrategyRecommendation, ComparisonMetric } from '@/types'

export function useStrategy() {
  const strategyRecommendations = ref<StrategyRecommendation[]>([])
  const comparisonMetrics = ref<ComparisonMetric[]>([])

  return { strategyRecommendations, comparisonMetrics }
}
