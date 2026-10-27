/**
 *   node web/frontend/src/composables/guardrail/__tests__/useInputGuardrailDemo.smoke.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '../useInputGuardrailDemo.ts'), 'utf8')

const forbidden = [
  "from '@/stores/input'",
  "from '@/components/data-input/",
  "from '@/composables/data-input/",
  'useInputStore',
  'useDataInputPage',
  'data-input.css',
  'risk-scan-tasks',
  'lineage/build',
  'parse-records',
  '/data-input/upload',
  'useOutputGuardrailDemo',
  'useOutputGuardrailLive',
  'risk_static_dynbench',
]

for (const token of forbidden) {
  if (src.includes(token)) {
    throw new Error(`useInputGuardrailDemo.ts must not contain ${token}`)
  }
}

const required = [
  "from './inputGuardrailDemoMap'",
  'getInputCorpusCatalog',
  'getInputCorpusRecords',
  'getValueAssessment',
  'getValueAttribution',
  'getTopic2PrerunSamples',
  'buildRiskAttribution',
  'getTopic4StaticLineage',
  'use_prerun: true',
  'getTopic2PrerunSamples({ limit: PRERUN_LIMIT })',
  '语料目录不可达',
  '价值预跑评估不可达',
  '课题二预跑样本不可达',
  '静态血缘图谱暂不可用',
  'export function useInputGuardrailDemo',
]

for (const token of required) {
  if (!src.includes(token)) {
    throw new Error(`useInputGuardrailDemo.ts missing ${token}`)
  }
}

console.log('useInputGuardrailDemo.smoke.mjs ok')
