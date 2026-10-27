import { ref } from 'vue'
import type { InferProgressStep } from '@/types'
import { inferSingleSample } from '@/api/output'

export function useInference() {
  const inferLoading = ref(false)
  const inferResponse = ref('')
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const inferResult = ref<any>(null)
  const inferModelId = ref('qwen3.5-9B-V7')
  const inferTask = ref('joint_level_then_multilabel')
  const inferShowMockLabel = ref(false)
  const inferSource = ref('')
  const inferProgressSteps = ref<InferProgressStep[]>([])

  function setInferResponse(text: string) {
    inferResponse.value = text
  }

  function extractInferError(data: Record<string, unknown>): Error {
    const source = typeof data.source === 'string' ? data.source : ''
    const isUnavailable = source === 'unavailable'
    const stepErr = (data.steps as Array<{ status: string; detail?: unknown }> | undefined)?.find(
      (s) => s.status === 'error',
    )
    const stepDetail = typeof stepErr?.detail === 'string' ? stepErr.detail : ''
    const stderrText = typeof data.stderr === 'string' ? data.stderr : ''
    // 提取 stderr 中最后一行 Error（通常是最关键的错误信息）
    const stderrLastLine =
      stderrText
        .split('\n')
        .filter((l) => l.includes('Error') || l.includes('error'))
        .slice(-1)[0]
        ?.trim() || ''

    // 1. 连接层错误（本机无法连接 Benchmark）
    if (isUnavailable) {
      const rawResponse = typeof data.raw_response === 'string' ? data.raw_response : ''
      return new Error(
        `【本地连接失败 — 课题5后端无法连接到 Benchmark】\n\n${stepDetail || rawResponse}`,
      )
    }

    // 2. 远程推理错误（Benchmark 可达，但推理引擎报错）
    // 组合：步骤描述 + 具体 stderr 错误信息
    const parts: string[] = []
    if (stepDetail) parts.push(stepDetail)
    if (stderrLastLine && !stepDetail.includes(stderrLastLine))
      parts.push(`具体错误: ${stderrLastLine}`)

    const prefix = source === 'remote' ? '【远程 Benchmark 推理失败】' : '【推理失败】'
    return new Error(`${prefix}\n\n${parts.join('\n') || '推理引擎返回未知错误'}`)
  }

  function buildInferSteps(
    serverSteps: Array<{ name: string; status: string; detail?: unknown }>,
  ): InferProgressStep[] {
    return serverSteps
      .filter((s) =>
        ['输入', '模型原始', '解析安全与类别', '分级模型原始', '解析分级分类'].some((k) =>
          s.name.includes(k),
        ),
      )
      .map((s) => ({
        name: s.name,
        status: s.status as InferProgressStep['status'],
        detail:
          typeof s.detail === 'string'
            ? s.detail.substring(0, 180)
            : JSON.stringify(s.detail || {}).substring(0, 180),
      }))
  }

  function flattenInferResult(data: Record<string, unknown>) {
    const r = (data.result as Record<string, unknown>) || data
    const riskCategories = Array.isArray(r.risk_categories) ? r.risk_categories : []
    const safeType =
      (r.safe_type as string) ||
      (r.pred_safe_type as string) ||
      (Number(r.risk_level ?? r.pred_risk_level ?? 0) > 0 || riskCategories.length
        ? 'unsafe'
        : 'safe')
    const safeLabel = safeType === 'unsafe' ? '有害' : '安全'
    const lv = (r.risk_level ?? r.pred_risk_level ?? 'N/A') as string | number
    const lvNum = typeof lv === 'number' ? lv : parseInt(String(lv), 10)
    const lvLabel =
      lvNum === 3 || String(lv).includes('3')
        ? '高风险'
        : lvNum === 2 || String(lv).includes('2')
          ? '中风险'
          : lvNum === 1 || String(lv).includes('1')
            ? '低风险'
            : lvNum === 0 || String(lv) === '0'
              ? '无风险'
              : String(lv)
    const category =
      (riskCategories.length ? riskCategories.join('、') : '') ||
      (r.risk_category_name as string) ||
      (r.risk_category as string) ||
      (r.pred_category as string) ||
      (r.pred_category_code as string) ||
      'N/A'
    const categoryCode = (r.risk_category as string) || (data.pred_category_code as string) || ''
    const resultClassification = (r.classification as Record<string, unknown>) || {}
    const resultSeverity = (r.severity as Record<string, unknown>) || {}
    const rawResponse =
      (resultClassification.raw_response as string) ||
      (resultSeverity.raw_response as string) ||
      (r.raw_output as string) ||
      (data.raw_response as string) ||
      ''
    const steps = (data.steps as Array<{ name: string; detail?: { prompt?: string } }>) || []
    const promptUsed = steps.find((s) => s.name === '构造评测 Prompt')?.detail?.prompt || ''
    return { safeType, safeLabel, lv, lvLabel, category, categoryCode, rawResponse, promptUsed }
  }

  function buildFallbackResult(reason: string) {
    return {
      ok: false,
      cached: false,
      pred_safe_type: 'error' as const,
      pred_risk_level: '',
      pred_category: '推理异常',
      pred_category_code: '',
      raw_response: reason,
      prompt_used: '',
      source: 'unavailable',
      steps: [] as InferProgressStep[],
    }
  }

  async function runInfer() {
    if (!inferResponse.value.trim()) return
    inferLoading.value = true
    inferResult.value = null
    inferProgressSteps.value = []
    inferShowMockLabel.value = false
    inferSource.value = ''

    const textLen = inferResponse.value.length
    inferProgressSteps.value.push({
      name: '远程推理',
      status: 'running',
      detail: `已发送 ${textLen} 字符到 vLLM 推理服务，等待 GPU 返回…`,
    })

    try {
      /* eslint-disable @typescript-eslint/no-explicit-any */
      const data = (await inferSingleSample({
        task: inferTask.value,
        response: inferResponse.value,
        model_id: inferModelId.value,
        use_vllm: true,
        use_api: false,
        max_model_len: 32768,
        max_new_tokens: 64,
        severity_max_new_tokens: 16,
        evidence_max_new_tokens: 1536,
      })) as any
      /* eslint-enable @typescript-eslint/no-explicit-any */

      if (!data?.ok) throw extractInferError(data)

      inferProgressSteps.value = buildInferSteps(data.steps || [])

      const normalized = flattenInferResult(data)
      inferProgressSteps.value.push({
        name: '结果汇总',
        status: 'done',
        detail: `判定: ${normalized.safeLabel} | 风险等级: ${normalized.lvLabel} | 分类: ${normalized.category}${data.cached ? ' [命中缓存]' : ''}`,
      })

      inferResult.value = {
        ...data,
        pred_safe_type: normalized.safeType,
        pred_risk_level: String(normalized.lv),
        pred_category: normalized.category,
        pred_category_code: normalized.categoryCode,
        raw_response: normalized.rawResponse,
        prompt_used: normalized.promptUsed,
      }
      inferSource.value = data.source || 'benchmark'
      inferShowMockLabel.value = data.source === 'mock'
    } catch (err: unknown) {
      const reason = (err as Error)?.message || '推理服务异常'
      inferProgressSteps.value = [{ name: '推理结果', status: 'error', detail: reason }]
      inferResult.value = buildFallbackResult(reason)
      inferSource.value = 'unavailable'
      inferShowMockLabel.value = false
    } finally {
      inferLoading.value = false
    }
  }

  return {
    inferLoading,
    inferResponse,
    inferResult,
    inferModelId,
    inferTask,
    inferShowMockLabel,
    inferSource,
    inferProgressSteps,
    setInferResponse,
    runInfer,
  }
}
