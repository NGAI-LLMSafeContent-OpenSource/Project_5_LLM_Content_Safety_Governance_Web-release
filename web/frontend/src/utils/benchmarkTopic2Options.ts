import type { Topic2OptionsResponse, Topic2SeedbankStatsResponse } from '@/types'

export interface Topic2SelectOption {
  value: string
  label: string
  count?: number
  disabled?: boolean
  tags?: string[]
}

export interface Topic2ModeratorGroup {
  key: string
  label: string
  options: Topic2SelectOption[]
}

const DEFAULT_L1 = 'L1-2 Explicit Harmful Injection'

const RULE_MODERATORS = new Set(['keyword', 'keyword_strict', 'keyword_permissive', 'random'])
const DEEPSEEK_MODERATORS = new Set(['deepseek', 'DeepSeek-V3.2'])
const GUARD_MARKERS = [
  'guard',
  'qwen3guard',
  'llamaguard',
  'wildguard',
  'granite-guardian',
  'shieldgemma',
]

const DEFAULT_AGENT_MODELS: Topic2SelectOption[] = [
  {
    value: 'claude-sonnet-4-6',
    label: 'claude-sonnet-4-6',
    tags: ['上游 Agent ID', '实际 provider 由课题二路由'],
  },
  {
    value: 'claude-opus-4',
    label: 'claude-opus-4',
    tags: ['上游 Agent ID', '实际 provider 由课题二路由'],
  },
  {
    value: 'claude-3-5-sonnet-20241022',
    label: 'claude-3-5-sonnet',
    tags: ['上游 Agent ID', '实际 provider 由课题二路由'],
  },
]

export function normalizeTopic2Languages(options: Topic2OptionsResponse | null): string[] {
  const languages = Array.isArray(options?.languages) ? options.languages : []
  const normalized = languages.filter((item): item is string => typeof item === 'string')
  return normalized.length > 0 ? normalized : ['zh', 'en', 'zh+en']
}

export function normalizeTopic2L1Options(
  stats: Topic2SeedbankStatsResponse | null,
): Topic2SelectOption[] {
  const entries = normalizeStatEntries(stats?.by_l1)
  if (!entries.some((item) => item.value === DEFAULT_L1)) {
    entries.unshift({
      value: DEFAULT_L1,
      label: DEFAULT_L1,
    })
  }
  return entries
}

export function normalizeTopic2L2Options(
  stats: Topic2SeedbankStatsResponse | null,
): Topic2SelectOption[] {
  return normalizeStatEntries(stats?.by_l2)
}

export function normalizeTopic2ModeratorGroups(
  options: Topic2OptionsResponse | null,
): Topic2ModeratorGroup[] {
  const rawModerators = Array.isArray(options?.moderators) ? options.moderators : ['keyword']
  const moderators = uniqueByValue(rawModerators.map(normalizeNamedOption))

  const groups: Topic2ModeratorGroup[] = [
    { key: 'rule', label: '无需 Key / 本地规则', options: [] },
    { key: 'deepseek', label: 'DeepSeek Key 可用时', options: [] },
    { key: 'dmx', label: 'DMX/API 可用时', options: [] },
    { key: 'guard', label: '本地 vLLM Guard', options: [] },
  ]

  for (const moderator of moderators) {
    const group = groupForModerator(moderator.value)
    const tags = tagsForModeratorGroup(group)
    groups.find((item) => item.key === group)?.options.push({ ...moderator, tags })
  }

  if (!groups[0].options.some((item) => item.value === 'keyword')) {
    groups[0].options.unshift({
      value: 'keyword',
      label: 'keyword',
      tags: tagsForModeratorGroup('rule'),
    })
  }

  return groups.filter((group) => group.options.length > 0)
}

export function normalizeTopic2AgentModels(
  options: Topic2OptionsResponse | null,
): Topic2SelectOption[] {
  const rawAgentModels = Array.isArray(options?.agent_models) ? options.agent_models : []
  const upstreamModels = rawAgentModels.map(normalizeNamedOption)
  return uniqueByValue([...DEFAULT_AGENT_MODELS, ...upstreamModels])
}

function normalizeStatEntries(value: unknown): Topic2SelectOption[] {
  if (Array.isArray(value)) {
    return value.map(normalizeCountedOption).filter(isNonEmptyOption)
  }

  if (isRecord(value)) {
    return Object.entries(value).map(([key, count]) => ({
      value: key,
      label: key,
      count: typeof count === 'number' ? count : undefined,
    }))
  }

  return []
}

function normalizeCountedOption(value: unknown): Topic2SelectOption {
  if (typeof value === 'string') {
    return { value, label: value }
  }

  if (!isRecord(value)) {
    return { value: '', label: '' }
  }

  const name = firstString(value, ['name', 'label', 'value', 'l1', 'l2', 'category'])
  const id = firstString(value, ['value', 'id', 'name', 'label'])
  const count = firstNumber(value, ['count', 'total', 'sample_count', 'samples'])
  return {
    value: id || name,
    label: name || id,
    count,
  }
}

function normalizeNamedOption(value: unknown): Topic2SelectOption {
  if (typeof value === 'string') {
    return { value, label: value }
  }

  if (!isRecord(value)) {
    return { value: '', label: '' }
  }

  const optionValue = firstString(value, ['value', 'id', 'name', 'label'])
  const label = firstString(value, ['label', 'name', 'value', 'id'])
  const disabled = value.disabled === true
  return {
    value: optionValue,
    label: label || optionValue,
    disabled,
  }
}

function groupForModerator(value: string): string {
  if (RULE_MODERATORS.has(value)) {
    return 'rule'
  }
  if (DEEPSEEK_MODERATORS.has(value)) {
    return 'deepseek'
  }
  const lowerValue = value.toLowerCase()
  if (GUARD_MARKERS.some((marker) => lowerValue.includes(marker))) {
    return 'guard'
  }
  return 'dmx'
}

function tagsForModeratorGroup(group: string): string[] {
  if (group === 'rule') {
    return ['无需 Key', 'baseline']
  }
  if (group === 'deepseek') {
    return ['需 DEEPSEEK_API_KEY', '待验证']
  }
  if (group === 'guard') {
    return ['需本地 vLLM', '未确认']
  }
  return ['需 DMX/API Key', '未确认']
}

function firstString(value: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const item = value[key]
    if (typeof item === 'string' && item.trim()) {
      return item
    }
  }
  return ''
}

function firstNumber(value: Record<string, unknown>, keys: string[]): number | undefined {
  for (const key of keys) {
    const item = value[key]
    if (typeof item === 'number') {
      return item
    }
  }
  return undefined
}

function uniqueByValue(options: Topic2SelectOption[]): Topic2SelectOption[] {
  const seen = new Set<string>()
  const result: Topic2SelectOption[] = []
  for (const option of options) {
    if (!isNonEmptyOption(option) || seen.has(option.value)) {
      continue
    }
    seen.add(option.value)
    result.push(option)
  }
  return result
}

function isNonEmptyOption(option: Topic2SelectOption): boolean {
  return Boolean(option.value && option.label)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
