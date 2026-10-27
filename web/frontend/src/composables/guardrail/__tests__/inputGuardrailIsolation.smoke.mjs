/**
 *   node web/frontend/src/composables/guardrail/__tests__/inputGuardrailIsolation.smoke.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontendSrc = join(here, '../../..')

const isolatedFiles = [
  'composables/guardrail/inputGuardrailDemoMap.ts',
  'composables/guardrail/useInputGuardrailDemo.ts',
  'composables/guardrail/useInputGuardrailLive.ts',
  'components/guardrail/InputGuardrailIngest.vue',
  'components/guardrail/InputGuardrailDetect.vue',
  'components/guardrail/InputGuardrailEvidence.vue',
  'components/guardrail/InputGuardrailDisposal.vue',
  'views/InputGuardrailView.vue',
]

const forbidden = [
  'useInputStore',
  '@/stores/input',
  '@/components/data-input/',
  '@/composables/data-input/',
  'useDataInputPage',
  'data-input.css',
  'risk-scan-tasks',
  'lineage/build',
  'parse-records',
  '已入库',
  '开始训练',
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

const viewSrc = readSrc('views/InputGuardrailView.vue')
for (const token of [
  'guardrail-panel-ingest',
  '@run-live',
  'useInputGuardrailLive',
  'InputGuardrailDetect',
  "demoMode: 'live_run'",
]) {
  if (!viewSrc.includes(token)) {
    throw new Error(`InputGuardrailView.vue missing ${token}`)
  }
}
if (viewSrc.includes('guardrail-page__grid')) {
  throw new Error('InputGuardrailView.vue must not keep the placeholder grid')
}
if (viewSrc.includes('上传')) {
  throw new Error('InputGuardrailView.vue must not contain 上传')
}

const ingestSrc = readSrc('components/guardrail/InputGuardrailIngest.vue')
if (ingestSrc.includes('risk_static_dynbench') || ingestSrc.includes('上传')) {
  throw new Error('InputGuardrailIngest.vue must not offer static dynbench or upload')
}

const detectSrc = readSrc('components/guardrail/InputGuardrailDetect.vue')
if (!detectSrc.includes('以下结果来自本次输入数据治理运行，不是预跑静态拼接。')) {
  throw new Error('InputGuardrailDetect.vue missing live run notice')
}

const disposalSrc = readSrc('components/guardrail/InputGuardrailDisposal.vue')
if (
  !disposalSrc.includes(
    '以下为本次输入护栏运行生成的修正建议。保存后将形成课题五本地草稿，待人工复核后再入库。',
  )
) {
  throw new Error('InputGuardrailDisposal.vue missing live disposal notice')
}
if (!disposalSrc.includes('待人工复核后入库')) {
  throw new Error('InputGuardrailDisposal.vue missing REVIEW_STATUS')
}

const loaderSrc = readSrc('composables/guardrail/useInputGuardrailDemo.ts')
if (!loaderSrc.includes('use_prerun: true')) {
  throw new Error('useInputGuardrailDemo.ts must pass use_prerun: true')
}
if (!loaderSrc.includes('getTopic2PrerunSamples({ limit: PRERUN_LIMIT })')) {
  throw new Error('useInputGuardrailDemo.ts must call prerun without asset_id')
}
for (const token of ['valueEvidenceRows', 'riskEvidenceRows']) {
  const liveSrc = readSrc('composables/guardrail/useInputGuardrailLive.ts')
  if (!liveSrc.includes(token)) {
    throw new Error(`useInputGuardrailLive.ts must expose ${token}`)
  }
  if (!viewSrc.includes(`${token}.value`)) {
    throw new Error(`InputGuardrailView.vue workflow payload must consume ${token}`)
  }
}

const dataInputView = readSrc('views/DataInputView.vue')
if (!dataInputView.includes('DataInput')) {
  throw new Error('DataInputView.vue should remain the legacy wizard')
}

console.log('inputGuardrailIsolation.smoke.mjs ok')
