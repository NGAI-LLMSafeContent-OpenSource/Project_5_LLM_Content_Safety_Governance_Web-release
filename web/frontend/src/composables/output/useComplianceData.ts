import { ref, computed } from 'vue'
import type { ComplianceSample } from '@/types'

export type { ComplianceSample }

const DATA_URL = '/risk-edit-data/precomputed/demo_bundle.json'
const PROMPT_DATA_URL = '/risk-edit-data/benchmark_results/prompt.json'
const H1H4_DATA_URL = '/risk-edit-data/benchmark_results/h1h4.json'

// 单例
const loading = ref(false)
const error = ref('')
const allSamples = ref<ComplianceSample[]>([])
const languages = ref<string[]>([])

const langSamples = computed(() => {
  const list = allSamples.value
  if (!list || list.length === 0) return {}
  const map: Record<string, ComplianceSample[]> = {}
  for (const s of list) {
    const lang = s.language || 'zh-Hans'
    if (!map[lang]) map[lang] = []
    map[lang].push(s)
  }
  return map
})

async function load() {
  if (allSamples.value.length > 0) return
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch(DATA_URL)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    const resultsMap = data.results || {}
    const samples: ComplianceSample[] = []
    const langSet = new Set<string>()
    for (const [langKey, langData] of Object.entries(data.languages || {}) as Array<
      [string, { samples?: Array<Record<string, unknown>> }]
    >) {
      const langResults = (resultsMap[langKey] || {}) as Record<string, Record<string, unknown>>
      const rawSamples = langData?.samples || []
      for (let i = 0; i < rawSamples.length; i++) {
        const raw = rawSamples[i] as Record<string, unknown>
        // Editing data lives in results[lang][source_id].data (not compliance_editing)
        const sourceId = (raw.source_id as string) || ''
        const resultEntry = langResults[sourceId]
        const editData = (resultEntry?.data || {}) as Record<string, unknown>
        const ce = (raw.compliance_editing || editData) as Record<string, unknown>
        const q = (ce.quality || {}) as Record<string, unknown>
        const meta = (raw.metadata || {}) as Record<string, unknown>
        const lang = (raw.language as string) || langKey
        langSet.add(lang)
        samples.push({
          index: i,
          source_id: (raw.source_id as string) || '',
          source_index: (raw.source_index as number) ?? i,
          language: lang,
          prompt: (raw.prompt as string) || '',
          text: (raw.text as string) || '',
          categories: (raw.categories as string[]) || [],
          risk_category:
            (raw.risk_category as string) ||
            (Array.isArray(raw.categories) ? raw.categories[0] : '') ||
            '',
          risk_category_id: (raw.risk_category_id as string) || '',
          risk_level: (raw.risk_level as string) || '',
          difficulty_level: (meta.difficulty_level as string) || '',
          harmful_spans:
            (raw.harmful_spans as Array<{ start: number; end: number }>) ||
            (ce.risk_spans as Array<{ start: number; end: number }>) ||
            [],
          harmless_spans: (raw.harmless_spans as Array<{ start: number; end: number }>) || [],
          edited_text: (ce.edited_text as string) || (raw.text as string) || '',
          translated_input_zh:
            ((ce.trace as Record<string, unknown>)?.translated_input_zh as string) || '',
          edited_text_zh:
            ((ce.trace as Record<string, unknown>)?.edited_text_zh as string) ||
            (ce.edited_text as string) ||
            '',
          edits: ((ce.edits || []) as Array<Record<string, unknown>>).map((e) => ({
            original: (e.original as string) || '',
            replacement: (e.replacement as string) || '',
            reason: (e.reason as string) || '',
            start: e.start as number | undefined,
            end: e.end as number | undefined,
          })),
          quality: {
            pre_safety_label: (q.pre_safety_label as string) || 'Unsafe',
            post_safety_label: (q.post_safety_label as string) || '—',
            risk_reduced: (q.risk_reduced as boolean) ?? false,
            needs_manual_review: (q.needs_manual_review as boolean) ?? false,
            unchanged_non_risk_ratio: (q.unchanged_non_risk_ratio as number) ?? 0,
          },
          disposition: (ce.disposition as string) || '—',
          elapsed_seconds: (ce.elapsed_seconds as number) || 0,
        })
      }
    }
    allSamples.value = samples
    languages.value = [...langSet].sort()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

// Prompt results data (separate source: prompt.json)
const promptSamples = ref<ComplianceSample[]>([])
const promptLangSamples = computed(() => {
  const list = promptSamples.value
  if (!list || list.length === 0) return {}
  const map: Record<string, ComplianceSample[]> = {}
  for (const s of list) {
    const lang = s.language || 'zh-Hans'
    if (!map[lang]) map[lang] = []
    map[lang].push(s)
  }
  return map
})
const promptLoading = ref(false)

async function loadPrompt() {
  if (promptSamples.value.length > 0) return
  promptLoading.value = true
  try {
    const resp = await fetch(PROMPT_DATA_URL)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    const results: ComplianceSample[] = []
    for (const [langKey, langData] of Object.entries(data.languages || {}) as Array<
      [string, { samples?: Array<Record<string, unknown>> }]
    >) {
      for (let i = 0; i < (langData?.samples?.length || 0); i++) {
        const raw = (langData.samples || [])[i] as Record<string, unknown>
        const ce = (raw.compliance_editing || {}) as Record<string, unknown>
        const q = (ce.quality || {}) as Record<string, unknown>
        const meta = (raw.metadata || {}) as Record<string, unknown>
        results.push({
          index: i,
          source_id: (raw.source_id as string) || '',
          source_index: (raw.source_index as number) ?? i,
          language: (raw.language as string) || langKey,
          prompt: (raw.prompt as string) || '',
          text: (raw.text as string) || '',
          categories: (raw.categories as string[]) || [],
          risk_category: (raw.risk_category as string) || '',
          risk_category_id: (raw.risk_category_id as string) || '',
          risk_level: (raw.risk_level as string) || '',
          difficulty_level: (meta.difficulty_level as string) || '',
          harmful_spans: (raw.harmful_spans as Array<{ start: number; end: number }>) || [],
          harmless_spans: (raw.harmless_spans as Array<{ start: number; end: number }>) || [],
          edited_text: (ce.edited_text as string) || '',
          translated_input_zh:
            ((ce.trace as Record<string, unknown>)?.translated_input_zh as string) || '',
          edited_text_zh:
            ((ce.trace as Record<string, unknown>)?.edited_text_zh as string) ||
            (ce.edited_text as string) ||
            '',
          edits: ((ce.edits || []) as Array<Record<string, unknown>>).map((e) => ({
            original: (e.original as string) || '',
            replacement: (e.replacement as string) || '',
            reason: (e.reason as string) || '',
            start: e.start as number | undefined,
            end: e.end as number | undefined,
          })),
          quality: {
            pre_safety_label: (q.pre_safety_label as string) || 'Unsafe',
            post_safety_label: (q.post_safety_label as string) || '—',
            risk_reduced: (q.risk_reduced as boolean) ?? false,
            needs_manual_review: (q.needs_manual_review as boolean) ?? false,
            unchanged_non_risk_ratio: (q.unchanged_non_risk_ratio as number) ?? 0,
          },
          disposition: (ce.disposition as string) || '—',
          elapsed_seconds: (ce.elapsed_seconds as number) || 0,
        })
      }
    }
    promptSamples.value = results
  } catch {
    /* ignore */
  } finally {
    promptLoading.value = false
  }
}

// h1h4 batch data (separate source: h1h4.json)
const h1h4Samples = ref<ComplianceSample[]>([])
const h1h4LangSamples = computed(() => {
  const list = h1h4Samples.value
  if (!list || list.length === 0) return {}
  const map: Record<string, ComplianceSample[]> = {}
  for (const s of list) {
    const lang = s.language || 'zh-Hans'
    if (!map[lang]) map[lang] = []
    map[lang].push(s)
  }
  return map
})
const h1h4Loading = ref(false)
const h1h4Summary = ref<{ total: number; safeCount: number; reviewCount: number } | null>(null)

async function loadH1h4() {
  if (h1h4Samples.value.length > 0) return
  h1h4Loading.value = true
  try {
    const resp = await fetch(H1H4_DATA_URL)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    const results: ComplianceSample[] = []
    for (const [langKey, langData] of Object.entries(data.languages || {}) as Array<
      [string, { samples?: Array<Record<string, unknown>> }]
    >) {
      for (let i = 0; i < (langData?.samples?.length || 0); i++) {
        const raw = (langData.samples || [])[i] as Record<string, unknown>
        const ce = (raw.compliance_editing || {}) as Record<string, unknown>
        const q = (ce.quality || {}) as Record<string, unknown>
        const meta = (raw.metadata || {}) as Record<string, unknown>
        results.push({
          index: i,
          source_id: (raw.source_id as string) || '',
          source_index: (raw.source_index as number) ?? i,
          language: (raw.language as string) || langKey,
          prompt: (raw.prompt as string) || '',
          text: (raw.text as string) || '',
          categories: (raw.categories as string[]) || [],
          risk_category: (raw.risk_category as string) || '',
          risk_category_id: (raw.risk_category_id as string) || '',
          risk_level: (raw.risk_level as string) || '',
          difficulty_level: (meta.difficulty_level as string) || '',
          harmful_spans: (raw.harmful_spans as Array<{ start: number; end: number }>) || [],
          harmless_spans: (raw.harmless_spans as Array<{ start: number; end: number }>) || [],
          edited_text: (ce.edited_text as string) || '',
          translated_input_zh: '',
          edited_text_zh: '',
          edits: ((ce.edits || []) as Array<Record<string, unknown>>).map((e) => ({
            original: (e.original as string) || '',
            replacement: (e.replacement as string) || '',
            reason: (e.reason as string) || '',
            start: e.start as number | undefined,
            end: e.end as number | undefined,
          })),
          quality: {
            pre_safety_label: (q.pre_safety_label as string) || 'Unsafe',
            post_safety_label: (q.post_safety_label as string) || '—',
            risk_reduced: (q.risk_reduced as boolean) ?? false,
            needs_manual_review: (q.needs_manual_review as boolean) ?? false,
            unchanged_non_risk_ratio: (q.unchanged_non_risk_ratio as number) ?? 0,
          },
          disposition: (ce.disposition as string) || '—',
          elapsed_seconds: (ce.elapsed_seconds as number) || 0,
        })
      }
    }
    h1h4Samples.value = results
    // 汇总所有语言的 summary 统计数据
    let totalCount = 0
    let safeCount = 0
    let reviewCount = 0
    for (const s of results) {
      totalCount++
      if ((s.quality?.post_safety_label || '').toLowerCase() === 'safe') safeCount++
      if (s.quality?.needs_manual_review) reviewCount++
    }
    h1h4Summary.value = { total: totalCount, safeCount, reviewCount }
  } catch {
    /* ignore */
  } finally {
    h1h4Loading.value = false
  }
}

export function useComplianceData() {
  return {
    loading,
    error,
    allSamples,
    languages,
    langSamples,
    load,
    promptSamples,
    promptLangSamples,
    promptLoading,
    loadPrompt,
    h1h4Samples,
    h1h4LangSamples,
    h1h4Loading,
    h1h4Summary,
    loadH1h4,
  }
}
