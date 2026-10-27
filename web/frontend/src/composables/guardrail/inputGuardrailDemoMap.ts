export const VALUE_KIND = 'value_qa'
export const RISK_STATIC_KIND = 'risk_static_dynbench'
export const RECORDS_LIMIT = 5
export const ASSESSMENT_LIMIT = 24
export const PRERUN_LIMIT = 40
export const ATTRIBUTION_LIMIT = 24
export const FIX_LIST_LIMIT = 5
export const RADAR_LIMIT = 6
export const L1_LABEL_LIMIT = 3
export const STRATEGY_TAG_LIMIT = 3
export const SNIPPET_MAX = 80

export const DISPOSAL_NOTICE = '以下为预跑检测生成的修正建议，不表示语料已写入本地库。'
export const SOURCE_NOTICE =
  '价值证据、风险证据与血缘图谱来自不同预跑资产，不表示同一条语料已同时完成三维检测。'
export const EVIDENCE_STATIC_NOTICE = '本批 live run 证据，绑定当前 job。'
export const VALUE_BADGE = '价值预跑'
export const RISK_BADGE = '正式预跑'
export const ABNORMAL_CARD_SOURCE = '课题二 live 检测 / demo adapter 明确兜底'
export const POISON_CARD_SOURCE = '本批异常/投毒风险复核切面'
export const REVIEW_STATUS = '待人工复核后入库'
export const EMPTY_CATALOG = '尚未导入课题一 value_qa 预跑资产'
export const ERR_CATALOG = '语料目录不可达'
export const ERR_VALUE = '价值预跑评估不可达'
export const ERR_RISK = '课题二预跑样本不可达'
export const ERR_LINEAGE = '静态血缘图谱暂不可用'
export const ERR_VALUE_EVIDENCE = '暂无可用低价值样本'
export const ERR_RISK_EVIDENCE = '暂无可用风险样本'
export const ERR_FIX = '暂无预跑修正建议'

export type EvidenceTrack = 'value' | 'risk'

export interface CatalogLike {
  asset_id: string
  name: string
  kind?: string
  ready?: boolean
  sample_count?: number
  source_label?: string
}

export interface AttributionLike {
  id?: string
  snippet?: string
  suggestion?: string
  evidence_chain?: string[]
  attribution_steps?: Array<{ title?: string; detail?: string }>
  quality_level?: string
  status?: string
  dimension?: string
  risk_category_l1?: string
  risk_category_l2?: string
  strategy_chain?: string[]
}

export interface PrerunLike {
  id?: string
  snippet?: string
  suggestion?: string
  status?: string
  harm_category_l1?: string
  harm_category_l2?: string
  strategy_chain?: string[]
  bypassed_moderators?: string[]
}

export interface InputGuardrailEvidenceView {
  id: string
  track: EvidenceTrack
  snippet: string
  suggestion: string
  evidenceChain: string[]
  attributionSteps: Array<{ title: string; detail: string }>
  qualityLevel: string
  dimension: string
  riskL1: string
  riskL2: string
  strategyChain: string[]
}

export interface AbnormalSlice {
  pairCount: number
  total: number
  abnormalCount: number
  l1Labels: string[]
  hasDetail: boolean
}

export interface PoisonSlice {
  strategyCount: number
  bypassCount: number
  topStrategies: string[]
  hasDetail: boolean
}

export interface LineageSlice {
  totalNodes: number
  totalEdges: number
  riskyNodes: number
  reportSummary: string
  hasDetail: boolean
}

export interface FixItem {
  id?: string
  category?: string
  disposition?: string
  problemSummary?: string
  status?: string
  snippet: string
  suggestion: string
}

export interface DemoCategorySummary {
  category: string
  count: number
  dispositions: string[]
  note: string
}

export interface DemoSampleRow {
  id: string
  category: string
  sourceTopic: string
  sourceLabel: string
  expectedDisposition: string
  dispositionHelp: string
  snippet: string
}

