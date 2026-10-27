import { ref } from 'vue'
import type { AttributionNode } from '@/types'
import { fetchRiskAttribution } from '@/api/output'
import { mockRiskAttributionNodes } from '@/utils/output-mock'

export function useAttribution() {
  const diversityAttributionNodes = ref<AttributionNode[]>([])
  const riskAttributionNodes = ref<AttributionNode[]>([])
  const riskAttributionLoading = ref(false)
  const riskAttributionError = ref('')
  const riskAttributionSource = ref<'live' | 'mock'>('mock')

  async function loadRiskAttribution(datasetId = '', limit = 50) {
    riskAttributionLoading.value = true
    riskAttributionError.value = ''
    try {
      const data = await fetchRiskAttribution({ dataset_id: datasetId, limit })
      if (data && data.length > 0) {
        riskAttributionNodes.value = data
        riskAttributionSource.value = 'live'
        return
      }
    } catch (e: unknown) {
      riskAttributionError.value = e instanceof Error ? e.message : '归因数据加载失败'
    } finally {
      riskAttributionLoading.value = false
    }
    // 降级到 Mock
    if (riskAttributionNodes.value.length === 0) {
      riskAttributionNodes.value = mockRiskAttributionNodes as AttributionNode[]
      riskAttributionSource.value = 'mock'
    }
  }

  return {
    diversityAttributionNodes,
    riskAttributionNodes,
    riskAttributionLoading,
    riskAttributionError,
    riskAttributionSource,
    loadRiskAttribution,
  }
}
