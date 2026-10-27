import { ref } from 'vue'
import type {
  CorrectionSample,
  CultureSample,
  CultureAnalyzeResult,
  CultureDatasetStats,
  InferProgressStep,
} from '@/types'
import { CorrectionStatus, type DataSource } from '@/types'
import { fetchCultureSamples, analyzeCultureText } from '@/api/output'

export function useCorrection() {
  // ============================================================
  // Step 5: 修正
  // ============================================================

  const correctionSamples = ref<CorrectionSample[]>([])

  const cultureSamples = ref<CultureSample[]>([])
  const cultureAnalyzeResult = ref<CultureAnalyzeResult | null>(null)
  const cultureAnalyzeLoading = ref(false)
  const cultureAgentSteps = ref<InferProgressStep[]>([])
  const cultureDataSource = ref<DataSource>('')
  const cultureStats = ref<CultureDatasetStats | null>(null)
  const selectedCultureSampleId = ref<string>('')

  function computeCultureStats(samples: CultureSample[]): CultureDatasetStats {
    const ethnicCounts: Record<string, number> = {}
    const categoryCounts: Record<string, number> = {}
    let explicitCount = 0
    let implicitCount = 0
    for (const s of samples) {
      ethnicCounts[s.ethnic] = (ethnicCounts[s.ethnic] || 0) + 1
      categoryCounts[s.category] = (categoryCounts[s.category] || 0) + 1
      if (s.bgType === 'explicit') explicitCount++
      else implicitCount++
    }
    return {
      total: samples.length,
      explicitCount,
      implicitCount,
      ethnicCounts,
      categoryCounts,
    }
  }

  async function loadCultureData() {
    cultureDataSource.value = ''
    try {
      const data = await fetchCultureSamples()
      if (data && data.samples && data.samples.length > 0) {
        cultureSamples.value = data.samples as unknown as CultureSample[]
        cultureDataSource.value = data.source === 'real' ? 'real' : 'demo_fixture'
        cultureStats.value = {
          total: data.total,
          explicitCount: data.explicit_count,
          implicitCount: data.implicit_count,
          ethnicCounts: data.ethnic_counts,
          categoryCounts: data.category_counts,
        }
      } else {
        throw new Error('Empty response')
      }
    } catch {
      cultureSamples.value = []
      cultureDataSource.value = 'unavailable'
      cultureStats.value = computeCultureStats([])
    }
    if (!cultureStats.value) {
      cultureStats.value = computeCultureStats(cultureSamples.value as unknown as CultureSample[])
    }
    if (cultureSamples.value.length > 0 && !selectedCultureSampleId.value) {
      selectedCultureSampleId.value = cultureSamples.value[0].id
    }
  }

  async function analyzeCulture(text: string) {
    cultureAnalyzeLoading.value = true
    cultureAnalyzeResult.value = null
    cultureAgentSteps.value = [
      { name: '文化识别', status: 'running', detail: '提取文化线索…' },
      { name: '知识检索', status: 'pending', detail: '' },
      { name: '自适应生成', status: 'pending', detail: '' },
      { name: '评分与纠偏', status: 'pending', detail: '' },
    ]

    try {
      const data = await analyzeCultureText(text)
      cultureAgentSteps.value[0] = {
        name: '文化识别',
        status: 'done',
        detail: `识别为${data.ethnic}，置信度${data.confidence}%`,
      }
      await new Promise((r) => setTimeout(r, 300))
      cultureAgentSteps.value[1] = {
        name: '知识检索',
        status: 'done',
        detail: `检索到${data.category}类知识，Top-3结果已返回`,
      }
      await new Promise((r) => setTimeout(r, 200))
      cultureAgentSteps.value[2] = {
        name: '自适应生成',
        status: 'done',
        detail: `第一人称文化应答已生成（${data.generated.length}字符）`,
      }
      await new Promise((r) => setTimeout(r, 200))
      cultureAgentSteps.value[3] = {
        name: '评分与纠偏',
        status: 'done',
        detail: `综合评分${data.scores.total}分`,
      }
      cultureAnalyzeResult.value = data as unknown as CultureAnalyzeResult
    } catch (err: unknown) {
      const reason = (err as Error)?.message || '分析服务异常'
      cultureAgentSteps.value = [{ name: '推理失败', status: 'error', detail: reason }]
    } finally {
      cultureAnalyzeLoading.value = false
    }
  }

  function updateCorrectionStatus(sampleId: string, status: CorrectionStatus) {
    const sample = correctionSamples.value.find((s) => s.id === sampleId)
    if (sample) {
      sample.status = status
      sample.operator = '当前会话'
      sample.operateTime = new Date().toLocaleString('zh-CN', { hour12: false })
    }
  }

  return {
    correctionSamples,
    cultureSamples,
    cultureAnalyzeResult,
    cultureAnalyzeLoading,
    cultureAgentSteps,
    cultureDataSource,
    cultureStats,
    selectedCultureSampleId,
    computeCultureStats,
    loadCultureData,
    analyzeCulture,
    updateCorrectionStatus,
  }
}
