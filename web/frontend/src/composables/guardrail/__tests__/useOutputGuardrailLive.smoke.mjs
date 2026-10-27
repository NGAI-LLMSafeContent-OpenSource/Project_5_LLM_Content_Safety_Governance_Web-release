/**
 *   node web/frontend/src/composables/guardrail/__tests__/useOutputGuardrailLive.smoke.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '../useOutputGuardrailLive.ts'), 'utf8')

const forbidden = [
  "from '@/stores/output'",
  "from '@/stores/output/",
  "from '@/components/output/",
  "from '@/composables/output/",
  'useOutputStore',
  'useComplianceData',
  'useOutputWizard',
  '/eval-tasks',
  'startEvalTask',
  'demo_bundle.json',
  'useOutputGuardrailDemo',
]

for (const token of forbidden) {
  if (src.includes(token)) {
    throw new Error(`useOutputGuardrailLive.ts must not contain ${token}`)
  }
}

const required = [
  'fetchGuardrailDemoPacks',
  'startGuardrailLiveBatch',
  'fetchGuardrailLiveBatch',
  'LIVE_DISPOSAL_NOTICE',
  'export function useOutputGuardrailLive',
]

for (const token of required) {
  if (!src.includes(token)) {
    throw new Error(`useOutputGuardrailLive.ts missing ${token}`)
  }
}

if (!src.includes('以下结果来自本次运行，不是预跑静态样例。')) {
  throw new Error('useOutputGuardrailLive.ts missing live disposal notice')
}

console.log('useOutputGuardrailLive.smoke.mjs ok')