export interface RunDispositionSummary {
  total: number
  done: number
  pass: number
  review: number
  revise: number
  status: string
  jobId: string
}

export interface DispositionCategoryRow {
  category: string
  sampleCount: number
  pass: number
  review: number
  revise: number
  note: string
}

export interface ValueBasis {
  primaryDim: string
  secondaryDim: string
  qualityLevel: string
  reason: string
  notApplicable: boolean
}

export interface RiskBasis {
  riskStatus: string
  l1: string
  l2: string
  evidenceItems: string[]
  notTriggered: boolean
}

export interface UnreleasedEvidenceRow {
  id: string
  category: string
  disposition: string
  dispositionHelp: string
  attributionSummary: string
  valueLevel: string
  valueDim: string
  riskStatus: string
  riskL1: string
  derivation: string
}

export interface UnreleasedEvidenceDetail {
  id: string
  category: string
  disposition: string
  dispositionHelp: string
  triggerText: string
  basis: string[]
  suggestion: string
  valueBasis: ValueBasis
  riskBasis: RiskBasis
  derivationRule: string
}

export const DISPOSITION_HELP: Record<string, string> = {
  pass: '语料质量和风险状态基本可接受，可以进入候选入库或低风险抽检。',
  review: '语料存在风险、边界意图、信息不足或需要确认的地方，先交给人工复核。',
  revise: '语料明显低质、事实错配或价值表达有问题，需要修正后再复核。',
}

export function pickValueCatalogItems<T extends CatalogLike>(items: T[]): T[] {
  return items.filter((item) => item.kind === VALUE_KIND)
}

export function pickDefaultValueAsset<T extends CatalogLike>(items: T[]): T | null {
  const valueItems = pickValueCatalogItems(items)
  return valueItems.find((item) => item.ready) ?? valueItems[0] ?? null
}

export function truncateText(text: string, max = SNIPPET_MAX): string {
  const value = text.trim()
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}

export function mapRadarScores(
  scores: Record<string, number> | null | undefined,
  limit = RADAR_LIMIT,
): Array<{ name: string; score: number }> {
  if (!scores) return []
  return Object.entries(scores)
    .filter(([name, score]) => name.trim() && Number.isFinite(score))
    .slice(0, limit)
    .map(([name, score]) => ({ name, score }))
}

export function mapQualityDistribution(
  dist: Record<string, number> | null | undefined,
): Array<{ label: string; count: number }> {
  if (!dist) return []
  return Object.entries(dist)
    .filter(([label, count]) => label.trim() && Number.isFinite(count) && count > 0)
    .map(([label, count]) => ({ label, count }))
}

export function mapAbnormalSlice(
  rows: PrerunLike[],
  pairCount: number,
  total: number,
  l1Labels: string[],
): AbnormalSlice {
  const abnormalCount = rows.filter((row) => row.status === '异常').length
  const labels = l1Labels.filter((item) => item.trim()).slice(0, L1_LABEL_LIMIT)
  return {
    pairCount,
    total,
    abnormalCount,
    l1Labels: labels,
    hasDetail: pairCount > 0 || total > 0 || abnormalCount > 0 || labels.length > 0,
  }
}

export function mapPoisonSlice(rows: PrerunLike[]): PoisonSlice {
  let strategyCount = 0
  let bypassCount = 0
  const counts = new Map<string, number>()
  for (const row of rows) {
    const strategies = row.strategy_chain?.filter((item) => item.trim()) ?? []
    const bypassed = row.bypassed_moderators?.filter((item) => item.trim()) ?? []
    if (strategies.length) strategyCount += 1
    if (bypassed.length) bypassCount += 1
    for (const item of strategies) counts.set(item, (counts.get(item) || 0) + 1)
  }
  const topStrategies = [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, STRATEGY_TAG_LIMIT)
    .map(([name]) => name)
  return {
    strategyCount,
    bypassCount,
    topStrategies,
    hasDetail: strategyCount > 0 || bypassCount > 0 || topStrategies.length > 0,
  }
}

