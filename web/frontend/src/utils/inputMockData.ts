export interface InputAssessmentRow {
  id: string
  score: string
  status: string
  snippet: string
  suggestion: string
  source?: string
  summary?: string
  lineageNodeId?: string
  lineageNodeLabel?: string
  riskCategoryL1?: string
  riskCategoryL2?: string
  predictedL1Id?: string
  detectMethod?: string
  action?: string
  isAbnormal?: boolean
  evidenceChain?: string[]
  findings?: Array<{ keyword: string; evidence: string; riskType: string; label?: string }>
  issueSpans?: Array<{ type: string; sentence: string; span: string }>
  attributionSteps?: Array<{ title: string; detail: string }>
  note?: string
  dimension?: string
  topic?: string
  trueLabel?: string
  predictedLabel?: string
  qualityLevel?: string
  groupId?: string
  difficultyLevel?: string
  strategyChain?: string[]
}

export interface InputScienceStandard {
  id: string
  name: string
  desc: string
  tag: string
  enabled: boolean
  /** Original L2 label from corpus (before ZH mapping). */
  rawName?: string
  /** Parent L1 code when this is a Topic2 L2 tag. */
  l1Code?: string
  /** False when parent L1 is unchecked. */
  parentEnabled?: boolean
}

export interface InputLineageNode {
  id: string
  type: string
  summary: string
  url: string
  docName: string
  docId: string
  topic: string
  pipeline: string
  isRisky?: boolean
  riskLevel?: string
  riskTypes?: string[]
}

export interface InputStatItem {
  val: string
  label: string
}

/** Risk-track summary derived from Topic 2 detection results. */
export interface RiskAssessmentSummary {
  total: number
  abnormal: number
  normal: number
  highRisk: number
  l1Covered: number
  anomalyRate: number
  method: string
  methodLabel: string
  ready: boolean
}

export const emptyRiskAssessmentSummary = (): RiskAssessmentSummary => ({
  total: 0,
  abnormal: 0,
  normal: 0,
  highRisk: 0,
  l1Covered: 0,
  anomalyRate: 0,
  method: '',
  methodLabel: '',
  ready: false,
})

/** Value-track summary derived from Topic 1 assessment results. */
export interface ValueAssessmentSummary {
  total: number
  excellent: number
  good: number
  improve: number
  improveRate: number
  ready: boolean
}

export const emptyValueAssessmentSummary = (): ValueAssessmentSummary => ({
  total: 0,
  excellent: 0,
  good: 0,
  improve: 0,
  improveRate: 0,
  ready: false,
})

export type InputFixStatus = '待处理' | '需复核' | '已采纳' | '已跳过'

export interface InputFixItem {
  id: string
  title: string
  status: InputFixStatus
  original: string
  suggest: string
  recommended: string
  sampleId?: string
  evidenceChain?: string[]
  attributionSteps?: Array<{ title: string; detail: string }>
  lineageNodeLabel?: string
  contractStatus?: string
  riskCategoryL1?: string
  riskCategoryL2?: string
  predictedL1Id?: string
  detectMethod?: string
  action?: string
  note?: string
  issueSpans?: Array<{ type: string; sentence: string; span: string }>
}

export type CorrectionPreviewRange = 'all' | InputFixStatus

export function cloneInputItems<T>(items: T[]): T[] {
  return items.map((item) => ({ ...item }))
}

export const inputValueAssessmentRows: InputAssessmentRow[] = [
  {
    id: 'V-1084',
    score: '0.92',
    status: '优',
    snippet: '节日叙事完整保留了地方语境，表达尊重且知识点覆盖均衡。',
    suggestion: '保持当前表达，并继续补充地域差异样本。',
  },
  {
    id: 'V-2217',
    score: '0.74',
    status: '良',
    snippet: '传统文化样本具备内容基础，但背景语境略有压缩。',
    suggestion: '补充背景说明与传承线索，提升文化解释完整度。',
  },
  {
    id: 'V-3045',
    score: '0.48',
    status: '待提升',
    snippet: '问答中科学性与文化性表达交叉，价值维度不够清晰。',
    suggestion: '拆分语义角色并补齐价值维度标签。',
  },
  {
    id: 'V-4092',
    score: '0.36',
    status: '待提升',
    snippet: '地域知识覆盖偏窄，部分样本仅体现单一来源观点。',
    suggestion: '补齐多来源样本，并增加地域对照说明。',
  },
]

export const inputRiskAssessmentRows: InputAssessmentRow[] = [
  {
    id: 'R-011',
    score: '1.00',
    status: '异常',
    isAbnormal: true,
    predictedL1Id: 'L1-3',
    riskCategoryL1: 'L1-3 Implicit Bias Contamination',
    snippet: '原文包含明显文化刻板印象表述。',
    suggestion: '替换为中性描述并保留事实依据。',
  },
  {
    id: 'R-024',
    score: '1.00',
    status: '异常',
    isAbnormal: true,
    predictedL1Id: 'L1-4',
    riskCategoryL1: 'L1-4 Factual Misleading and Hallucination Contamination',
    snippet: '部分样本存在事实表述与语境不一致。',
    suggestion: '补充来源与上下文说明，降低歧义。',
  },
  {
    id: 'R-039',
    score: '0.00',
    status: '安全',
    isAbnormal: false,
    snippet: '当前片段未检出异常，仍建议抽检标签一致性。',
    suggestion: '保持现有内容并纳入抽检。',
  },
  {
    id: 'R-052',
    score: '1.00',
    status: '异常',
    isAbnormal: true,
    predictedL1Id: 'L1-2',
    riskCategoryL1: 'L1-2 Explicit Harmful Injection',
    snippet: '科学实验描述中存在变量定义不清晰问题。',
    suggestion: '补充变量定义和实验条件，减少误读。',
  },
]

