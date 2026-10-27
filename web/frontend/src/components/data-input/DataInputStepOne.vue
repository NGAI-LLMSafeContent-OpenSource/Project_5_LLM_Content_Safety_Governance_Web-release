<template>
  <div class="step-one-hero">
    <div class="step-one-hero__copy">
      <h1 class="step-one-hero__title">训练语料构建</h1>
      <p class="step-one-hero__desc">
        价值轨与风险轨分轨绑定语料：价值侧用课题一 value_qa，风险侧用课题二静态兜底（也可再跑
        neuron）。也可上传自定义文件。
      </p>
    </div>
    <div class="step-one-status-cards">
      <div
        v-for="card in statusCards"
        :key="card.key"
        class="step-one-status-card"
        :class="`step-one-status-card--${card.tone}`"
      >
        <span class="step-one-status-card__label">{{ card.label }}</span>
        <span class="step-one-status-card__sub">{{ card.sub }}</span>
      </div>
    </div>
  </div>

  <div class="input-section">
    <div class="input-section-title">
      <span class="input-section-title__emoji" aria-hidden="true">🗂️</span>
      <span>语料列表</span>
    </div>
    <p class="corpus-hint">请分别为价值轨、风险轨选择语料。价值侧对接课题一、风险侧对接课题二</p>
    <div class="corpus-toolbar">
      <button
        type="button"
        class="btn btn-secondary btn-sm"
        :disabled="corpusCatalogLoading"
        @click="$emit('refresh-corpus-catalog')"
      >
        {{ corpusCatalogLoading ? '刷新中…' : '刷新预跑列表' }}
      </button>
      <span v-if="corpusCatalogMessage" class="corpus-toolbar__msg">
        {{ corpusCatalogMessage }}
      </span>
    </div>

    <div class="corpus-track-grid">
      <div class="corpus-track-panel corpus-track-panel--value">
        <div class="corpus-track-panel__head">
          <strong>价值侧语料</strong>
          <button
            v-if="valueSelectedCorpus"
            type="button"
            class="btn btn-secondary btn-sm"
            @click="$emit('clear-value-corpus')"
          >
            取消已选
          </button>
        </div>
        <div v-if="valueSelectedCorpus" class="corpus-selected">
          <strong>已选：</strong>
          {{ valueSelectedCorpus.name }}
          <span class="corpus-pill">{{ valueSelectedCorpus.sourceLabel }}</span>
          <span class="corpus-pill">{{ valueSelectedCorpus.total }} 条</span>
          <span class="corpus-pill">价值轨</span>
        </div>
        <div v-if="corpusCatalogLoading && !valueCatalog.length" class="corpus-empty">
          正在加载价值语料…
        </div>
        <div v-else-if="!valueCatalog.length" class="corpus-empty">
          暂无课题一 value_qa 预跑资产，请先导入或改用上传。
        </div>
        <div v-else class="corpus-list">
          <button
            v-for="item in valueCatalog"
            :key="item.assetId"
            type="button"
            class="corpus-card"
            :class="{
              'is-selected': valueSelectedCorpus?.assetId === item.assetId,
              'is-loading': corpusSelectLoading && selectingAssetId === item.assetId,
            }"
            :disabled="corpusSelectLoading"
            @click="onSelectCorpus(item.assetId, item.kind)"
          >
            <div class="corpus-card__head">
              <span class="corpus-card__name">{{ item.name }}</span>
              <span class="corpus-pill">{{ item.sourceLabel }}</span>
            </div>
            <div class="corpus-card__meta">
              <span>{{ item.trackHint || '价值轨' }}</span>
              <span v-if="item.sampleCount">约 {{ item.sampleCount }} 条</span>
            </div>
            <p class="corpus-card__desc">{{ item.description }}</p>
          </button>
        </div>
      </div>

      <div class="corpus-track-panel corpus-track-panel--risk">
        <div class="corpus-track-panel__head">
          <strong>风险侧语料</strong>
          <button
            v-if="riskSelectedCorpus"
            type="button"
            class="btn btn-secondary btn-sm"
            @click="$emit('clear-risk-corpus')"
          >
            取消已选
          </button>
        </div>
        <div v-if="riskSelectedCorpus" class="corpus-selected corpus-selected--risk">
          <strong>已选：</strong>
          {{ riskSelectedCorpus.name }}
          <span class="corpus-pill">{{ riskSelectedCorpus.sourceLabel }}</span>
          <span class="corpus-pill">{{ riskSelectedCorpus.total }} 条</span>
          <span class="corpus-pill">风险轨 · 静态预跑</span>
        </div>
        <div v-if="corpusCatalogLoading && !riskCatalog.length" class="corpus-empty">
          正在加载风险语料…
        </div>
        <div v-else-if="!riskCatalog.length" class="corpus-empty">
          暂无课题二静态兜底语料，请确认 web/backend/data/input_corpora 下有 dynbench jsonl。
        </div>
        <div v-else class="corpus-list">
          <button
            v-for="item in riskCatalog"
            :key="item.assetId"
            type="button"
            class="corpus-card corpus-card--risk"
            :class="{
              'is-selected': riskSelectedCorpus?.assetId === item.assetId,
              'is-loading': corpusSelectLoading && selectingAssetId === item.assetId,
            }"
            :disabled="corpusSelectLoading"
            @click="onSelectCorpus(item.assetId, item.kind)"
          >
            <div class="corpus-card__head">
              <span class="corpus-card__name">{{ item.name }}</span>
              <span class="corpus-pill">{{ item.sourceLabel }}</span>
            </div>
            <div class="corpus-card__meta">
              <span>{{ item.trackHint || '风险轨' }}</span>
              <span v-if="item.sampleCount">约 {{ item.sampleCount }} 条</span>
            </div>
            <p class="corpus-card__desc">{{ item.description }}</p>
          </button>
        </div>
      </div>
    </div>
  </div>

  <div class="input-section">
    <div class="input-section-title">
      <el-icon class="icon" aria-hidden="true"><FolderOpened /></el-icon>
      <span>上传自定义语料</span>
    </div>
    <input
      ref="fileInputRef"
      class="file-upload-input"
      type="file"
      multiple
      :accept="datasetUploadAccept"
      @change="$emit('file-select', $event)"
    />
    <div
      class="definition-upload-box definition-upload-box--demo"
      :class="{ 'is-dragover': isDraggingFiles }"
      @click="openFilePicker"
      @dragenter.prevent="$emit('drag-state', true)"
      @dragover.prevent="$emit('drag-state', true)"
      @dragleave.prevent="$emit('drag-state', false)"
      @drop.prevent="$emit('file-drop', $event)"
    >
      <el-icon class="definition-upload-cloud" aria-hidden="true"><UploadFilled /></el-icon>
      <span class="definition-upload-title">拖拽文件到这里，或点击上传</span>
      <span class="definition-upload-desc">
        支持 {{ datasetUploadSupportLabel }}；上传后会替换所选轨道的预跑语料。单文件不超过 500MB
      </span>
    </div>

    <div class="definition-source-stack">
      <div v-for="item in uploadedFiles" :key="item.id" class="definition-source-row">
        <el-icon class="definition-source-row-icon" aria-hidden="true"><Document /></el-icon>
        <div class="upload-parse-meta">
          <span class="definition-source-name">{{ item.file.name }}</span>
          <span class="upload-parse-meta__sub">
            {{ formatFileSize(item.file.size) }}
            <template v-if="item.parseStatus === 'parsed'">
              · 已解析 {{ item.recordCount }} 条切片
            </template>
            <template v-else-if="item.parseStatus === 'failed'">
              · 解析失败：{{ item.parseReason || '无法提取文本' }}
            </template>
            <template v-else-if="item.parseStatus === 'parsing'">· 解析中…</template>
          </span>
        </div>
        <button type="button" aria-label="移除文档" @click="$emit('remove-file', item.id)">
          ×
        </button>
      </div>
      <div v-if="uploadParseLoading" class="definition-source-hint">正在上传并解析文档...</div>
    </div>

    <div v-if="uploadedFiles.length" class="definition-parsed-count">
      当前已解析 {{ parsedUploadCount }} / {{ uploadedFiles.length }} 个文件
    </div>
  </div>

  <div class="input-section">
    <DataInputTopic1ToolPanel
      :catalog="topic1ToolCatalog"
      :loading="topic1ToolCatalogLoading"
      :error="topic1ToolCatalogError"
      @refresh="$emit('refresh-topic1-tools')"
    />
  </div>
