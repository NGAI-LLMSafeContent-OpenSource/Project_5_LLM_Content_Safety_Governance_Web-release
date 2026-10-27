// @ts-expect-error -- this Node-only test runs through tsx; the app omits Node declarations.
import assert from 'node:assert/strict'
// @ts-expect-error -- this Node-only test runs through tsx; the app omits Node declarations.
import test from 'node:test'

import {
  createCbrneSampleDrawerSession,
  createCbrneSampleDisclosureController,
  type CbrneSampleDrawerSessionState,
  type CbrneSampleDisclosureState,
} from '../useCbrneSampleDisclosure'
import type { BenchmarkCbrneSampleDetail, BenchmarkCbrneSampleRefItem } from '../../../types'

function detail(sampleId: string, requestId: string): BenchmarkCbrneSampleDetail {
  return {
    asset_id: 'asset-1',
    asset_version: '1',
    sample_id: sampleId,
    full_text: `full ${sampleId}`,
    raw: { prompt: `full ${sampleId}` },
    platform_normalized: { sample_id: sampleId },
    access_event: {
      event_id: `event-${requestId}`,
      asset_id: 'asset-1',
      asset_version: '1',
      sample_id: sampleId,
      action_type: 'benchmark_sample_full_text_disclosure',
      accessed_at: '2026-10-16T12:00:00',
      disclosure_request_id: requestId,
    },
  }
}

function state(): CbrneSampleDisclosureState {
  return { status: 'idle', sampleId: '', detail: null, errorMessage: '' }
}

function refItem(sampleId: string): BenchmarkCbrneSampleRefItem {
  return {
    sample_id: sampleId,
    label: 'unsafe',
    cbrne_category: 'Chemical',
    source: 'WMDP',
    exposure_tier: 'T2',
    evaluator_relative_difficulty: 3,
    text_preview: 'redacted preview',
  }
}

function drawerState(): CbrneSampleDrawerSessionState {
  return {
    isOpen: false,
    assetId: '',
    refsStatus: 'idle',
    refs: [],
    refsErrorMessage: '',
    total: 0,
    currentPage: 1,
    pageSize: 20,
    selectedRef: null,
    disclosure: state(),
  }
}

test('only an explicit disclose action calls the command client', async () => {
  const calls: string[] = []
  const disclosureState = state()
  const controller = createCbrneSampleDisclosureController({
    state: disclosureState,
    createRequestId: () => 'request-1',
    discloseSample: async (_assetId, sampleId, requestId) => {
      calls.push(requestId)
      return detail(sampleId, requestId)
    },
  })

  assert.equal(calls.length, 0)
  await controller.disclose('asset-1', 'sample-1')
  assert.deepEqual(calls, ['request-1'])
  assert.equal(disclosureState.status, 'success')
  assert.equal(disclosureState.detail?.full_text, 'full sample-1')
})

test('pending repeated clicks submit the same user action only once', async () => {
  let resolveRequest!: (value: BenchmarkCbrneSampleDetail) => void
  const pending = new Promise<BenchmarkCbrneSampleDetail>((resolve) => {
    resolveRequest = resolve
  })
  let calls = 0
  const disclosureState = state()
  const controller = createCbrneSampleDisclosureController({
    state: disclosureState,
    createRequestId: () => 'request-pending',
    discloseSample: async () => {
      calls += 1
      return pending
    },
  })

  const first = controller.disclose('asset-1', 'sample-1')
  const repeated = controller.disclose('asset-1', 'sample-1')
  assert.equal(calls, 1)
  assert.equal(disclosureState.status, 'loading')
  resolveRequest(detail('sample-1', 'request-pending'))
  await Promise.all([first, repeated])
  assert.equal(disclosureState.status, 'success')
})

