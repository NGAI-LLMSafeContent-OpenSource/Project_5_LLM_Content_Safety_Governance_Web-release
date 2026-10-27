import type { GovernanceDomain, GovernanceDomainKey, GovernanceTabNavigationKey } from '@/types'

export const GOVERNANCE_DOMAINS: readonly GovernanceDomain[] = [
  {
    key: 'input',
    label: '输入语料治理',
    heading: '从语料开始一次治理任务',
    description:
      '对照课题一价值语料的高/中/低三档回答，查看训练语料工具状态，或对课题二输入风险静态验证语料发起在线二次检测。',
    placeholder: '例如：按主题检索价值问题组并对照高中低三档回答',
    suggestions: [
      {
        id: 'input-value-tier-compare',
        title: '检索价值问题组并对照高中低三档',
        prompt: '请检索价值问题组，并打开高/中/低三档回答对照。',
        kind: 'action',
        capability: 'value_qa_search',
      },
      {
        id: 'input-risk-corpus-rescan',
        title: '输入风险语料在线二次检测',
        prompt: '对课题二输入风险静态验证语料（400条）发起在线二次检测（最多 5 条）',
        kind: 'action',
        capability: 'risk_corpus_rescan',
      },
      {
        id: 'input-topic1-corpus-tools',
        title: '查看课题一训练语料工具状态',
        prompt: '查看课题一稀缺度评估、数据去噪、数据去害和数据选择工具的接入状态。',
        kind: 'action',
        capability: 'topic1_corpus_tool_catalog',
      },
      {
        id: 'input-cbrne-overview',
        title: '查看 CBRNE 异常数据资产总览',
        prompt: '查看课题二 CBRNE 异常数据资产的规模与分布',
        kind: 'action',
        capability: 'cbrne_dataset_overview',
      },
    ],
  },
  {
    key: 'output',
    label: '输出内容治理',
    heading: '从预跑结果开始审阅',
    description: '对文化与风险系统预跑记录发起审阅任务；浏览目录本身不会创建治理任务。',
    placeholder: '例如：帮我审阅一条文化多样性系统预跑记录',
    suggestions: [
      {
        id: 'output-risk-system-record-search',
        title: '查看最近的风险安全评测系统预跑记录',
        prompt: '查看最近的风险安全评测系统预跑记录',
        kind: 'action',
        capability: 'risk_system_record_search',
      },
      {
        id: 'output-cultural-system-record-search',
        title: '查看最近的文化多样性系统预跑记录',
        prompt: '查看最近的文化多样性系统预跑记录',
        kind: 'action',
        capability: 'cultural_system_record_search',
      },
    ],
  },
]

export function getGovernanceDomain(key: string): GovernanceDomain {
  return GOVERNANCE_DOMAINS.find((domain) => domain.key === key) ?? GOVERNANCE_DOMAINS[0]
}

export function nextGovernanceDomain(
  current: GovernanceDomainKey,
  key: GovernanceTabNavigationKey,
): GovernanceDomainKey {
  if (key === 'Home') return GOVERNANCE_DOMAINS[0].key
  if (key === 'End') return GOVERNANCE_DOMAINS[GOVERNANCE_DOMAINS.length - 1].key

  const currentIndex = GOVERNANCE_DOMAINS.findIndex((domain) => domain.key === current)
  const delta = key === 'ArrowRight' ? 1 : key === 'ArrowLeft' ? -1 : 0
  const nextIndex = (currentIndex + delta + GOVERNANCE_DOMAINS.length) % GOVERNANCE_DOMAINS.length
  return GOVERNANCE_DOMAINS[nextIndex].key
}

export function isGovernanceTabNavigationKey(key: string): key is GovernanceTabNavigationKey {
  return ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)
}

export interface GovernanceSuggestionBinding {
  capability?: string
  skillKey?: string
  parameters?: Record<string, unknown>
}

/**
 * The trusted control-plane binding a recommendation carries, or `undefined`
 * when it is not bound to a capability/skill. Callers pass this verbatim on the
 * turn so the server plans for the bound target instead of reading the prompt.
 */
export function governanceSuggestionBinding(suggestion: {
  capability?: string | null
  skill_key?: string | null
  parameters?: Record<string, unknown> | null
}): GovernanceSuggestionBinding | undefined {
  const capability = suggestion.capability?.trim()
  const skillKey = suggestion.skill_key?.trim()
  const parameters = suggestion.parameters
  if (!capability && !skillKey) return undefined
  return {
    ...(capability ? { capability } : {}),
    ...(capability && parameters && Object.keys(parameters).length > 0 ? { parameters } : {}),
    ...(skillKey ? { skillKey } : {}),
  }
}

export function isExecutableRecommend(suggestion: {
  kind?: string
  capability?: string | null
  skill_key?: string | null
  prompt?: string
}): boolean {
  if (suggestion.kind === 'explanation') return false
  return governanceSuggestionBinding(suggestion) !== undefined && Boolean(suggestion.prompt?.trim())
}
