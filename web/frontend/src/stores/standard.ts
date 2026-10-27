import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { TabKey } from '@/types'
import {
  inputRiskStandards,
  inputValueStandards,
  type DefinitionStandard,
  type DefinitionStandardStatus,
} from '@/utils/definitionConfig'

export interface StandardItem {
  id: string
  definitionType: TabKey
  name: string
  desc: string
  tag: string
  enabled: boolean
  status: DefinitionStandardStatus
  category?: string
  level1: string
  level2: string
  level3: string
}

export interface RadarIndicatorItem {
  id: string
  /** Score key used by radarScores (raw primary / L1 code). */
  name: string
  /** Optional display label on radar chips / axes. */
  label?: string
  enabled: boolean
}

const TOPIC2_L1_AXES = [
  { code: 'L1-1', fullZh: 'CBRNE（化生放核爆）' },
  { code: 'L1-2', fullZh: '显式有害注入' },
  { code: 'L1-3', fullZh: '隐性偏见污染' },
  { code: 'L1-4', fullZh: '事实误导与幻觉污染' },
] as const

/** value_qa 一级维度展示名（兼容旧口径别名） */
const VALUE_QA_STANDARD_TAG = '课题一 value_qa'
const valueLevel1DisplayNameMap: Record<string, string> = {
  伦理敏感度: '伦理合规度',
  文化忠诚度: '文化忠实度',
  伦理合规度: '伦理合规度',
  文化忠实度: '文化忠实度',
}

export function formatValueQaPrimaryDimension(raw: string): string {
  const text = String(raw || '').trim()
  if (!text) return ''
  return valueLevel1DisplayNameMap[text] ?? text
}

function toStandardItem(item: DefinitionStandard): StandardItem {
  return {
    id: item.id,
    definitionType: item.definitionType,
    name: item.name,
    desc: item.definition,
    tag: item.tag,
    enabled: item.defaultEnabled && item.status !== 'ignored',
    status: item.status,
    category: item.category,
    level1: item.level1,
    level2: item.level2,
    level3: item.level3,
  }
}

function toRadarItems(items: DefinitionStandard[]): RadarIndicatorItem[] {
  return items.map((item) => ({
    id: item.id,
    name: item.name,
    enabled: item.defaultEnabled && item.status !== 'ignored',
  }))
}

function toLevel1StandardItems(items: DefinitionStandard[]): StandardItem[] {
  const grouped = new Map<string, StandardItem>()
  items.forEach((item) => {
    const existing = grouped.get(item.level1)
    if (existing) {
      existing.enabled = existing.enabled || (item.defaultEnabled && item.status !== 'ignored')
      if (existing.status !== 'adopted' && item.status === 'adopted') existing.status = 'adopted'
      return
    }

    grouped.set(item.level1, {
      id: `input-value-level1-${item.level1}`,
      definitionType: item.definitionType,
      name: item.level1,
      desc: `${item.category ?? '输入语料'} / ${item.level1}`,
      tag: '多民族数据集',
      enabled: item.defaultEnabled && item.status !== 'ignored',
      status: item.status,
      category: item.category,
      level1: item.level1,
      level2: '',
      level3: '',
    })
  })
  return Array.from(grouped.values())
}

