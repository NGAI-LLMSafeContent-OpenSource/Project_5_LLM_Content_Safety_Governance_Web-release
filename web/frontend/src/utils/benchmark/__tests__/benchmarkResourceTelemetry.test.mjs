import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BENCHMARK_RESOURCE_RESOLUTION_EVENT,
  emitBenchmarkResourceResolution,
} from '../benchmarkResourceTelemetry.ts'

test('emits a fixed non-sensitive identity for each resolution outcome', () => {
  const target = new EventTarget()
  globalThis.window = target

  const seen = []
  target.addEventListener(BENCHMARK_RESOURCE_RESOLUTION_EVENT, (event) => {
    seen.push(event.detail)
  })

  emitBenchmarkResourceResolution('canonical-hit', {
    assetId: ' topic2_cbrne_v1 ',
    sampleId: ' cbrne-0001 ',
  })
  emitBenchmarkResourceResolution('legacy-normalized', {
    assetId: 'topic2_cbrne_v1',
    sampleId: 'cbrne-0001',
  })
  emitBenchmarkResourceResolution('asset-not-found', { assetId: 'missing' })
  emitBenchmarkResourceResolution('sample-not-found', {
    assetId: 'topic2_cbrne_v1',
    sampleId: 'missing',
  })
  emitBenchmarkResourceResolution('service-failure', {
    assetId: 'topic2_cbrne_v1',
    sampleId: 'cbrne-0001',
  })

  assert.deepEqual(seen, [
    { outcome: 'canonical-hit', assetId: 'topic2_cbrne_v1', sampleId: 'cbrne-0001' },
    { outcome: 'legacy-normalized', assetId: 'topic2_cbrne_v1', sampleId: 'cbrne-0001' },
    { outcome: 'asset-not-found', assetId: 'missing' },
    { outcome: 'sample-not-found', assetId: 'topic2_cbrne_v1', sampleId: 'missing' },
    { outcome: 'service-failure', assetId: 'topic2_cbrne_v1', sampleId: 'cbrne-0001' },
  ])
  for (const detail of seen) {
    for (const key of Object.keys(detail)) {
      assert.ok(['outcome', 'assetId', 'sampleId'].includes(key), `unexpected key ${key}`)
    }
    assert.equal('full_text' in detail, false)
    assert.equal('text_preview' in detail, false)
  }
})

test('returns the detail without a window so server-side imports stay safe', () => {
  const original = globalThis.window
  delete globalThis.window
  try {
    assert.deepEqual(emitBenchmarkResourceResolution('service-failure', { assetId: 'asset-1' }), {
      outcome: 'service-failure',
      assetId: 'asset-1',
    })
  } finally {
    globalThis.window = original
  }
})
