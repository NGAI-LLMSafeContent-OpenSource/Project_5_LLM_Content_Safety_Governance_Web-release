import type { GovernanceDomainKey } from '@/types'
import { createUuid } from '@/utils/uuid'

const STORAGE_KEY = 'governance-client-state'
const SCHEMA_VERSION = 1
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export interface GovernanceClientState {
  schemaVersion: number
  clientId: string
  activeDomain: GovernanceDomainKey
  recentSessionId: string | null
}

function validUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}

function newState(clientId: string = createUuid()): GovernanceClientState {
  return {
    schemaVersion: SCHEMA_VERSION,
    clientId,
    activeDomain: 'input',
    recentSessionId: null,
  }
}

export function saveGovernanceClientState(state: GovernanceClientState): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

export function loadGovernanceClientState(): {
  state: GovernanceClientState
  persistent: boolean
} {
  let state = newState()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved: unknown = JSON.parse(raw)
      if (saved && typeof saved === 'object') {
        const candidate = saved as Partial<GovernanceClientState>
        if (validUuid(candidate.clientId)) {
          state = newState(candidate.clientId)
          if (candidate.schemaVersion === SCHEMA_VERSION) {
            state.activeDomain = candidate.activeDomain === 'output' ? 'output' : 'input'
            state.recentSessionId = validUuid(candidate.recentSessionId)
              ? candidate.recentSessionId
              : null
          }
        }
      }
    }
  } catch {
    // Invalid or unavailable browser storage is recovered without trusting its contents.
  }
  return { state, persistent: saveGovernanceClientState(state) }
}