test('a later explicit action gets a new disclosure request identity', async () => {
  const requestIds = ['request-1', 'request-2']
  const seen: string[] = []
  const controller = createCbrneSampleDisclosureController({
    state: state(),
    createRequestId: () => requestIds.shift() ?? 'unexpected',
    discloseSample: async (_assetId, sampleId, requestId) => {
      seen.push(requestId)
      return detail(sampleId, requestId)
    },
  })

  await controller.disclose('asset-1', 'sample-1')
  await controller.disclose('asset-1', 'sample-1')
  assert.deepEqual(seen, ['request-1', 'request-2'])
})

test('reset clears full text and ignores a response that arrives after close', async () => {
  let resolveRequest!: (value: BenchmarkCbrneSampleDetail) => void
  const pending = new Promise<BenchmarkCbrneSampleDetail>((resolve) => {
    resolveRequest = resolve
  })
  const disclosureState = state()
  const controller = createCbrneSampleDisclosureController({
    state: disclosureState,
    createRequestId: () => 'request-late',
    discloseSample: async () => pending,
  })

  const request = controller.disclose('asset-1', 'sample-1')
  controller.reset()
  assert.deepEqual(disclosureState, {
    status: 'idle',
    sampleId: '',
    detail: null,
    errorMessage: '',
  })
  resolveRequest(detail('sample-1', 'request-late'))
  await request
  assert.equal(disclosureState.detail, null)
  assert.equal(disclosureState.status, 'idle')
})

test('switching samples clears the old context and ignores its late response', async () => {
  let resolveFirst!: (value: BenchmarkCbrneSampleDetail) => void
  const firstPending = new Promise<BenchmarkCbrneSampleDetail>((resolve) => {
    resolveFirst = resolve
  })
  const disclosureState = state()
  const controller = createCbrneSampleDisclosureController({
    state: disclosureState,
    createRequestId: () => `request-${disclosureState.sampleId || 'first'}`,
    discloseSample: async (_assetId, sampleId, requestId) =>
      sampleId === 'sample-1' ? firstPending : detail(sampleId, requestId),
  })

  const first = controller.disclose('asset-1', 'sample-1')
  await controller.disclose('asset-1', 'sample-2')
  assert.equal(disclosureState.detail?.sample_id, 'sample-2')

  resolveFirst(detail('sample-1', 'request-first'))
  await first
  assert.equal(disclosureState.detail?.sample_id, 'sample-2')
})

test('retry after the server committed but the response was lost reuses the user action identity', async () => {
  let attempt = 0
  const seenRequestIds: string[] = []
  const disclosureState = state()
  const controller = createCbrneSampleDisclosureController({
    state: disclosureState,
    createRequestId: () => `request-${attempt + 1}`,
    discloseSample: async (_assetId, sampleId, requestId) => {
      attempt += 1
      seenRequestIds.push(requestId)
      if (attempt === 1) throw new Error('网络中断')
      return detail(sampleId, requestId)
    },
  })

  await controller.disclose('asset-1', 'sample-1')
  assert.equal(disclosureState.status, 'error')
  assert.equal(disclosureState.errorMessage, '网络中断')
  assert.equal(disclosureState.detail, null)

  await controller.disclose('asset-1', 'sample-1')
  assert.equal(disclosureState.status, 'success')
  assert.equal(disclosureState.errorMessage, '')
  assert.equal((disclosureState.detail as BenchmarkCbrneSampleDetail | null)?.sample_id, 'sample-1')
  assert.deepEqual(seenRequestIds, ['request-1', 'request-1'])
  assert.equal(
    (disclosureState.detail as BenchmarkCbrneSampleDetail | null)?.access_event
      .disclosure_request_id,
    'request-1',
  )
})