</template>

<script setup lang="ts">
import { Document, FolderOpened, UploadFilled } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import DataInputTopic1ToolPanel from '@/components/data-input/DataInputTopic1ToolPanel.vue'
import { datasetUploadAccept, datasetUploadSupportLabel } from '@/utils/dataInputConfig'
import type { DataInputTrack, DatasetFormModel } from '@/utils/dataInputConfig'
import type { DatasetUploadItem } from '@/stores/input'
import type { Topic1CorpusToolCatalogResult } from '@/types/topic1CorpusTools'

export interface CorpusCatalogItemView {
  assetId: string
  name: string
  kind: string
  sourceLabel: string
  sampleCount: number
  ready: boolean
  description: string
  trackHint: string
  track?: 'value' | 'risk' | ''
}

export interface SelectedCorpusView {
  assetId: string
  name: string
  kind: string
  sourceLabel: string
  total: number
}

const props = defineProps<{
  datasetForm: DatasetFormModel
  customCorpusTrack: DataInputTrack
  uploadedFiles: DatasetUploadItem[]
  isDraggingFiles: boolean
  uploadParseLoading?: boolean
  corpusCatalog: CorpusCatalogItemView[]
  corpusCatalogLoading: boolean
  corpusCatalogMessage: string
  valueSelectedCorpus: SelectedCorpusView | null
  riskSelectedCorpus: SelectedCorpusView | null
  corpusSelectLoading: boolean
  topic1ToolCatalog: Topic1CorpusToolCatalogResult | null
  topic1ToolCatalogLoading: boolean
  topic1ToolCatalogError: string
  statusCards?: Array<{ key: string; label: string; sub: string; tone: 'ok' | 'warn' | 'info' }>
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectingAssetId = ref('')
const statusCards = computed(() =>
  (props.statusCards ?? []).filter(
    (card) => card.key === 'value-corpus' || card.key === 'risk-corpus',
  ),
)
const parsedUploadCount = computed(
  () => props.uploadedFiles.filter((item) => item.parseStatus === 'parsed').length,
)
const valueCatalog = computed(() =>
  props.corpusCatalog.filter(
    (item) =>
      item.track === 'value' ||
      item.kind === 'value_qa' ||
      (!item.track && item.kind !== 'risk_static_dynbench' && item.kind !== 'topic2_prerun'),
  ),
)
const riskCatalog = computed(() =>
  props.corpusCatalog.filter(
    (item) =>
      item.track === 'risk' ||
      item.kind === 'risk_static_dynbench' ||
      item.kind === 'topic2_prerun',
  ),
)

const emit = defineEmits<{
  (e: 'update:datasetForm', value: DatasetFormModel): void
  (e: 'update:customCorpusTrack', value: DataInputTrack): void
  (e: 'drag-state', value: boolean): void
  (e: 'file-select', event: Event): void
  (e: 'file-drop', event: DragEvent): void
  (e: 'remove-file', fileId: string): void
  (e: 'refresh-corpus-catalog'): void
  (e: 'select-corpus', payload: { assetId: string; kind: string }): void
  (e: 'clear-value-corpus'): void
  (e: 'clear-risk-corpus'): void
  (e: 'refresh-topic1-tools'): void
}>()

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function onSelectCorpus(assetId: string, kind: string) {
  selectingAssetId.value = assetId
  emit('select-corpus', { assetId, kind })
}
</script>

<style scoped>
.step-one-hero {
  display: grid;
  gap: 14px;
  margin-bottom: 16px;
  border: 1px solid rgba(21, 101, 192, 0.12);
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
  padding: 16px;
}

.step-one-hero__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.25;
}

