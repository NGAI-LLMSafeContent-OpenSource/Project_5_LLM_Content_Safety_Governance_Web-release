import type {
  BenchmarkCbrneSampleDetail,
  BenchmarkCbrneSampleRefItem,
  BenchmarkCbrneSampleRefsResponse,
} from '../../types'

export type CbrneSampleDisclosureStatus = 'idle' | 'loading' | 'success' | 'error'

export interface CbrneSampleDisclosureState {
  status: CbrneSampleDisclosureStatus
  sampleId: string
  detail: BenchmarkCbrneSampleDetail | null
  errorMessage: string
}

export interface CbrneSampleDisclosureControllerOptions {
  state: CbrneSampleDisclosureState
  discloseSample: (
    assetId: string,
    sampleId: string,
    disclosureRequestId: string,
  ) => Promise<BenchmarkCbrneSampleDetail>
  createRequestId: () => string
}

export interface CbrneSampleDisclosureController {
  disclose: (assetId: string, sampleId: string) => Promise<void>
  reset: () => void
}

export function createCbrneSampleDisclosureController(
  options: CbrneSampleDisclosureControllerOptions,
): CbrneSampleDisclosureController {
  const { state, discloseSample, createRequestId } = options
  let generation = 0
  let activeAssetId = ''
  let activeDisclosureRequestId = ''

  function reset() {
    generation += 1
    state.status = 'idle'
    state.sampleId = ''
    state.detail = null
    state.errorMessage = ''
    activeAssetId = ''
    activeDisclosureRequestId = ''
  }

  async function disclose(assetId: string, sampleId: string) {
    if (state.status === 'loading' && activeAssetId === assetId && state.sampleId === sampleId) {
      return
    }

    const isRetry =
      state.status === 'error' && activeAssetId === assetId && state.sampleId === sampleId
    const requestGeneration = ++generation
    const disclosureRequestId = isRetry ? activeDisclosureRequestId : createRequestId()
    state.status = 'loading'
    activeAssetId = assetId
    activeDisclosureRequestId = disclosureRequestId
    state.sampleId = sampleId
    state.detail = null
    state.errorMessage = ''

    try {
      const response = await discloseSample(assetId, sampleId, disclosureRequestId)
      if (generation !== requestGeneration) {
        return
      }
      state.detail = response
      state.status = 'success'
    } catch (error) {
      if (generation !== requestGeneration) {
        return
      }
      state.detail = null
      state.status = 'error'
      state.errorMessage = error instanceof Error ? error.message : 'CBRNE 样本全文披露失败'
    }
  }

  return { disclose, reset }
}

export type CbrneSampleRefsStatus = 'idle' | 'loading' | 'success' | 'error'

export interface CbrneSampleDrawerSessionState {
  isOpen: boolean
  assetId: string
  refsStatus: CbrneSampleRefsStatus
  refs: BenchmarkCbrneSampleRefItem[]
  refsErrorMessage: string
  total: number
  currentPage: number
  pageSize: number
  /** Masked reference selected by a deep link or a row click; never full text. */
  selectedRef: BenchmarkCbrneSampleRefItem | null
  disclosure: CbrneSampleDisclosureState
}

export interface CbrneSampleDrawerSessionOptions {
  state: CbrneSampleDrawerSessionState
  listSampleRefs: (
    assetId: string,
    pagination: { limit: number; offset: number },
  ) => Promise<BenchmarkCbrneSampleRefsResponse>
  discloseSample: CbrneSampleDisclosureControllerOptions['discloseSample']
  createRequestId: () => string
}

export interface CbrneSampleDrawerSession {
  open: (assetId: string, focusRef?: BenchmarkCbrneSampleRefItem | null) => Promise<void>
  restore: (
    assetId: string,
    page?: number,
    focusRef?: BenchmarkCbrneSampleRefItem | null,
  ) => Promise<void>
  goToPage: (page: number) => Promise<void>
  changePageSize: (pageSize: number) => Promise<void>
  switchAsset: (assetId: string) => Promise<void>
  selectSample: (ref: BenchmarkCbrneSampleRefItem) => void
  disclose: (sampleId: string) => Promise<void>
  retry: () => Promise<void>
  close: () => void
}

export function createCbrneSampleDrawerSession(
  options: CbrneSampleDrawerSessionOptions,
): CbrneSampleDrawerSession {
  const { state, listSampleRefs } = options
  const disclosureController = createCbrneSampleDisclosureController({
    state: state.disclosure,
    discloseSample: options.discloseSample,
    createRequestId: options.createRequestId,
  })
  let refsGeneration = 0

  function clearRefs() {
    refsGeneration += 1
    state.refsStatus = 'idle'
    state.refs = []
    state.refsErrorMessage = ''
    state.total = 0
  }

  async function loadRefs() {
    if (!state.isOpen || !state.assetId) return
    const requestGeneration = ++refsGeneration
    const requestedAssetId = state.assetId
    state.refsStatus = 'loading'
    state.refsErrorMessage = ''
    try {
      const response = await listSampleRefs(requestedAssetId, {
        limit: state.pageSize,
        offset: (state.currentPage - 1) * state.pageSize,
      })
      if (
        requestGeneration !== refsGeneration ||
        !state.isOpen ||
        state.assetId !== requestedAssetId
      ) {
        return
      }
      state.refs = response.items
      state.total = response.total
      state.refsStatus = 'success'
    } catch (error) {
      if (requestGeneration !== refsGeneration) return
      state.refs = []
      state.total = 0
      state.refsStatus = 'error'
      state.refsErrorMessage = error instanceof Error ? error.message : 'CBRNE 样本引用读取失败'
    }
  }

  async function restore(
    assetId: string,
    page = 1,
    focusRef: BenchmarkCbrneSampleRefItem | null = null,
  ) {
    const normalizedAssetId = assetId.trim()
    if (!normalizedAssetId) return
    const sameAsset = state.assetId === normalizedAssetId
    // Entering (or re-entering) a deep-linked sample always starts masked.
    if (!sameAsset || focusRef) disclosureController.reset()
    state.isOpen = true
    state.assetId = normalizedAssetId
    state.currentPage = Math.max(1, page)
    if (focusRef) state.selectedRef = focusRef
    else if (!sameAsset) state.selectedRef = null
    await loadRefs()
  }

  async function open(assetId: string, focusRef: BenchmarkCbrneSampleRefItem | null = null) {
    await restore(assetId, 1, focusRef)
  }

  async function goToPage(page: number) {
    state.currentPage = Math.max(1, page)
    await loadRefs()
  }

  async function changePageSize(pageSize: number) {
    state.pageSize = Math.max(1, pageSize)
    state.currentPage = 1
    await loadRefs()
  }

  async function switchAsset(assetId: string) {
    clearRefs()
    disclosureController.reset()
    state.selectedRef = null
    state.assetId = ''
    if (!state.isOpen) return
    await open(assetId)
  }

  function selectSample(ref: BenchmarkCbrneSampleRefItem) {
    state.selectedRef = ref
  }

  async function disclose(sampleId: string) {
    if (!state.isOpen || !state.assetId) return
    await disclosureController.disclose(state.assetId, sampleId)
  }

  async function retry() {
    if (!state.disclosure.sampleId) return
    await disclose(state.disclosure.sampleId)
  }

  function close() {
    state.isOpen = false
    state.assetId = ''
    state.currentPage = 1
    state.selectedRef = null
    clearRefs()
    disclosureController.reset()
  }

  return {
    open,
    restore,
    goToPage,
    changePageSize,
    switchAsset,
    selectSample,
    disclose,
    retry,
    close,
  }
}
