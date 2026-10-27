<template>
  <section class="asset-resource" aria-labelledby="asset-resource-title">
    <nav class="asset-resource__nav" aria-label="Benchmark 资产导航">
      <RouterLink class="asset-resource__back" :to="allAssetsRoute">返回全部资产</RouterLink>
      <span aria-hidden="true">/</span>
      <span>资产资源</span>
    </nav>

    <header class="asset-resource__header">
      <div>
        <span class="asset-resource__eyebrow">Benchmark asset resource</span>
        <h1 id="asset-resource-title">
          {{ state.status === 'success' && state.asset ? state.asset.name : 'Benchmark 资产' }}
        </h1>
        <p>此地址固定表示一个已登记资产，并从 Benchmark 资产接口读取与全部资产列表相同的事实。</p>
      </div>
      <code data-testid="benchmark-resource-asset-id">{{ assetId }}</code>
    </header>

    <div class="asset-resource__state" aria-live="polite">
      <div v-if="state.status === 'loading'" class="asset-resource__loading" role="status">
        <span class="asset-resource__spinner" aria-hidden="true"></span>
        <div>
          <strong>正在读取资产</strong>
          <p>目标资产 ID：{{ assetId }}</p>
        </div>
      </div>

      <div
        v-else-if="state.status === 'not-found'"
        class="asset-resource__message is-not-found"
        role="alert"
      >
        <span class="asset-resource__state-label">未找到</span>
        <h2>未找到 Benchmark 资产</h2>
        <p>
          目标资产 ID：
          <code>{{ assetId }}</code>
        </p>
        <RouterLink class="asset-resource__action" :to="allAssetsRoute">返回全部资产</RouterLink>
      </div>

      <div
        v-else-if="state.status === 'error'"
        class="asset-resource__message is-error"
        role="alert"
      >
        <span class="asset-resource__state-label">读取失败</span>
        <h2>资产服务暂时不可用</h2>
        <p>
          目标资产 ID：
          <code>{{ assetId }}</code>
        </p>
        <p>{{ state.errorMessage }}</p>
        <button type="button" class="asset-resource__action" @click="retry">重新读取</button>
      </div>

      <div v-else-if="state.status === 'success' && state.asset" class="asset-resource__content">
        <div
          v-if="sampleState.status === 'loading'"
          class="asset-resource__sample-status"
          role="status"
          data-testid="benchmark-sample-resource-loading"
        >
          <span class="asset-resource__spinner" aria-hidden="true"></span>
          <p>
            正在读取脱敏样本引用：
            <code>{{ sampleState.sampleId }}</code>
          </p>
        </div>

        <div
          v-else-if="sampleState.status === 'not-found'"
          class="asset-resource__message is-not-found"
          role="alert"
          data-testid="benchmark-sample-resource-not-found"
        >
          <span class="asset-resource__state-label">样本未找到</span>
          <h2>未找到 CBRNE 样本</h2>
          <p>
            目标样本 ID：
            <code>{{ sampleState.sampleId }}</code>
            。所属资产仍可正常浏览。
          </p>
          <RouterLink class="asset-resource__action" :to="assetRoute">返回资产资源</RouterLink>
        </div>

        <div
          v-else-if="sampleState.status === 'error'"
          class="asset-resource__message is-error"
          role="alert"
          data-testid="benchmark-sample-resource-error"
        >
          <span class="asset-resource__state-label">读取失败</span>
          <h2>样本服务暂时不可用</h2>
          <p>
            目标样本 ID：
            <code>{{ sampleState.sampleId }}</code>
          </p>
          <p>{{ sampleState.errorMessage }}</p>
          <button type="button" class="asset-resource__action" @click="retrySample">
            重新读取样本
          </button>
        </div>

        <article class="asset-resource__facts" data-testid="benchmark-asset-resource-facts">
          <div class="asset-resource__facts-heading">
            <div>
              <span class="asset-resource__state-label">已登记资产</span>
              <h2>{{ state.asset.name }}</h2>
            </div>
            <span class="asset-resource__mode">{{ state.asset.source_mode }}</span>
          </div>
          <dl>
            <div>
              <dt>资产 ID</dt>
              <dd>
                <code>{{ state.asset.asset_id }}</code>
              </dd>
            </div>
            <div>
              <dt>任务 ID</dt>
              <dd>
                <code>{{ state.asset.task_id || '-' }}</code>
              </dd>
            </div>
            <div>
              <dt>产物 SHA-256</dt>
              <dd>
                <code>{{ state.asset.artifact_sha256 || '-' }}</code>
              </dd>
            </div>
            <div>
              <dt>登记时间</dt>
              <dd>{{ formatDate(state.asset.created_at) }}</dd>
            </div>
          </dl>
          <details>
            <summary>查看资产清单</summary>
            <pre>{{ JSON.stringify(state.asset.manifest, null, 2) }}</pre>
          </details>
        </article>

        <BenchmarkAssetPanel
          :artifacts="[]"
          :registry-assets="[state.asset]"
          :is-loading="false"
          :is-active-tab="true"
          error-message=""
          resource-mode
          :focus-sample="sampleState.ref"
          @refresh="retry"
          @view-evaluations="goToEvaluations"
          @close-sample-resource="returnToAssetResource"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, shallowReactive, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { getBenchmarkAsset, getCbrneSampleRef } from '@/api/benchmark'
