/**
 * Risk prerun review task actions shared through the governance timeline (#90/#91).
 *
 * The 「创建审阅任务」 button lives inside GovernanceSystemRecordDetailCard,
 * two levels below GovernanceView. The view provides this contract; the detail
 * card injects it. #91 adds evidence-pack export on the same inject so the
 * report card never owns the client id.
 */
import type { InjectionKey } from 'vue'

export interface GovernanceRiskReviewActions {
  /** Record whose review-task creation request is in flight. */
  busyRecordId: string | null
  /** Record whose last creation request failed, paired with `error`. */
  errorRecordId: string | null
  error: string
  create: (recordId: string, recordVersion: string) => void
  /** Task whose evidence-pack export is in flight (#91). */
  exportBusyTaskId: string | null
  exportErrorTaskId: string | null
  exportError: string
  downloadEvidencePack: (taskId: string) => void
}

export const GOVERNANCE_RISK_REVIEW_ACTIONS: InjectionKey<GovernanceRiskReviewActions> = Symbol(
  'governance-risk-review-actions',
)