export function mapLineageSlice(
  summary: { totalNodes?: number; totalEdges?: number; riskyNodes?: number } | null | undefined,
  reportSummary = '',
): LineageSlice {
  const totalNodes = summary?.totalNodes ?? 0
  const totalEdges = summary?.totalEdges ?? 0
  const riskyNodes = summary?.riskyNodes ?? 0
  const report = reportSummary.trim()
  return {
    totalNodes,
    totalEdges,
    riskyNodes,
    reportSummary: truncateText(report, 160),
    hasDetail: totalNodes > 0 || totalEdges > 0 || riskyNodes > 0 || Boolean(report),
  }
}

export function isLowValueRow(row: AttributionLike): boolean {
  return row.quality_level === 'low' || row.status === '待提升'
}

export function isRiskRow(row: { status?: string }): boolean {
  return row.status === '异常' || row.status === '高风险' || row.status === '中风险'
}

export function pickEvidenceIndex<T>(rows: T[], predicate: (row: T) => boolean): number {
  const index = rows.findIndex(predicate)
  if (index >= 0) return index
  return rows.length ? 0 : -1
}

export function nextIndex(length: number, current: number): number {
  if (length <= 0) return -1
  return (current + 1) % length
}

function asId(value: string | undefined, fallback: string): string {
  return value?.trim() || fallback
}

export function mapValueEvidence(row: AttributionLike): InputGuardrailEvidenceView {
  return {
    id: asId(row.id, 'value'),
    track: 'value',
    snippet: row.snippet || '',
    suggestion: row.suggestion || '',
    evidenceChain: row.evidence_chain?.filter(Boolean) ?? [],
    attributionSteps: (row.attribution_steps ?? [])
      .filter((step) => step.title || step.detail)
      .map((step) => ({ title: step.title || '', detail: step.detail || '' })),
    qualityLevel: row.quality_level || row.status || '',
    dimension: row.dimension || '',
    riskL1: '',
    riskL2: '',
    strategyChain: [],
  }
}

export function mapRiskEvidenceFromAttribution(row: AttributionLike): InputGuardrailEvidenceView {
  return {
    id: asId(row.id, 'risk'),
    track: 'risk',
    snippet: row.snippet || '',
    suggestion: row.suggestion || '',
    evidenceChain: row.evidence_chain?.filter(Boolean) ?? [],
    attributionSteps: (row.attribution_steps ?? [])
      .filter((step) => step.title || step.detail)
      .map((step) => ({ title: step.title || '', detail: step.detail || '' })),
    qualityLevel: row.status || '',
    dimension: '',
    riskL1: row.risk_category_l1 || '',
    riskL2: row.risk_category_l2 || '',
    strategyChain: row.strategy_chain?.filter(Boolean) ?? [],
  }
}

export function mapRiskEvidenceFromPrerun(row: PrerunLike): InputGuardrailEvidenceView {
  return {
    id: asId(row.id, 'prerun'),
    track: 'risk',
    snippet: row.snippet || '',
    suggestion: row.suggestion || '',
    evidenceChain: [],
    attributionSteps: [],
    qualityLevel: row.status || '',
    dimension: '',
    riskL1: row.harm_category_l1 || '',
    riskL2: row.harm_category_l2 || '',
    strategyChain: row.strategy_chain?.filter(Boolean) ?? [],
  }
}

export function mapFixItems(
  rows: Array<{ snippet?: string; suggestion?: string }>,
  limit = FIX_LIST_LIMIT,
): FixItem[] {
  return rows
    .map((row) => ({
      snippet: row.snippet?.trim() || '',
      suggestion: row.suggestion?.trim() || '',
    }))
    .filter((row) => row.snippet || row.suggestion)
    .slice(0, limit)
}
