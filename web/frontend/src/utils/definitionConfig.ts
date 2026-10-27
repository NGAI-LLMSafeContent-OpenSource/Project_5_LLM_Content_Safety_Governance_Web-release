import type { TabKey } from '@/types'
import { sharedDefinitionAgents, sharedDefinitionTimeline } from '@/utils/definitionSharedConfig'

export type DefinitionStepKey = 1 | 2 | 3
export type DefinitionStandardStatus = 'pending' | 'adopted' | 'ignored' | 'edited'

export interface DefinitionStandard {
  id: string
  candidateId?: number
  definitionType: TabKey
  name: string
  definition: string
  source?: string
  formula?: string
  rationale?: string
  evidenceText?: string
  category?: string
  level1: string
  level2: string
  level3: string
  tag: string
  defaultEnabled: boolean
  status: DefinitionStandardStatus
}

export interface DefinitionAgentConfig {
  id: string
  name: string
  avatar: string
  desc: string
}

export interface DefinitionTimelineItem {
  id: string
  time: string
  title: string
  desc: string
  status?: string
}

export interface DefinitionSummaryItem {
  id: string
  label: string
  value: string | number
}

export interface DefinitionTabConfig {
  key: TabKey
  label: string
  icon: string
  policyTitle: string
  summaryTitle: string
  rootTitle: string
  defaultPolicy: string
  defaultSample: string
  categoryOptions: string[]
  level1Options: string[]
  level2Options: string[]
  agents: DefinitionAgentConfig[]
  timeline: DefinitionTimelineItem[]
  summary: DefinitionSummaryItem[]
  standards: DefinitionStandard[]
}

export interface DefinitionBranch {
  id: string
  title: string
  childGroups: DefinitionBranchGroup[]
}

export interface DefinitionBranchGroup {
  id: string
  label: string
  leafNodes: DefinitionBranchNode[]
}

export interface DefinitionBranchNode {
  id: string
  label: string
  status: DefinitionStandardStatus
  children: DefinitionBranchNode[]
  kind?: 'predefined' | 'mined'
  definition?: string
  tag?: string
  level1?: string
  level2?: string
  source?: string
  formula?: string
  rationale?: string
  evidenceText?: string
}

