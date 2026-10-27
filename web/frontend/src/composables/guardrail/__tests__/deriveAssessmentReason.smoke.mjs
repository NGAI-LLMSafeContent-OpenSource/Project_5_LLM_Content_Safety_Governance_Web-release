/**
 *   node --experimental-strip-types web/frontend/src/composables/guardrail/__tests__/deriveAssessmentReason.smoke.mjs
 */
import { deriveAssessmentReason } from '../deriveAssessmentReason.ts'

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

const empty = {
  valuePrimary: '',
  valueLevel: '',
  riskL1: '',
  riskAbnormal: false,
  riskStatus: '',
}

assertEqual(deriveAssessmentReason(empty), '无风险命中、无价值问题 → pass', 'general pass')
assertEqual(
  deriveAssessmentReason({ ...empty, valuePrimary: '文化忠实度', valueLevel: 'high' }),
  '价值可接受，风险未命中 → pass',
  'value high pass',
)
assertEqual(
  deriveAssessmentReason({ ...empty, valuePrimary: '文化忠实度', valueLevel: 'medium' }),
  '价值中等，需补强确认 → review',
  'value medium review',
)
assertEqual(
  deriveAssessmentReason({ ...empty, valuePrimary: '文化忠实度', valueLevel: 'low' }),
  '价值档位 low（文化忠实度）→ revise',
  'value low revise',
)
assertEqual(
  deriveAssessmentReason({ ...empty, riskL1: 'L1-2 显式有害注入', riskAbnormal: true }),
  'L1-2 显式有害注入 命中 → review',
  'risk hit review',
)
assertEqual(
  deriveAssessmentReason({ ...empty, riskL1: 'L1-2 显式有害注入', riskStatus: '待复核' }),
  'L1-2 显式有害注入 待复核 → review',
  'borderline review',
)

console.log('deriveAssessmentReason.smoke.mjs ok')
