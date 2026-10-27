import type { TabKey } from '@/types'
import type { DefinitionFormState } from '@/types/definition'
import type {
  DefinitionStandard,
  DefinitionStandardStatus,
  DefinitionTabConfig,
} from '@/utils/definitionConfig'

export interface DefinitionStandardPayload {
  id: string
  definitionType: TabKey
  name: string
  category?: string
  level1: string
  level2: string
  level3: string
  status: DefinitionStandardStatus
  enabled: boolean
}

export interface DefinitionTabPayload {
  key: TabKey
  formState: DefinitionFormState
  standards: DefinitionStandardPayload[]
}

export interface DefinitionWorkflowPayload {
  activeTab: TabKey
  tabs: Record<TabKey, DefinitionTabPayload>
}

export function buildDefinitionWorkflowPayload(options: {
  activeTab: TabKey
  canonicalTabConfigs: Record<TabKey, DefinitionTabConfig>
  formStateByTab: Record<TabKey, DefinitionFormState>
  standardStatusByTab: Record<TabKey, Record<string, DefinitionStandardStatus>>
}): DefinitionWorkflowPayload {
  const tabs = Object.values(options.canonicalTabConfigs).reduce(
    (acc, config) => {
      acc[config.key] = {
        key: config.key,
        formState: options.formStateByTab[config.key],
        standards: config.standards.map((standard) =>
          toDefinitionStandardPayload(standard, options.standardStatusByTab[config.key]),
        ),
      }
      return acc
    },
    {} as Record<TabKey, DefinitionTabPayload>,
  )

  return {
    activeTab: options.activeTab,
    tabs,
  }
}

function toDefinitionStandardPayload(
  standard: DefinitionStandard,
  statusByStandardId: Record<string, DefinitionStandardStatus>,
): DefinitionStandardPayload {
  const status = statusByStandardId[standard.id] ?? standard.status
  return {
    id: standard.id,
    definitionType: standard.definitionType,
    name: standard.name,
    category: standard.category,
    level1: standard.level1,
    level2: standard.level2,
    level3: standard.level3,
    status,
    enabled: status !== 'ignored',
  }
}
