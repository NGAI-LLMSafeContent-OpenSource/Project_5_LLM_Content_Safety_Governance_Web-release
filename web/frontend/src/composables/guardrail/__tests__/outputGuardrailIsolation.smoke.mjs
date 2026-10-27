/**
 *   node web/frontend/src/composables/guardrail/__tests__/outputGuardrailIsolation.smoke.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontendSrc = join(here, '../../..')

const isolatedFiles = [
  'composables/guardrail/useOutputGuardrailLive.ts',
  'components/guardrail/OutputGuardrailIngest.vue',
  'components/guardrail/OutputGuardrailDetect.vue',
  'components/guardrail/OutputGuardrailEvidence.vue',
  'components/guardrail/OutputGuardrailDisposal.vue',
  'views/OutputGuardrailView.vue',
]

const forbidden = [
  'useOutputStore',
  '@/stores/output',
  '@/components/output/',
  'useComplianceData',
  'useOutputWizard',
  'output-wizard.css',
  '开始训练',
  '后训练策略',
  'demo_bundle.json',
  'useOutputGuardrailDemo',
  '以下为预跑合规编辑样例，不表示当前评测样本已实时改写。',
]

function readSrc(relPath) {
  return readFileSync(join(frontendSrc, relPath), 'utf8')
}

for (const relPath of isolatedFiles) {
  const src = readSrc(relPath)
  for (const token of forbidden) {
    if (src.includes(token)) {
      throw new Error(`${relPath} must not contain ${token}`)
    }
  }
}

const viewSrc = readSrc('views/OutputGuardrailView.vue')
for (const token of ['guardrail-panel-ingest', '@select', '运行本批', 'useOutputGuardrailLive']) {
  if (!viewSrc.includes(token)) {
    throw new Error(`OutputGuardrailView.vue missing ${token}`)
  }
}

const ingestSrc = readSrc('components/guardrail/OutputGuardrailIngest.vue')
if (!ingestSrc.includes('运行本批')) {
  throw new Error('OutputGuardrailIngest.vue missing 运行本批')
}

const disposalSrc = readSrc('components/guardrail/OutputGuardrailDisposal.vue')
const liveNotice = '以下结果来自本次运行，不是预跑静态样例。'
if (!disposalSrc.includes('LIVE_DISPOSAL_NOTICE') && !disposalSrc.includes(liveNotice)) {
  throw new Error('OutputGuardrailDisposal.vue must include the live disposal notice')
}

const outputViewSrc = readSrc('views/OutputView.vue')
if (outputViewSrc.includes('后训练策略建议')) {
  throw new Error('OutputView.vue must not expose 后训练策略建议 in the primary flow')
}

console.log('outputGuardrailIsolation.smoke.mjs ok')