export const inputValueScienceStandards: InputScienceStandard[] = [
  {
    id: 'value-science-data-scarcity',
    name: '科学数据稀缺性',
    desc: '识别科学语料中高价值但低频的数据类型。',
    tag: '科研数据',
    enabled: true,
  },
  {
    id: 'value-science-task-adaptability',
    name: '科学任务适配性',
    desc: '评估语料对科学任务流程与推理结构的适配程度。',
    tag: '任务适配',
    enabled: true,
  },
  {
    id: 'value-science-ethics-sensitivity',
    name: '科学伦理敏感度',
    desc: '评估科学语料在伦理、合规与安全边界上的敏感性。',
    tag: '伦理合规',
    enabled: true,
  },
]

export const inputRiskScienceStandards: InputScienceStandard[] = [
  {
    id: 'risk-science-factual-error',
    name: '科学事实错误',
    desc: '识别科学知识事实性错误。',
    tag: '高敏',
    enabled: true,
  },
  {
    id: 'risk-science-data-specification',
    name: '数据规范性风险',
    desc: '识别数据结构与标注规范偏差。',
    tag: '需关注',
    enabled: true,
  },
]

export const inputLineageNodes: InputLineageNode[] = [
  {
    id: 'META-ROOT-0001',
    type: 'Meta 聚合根',
    summary:
      '多来源文档的元数据聚合根，负责挂载来源可信度、版权属性与采集批次信息。下游连接 Chunk / Question / Answer。',
    url: 'https://example.org/internal/folk-corpus/v3/meta#META-ROOT-0001',
    docName: '输入语料总索引（内部）',
    docId: 'DOC-META-ROOT-0001',
    topic: '多源聚合 / 治理元信息',
    pipeline: '血缘构建 / ingest-normalize-v2.3 -> entity-link -> graph-merge',
  },
  {
    id: 'CHUNK-04218',
    type: 'Chunk',
    summary: '源自民俗问答语料的文本切片，关联 Meta 聚合根，并向下连接 Question 与 Cleaned Chunk。',
    url: 'https://example.org/internal/folk-corpus/v3/chunks#CHUNK-04218',
    docName: '西南地区节日民俗汇编（内部稿）',
    docId: 'DOC-FOLK-2024-018',
    topic: '节日习俗 / 文化多样性',
    pipeline: '血缘构建 / ingest-normalize-v2.3 -> entity-link -> graph-merge',
  },
]

export const inputRadarScores: Record<string, number> = {
  文化元素符合度: 0.86,
  '行为/社会规范符合度': 0.78,
  价值观忠实度: 0.83,
  公平性敏感度: 0.71,
  伤害风险敏感度: 0.69,
  隐私敏感度: 0.74,
  科学真实性: 0.8,
  基于数据分布的语义稀缺度: 0.66,
  基于参考模型的语义稀缺度: 0.63,
  指令形态适配度: 0.77,
  语义匹配度: 0.82,
  任务性能提升度: 0.75,
  文化偏见风险: 0.72,
  语言歧视风险: 0.68,
  宗教冲突风险: 0.59,
  科学事实错误: 0.63,
  数据规范性风险: 0.66,
}

export const inputValueStats: InputStatItem[] = [
  { val: '12,480', label: '总数据条数' },
  { val: '1,026', label: '待提升条数' },
  { val: '2,384', label: '良档条数' },
  { val: '9,070', label: '优档条数' },
]

export const inputRiskStats: InputStatItem[] = [
  { val: '—', label: '异常率' },
  { val: '0', label: '检测条数' },
  { val: '0', label: '安全样本' },
  { val: '0', label: '异常条数' },
]

export const inputValueFixes: InputFixItem[] = [
  {
    id: 'value-fix-expand-samples',
    title: '价值样本扩充',
    status: '待处理',
    original: '文化日常语境样本不足。',
    suggest: '补充教育、生活场景样本，并增加跨地区表达对照。',
    recommended: '补充教育、生活场景样本，并增加跨地区表达对照。',
  },
  {
    id: 'value-fix-cultural-context',
    title: '文化语境补全',
    status: '需复核',
    original: '节日类样本缺少历史来源和地域差异说明。',
    suggest: '增加节日来源、传承地区与现代实践差异字段。',
    recommended: '增加节日来源、传承地区与现代实践差异字段。',
  },
  {
    id: 'value-fix-label-calibration',
    title: '价值标签校准',
    status: '待处理',
    original: '部分样本价值标签只标注一级维度，缺少二级维度证据。',
    suggest: '补齐文化忠实度、价值观忠实度等二级标签证据。',
    recommended: '补齐文化忠实度、价值观忠实度等二级标签证据。',
  },
]

export const inputRiskFixes: InputFixItem[] = [
  {
    id: 'risk-fix-label-standard',
    title: '标注规范统一',
    status: '需复核',
    original: '风险标注口径不一致。',
    suggest: '统一阈值并回标，补充示例边界集。',
    recommended: '统一阈值并回标，补充示例边界集。',
  },
  {
    id: 'risk-fix-high-risk-review',
    title: '高风险样本复核',
    status: '待处理',
    original: '部分高风险样本缺少人工确认记录。',
    suggest: '进入人工复核队列，并补充复核人、复核时间和处理结果。',
    recommended: '进入人工复核队列，并补充复核人、复核时间和处理结果。',
  },
  {
    id: 'risk-fix-sensitive-boundary',
    title: '敏感词边界修正',
    status: '待处理',
    original: '敏感词命中规则对中性引用片段误伤较多。',
    suggest: '增加上下文窗口判断，区分引用、解释和攻击性表达。',
    recommended: '增加上下文窗口判断，区分引用、解释和攻击性表达。',
  },
]
