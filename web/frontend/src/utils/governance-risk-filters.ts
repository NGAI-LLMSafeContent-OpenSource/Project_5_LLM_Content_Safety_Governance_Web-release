/**
 * Clickable risk-corpus filter values (#60).
 *
 * `risk_corpus_search` accepts source / harm_category_L1 / harm_category_L2 /
 * reference_label, but its own payload never lists the available values. The
 * values come from the session's most recent `risk_corpus_overview` result, so
 * this module turns that overview payload into grouped, clickable options and
 * keeps the prompt wording deterministic.
 *
 * Kept dependency-free so the Node smoke test can import it directly; the
 * overview payload is typed as `unknown` and validated field by field.
 */

export const RISK_FILTER_KEYS = [
  'source',
  'harm_category_L1',
  'harm_category_L2',
  'reference_label',
] as const

export type RiskFilterKey = (typeof RISK_FILTER_KEYS)[number]

export interface RiskFilterOption {
  value: string
  display: string
}

export interface RiskFilterGroup {
  key: RiskFilterKey
  label: string
  options: RiskFilterOption[]
}

const RISK_FILTER_GROUP_LABELS: Record<RiskFilterKey, string> = {
  source: '来源',
  harm_category_L1: '一级分类',
  harm_category_L2: '二级分类',
  reference_label: '参考标注',
}

const RISK_REFERENCE_LABEL_DISPLAY: Record<string, string> = {
  safe: '安全',
  unsafe: '不安全',
}

function distributionFor(
  payload: Record<string, unknown>,
  key: RiskFilterKey,
): Record<string, number> | null {
  const raw = payload[`${key}_distribution`]
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as Record<string, number>
}

function optionDisplay(key: RiskFilterKey, value: string): string {
  if (key === 'reference_label') return RISK_REFERENCE_LABEL_DISPLAY[value] ?? value
  return value
}

/**
 * Group the clickable filter values exposed by a `risk_corpus_overview` payload.
 *
 * Returns `[]` when no overview payload is available or it carries no usable
 * distribution, so callers can render the explicit degradation hint instead of
 * an empty chip row.
 */
export function buildRiskFilterGroups(overviewPayload: unknown): RiskFilterGroup[] {
  if (!overviewPayload || typeof overviewPayload !== 'object') return []
  const payload = overviewPayload as Record<string, unknown>
  const groups: RiskFilterGroup[] = []
  for (const key of RISK_FILTER_KEYS) {
    const distribution = distributionFor(payload, key)
    if (!distribution) continue
    const options = Object.keys(distribution)
      .filter((value) => value)
      .map((value) => ({ value, display: optionDisplay(key, value) }))
    if (options.length === 0) continue
    groups.push({ key, label: RISK_FILTER_GROUP_LABELS[key], options })
  }
  return groups
}

/**
 * Deterministic prompt for one clicked value. It names the capability field
 * verbatim so the assistant maps it to the exact `risk_corpus_search`
 * parameter instead of guessing a filter; "风险样本" keeps the intent inside
 * the input risk domain.
 */
export function buildRiskFilterPrompt(key: RiskFilterKey, value: string): string {
  return `筛选风险样本：${key} = ${value}`
}

/** Prompt used when the session has no `risk_corpus_overview` yet. */
export const RISK_OVERVIEW_PROMPT = '请查看风险语料构成。'
