/**
 * Cultural prerun review task actions shared through the governance timeline.
 *
 * The 「创建审阅任务」 button lives inside GovernanceCulturalRecordDetailCard,
 * two levels below GovernanceView, so threading busy/error props through
 * GovernanceTimeline would be prop drilling (frontend docs 11-code-patterns.md,
 * anti-pattern 7). The view provides this contract instead and the detail card
 * injects it. Unlike the rescan actions there is exactly one create action: the
 * explicit, read-only review-task creation (#88). #89 adds evidence-pack export
 * on the same inject so the report card never owns the client id.
 */
import type { InjectionKey } from 'vue'

export interface GovernanceCulturalReviewActions {
  /** Record whose review-task creation request is in flight. */
  busyRecordId: string | null
  /** Record whose last creation request failed, paired with `error`. */
  errorRecordId: string | null
  error: string
  create: (recordId: string, recordVersion: string) => void
  /** Task whose evidence-pack export is in flight (#89). */
  exportBusyTaskId: string | null
  exportErrorTaskId: string | null
  exportError: string
  downloadEvidencePack: (taskId: string) => void
}

export const GOVERNANCE_CULTURAL_REVIEW_ACTIONS: InjectionKey<GovernanceCulturalReviewActions> =
  Symbol('governance-cultural-review-actions')