import { ApiRequestError } from '@/api/request'
import BenchmarkAssetPanel from '@/components/benchmark/BenchmarkAssetPanel.vue'
import { emitBenchmarkResourceResolution } from '@/utils/benchmark/benchmarkResourceTelemetry'
import type { BenchmarkArtifactItem, BenchmarkCbrneSampleRefResponse } from '@/types'

const props = defineProps<{ assetId: string; sampleId?: string }>()
const router = useRouter()
const state = shallowReactive<{
  assetId: string
  status: 'idle' | 'loading' | 'success' | 'not-found' | 'error'
  asset: BenchmarkArtifactItem | null
  errorMessage: string
}>({ assetId: '', status: 'idle', asset: null, errorMessage: '' })
const sampleState = shallowReactive<{
  sampleId: string
  status: 'idle' | 'loading' | 'success' | 'not-found' | 'error'
  ref: BenchmarkCbrneSampleRefResponse | null
  errorMessage: string
}>({ sampleId: '', status: 'idle', ref: null, errorMessage: '' })
const allAssetsRoute = { name: 'benchmark', query: { view: 'expert', tab: 'assets' } }
const assetRoute = computed(() => ({
  name: 'benchmark-asset',
  params: { assetId: state.assetId },
}))
let generation = 0
let sampleGeneration = 0

watch(
  () => props.assetId,
  (assetId) => {
    void load(assetId)
  },
  { immediate: true },
)

watch(
  () => props.sampleId ?? '',
  (sampleId) => {
    if (state.status !== 'success') return
    void loadSample(sampleId, generation)
  },
)

async function load(rawAssetId: string) {
  const assetId = rawAssetId.trim()
  const requestGeneration = ++generation
  state.assetId = assetId
  state.status = 'loading'
  state.asset = null
  state.errorMessage = ''
  resetSampleState(props.sampleId ?? '')

  try {
    const asset = await getBenchmarkAsset(assetId)
    if (requestGeneration !== generation) return
    state.asset = asset
    state.status = 'success'
    if (!props.sampleId?.trim()) {
      emitBenchmarkResourceResolution('canonical-hit', { assetId })
    }
    await loadSample(props.sampleId ?? '', requestGeneration)
  } catch (error) {
    if (requestGeneration !== generation) return
    state.errorMessage = error instanceof Error ? error.message : '资产服务暂时不可用'
    const isMissing = error instanceof ApiRequestError && error.status === 404
    state.status = isMissing ? 'not-found' : 'error'
    emitBenchmarkResourceResolution(isMissing ? 'asset-not-found' : 'service-failure', {
      assetId,
      sampleId: props.sampleId,
    })
  }
}

async function loadSample(rawSampleId: string, assetGeneration: number) {
  const sampleId = String(rawSampleId || '').trim()
  const requestGeneration = ++sampleGeneration
  sampleState.sampleId = sampleId
  sampleState.ref = null
  sampleState.errorMessage = ''
  if (!sampleId) {
    sampleState.status = 'idle'
    return
  }
  if (assetGeneration !== generation) return

  sampleState.status = 'loading'
  try {
    // Masked identity only: never the disclosure command, never an access event.
    const ref = await getCbrneSampleRef(state.assetId, sampleId)
    if (assetGeneration !== generation || requestGeneration !== sampleGeneration) return
    sampleState.ref = ref
    sampleState.status = 'success'
    emitBenchmarkResourceResolution('canonical-hit', {
      assetId: state.assetId,
      sampleId,
    })
  } catch (error) {
    if (assetGeneration !== generation || requestGeneration !== sampleGeneration) return
    sampleState.errorMessage = error instanceof Error ? error.message : '样本服务暂时不可用'
    const isMissing =
      error instanceof ApiRequestError && (error.status === 404 || error.status === 422)
    sampleState.status = isMissing ? 'not-found' : 'error'
    emitBenchmarkResourceResolution(isMissing ? 'sample-not-found' : 'service-failure', {
      assetId: state.assetId,
      sampleId,
    })
  }
}

