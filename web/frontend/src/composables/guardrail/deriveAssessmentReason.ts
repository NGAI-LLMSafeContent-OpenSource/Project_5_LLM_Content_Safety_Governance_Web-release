export interface AssessmentReasonInput {
  valuePrimary: string
  valueLevel: string
  riskL1: string
  riskAbnormal: boolean
  riskStatus: string
}

export function deriveAssessmentReason(row: AssessmentReasonInput): string {
  if (row.riskAbnormal && row.riskL1) return `${row.riskL1} 命中 → review`
  if (row.riskStatus === '待复核') return `${row.riskL1 || '风险'} 待复核 → review`
  if (row.valueLevel === 'low') return `价值档位 low（${row.valuePrimary}）→ revise`
  if (row.valueLevel === 'medium') return '价值中等，需补强确认 → review'
  if (!row.valuePrimary && !row.riskL1) return '无风险命中、无价值问题 → pass'
  return '价值可接受，风险未命中 → pass'
}