.step-one-hero__desc {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.step-one-status-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.step-one-status-card {
  border-radius: 12px;
  background: #f7f9fb;
  border: 1px solid #cfd8e3;
  padding: 10px 12px;
}

.step-one-status-card__label {
  display: block;
  color: #8a96a6;
  font-size: 12px;
  font-weight: 600;
}

.step-one-status-card__sub {
  display: block;
  margin-top: 4px;
  color: #8a96a6;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
}

.step-one-status-card--ok {
  background: rgba(255, 255, 255, 0.88);
  border-color: #2e7d32;
  box-shadow: inset 3px 0 0 #2e7d32;
}

.step-one-status-card--ok .step-one-status-card__label,
.step-one-status-card--ok .step-one-status-card__sub {
  color: var(--text-primary);
}

.step-one-status-card--info {
  box-shadow: inset 3px 0 0 #1565c0;
}

.corpus-hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: #5c7188;
}

.corpus-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.corpus-toolbar__msg {
  font-size: 12px;
  color: #6b86a5;
}

.corpus-track-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.corpus-track-panel {
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}

.corpus-track-panel--value {
  box-shadow: inset 3px 0 0 #1565c0;
}

.corpus-track-panel--risk {
  box-shadow: inset 3px 0 0 #c62828;
}