export const useStandardStore = defineStore('standard', () => {
  const valueStandards = ref<StandardItem[]>(inputValueStandards.map(toStandardItem))
  const riskStandards = ref<StandardItem[]>(inputRiskStandards.map(toStandardItem))
  const valueStandardGroups = ref<StandardItem[]>(toLevel1StandardItems(inputValueStandards))
  const valueRadarIndicators = ref<RadarIndicatorItem[]>(toRadarItems(inputValueStandards))
  const riskRadarIndicators = ref<RadarIndicatorItem[]>(toRadarItems(inputRiskStandards))

  const selectedValueRadarIndicators = computed(() =>
    valueRadarIndicators.value.filter((item) => item.enabled).map((item) => item.name),
  )
  const selectedRiskRadarIndicators = computed(() =>
    riskRadarIndicators.value.filter((item) => item.enabled).map((item) => item.name),
  )

  function setDefinitionStandardStatus(
    tab: Extract<TabKey, 'input-value' | 'input-risk'>,
    id: string,
    status: DefinitionStandardStatus,
  ) {
    const standards = tab === 'input-value' ? valueStandards.value : riskStandards.value
    const radarIndicators =
      tab === 'input-value' ? valueRadarIndicators.value : riskRadarIndicators.value
    const item = standards.find((standard) => standard.id === id)
    if (!item) return

    item.status = status
    item.enabled = status !== 'ignored'

    const radarItem = radarIndicators.find((indicator) => indicator.id === item.id)
    if (radarItem) radarItem.enabled = item.enabled
    if (tab === 'input-value') syncValueStandardGroup(item.level1)
  }

  function syncDefinitionStandards(
    tab: Extract<TabKey, 'input-value' | 'input-risk'>,
    items: DefinitionStandard[],
  ) {
    const standards = tab === 'input-value' ? valueStandards.value : riskStandards.value
    const radarIndicators =
      tab === 'input-value' ? valueRadarIndicators.value : riskRadarIndicators.value

    items.forEach((item) => {
      const next = toStandardItem(item)
      const existing = standards.find((standard) => standard.id === next.id)
      if (existing) {
        Object.assign(existing, next)
      } else {
        standards.push(next)
      }

      const radarNext = {
        id: item.id,
        name: item.name,
        enabled: item.defaultEnabled && item.status !== 'ignored',
      }
      const radarExisting = radarIndicators.find((indicator) => indicator.id === radarNext.id)
      if (radarExisting) {
        Object.assign(radarExisting, radarNext)
      } else {
        radarIndicators.push(radarNext)
      }
    })

    // 输入模块价值轨筛选已接入 value_qa 时，勿用定义模块指标覆盖筛选分组
    if (tab === 'input-value') {
      const usingValueQa = valueStandardGroups.value.some(
        (item) => item.tag === VALUE_QA_STANDARD_TAG,
      )
      if (!usingValueQa) {
        valueStandardGroups.value = toLevel1StandardItems(
          valueStandards.value.map((item) => ({
            id: item.id,
            definitionType: item.definitionType,
            name: item.name,
            definition: item.desc,
            category: item.category,
            level1: item.level1,
            level2: item.level2,
            level3: item.level3,
            tag: item.tag,
            defaultEnabled: item.enabled,
            status: item.status,
          })),
        )
      }
    }
  }

  function toggleStandardEnabled(tab: Extract<TabKey, 'input-value' | 'input-risk'>, id: string) {
    const standards = tab === 'input-value' ? valueStandards.value : riskStandards.value
    const radarIndicators =
      tab === 'input-value' ? valueRadarIndicators.value : riskRadarIndicators.value
    const item = standards.find((standard) => standard.id === id)
    if (!item) return

    item.enabled = !item.enabled
    item.status = item.enabled ? 'adopted' : 'ignored'

    const radarItem = radarIndicators.find((indicator) => indicator.id === item.id)
    if (radarItem) radarItem.enabled = item.enabled
  }

  function toggleValueStandardGroup(id: string) {
    const group = valueStandardGroups.value.find((item) => item.id === id)
    if (!group) return

    group.enabled = !group.enabled
    group.status = group.enabled ? 'adopted' : 'ignored'

    valueStandards.value.forEach((standard) => {
      if (standard.level1 !== group.level1) return
      standard.enabled = group.enabled
      standard.status = group.status
    })

    // Primary checklist filters samples; radar follows AI-for-Science (secondary) when present.
    const radarUsesPrimary = valueRadarIndicators.value.some(
      (indicator) => indicator.id === group.id || indicator.name === group.level1,
    )
    if (radarUsesPrimary) {
      const radarItem = valueRadarIndicators.value.find(
        (indicator) => indicator.id === group.id || indicator.name === group.level1,
      )
      if (radarItem) radarItem.enabled = group.enabled
    }
  }

  function toggleRadarIndicator(track: 'value' | 'risk', id: string) {
    const radarIndicators =
      track === 'value' ? valueRadarIndicators.value : riskRadarIndicators.value
    const item = radarIndicators.find((indicator) => indicator.id === id)
    if (!item) return

    item.enabled = !item.enabled

    if (track === 'value') {
      const group = valueStandardGroups.value.find(
        (standard) => standard.id === item.id || standard.level1 === item.name,
      )
      if (group) {
        group.enabled = item.enabled
        group.status = item.enabled ? 'adopted' : 'ignored'
        valueStandards.value.forEach((standard) => {
          if (standard.level1 !== group.level1) return
          standard.enabled = item.enabled
          standard.status = group.status
        })
      }
      return item
    }

    const riskItem = riskStandards.value.find(
      (standard) => standard.id === item.id || standard.level1 === item.name,
    )
    if (riskItem) {
      riskItem.enabled = item.enabled
      riskItem.status = item.enabled ? 'adopted' : 'ignored'
    }
    return item
  }

  /** Sync radar axes with AI-for-Science (secondary) checklist. */
  function syncValueRadarFromScienceStandards(
    items: Array<{ id: string; name: string; enabled: boolean }>,
  ) {
    if (!items.length) return
    valueRadarIndicators.value = items.map((item) => ({
      id: item.id,
      name: item.name,
      label: item.name,
      enabled: item.enabled,
    }))
  }

  function setValueRadarIndicatorEnabled(id: string, enabled: boolean) {
    const item = valueRadarIndicators.value.find(
      (indicator) => indicator.id === id || indicator.name === id,
    )
    if (item) item.enabled = enabled
  }

  function syncValueStandardGroup(level1: string) {
    const group = valueStandardGroups.value.find((item) => item.level1 === level1)
    if (!group) return

    const standards = valueStandards.value.filter((item) => item.level1 === level1)
    group.enabled = standards.some((item) => item.enabled)
    group.status = group.enabled ? 'adopted' : 'ignored'
  }

  function applyValueQaScreeningDimensions(
    dimensions: Array<{ name: string; kind: string; count: number }>,
  ) {
    const primary = dimensions.filter((item) => item.kind === 'primary' && item.name.trim())
    const secondary = dimensions.filter((item) => item.kind === 'secondary' && item.name.trim())
    const previousEnabledById = new Map(
      valueStandardGroups.value.map((item) => [item.id, item.enabled] as const),
    )
    const previousEnabledByLevel1 = new Map(
      valueStandardGroups.value.map((item) => [item.level1, item.enabled] as const),
    )
    const hadPreviousSelection = valueStandardGroups.value.some(
      (item) => item.tag === VALUE_QA_STANDARD_TAG,
    )

    if (primary.length > 0) {
      valueStandardGroups.value = primary.map((item) => {
        const id = `topic1-primary-${item.name}`
        const preserved = hadPreviousSelection
          ? (previousEnabledById.get(id) ?? previousEnabledByLevel1.get(item.name) ?? true)
          : true
        return {
          id,
          definitionType: 'input-value' as const,
          name: valueLevel1DisplayNameMap[item.name] ?? item.name,
          desc: `课题一 value_qa 一级维度 · ${item.count} 组`,
          tag: VALUE_QA_STANDARD_TAG,
          enabled: preserved,
          status: (preserved ? 'adopted' : 'ignored') as DefinitionStandardStatus,
          category: '课题一价值评测',
          level1: item.name,
          level2: '',
          level3: '',
        }
      })
      // Prefer secondary (AI for Science) for radar; fallback to primary when no secondary.
      if (secondary.length === 0) {
        valueRadarIndicators.value = valueStandardGroups.value.map((item) => ({
          id: item.id,
          name: item.level1,
          label: item.name,
          enabled: item.enabled,
        }))
      }
    }

    const secondarySource = secondary.length > 0 ? secondary : []
    if (secondarySource.length > 0) {
      const previousRadarEnabled = new Map(
        valueRadarIndicators.value.map((item) => [item.name, item.enabled] as const),
      )
      valueStandards.value = secondarySource.map((item) => ({
        id: `topic1-secondary-${item.name}`,
        definitionType: 'input-value' as const,
        name: item.name,
        desc: `课题一 value_qa 二级维度 · ${item.count} 组`,
        tag: VALUE_QA_STANDARD_TAG,
        enabled: previousRadarEnabled.get(item.name) ?? true,
        status: ((previousRadarEnabled.get(item.name) ?? true)
          ? 'adopted'
          : 'ignored') as DefinitionStandardStatus,
        category: '课题一价值评测',
        level1: '',
        level2: item.name,
        level3: '',
      }))
      valueRadarIndicators.value = secondarySource.map((item) => ({
        id: `topic1-science-${item.name}`,
        name: item.name,
        label: item.name,
        enabled: previousRadarEnabled.get(item.name) ?? true,
      }))
    } else if (secondary.length === 0 && primary.length === 0) {
      // keep existing
    } else if (primary.length > 0 && secondary.length === 0) {
      // radar already set from primary above
    }
  }

  /** 风险轨筛选：对齐课题二 L1-1～L1-4，并按本批语料覆盖默认勾选 */
  function applyTopic2RiskScreeningDimensions(
    dimensions: Array<{ code: string; label: string; count: number }>,
  ) {
    const countByCode = new Map(
      dimensions
        .filter((item) => item.code.trim())
        .map((item) => [item.code, Math.max(0, item.count || 0)] as const),
    )
    const anyPresent = Array.from(countByCode.values()).some((count) => count > 0)
    const previousEnabledByCode = new Map(
      riskStandards.value
        .filter((item) => item.id.startsWith('topic2-l1-'))
        .map((item) => [item.level1, item.enabled] as const),
    )
    const hadPreviousTopic2 = previousEnabledByCode.size > 0

    riskStandards.value = TOPIC2_L1_AXES.map((axis) => {
      const count = countByCode.get(axis.code) ?? 0
      const present = count > 0
      const defaultEnabled = anyPresent ? present : true
      const enabled = hadPreviousTopic2
        ? (previousEnabledByCode.get(axis.code) ?? defaultEnabled)
        : defaultEnabled
      return {
        id: `topic2-l1-${axis.code}`,
        definitionType: 'input-risk' as const,
        name: `${axis.code} ${axis.fullZh}`,
        desc: present ? `本批覆盖 ${count} 条样本` : '本批暂无该 L1 样本',
        tag: present ? '本批覆盖' : '课题二 L1',
        enabled,
        status: (enabled ? 'adopted' : 'ignored') as DefinitionStandardStatus,
        category: '课题二风险 taxonomy',
        level1: axis.code,
        level2: '',
        level3: '',
      }
    })

    riskRadarIndicators.value = riskStandards.value.map((item) => ({
      id: item.id,
      name: item.level1,
      label: item.name,
      enabled: item.enabled,
    }))
  }

  function enabledRiskL1Codes(): string[] {
    return riskStandards.value
      .filter((item) => item.enabled && item.level1.startsWith('L1-'))
      .map((item) => item.level1)
  }

  function enabledValuePrimaryNames(): string[] {
    return valueStandardGroups.value
      .filter((item) => item.enabled)
      .map((item) => item.level1)
      .filter(Boolean)
  }

  return {
    valueStandards,
    riskStandards,
    valueStandardGroups,
    valueRadarIndicators,
    riskRadarIndicators,
    selectedValueRadarIndicators,
    selectedRiskRadarIndicators,
    setDefinitionStandardStatus,
    syncDefinitionStandards,
    toggleStandardEnabled,
    toggleValueStandardGroup,
    toggleRadarIndicator,
    applyValueQaScreeningDimensions,
    applyTopic2RiskScreeningDimensions,
    syncValueRadarFromScienceStandards,
    setValueRadarIndicatorEnabled,
    enabledRiskL1Codes,
    enabledValuePrimaryNames,
  }
})
