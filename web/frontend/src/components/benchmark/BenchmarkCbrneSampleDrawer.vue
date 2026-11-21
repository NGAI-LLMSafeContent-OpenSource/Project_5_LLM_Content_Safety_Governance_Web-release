<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="78%"
    append-to-body
    destroy-on-close
    class="cbrne-sample-drawer-host"
    modal-class="cbrne-sample-drawer-modal"
    @update:model-value="handleVisibilityChange"
    @opened="openDrawerSession"
    @closed="handleClosed"
  >
    <div v-if="asset" class="cbrne-sample-drawer">
      <section class="drawer-summary">
        <div>
          <h3>{{ asset.name }}</h3>
          <p>
            列表仅展示脱敏预览与稳定样本引用。样本全文需显式点击「查看全文并记录访问」后加载；关闭抽屉会清除全文状态，不会写回列表或
            URL。
          </p>
        </div>
        <dl>
          <div>
            <dt>Asset</dt>
            <dd class="mono">{{ asset.asset_id }}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{{ assetVersionLabel }}</dd>
          </div>
          <div>
            <dt>Refs</dt>
            <dd>{{ total }}</dd>
          </div>
        </dl>
      </section>

      <el-alert
        v-if="refsErrorMessage"
        type="warning"
        :title="refsErrorMessage"
        :closable="false"
        show-icon
        role="alert"
        aria-live="assertive"
      />

      <section class="sample-layout">
        <div class="sample-table-wrap">
          <el-table
            v-loading="isLoading"
            :data="refs"
            height="520"
            size="small"
            row-key="sample_id"
            :current-row-key="selectedRef?.sample_id"
            highlight-current-row
            @row-click="handleRowSelect"
          >
            <el-table-column prop="sample_id" label="Sample ID" min-width="140" />
            <el-table-column prop="label" label="Label" width="90" />
            <el-table-column prop="cbrne_category" label="Category" min-width="120" />
            <el-table-column prop="source" label="Source" min-width="110" />
            <el-table-column prop="exposure_tier" label="Tier" width="70" />
            <el-table-column prop="evaluator_relative_difficulty" label="Difficulty" width="90" />
            <el-table-column
              prop="text_preview"
              label="Preview"
              min-width="160"
              show-overflow-tooltip
            />
            <el-table-column label="操作" width="190" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  link
                  :loading="isDisclosureLoading(row.sample_id)"
                  :disabled="isDisclosureLoading(row.sample_id)"
                  :aria-label="disclosureButtonLabel(row.sample_id)"
                  data-testid="cbrne-open-detail"
                  @click.stop="loadDetail(row)"
                >
                  {{ disclosureButtonLabel(row.sample_id) }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="sample-pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              layout="total, prev, pager, next"
              :total="total"
              :page-sizes="[10, 20, 50]"
              @current-change="handlePageChange"
              @size-change="handlePageSizeChange"
            />
          </div>
        </div>

        <aside v-loading="isLoadingDetail" class="sample-detail" data-testid="cbrne-sample-detail">
          <div aria-live="polite" aria-atomic="true">
            <p v-if="disclosureState.status === 'loading'" role="status">
              正在披露样本全文并记录访问…
            </p>
            <p v-else-if="disclosureState.status === 'success'" role="status">
              样本全文已披露，访问记录已保存。
            </p>
          </div>
          <el-alert
            v-if="disclosureState.status === 'error'"
            type="warning"
            :title="disclosureState.errorMessage"
            :closable="false"
            show-icon
            role="alert"
            aria-live="assertive"
          >
            <template #default>
              <el-button type="primary" link @click="retryDisclosure">
                重试查看全文并记录访问
              </el-button>
            </template>
          </el-alert>
          <div v-if="!selectedRef && !selectedDetail" class="sample-detail__empty">
            <h4>受控样本详情</h4>
            <p>点击右侧「查看全文并记录访问」后才会请求并展示样本全文与原始/规范化字段。</p>
          </div>

          <div
            v-else-if="selectedRef && !selectedDetail"
            class="sample-detail__overview"
            data-testid="cbrne-masked-ref"
          >
            <div class="sample-detail__header">
              <div>
                <h4>{{ selectedRef.sample_id }}</h4>
                <span>脱敏引用 · 资产版本 {{ assetVersionLabel }}</span>
              </div>
              <el-tag size="small" type="info">masked</el-tag>
            </div>
            <dl class="detail-meta">
              <div>
                <dt>标签</dt>
                <dd>{{ selectedRef.label || '-' }}</dd>
              </div>
              <div>
                <dt>类别</dt>
                <dd>{{ selectedRef.cbrne_category || '-' }}</dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>{{ selectedRef.source || '-' }}</dd>
              </div>
              <div>
                <dt>Tier</dt>
                <dd>{{ selectedRef.exposure_tier || '-' }}</dd>
              </div>
              <div>
                <dt>评估器相对难度</dt>
                <dd>{{ selectedRef.evaluator_relative_difficulty }}</dd>
              </div>
            </dl>
            <div class="detail-block">
              <b>脱敏摘要</b>
              <p>{{ selectedRef.text_preview || '（无可用摘要）' }}</p>
            </div>
            <el-button
              size="small"
              type="primary"
              :loading="isDisclosureLoading(selectedRef.sample_id)"
              :disabled="isDisclosureLoading(selectedRef.sample_id)"
              @click="loadDetail(selectedRef)"
            >
              查看全文并记录访问
            </el-button>
          </div>

          <template v-else-if="selectedDetail">
            <div class="sample-detail__overview">
              <div class="sample-detail__header">
                <div>
                  <h4>{{ selectedDetail.sample_id }}</h4>
                  <span>v{{ selectedDetail.asset_version }}</span>
                </div>
                <el-tag size="small" type="warning">full text</el-tag>
              </div>
              <dl class="detail-meta">
                <div>
                  <dt>Access Action</dt>
                  <dd>{{ selectedDetail.access_event.action_type }}</dd>
                </div>
                <div>
                  <dt>Accessed At</dt>
                  <dd>{{ selectedDetail.access_event.accessed_at }}</dd>
                </div>
              </dl>
            </div>

            <div class="detail-block" data-testid="cbrne-full-text">
              <b>全文</b>
              <p>{{ selectedDetail.full_text }}</p>
            </div>

            <div class="detail-block">
              <b>原始字段（raw）</b>
              <pre>{{ formatJson(selectedDetail.raw) }}</pre>
            </div>

            <div class="detail-block">
              <b>平台规范化字段（platform_normalized）</b>
              <pre>{{ formatJson(selectedDetail.platform_normalized) }}</pre>
            </div>
          </template>
        </aside>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { discloseCbrneSample, getCbrneSampleRefs } from '@/api/benchmark'
import {
  createCbrneSampleDrawerSession,
  type CbrneSampleDrawerSessionState,
} from '@/composables/benchmark/useCbrneSampleDisclosure'
import type {
  BenchmarkArtifactItem,
  BenchmarkCbrneSampleRefItem,
  BenchmarkCbrneSampleRefResponse,
} from '@/types'
import { createUuid } from '@/utils/uuid'

const props = defineProps<{
  modelValue: boolean
  asset: BenchmarkArtifactItem | null
  /** Masked sample selected by the route; never contains full text (#175). */
  focusSample?: BenchmarkCbrneSampleRefResponse | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const drawerSessionState = reactive<CbrneSampleDrawerSessionState>({
  isOpen: false,
  assetId: '',
  refsStatus: 'idle',
  refs: [],
  refsErrorMessage: '',
  total: 0,
  currentPage: 1,
  pageSize: 20,
  selectedRef: null,
  disclosure: {
    status: 'idle',
    sampleId: '',
    detail: null,
    errorMessage: '',
  },
})
const drawerSession = createCbrneSampleDrawerSession({
  state: drawerSessionState,
  listSampleRefs: getCbrneSampleRefs,
  discloseSample: discloseCbrneSample,
  createRequestId: createUuid,
})
const refs = computed(() => drawerSessionState.refs)
const isLoading = computed(() => drawerSessionState.refsStatus === 'loading')
const refsErrorMessage = computed(() => drawerSessionState.refsErrorMessage)
const total = computed(() => drawerSessionState.total)
const currentPage = computed({
  get: () => drawerSessionState.currentPage,
  set: (value: number) => {
    drawerSessionState.currentPage = value
  },
})
const pageSize = computed({
  get: () => drawerSessionState.pageSize,
  set: (value: number) => {
    drawerSessionState.pageSize = value
  },
})
const disclosureState = drawerSessionState.disclosure
const selectedRef = computed(() => drawerSessionState.selectedRef)
const selectedDetail = computed(() => disclosureState.detail)
const isLoadingDetail = computed(() => disclosureState.status === 'loading')

const drawerTitle = computed(() =>
  props.asset ? `CBRNE 受控详情 · ${props.asset.name}` : 'CBRNE 受控详情',
)
const assetVersionLabel = computed(() => {
  const version = props.asset?.manifest?.version
  return typeof version === 'string' || typeof version === 'number' ? String(version) : '-'
})

function formatJson(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2)
}

async function openDrawerSession() {
  if (!props.asset) return
  await drawerSession.restore(props.asset.asset_id, currentPage.value, props.focusSample ?? null)
}

function handleRowSelect(row: BenchmarkCbrneSampleRefItem) {
  drawerSession.selectSample(row)
}

async function loadDetail(row: BenchmarkCbrneSampleRefItem) {
  if (!props.asset) {
    return
  }
  drawerSession.selectSample(row)
  await drawerSession.disclose(row.sample_id)
}

async function retryDisclosure() {
  await drawerSession.retry()
}

function isDisclosureLoading(sampleId: string) {
  return disclosureState.status === 'loading' && disclosureState.sampleId === sampleId
}

function disclosureButtonLabel(sampleId: string) {
  return disclosureState.status === 'success' && disclosureState.sampleId === sampleId
    ? '再次查看全文并记录访问'
    : '查看全文并记录访问'
}

function handlePageChange(page: number) {
  void drawerSession.goToPage(page)
}

function handlePageSizeChange(size: number) {
  void drawerSession.changePageSize(size)
}

function resetDrawerSession() {
  drawerSession.close()
}

function handleVisibilityChange(value: boolean) {
  if (!value) resetDrawerSession()
  emit('update:modelValue', value)
}

function handleClosed() {
  resetDrawerSession()
}

watch(
  () => props.asset?.asset_id,
  (assetId, previousAssetId) => {
    if (assetId !== previousAssetId) {
      if (assetId && props.modelValue) void drawerSession.switchAsset(assetId)
      else resetDrawerSession()
    }
  },
)

watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) resetDrawerSession()
  },
)