.corpus-track-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.corpus-track-panel__head strong {
  font-size: 14px;
  color: #1a2a44;
}

.corpus-selected {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #eef5fd;
  border: 1px solid #c5d5ea;
  font-size: 13px;
  color: #1a2a44;
}

.corpus-selected--risk {
  background: #fff5f5;
  border-color: #f0c7c7;
}

.corpus-empty {
  padding: 16px;
  border: 1px dashed #cbd8e7;
  border-radius: 10px;
  color: #6b86a5;
  font-size: 13px;
}

.corpus-list {
  display: grid;
  gap: 10px;
}

.corpus-card {
  text-align: left;
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.corpus-card:hover:not(:disabled) {
  border-color: #90caf9;
}

.corpus-card.is-selected {
  border-color: #1565c0;
  box-shadow: inset 3px 0 0 #1565c0;
  background: #f7faff;
}

.corpus-card--risk.is-selected {
  border-color: #c62828;
  box-shadow: inset 3px 0 0 #c62828;
  background: #fff8f8;
}

.corpus-card:disabled {
  opacity: 0.7;
  cursor: wait;
}

.corpus-card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}

.corpus-card__name {
  font-size: 14px;
  font-weight: 700;
  color: #1a2a44;
}

.corpus-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #5c7188;
  margin-bottom: 6px;
}

.corpus-card__desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #4a6380;
}

.corpus-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  background: #eef4fb;
  color: #1565c0;
}

.upload-parse-meta {
  min-width: 0;
}

.upload-parse-meta__sub {
  display: block;
  margin-top: 2px;
  color: #6b86a5;
  font-size: 12px;
  line-height: 1.4;
}

.file-upload-input {
  display: none;
}

.custom-corpus-track {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 4px;
  width: min(360px, 100%);
  padding: 4px;
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  background: #f5f8fc;
}

.custom-corpus-track__option {
  min-height: 36px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #5c7188;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.custom-corpus-track__option--value.active {
  background: #fff;
  color: #1565c0;
  box-shadow: inset 0 0 0 1px #90caf9;
}

.custom-corpus-track__option--risk.active {
  background: #fff;
  color: #c62828;
  box-shadow: inset 0 0 0 1px #ef9a9a;
}

@media (max-width: 960px) {
  .step-one-status-cards,
  .corpus-track-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .step-one-status-cards {
    grid-template-columns: 1fr;
  }
}
</style>