export const inputValueStandards: DefinitionStandard[] = [
  // 文化忠实度
  {
    id: 'input-value-cultural-entity-authenticity',
    definitionType: 'input-value',
    name: '文化实体真实性',
    definition: '评估训练语料中人物、地名、器物等文化实体是否真实可核验。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '文化元素符合度',
    level3: '文化实体真实性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-cultural-symbol-accuracy',
    definitionType: 'input-value',
    name: '文化符号准确性',
    definition: '评估文化符号、图腾、节庆意象等表达是否准确、完整。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '文化元素符合度',
    level3: '文化符号准确性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-corpus-origin',
    definitionType: 'input-value',
    name: '语料本源性',
    definition: '评估语料是否来源于对应文化语境，避免移花接木或失真转述。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '文化元素符合度',
    level3: '语料本源性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-etiquette-norm',
    definitionType: 'input-value',
    name: '行为礼仪规范性',
    definition: '评估样本对礼仪、称呼与交往规范的表达是否符合对应文化习惯。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '行为与社会规范符合度',
    level3: '行为礼仪规范性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-ethical-relation',
    definitionType: 'input-value',
    name: '伦理关系合理性',
    definition: '评估家庭、社群等伦理关系叙述是否合理，避免错位或冒犯。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '行为与社会规范符合度',
    level3: '伦理关系合理性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-folk-taboo',
    definitionType: 'input-value',
    name: '民俗禁忌规避度',
    definition: '评估语料是否规避民俗禁忌与不当戏谑表达。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '行为与社会规范符合度',
    level3: '民俗禁忌规避度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-mainstream-value',
    definitionType: 'input-value',
    name: '主流价值一致性',
    definition: '评估样本是否与对应文化主流价值叙事保持一致。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '价值观忠实度',
    level3: '主流价值一致性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-historical-objectivity',
    definitionType: 'input-value',
    name: '历史客观性',
    definition: '评估历史叙述是否客观可核，避免歪曲与虚构。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '价值观忠实度',
    level3: '历史客观性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-civilization-logic',
    definitionType: 'input-value',
    name: '文明逻辑性',
    definition: '评估文明演进、制度与观念表达是否自洽、合乎逻辑。',
    category: '文化忠实度',
    level1: '文化忠实度',
    level2: '价值观忠实度',
    level3: '文明逻辑性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  // 伦理合规度（原“伦理敏感度”）
  {
    id: 'input-value-group-bias-suppression',
    definitionType: 'input-value',
    name: '群体偏见抑制度',
    definition: '评估语料对群体刻板印象与偏见表达的抑制程度。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '公平合规度',
    level3: '群体偏见抑制度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-equal-opportunity',
    definitionType: 'input-value',
    name: '机会均等表达度',
    definition: '评估不同群体在机会、能力与贡献方面的表达是否均等。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '公平合规度',
    level3: '机会均等表达度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-vulnerable-care',
    definitionType: 'input-value',
    name: '弱势群体关怀度',
    definition: '评估对弱势群体的表述是否体现尊重与必要关怀。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '公平合规度',
    level3: '弱势群体关怀度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-negative-guidance-safety',
    definitionType: 'input-value',
    name: '负面引导安全性',
    definition: '评估语料是否避免不当负面引导与危险示范。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '伤害风险合规度',
    level3: '负面引导安全性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-public-interest',
    definitionType: 'input-value',
    name: '公共利益保护度',
    definition: '评估表达是否维护公共利益与公共秩序底线。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '伤害风险合规度',
    level3: '公共利益保护度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-violence-filter',
    definitionType: 'input-value',
    name: '暴力极端过滤度',
    definition: '评估对暴力、极端内容的过滤与边界提示是否充分。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '伤害风险合规度',
    level3: '暴力极端过滤度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-pii-desensitize',
    definitionType: 'input-value',
    name: '个人信息脱敏度',
    definition: '评估个人身份信息是否经过必要脱敏处理。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '隐私合规度',
    level3: '个人信息脱敏度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-sensitive-info-protect',
    definitionType: 'input-value',
    name: '敏感信息保护度',
    definition: '评估敏感信息（健康、信仰、行踪等）保护是否到位。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '隐私合规度',
    level3: '敏感信息保护度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-overcollection-control',
    definitionType: 'input-value',
    name: '过度采集控制度',
    definition: '评估是否避免非必要的个人信息过度采集与暴露。',
    category: '伦理合规度',
    level1: '伦理合规度',
    level2: '隐私合规度',
    level3: '过度采集控制度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  // 语义稀缺度
  {
    id: 'input-value-longtail-coverage',
    definitionType: 'input-value',
    name: '长尾知识覆盖',
    definition: '评估低频但有价值的长尾知识在语料中的覆盖程度。',
    category: '语义稀缺度',
    level1: '语义稀缺度',
    level2: '基于数据分布的语义稀缺度',
    level3: '长尾知识覆盖',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-professional-depth',
    definitionType: 'input-value',
    name: '专业逻辑深度',
    definition: '评估专业领域表达是否具备足够推理与逻辑深度。',
    category: '语义稀缺度',
    level1: '语义稀缺度',
    level2: '基于数据分布的语义稀缺度',
    level3: '专业逻辑深度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-model-cognition-gap',
    definitionType: 'input-value',
    name: '模型认知缺口度',
    definition: '结合参考模型识别当前语料相对模型能力的认知缺口。',
    category: '语义稀缺度',
    level1: '语义稀缺度',
    level2: '基于参考模型的语义稀缺度',
    level3: '模型认知缺口度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-knowledge-completion',
    definitionType: 'input-value',
    name: '知识补全贡献度',
    definition: '评估样本对知识补全与覆盖扩展的贡献程度。',
    category: '语义稀缺度',
    level1: '语义稀缺度',
    level2: '基于参考模型的语义稀缺度',
    level3: '知识补全贡献度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-capability-gain',
    definitionType: 'input-value',
    name: '能力增益度',
    definition: '评估样本对模型能力增益的潜在贡献。',
    category: '语义稀缺度',
    level1: '语义稀缺度',
    level2: '基于参考模型的语义稀缺度',
    level3: '能力增益度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  // 任务关联度
  {
    id: 'input-value-instruction-fit',
    definitionType: 'input-value',
    name: '指令适配度',
    definition: '评估语料指令形态与目标训练任务的适配程度。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '指令形态适配度',
    level3: '指令适配度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-format-norm',
    definitionType: 'input-value',
    name: '格式规范性',
    definition: '评估问答/指令格式是否规范、稳定、可解析。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '指令形态适配度',
    level3: '格式规范性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-constraint-clarity',
    definitionType: 'input-value',
    name: '约束明确性',
    definition: '评估任务约束、输出边界是否清晰可执行。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '指令形态适配度',
    level3: '约束明确性',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-domain-knowledge-match',
    definitionType: 'input-value',
    name: '行业知识匹配度',
    definition: '评估语料与目标行业知识体系的匹配程度。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '语义匹配度',
    level3: '行业知识匹配度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-semantic-relation-coverage',
    definitionType: 'input-value',
    name: '语义关系覆盖度',
    definition: '评估问题、证据与答案之间语义关系的覆盖完整性。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '语义匹配度',
    level3: '语义关系覆盖度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-e2e-task-gain',
    definitionType: 'input-value',
    name: '端到端任务增益',
    definition: '评估样本对端到端任务表现提升的贡献潜力。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '任务性能提升度',
    level3: '端到端任务增益',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-value-error-suppression',
    definitionType: 'input-value',
    name: '错误抑制度',
    definition: '评估样本对常见错误模式的抑制与纠偏作用。',
    category: '任务关联度',
    level1: '任务关联度',
    level2: '任务性能提升度',
    level3: '错误抑制度',
    tag: '预定指标',
    defaultEnabled: true,
    status: 'adopted',
  },
]

export const inputRiskStandards: DefinitionStandard[] = [
  {
    id: 'input-risk-cultural-bias',
    definitionType: 'input-risk',
    name: '文化偏见风险',
    definition: '识别训练语料中可能强化刻板印象或单一叙事的表达。',
    level1: '数据偏见',
    level2: '样本选择偏见',
    level3: '文化偏见风险',
    tag: '高敏指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-risk-language-discrimination',
    definitionType: 'input-risk',
    name: '语言歧视风险',
    definition: '识别语料中可能包含语言歧视、贬损或不平等表达的片段。',
    level1: '文化冲突',
    level2: '语言冲突',
    level3: '语言歧视风险',
    tag: '高敏指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'input-risk-religion-conflict',
    definitionType: 'input-risk',
    name: '宗教冲突风险',
    definition: '识别宗教相关冲突、误读或冒犯性表达风险。',
    level1: '文化冲突',
    level2: '宗教冲突',
    level3: '宗教冲突风险',
    tag: '需关注',
    defaultEnabled: false,
    status: 'pending',
  },
  {
    id: 'input-risk-science-fact',
    definitionType: 'input-risk',
    name: '科学事实错误',
    definition: '识别训练语料中的科学事实错误或实验条件缺失。',
    level1: '数据质量',
    level2: '准确性',
    level3: '科学事实错误',
    tag: '需关注',
    defaultEnabled: false,
    status: 'pending',
  },
]

const outputRiskStandards: DefinitionStandard[] = [
  {
    id: 'output-risk-harmful-advice',
    definitionType: 'output-risk',
    name: '有害建议风险',
    definition: '识别输出内容中可能诱导危险操作或违规行为的建议。',
    level1: '安全风险',
    level2: '有害建议',
    level3: '有害建议风险',
    tag: '输出指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'output-risk-factual-hallucination',
    definitionType: 'output-risk',
    name: '事实幻觉风险',
    definition: '识别输出内容中缺乏事实依据或与上下文冲突的表述。',
    level1: '事实风险',
    level2: '事实幻觉',
    level3: '事实幻觉风险',
    tag: '输出指标',
    defaultEnabled: true,
    status: 'adopted',
  },
]

const outputCultureStandards: DefinitionStandard[] = [
  {
    id: 'output-culture-accuracy',
    definitionType: 'output-culture',
    name: '文化表达准确性',
    definition: '评估输出内容对文化背景、术语与事实的表达是否准确。',
    level1: '文化尊重',
    level2: '文化准确性',
    level3: '文化表达准确性',
    tag: '输出指标',
    defaultEnabled: true,
    status: 'adopted',
  },
  {
    id: 'output-culture-context',
    definitionType: 'output-culture',
    name: '文化背景保留度',
    definition: '评估输出是否保留必要文化背景，避免断章取义。',
    level1: '文化理解',
    level2: '背景理解',
    level3: '文化背景保留度',
    tag: '输出指标',
    defaultEnabled: true,
    status: 'adopted',
  },
]

export const definitionStepItems = [
  { key: 1, number: 1, label: '输入与多智能体挖掘' },
  { key: 2, number: 2, label: '挖掘过程展示' },
  { key: 3, number: 3, label: '指标体系浏览' },
]

export const definitionTabConfigs: Record<TabKey, DefinitionTabConfig> = {
  'input-value': {
    key: 'input-value',
    label: '输入语料（价值）',
    icon: '💎',
    policyTitle: '输入语料（价值）相关政策规范',
    summaryTitle: '价值指标挖掘结果统计',
    rootTitle: '输入语料（价值）指标体系',
    defaultPolicy: '《“十四五”文化发展规划》提出推动中华优秀传统文化创造性转化和创新性发展。',
    defaultSample: '示例：少数民族文化、民俗知识、科学教育问答等训练语料。',
    categoryOptions: Array.from(
      new Set(
        inputValueStandards
          .map((item) => item.category)
          .filter((category): category is string => Boolean(category)),
      ),
    ),
    level1Options: Array.from(new Set(inputValueStandards.map((item) => item.level1))),
    level2Options: Array.from(new Set(inputValueStandards.map((item) => item.level2))),
    agents: sharedDefinitionAgents,
    timeline: sharedDefinitionTimeline,
    summary: [
      {
        id: 'value-l1',
        label: '一级指标',
        value: new Set(inputValueStandards.map((item) => item.level1)).size,
      },
      {
        id: 'value-l2',
        label: '二级指标',
        value: new Set(inputValueStandards.map((item) => item.level2)).size,
      },
      { id: 'value-l3', label: '三级指标', value: inputValueStandards.length },
      { id: 'value-cover', label: '覆盖完整度', value: '100%' },
    ],
    standards: inputValueStandards,
  },
  'input-risk': {
    key: 'input-risk',
    label: '输入语料（风险）',
    icon: '📥',
    policyTitle: '输入语料（风险）相关政策规范',
    summaryTitle: '输入风险指标挖掘结果统计',
    rootTitle: '输入语料（风险）指标体系',
    defaultPolicy: '训练数据治理需识别样本偏差、标注偏差、文化冲突与科学事实风险。',
    defaultSample: '示例：标签分布不均衡、事实错误、文化冲突敏感表达等训练语料。',
    categoryOptions: [],
    level1Options: ['数据偏见', '数据质量', '文化冲突'],
    level2Options: ['样本选择偏见', '语言冲突', '宗教冲突', '准确性'],
    agents: sharedDefinitionAgents,
    timeline: sharedDefinitionTimeline,
    summary: [
      { id: 'risk-l1', label: '一级指标', value: 3 },
      { id: 'risk-l2', label: '二级指标', value: 4 },
      { id: 'risk-l3', label: '三级指标', value: inputRiskStandards.length },
      { id: 'risk-cover', label: '覆盖完整度', value: '91%' },
    ],
    standards: inputRiskStandards,
  },
  'output-risk': {
    key: 'output-risk',
    label: '输出内容（风险）',
    icon: '📤',
    policyTitle: '输出内容（风险）相关政策规范',
    summaryTitle: '输出风险指标挖掘结果统计',
    rootTitle: '输出内容（风险）指标体系',
    defaultPolicy:
      '《生成式人工智能服务管理暂行办法》要求提供者承担网络信息内容生产者责任，对生成内容进行安全评估，防止产生歧视、偏见、有害信息等风险内容。',
    defaultSample:
      '示例：某大模型在回答专业医学问题时，给出了看似合理但实际存在医学事实错误的建议…',
    categoryOptions: [],
    level1Options: ['安全风险', '事实风险'],
    level2Options: ['有害建议', '事实幻觉'],
    agents: sharedDefinitionAgents,
    timeline: sharedDefinitionTimeline,
    summary: [
      { id: 'output-risk-l1', label: '一级指标', value: 2 },
      { id: 'output-risk-l2', label: '二级指标', value: 2 },
      { id: 'output-risk-l3', label: '三级指标', value: outputRiskStandards.length },
      { id: 'output-risk-cover', label: '覆盖完整度', value: '90%' },
    ],
    standards: outputRiskStandards,
  },
  'output-culture': {
    key: 'output-culture',
    label: '输出内容（文化多样性）',
    icon: '🌏',
    policyTitle: '输出内容（文化多样性）相关政策规范',
    summaryTitle: '文化多样性指标挖掘结果统计',
    rootTitle: '输出内容（文化多样性）指标体系',
    defaultPolicy:
      '《关于推进实施国家文化数字化战略的意见》强调要推动文化资源数字化、网络化、智能化，保护和发展各民族文化，促进中华文化全景呈现与多样化表达。',
    defaultSample:
      '示例：某大模型在生成少数民族节日相关文本时，对该民族特有的文化符号解释出现偏差…',
    categoryOptions: [],
    level1Options: ['文化尊重', '文化理解'],
    level2Options: ['文化准确性', '背景理解'],
    agents: sharedDefinitionAgents,
    timeline: sharedDefinitionTimeline,
    summary: [
      { id: 'output-culture-l1', label: '一级指标', value: 2 },
      { id: 'output-culture-l2', label: '二级指标', value: 2 },
      { id: 'output-culture-l3', label: '三级指标', value: outputCultureStandards.length },
      { id: 'output-culture-cover', label: '覆盖完整度', value: '93%' },
    ],
    standards: outputCultureStandards,
  },
}

export const definitionTabs = Object.values(definitionTabConfigs).map(({ key, label, icon }) => ({
  key,
  label,
  icon,
}))

export const inputDefinitionStandards = [...inputValueStandards, ...inputRiskStandards]

export function buildDefinitionBranches(standards: DefinitionStandard[]): DefinitionBranch[] {
  const branchMap = new Map<string, DefinitionBranch>()

  standards.forEach((standard) => {
    const level1 = (standard.level1 || '').trim() || '未分类'
    const level2 = (standard.level2 || '').trim() || '未分组'
    const level3 = (standard.level3 || standard.name || '').trim()
    if (!level3) return

    const branchId = `${standard.definitionType}-${level1}`
    const branch =
      branchMap.get(branchId) ??
      ({
        id: branchId,
        title: level1,
        childGroups: [],
      } satisfies DefinitionBranch)

    let group = branch.childGroups.find((item) => item.label === level2)
    if (!group) {
      group = {
        id: `${branchId}-${level2}`,
        label: level2,
        leafNodes: [],
      }
      branch.childGroups.push(group)
    }

    const kind: 'predefined' | 'mined' = standard.candidateId ? 'mined' : 'predefined'
    const existing = group.leafNodes.find((item) => item.label === level3)
    if (!existing) {
      group.leafNodes.push({
        id: standard.id,
        label: level3,
        status: standard.status,
        children: [],
        kind,
        definition: standard.definition,
        tag: standard.tag,
        level1,
        level2,
        source: standard.source,
        formula: standard.formula,
        rationale: standard.rationale,
        evidenceText: standard.evidenceText,
      })
    } else if (standard.status === 'adopted' || Boolean(standard.candidateId)) {
      // 预定三级已存在时：挖掘同名项合并状态；新挖掘三级会走上方新增分支
      if (standard.status === 'adopted') existing.status = 'adopted'
      else if (existing.status === 'pending' && standard.status !== 'ignored') {
        existing.status = standard.status
      }
      if (standard.definition) existing.definition = standard.definition
      if (standard.source) existing.source = standard.source
      if (standard.formula) existing.formula = standard.formula
      if (standard.rationale) existing.rationale = standard.rationale
      if (standard.evidenceText) existing.evidenceText = standard.evidenceText
      if (standard.tag) existing.tag = standard.tag
      if (kind === 'mined' && existing.kind === 'predefined') {
        existing.tag = existing.tag || '预定+挖掘命中'
      }
    }

    branchMap.set(branchId, branch)
  })

  return Array.from(branchMap.values())
}
