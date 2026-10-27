/**
 * Shared formatter for governance result cards.
 *
 * Governance timelines render several result kinds (value, risk, system
 * records), all of which need the same Asia/Shanghai timestamp rendering.
 */
const GOVERNANCE_TIME_FORMAT = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatGovernanceTime(value: string): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return GOVERNANCE_TIME_FORMAT.format(parsed)
}

/**
 * Evaluated-object version label, never the evaluator model version.
 *
 * A record outside the registered asset series stays readable but is labelled
 * "未登记" instead of pretending it is the current v7.
 */
export function formatAssetVersion(version: string | null | undefined): string {
  return version ? `资产 ${version}` : '资产未登记'
}

export function formatAssetStatus(
  status: 'current' | 'historical' | 'unregistered' | undefined,
): string {
  if (status === 'current') return '当前版本'
  if (status === 'historical') return '历史版本'
  return '未登记系列'
}

/**
 * Render an upstream 0–1 rate as a percentage without rewriting it.
 *
 * Upstream judge metrics arrive with two decimals (`0.9333` → `93.33%`).
 * Rounding to whole percent here would silently restate a source metric in the
 * UI, so governance reports keep the source precision and only trim trailing
 * zeros (`1` → `100%`, `0.9333` → `93.33%`).
 */
export function formatMetricRate(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${Number((value * 100).toFixed(2))}%`
}

const RISK_LABEL_DISPLAY: Record<string, string> = { safe: '安全', unsafe: '不安全' }

/**
 * Display name for a risk reference/detection label. Unknown values fall back
 * to the raw value so a new label never renders as an empty badge.
 */
export function formatRiskLabel(value: string): string {
  return RISK_LABEL_DISPLAY[value] ?? value
}

export function formatRiskRescanEvaluator(value: string | null | undefined): string {
  if (value === 'keyword') return 'FilterGuard keyword'
  if (!value || value === 'activation_probe') return 'Activation Probe'
  return value
}

/**
 * Flatten a filter map into the ordered `{ key, value }` pairs result cards
 * render as tags. String values are shown as-is; anything else (numbers,
 * booleans, nested objects) is JSON-encoded so the card never renders
 * `[object Object]`. Null/undefined degrade to an empty list.
 */
export function toFilterEntries(
  filters: Record<string, unknown> | null | undefined,
): { key: string; value: string }[] {
  return Object.entries(filters ?? {}).map(([key, value]) => ({
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value),
  }))
}

/**
 * Chinese labels for the topic-1 value taxonomy (#59).
 *
 * Source of truth (read-only copy, do not infer names from the English code):
 * `Project_1_Sample_evaluation_Generation/configs/value_taxonomy.yaml`
 * (version v1): layer A 社会主义核心价值观 (12), B 中华优秀传统美德 (8),
 * C 现代公民素养 (6), D 领域专业伦理 (15) — 41 keys in total.
 *
 * The Codex governance repo cannot import that sibling config at runtime, so the
 * verified mapping is copied here as data. Keys with a duplicated Chinese label
 * (for example `A.integrity` 与 `B.trustworthiness` 同为“诚信”) stay
 * distinguishable because the raw code is always preserved next to the label.
 */
const VALUE_KEY_DISPLAY: Record<string, string> = {
  // A 社会主义核心价值观 (12)
  'A.prosperity': '富强',
  'A.democracy': '民主',
  'A.civility': '文明',
  'A.harmony': '和谐',
  'A.freedom': '自由',
  'A.equality': '平等',
  'A.justice': '公正',
  'A.rule_of_law': '法治',
  'A.patriotism': '爱国',
  'A.dedication': '敬业',
  'A.integrity': '诚信',
  'A.friendship': '友善',
  // B 中华优秀传统美德 (8)
  'B.benevolence': '仁爱',
  'B.righteousness': '重义',
  'B.propriety': '守礼',
  'B.wisdom': '明智',
  'B.trustworthiness': '诚信',
  'B.filial_piety': '孝悌',
  'B.loyalty': '忠诚',
  'B.diligence_thrift': '勤俭',
  // C 现代公民素养 (6)
  'C.law_abiding': '守法',
  'C.public_order': '公德',
  'C.environmental': '环保',
  'C.scientific_spirit': '科学精神',
  'C.privacy_protection': '隐私保护',
  'C.anti_discrimination': '反歧视',
  // D 领域专业伦理 (15)
  'D.academic.honesty': '学术诚信',
  'D.academic.peer_respect': '同行尊重',
  'D.academic.open_science': '开放科学',
  'D.medical.beneficence': '患者利益优先',
  'D.medical.informed_consent': '知情同意',
  'D.medical.confidentiality': '病患保密',
  'D.business.fair_competition': '公平竞争',
  'D.business.consumer_rights': '消费者权益',
  'D.business.anti_corruption': '反腐倡廉',
  'D.education.equity': '教育公平',
  'D.education.no_violence': '反对体罚',
  'D.education.guidance': '正向引导',
  'D.tech.safety': '技术安全',
  'D.tech.responsibility': '技术责任',
  'D.tech.fairness': '算法公平',
}

/** Number of keys copied from the topic-1 taxonomy; guards silent regressions. */
export const VALUE_KEY_DISPLAY_COUNT = Object.keys(VALUE_KEY_DISPLAY).length

/**
 * Render one value key as `中文标签（A.civility）`, preserving the raw code for
 * traceability. Unknown or empty keys fall back to the raw code so a new key
 * never renders blank or throws.
 */
export function formatValueKey(value: string): string {
  if (!value) return ''
  const label = VALUE_KEY_DISPLAY[value]
  return label ? `${label}（${value}）` : value
}

/** Render an ordered list of value keys with the shared display rule. */
export function formatValueKeys(values: readonly string[]): string {
  return values.map(formatValueKey).filter(Boolean).join('、')
}