function resetSampleState(sampleId: string) {
  sampleGeneration += 1
  sampleState.sampleId = String(sampleId || '').trim()
  sampleState.status = 'idle'
  sampleState.ref = null
  sampleState.errorMessage = ''
}

async function retrySample() {
  if (state.status !== 'success' || !sampleState.sampleId) return
  await loadSample(sampleState.sampleId, generation)
}

async function retry() {
  await load(state.assetId)
}

function returnToAssetResource() {
  if (!state.assetId) return
  void router.replace(assetRoute.value)
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? value : new Date(timestamp).toLocaleString('zh-CN')
}

function goToEvaluations() {
  void router.push({ name: 'benchmark', query: { view: 'expert', tab: 'evaluations' } })
}
</script>

<style scoped>
.asset-resource {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.asset-resource__nav {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
}

.asset-resource__back,
.asset-resource__action {
  color: var(--accent-blue);
  font-weight: 700;
  text-decoration: none;
}

.asset-resource__back:hover,
.asset-resource__action:hover {
  text-decoration: underline;
}

.asset-resource__back:focus-visible,
.asset-resource__action:focus-visible {
  border-radius: var(--radius-sm);
  outline: 3px solid rgba(21, 101, 192, 0.28);
  outline-offset: 3px;
}

.asset-resource__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 24px;
  border: 1px solid var(--border-color);
  border-left: 4px solid var(--accent-blue);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.asset-resource__eyebrow,
.asset-resource__state-label {
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.asset-resource__header h1,
.asset-resource__message h2 {
  margin: 6px 0 0;
  color: var(--text-primary);
}

.asset-resource__header h1 {
  font-size: 26px;
}

.asset-resource__header p,
.asset-resource__message p,
.asset-resource__loading p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.asset-resource__header > code {
  max-width: min(46%, 560px);
  padding: 8px 10px;
  border: 1px solid #dbe5f1;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.asset-resource__state {
  min-height: 260px;
}

.asset-resource__content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.asset-resource__facts {
  padding: 20px 24px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.asset-resource__facts-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.asset-resource__facts h2 {
  margin: 6px 0 0;
}

.asset-resource__mode {
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.asset-resource__facts dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 20px 0;
}

.asset-resource__facts dl > div {
  min-width: 0;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.asset-resource__facts dt {
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.asset-resource__facts dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.asset-resource__facts summary {
  color: var(--accent-blue);
  cursor: pointer;
  font-weight: 700;
}

.asset-resource__facts pre {
  max-height: 360px;
  margin: 12px 0 0;
  padding: 14px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.asset-resource__loading,
.asset-resource__message {
  display: flex;
  min-height: 260px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 32px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  text-align: center;
}

.asset-resource__sample-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.asset-resource__sample-status .asset-resource__spinner {
  margin-bottom: 0;
  flex: 0 0 auto;
}

.asset-resource__sample-status p {
  margin: 0;
  color: var(--text-secondary);
}

.asset-resource__spinner {
  width: 28px;
  height: 28px;
  margin-bottom: 14px;
  border: 3px solid var(--bg-tertiary);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: asset-resource-spin 0.8s linear infinite;
}

.asset-resource__message.is-not-found {
  border-style: dashed;
}

.asset-resource__message.is-error {
  border-color: rgba(198, 40, 40, 0.32);
}

.asset-resource__message.is-error .asset-resource__state-label {
  color: var(--accent-red);
}

button.asset-resource__action,
a.asset-resource__action {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  margin-top: 18px;
  padding: 0 14px;
  border: 1px solid var(--accent-blue);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  cursor: pointer;
  font: inherit;
}

button.asset-resource__action:active,
a.asset-resource__action:active {
  background: var(--bg-secondary);
}

@keyframes asset-resource-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .asset-resource__spinner {
    animation: none;
  }
}

@media (max-width: 720px) {
  .asset-resource__header {
    flex-direction: column;
  }

  .asset-resource__header > code {
    max-width: 100%;
  }

  .asset-resource__facts-heading {
    flex-direction: column;
  }

  .asset-resource__facts dl {
    grid-template-columns: 1fr;
  }
}
</style>