test('drawer public flow never discloses on restore or pagination and invalidates a late response on close', async () => {
  const sessionState = drawerState()
  const pageOffsets: number[] = []
  const disclosureCalls: string[] = []
  let resolveDisclosure!: (value: BenchmarkCbrneSampleDetail) => void
  const pendingDisclosure = new Promise<BenchmarkCbrneSampleDetail>((resolve) => {
    resolveDisclosure = resolve
  })
  const session = createCbrneSampleDrawerSession({
    state: sessionState,
    createRequestId: () => 'request-session',
    listSampleRefs: async (assetId, pagination) => {
      pageOffsets.push(pagination.offset)
      return {
        asset_id: assetId,
        asset_version: '1',
        total: 60,
        limit: pagination.limit,
        offset: pagination.offset,
        items: [refItem(`sample-${pagination.offset + 1}`)],
      }
    },
    discloseSample: async (_assetId, sampleId, requestId) => {
      disclosureCalls.push(`${sampleId}:${requestId}`)
      return pendingDisclosure
    },
  })

  await session.restore('asset-1', 2)
  assert.deepEqual(pageOffsets, [20])
  assert.deepEqual(disclosureCalls, [])
  assert.equal(sessionState.isOpen, true)
  assert.equal(sessionState.disclosure.detail, null)

  await session.goToPage(3)
  assert.deepEqual(pageOffsets, [20, 40])
  assert.deepEqual(disclosureCalls, [])

  const firstClick = session.disclose('sample-41')
  const repeatedClick = session.disclose('sample-41')
  assert.deepEqual(disclosureCalls, ['sample-41:request-session'])
  session.close()
  assert.equal(sessionState.isOpen, false)
  assert.equal(sessionState.disclosure.detail, null)

  resolveDisclosure(detail('sample-41', 'request-session'))
  await Promise.all([firstClick, repeatedClick])
  assert.equal(sessionState.disclosure.detail, null)
  assert.equal(sessionState.disclosure.status, 'idle')
})

test('restoring a sample deep link selects the masked ref without disclosing', async () => {
  const sessionState = drawerState()
  const disclosureCalls: string[] = []
  const focusRef = refItem('sample-42')
  const session = createCbrneSampleDrawerSession({
    state: sessionState,
    createRequestId: () => 'request-deep-link',
    listSampleRefs: async (assetId, pagination) => ({
      asset_id: assetId,
      asset_version: '1',
      total: 60,
      limit: pagination.limit,
      offset: pagination.offset,
      items: [refItem('sample-1')],
    }),
    discloseSample: async (_assetId, sampleId, requestId) => {
      disclosureCalls.push(`${sampleId}:${requestId}`)
      return detail(sampleId, requestId)
    },
  })

  await session.restore('asset-1', 1, focusRef)
  assert.deepEqual(sessionState.selectedRef, focusRef)
  assert.deepEqual(disclosureCalls, [])
  assert.equal(sessionState.disclosure.status, 'idle')

  session.selectSample(refItem('sample-1'))
  assert.equal(sessionState.selectedRef?.sample_id, 'sample-1')
  assert.deepEqual(disclosureCalls, [])

  session.close()
  assert.equal(sessionState.selectedRef, null)
})

test('a new deep-linked sample returns the drawer to the masked state', async () => {
  const sessionState = drawerState()
  const disclosureCalls: string[] = []
  const session = createCbrneSampleDrawerSession({
    state: sessionState,
    createRequestId: () => 'request-reset',
    listSampleRefs: async (assetId, pagination) => ({
      asset_id: assetId,
      asset_version: '1',
      total: 1,
      limit: pagination.limit,
      offset: pagination.offset,
      items: [refItem('sample-1')],
    }),
    discloseSample: async (_assetId, sampleId, requestId) => {
      disclosureCalls.push(sampleId)
      return detail(sampleId, requestId)
    },
  })

  await session.restore('asset-1', 1, refItem('sample-1'))
  await session.disclose('sample-1')
  assert.equal(sessionState.disclosure.status, 'success')

  await session.restore('asset-1', 1, refItem('sample-2'))
  assert.deepEqual(disclosureCalls, ['sample-1'])
  assert.equal(sessionState.selectedRef?.sample_id, 'sample-2')
  assert.equal(sessionState.disclosure.detail, null)
  assert.equal(sessionState.disclosure.status, 'idle')
})