watch(
  () => props.focusSample,
  (focusSample) => {
    if (!focusSample || !props.modelValue || !props.asset) return
    // Route-level sample changes start masked again; never disclose here.
    void drawerSession.restore(props.asset.asset_id, 1, focusSample)
  },
)

onBeforeUnmount(resetDrawerSession)
</script>

<style scoped>
.cbrne-sample-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.drawer-summary h3 {
  margin: 0 0 6px;
  font-size: 16px;
}

.drawer-summary p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  max-width: 52rem;
  line-height: 1.5;
}

.drawer-summary dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(100px, 1fr));
  gap: 10px 16px;
  margin: 0;
}

.drawer-summary dt {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.drawer-summary dd {
  margin: 2px 0 0;
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}

.sample-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.9fr);
  gap: 14px;
  align-items: start;
}

.sample-table-wrap,
.sample-detail {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.sample-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 10px 12px;
}

.sample-detail {
  min-height: 520px;
  padding: 14px;
}

.sample-detail__empty p {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.sample-detail__header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.sample-detail__header h4 {
  margin: 0 0 4px;
}

.sample-detail__header span,
.detail-meta dt {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.detail-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin: 0 0 12px;
}

.detail-meta dd {
  margin: 2px 0 0;
  font-size: 13px;
  word-break: break-all;
}

.detail-block {
  margin-top: 12px;
}

.detail-block b {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
}

.detail-block p,
.detail-block pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.5;
}

.detail-block pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  max-height: 220px;
  overflow: auto;
}

@media (max-width: 1100px) {
  .sample-layout {
    grid-template-columns: 1fr;
  }

  .drawer-summary {
    flex-direction: column;
  }
}
</style>

<!--
  Drawer panel is absolute inside el-overlay. Offset only the teleported overlay so
  AppHeader stays visible/clickable; the panel then fills the remaining viewport.
-->
<style>
.cbrne-sample-drawer-modal.el-overlay {
  /* Match AppHeader heights: 64px desktop, 56px ≤900px. */
  --cbrne-drawer-header-offset: 64px;
  top: var(--cbrne-drawer-header-offset);
  height: calc(100% - var(--cbrne-drawer-header-offset));
  bottom: auto;
}

@media (max-width: 900px) {
  .cbrne-sample-drawer-modal.el-overlay {
    --cbrne-drawer-header-offset: 56px;
  }
}
</style>
