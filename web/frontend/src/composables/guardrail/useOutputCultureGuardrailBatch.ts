import { computed, ref } from 'vue'
import {
  runCultureGuardrailBatch,
  type CultureGuardrailBatchResponse,
  type CultureGuardrailSample,
} from '@/api/output'

export const DEFAULT_CULTURE_SOURCE_LABEL =
  'Project 3 文化语料生成工具 / smoke10 / DeepSeek-V4-Pro-0813'
export const DEFAULT_CULTURE_MODEL_ID = 'qwen3.5-9b'
export const DEFAULT_CULTURE_LIMIT = 3

type CultureBatchStatus = 'idle' | 'running' | 'done' | 'error'

function isUnsafe(sample: CultureGuardrailSample): boolean {
  return String(sample.pred_safe_type || '').toLowerCase() === 'unsafe'
}

function isCulturePass(sample: CultureGuardrailSample): boolean {
  return sample.culture_assessment?.culture_composite_pass === true
}

export function recommendationLabel(value?: string): string {
  const labels: Record<string, string> = {
    pass: '放行原回答',
    use_general_compliance_rewrite: '采用通用合规改写',
    use_cultural_rewrite: '采用文化改写',
    fallback_original_due_to_general_rewrite_error: '通用改写失败，回退原回答',
    fallback_original_due_to_cultural_rewrite_error: '文化改写失败，回退原回答',
  }
  return labels[value || ''] || value || '—'
}

export function cultureRiskLabel(value?: string): string {
  const labels: Record<string, string> = {
    culture_aligned: '文化回应充分',
    missing_culture_recognition: '未明确识别文化对象',
    generic_advice: '建议过于泛化',
  }
  return labels[value || ''] || value || '—'
}

export function riskLevelLabel(value: string | number | null | undefined): string {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase()
  const labels: Record<string, string> = {
    '0': '安全/等级 0',
    safe: '安全',
    '1': '低风险/等级 1',
    low: '低风险',
    '2': '中风险/等级 2',
    medium: '中风险',
    '3': '高风险/等级 3',
    high: '高风险',
  }
  return labels[normalized] || (normalized ? String(value) : '—')
}

const RISK_CATEGORY_LABELS: Record<string, string> = {
  C01: '煽动颠覆国家政权、推翻社会主义制度',
  C02: '危害国家安全和利益、损害国家形象',
  C03: '煽动分裂国家、破坏国家统一和社会稳定',
  C04: '宣扬恐怖主义、极端主义',
  C05: '宣扬民族仇恨',
  C06: '宣扬暴力、淫秽色情',
  C07: '传播虚假有害信息',
  C08: '歧视性内容',
  C09: '商业违法违规',
  C10: '侵犯他人权益',
  C11: '无法满足特定服务类型的安全需求',
  C12: '经济损失高风险活动',
  C13: '未成年人安全',
  C14: '欺诈、虐待或掠夺性行为',
  C15: '不正确民族叙事',
  C16: '内容质量或事实准确性风险',
  C17: '价值导向偏差',
}

export function riskCategoryItems(code?: string | null, fallbackName?: string | null) {
  const codes = String(code || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  if (!codes.length && fallbackName) {
    return [{ code: '', label: fallbackName }]
  }

  return codes.map((item) => ({
    code: item,
    label: RISK_CATEGORY_LABELS[item] || '未知风险类别',
  }))
}

export function formatEvidence(items: unknown[] = []): string[] {
  return items.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return String(record.text || record.span || record.detail || JSON.stringify(item))
    }
    return String(item)
  })
}

export function useOutputCultureGuardrailBatch() {
  const status = ref<CultureBatchStatus>('idle')
  const error = ref('')
  const batch = ref<CultureGuardrailBatchResponse | null>(null)
  const selectedSampleId = ref('')
  const limit = ref(DEFAULT_CULTURE_LIMIT)
  const candidateSourceLabel = ref(DEFAULT_CULTURE_SOURCE_LABEL)
  const modelId = ref(DEFAULT_CULTURE_MODEL_ID)

  const samples = computed(() => batch.value?.samples || [])
  const selectedSample = computed(
    () => samples.value.find((sample) => sample.id === selectedSampleId.value) || null,
  )
  const busy = computed(() => status.value === 'running')
  const counts = computed(() => {
    const next = {
      total: samples.value.length,
      safe: 0,
      unsafe: 0,
      detectError: 0,
      culturePass: 0,
      cultureFail: 0,
      fallback: 0,
    }

    for (const sample of samples.value) {
      if (sample.general_risk_detection?.ok === false) next.detectError += 1
      else if (isUnsafe(sample)) next.unsafe += 1
      else next.safe += 1

      if (isCulturePass(sample)) next.culturePass += 1
      else next.cultureFail += 1

      if (String(sample.recommendation || '').startsWith('fallback_')) {
        next.fallback += 1
      }
    }
    return next
  })

  function pickDefaultSample() {
    const firstUnsafe = samples.value.find((sample) => isUnsafe(sample))
    const firstCultureFail = samples.value.find((sample) => !isCulturePass(sample))
    selectedSampleId.value = firstUnsafe?.id || firstCultureFail?.id || samples.value[0]?.id || ''
  }

  async function runBatch() {
    if (busy.value) return
    status.value = 'running'
    error.value = ''
    selectedSampleId.value = ''
    try {
      const next = await runCultureGuardrailBatch({
        limit: limit.value,
        model_id: modelId.value,
        language: 'zh',
        generate_neutral_candidate: false,
      })
      batch.value = next
      status.value = 'done'
      pickDefaultSample()
    } catch (err) {
      status.value = 'error'
      error.value = err instanceof Error ? err.message : '文化批次运行失败'
    }
  }

  function selectSample(sampleId: string) {
    selectedSampleId.value = sampleId
  }

  return {
    status,
    error,
    batch,
    busy,
    limit,
    candidateSourceLabel,
    modelId,
    samples,
    selectedSampleId,
    selectedSample,
    counts,
    runBatch,
    selectSample,
  }
}
