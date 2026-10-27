import assert from 'node:assert/strict'
import test from 'node:test'

import {
  benchmarkAssetPath,
  benchmarkSamplePath,
  canonicalizeLegacyBenchmarkAssetQuery,
} from '../benchmarkAssetRoute.ts'

test('builds a canonical path with the asset identity in one encoded segment', () => {
  assert.equal(benchmarkAssetPath(' topic2/cbrne v1 '), '/benchmark/assets/topic2%2Fcbrne%20v1')
})

test('builds a canonical sample path scoped to its asset', () => {
  assert.equal(
    benchmarkSamplePath('topic2_cbrne_v1', ' cbrne/0001 '),
    '/benchmark/assets/topic2_cbrne_v1/samples/cbrne%2F0001',
  )
})

test('normalizes a legacy sample link to the canonical sample identity', () => {
  assert.deepEqual(
    canonicalizeLegacyBenchmarkAssetQuery({
      focusAsset: 'topic2_cbrne_v1',
      cbrneSample: 'cbrne-0001',
      mode: 'expert',
    }),
    {
      assetId: 'topic2_cbrne_v1',
      sampleId: 'cbrne-0001',
      query: { mode: 'expert' },
    },
  )
})

test('normalizes focusAsset while preserving unrelated query state', () => {
  assert.deepEqual(
    canonicalizeLegacyBenchmarkAssetQuery({
      focusAsset: 'topic2_cbrne_v1',
      mode: 'expert',
    }),
    {
      assetId: 'topic2_cbrne_v1',
      query: { mode: 'expert' },
    },
  )
})

test('uses the first legacy value and rejects a blank asset identity', () => {
  assert.deepEqual(canonicalizeLegacyBenchmarkAssetQuery({ focusAsset: ['asset-1', 'asset-2'] }), {
    assetId: 'asset-1',
    query: {},
  })
  assert.equal(canonicalizeLegacyBenchmarkAssetQuery({ focusAsset: '   ' }), null)
})
