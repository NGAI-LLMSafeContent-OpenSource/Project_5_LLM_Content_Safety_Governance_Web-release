/**
 * Risk re-detection task actions shared through the governance timeline.
 *
 * The confirm/result cards live two levels below GovernanceView, so threading
 * busy/error/status props through GovernanceTimeline would be prop drilling
 * (frontend docs 11-code-patterns.md, anti-pattern 7). The view provides this
 * contract instead and the cards inject it.
 */
import type { InjectionKey } from 'vue'
import type { GovernanceResultProjectionData } from '@/types'

export type GovernanceRescanAction = 'confirm' | 'cancel' | 'retry'

export interface GovernanceRescanActions {
  /** Latest server-known status per re-detection task id (refresh recovery). */
  statuses: Record<string, string>
  /**
   * Latest task-level aggregated result per task id (#64 `get_task.result`).
   * The result message payload carries no run provenance, so the projection
   * reads the aggregated result here to show 来源与运行历史.
   */
  results: Record<string, GovernanceResultProjectionData | null>
  /** Task currently executing a confirm/cancel/retry request. */
  busyTaskId: string | null
  /** Which action is in flight for `busyTaskId`, so labels stay honest. */
  busyAction: GovernanceRescanAction | null
  /** Task whose last action failed, paired with `error`. */
  errorTaskId: string | null
  error: string
  exportBusyTaskId: string | null
  exportErrorTaskId: string | null
  exportError: string
  confirm: (taskId: string) => void
  cancel: (taskId: string) => void
  retry: (taskId: string) => void
  /**
   * #167: export the `risk_corpus_rescan` v2 evidence pack projected from the
   * persisted result (never re-runs detection).
   */
  downloadRiskRescanEvidencePack: (taskId: string) => void
}

export const GOVERNANCE_RESCAN_ACTIONS: InjectionKey<GovernanceRescanActions> = Symbol(
  'governance-rescan-actions',
)
