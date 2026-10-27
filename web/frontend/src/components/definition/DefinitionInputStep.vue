<template>
  <section class="step-panel active">
    <div class="definition-input-subtabs">
      <button
        type="button"
        class="definition-input-subtab"
        :class="{ active: activePane === 'mining' }"
        @click="selectPane('mining')"
      >
        指标挖掘
      </button>
      <button
        type="button"
        class="definition-input-subtab"
        :class="{ active: activePane === 'history' }"
        @click="selectPane('history')"
      >
        历史记录
        <span v-if="historyItems.length" class="definition-input-subtab-count">
          {{ historyItems.length }}
        </span>
      </button>
    </div>

    <div v-show="activePane === 'mining'" class="input-section definition-agent-demo">
      <div class="input-section-title">
        <span class="icon">☁️</span>
        <span>智能体演示</span>
      </div>

      <div class="definition-demo-subtitle">上传政策文件、项目文档或指标说明文档</div>

      <label
        class="definition-upload-box definition-upload-box--demo"
        :class="{ 'is-dragover': isDragover }"
        @dragenter.prevent="isDragover = true"
        @dragover.prevent="isDragover = true"
        @dragleave.prevent="isDragover = false"
        @drop.prevent="handleFileDrop"
      >
        <input
          class="definition-upload-input"
          type="file"
          multiple
          accept=".txt,.md,.json,.csv,.html,.htm,.docx,.pptx,.xlsx,.pdf,text/plain,text/html,application/json,application/pdf"
          @change="handleFileChange"
        />
        <span class="definition-upload-cloud">☁️</span>
        <span class="definition-upload-title">拖拽文件到这里，或点击上传</span>
        <span class="definition-upload-desc">
          单次最多 30 个文件，支持文本、PDF、docx、xlsx、pptx、html 等格式
        </span>
      </label>

      <div class="definition-source-stack">
        <div v-for="doc in state.uploadedDocuments" :key="doc.id" class="definition-source-row">
          <span class="definition-source-row-icon">📄</span>
          <span class="definition-source-name">{{ doc.name }}</span>
          <button type="button" aria-label="移除文档" @click="removeUploadedDocument(doc.id)">
            ×
          </button>
        </div>
        <div v-if="isUploading" class="definition-source-hint">正在上传并解析文档...</div>
      </div>

      <div class="form-group definition-demo-field">
        <label class="form-label">文档链接</label>
        <textarea
          class="definition-link-textarea"
          :value="state.webLinksText"
          rows="5"
          placeholder="可填写多个文档链接，支持换行、空格、逗号或分号分隔&#10;https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm&#10;https://www.nda.gov.cn/sjj/ywpd/sjzg/0922/xxx.pdf"
          @input="updateField('webLinksText', $event)"
        ></textarea>
      </div>

      <div class="definition-parsed-count">
        当前已解析 {{ state.uploadedDocuments.length }} / 30 个文件
      </div>

      <div class="form-group definition-demo-field">
        <label class="form-label">挖掘要求</label>
        <select :value="state.miningDemand" @change="updateField('miningDemand', $event)">
          <option v-for="option in miningDemandOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <div class="definition-demo-actions">
        <button class="btn btn-primary" type="button" @click="$emit('next')">启动智能体挖掘</button>
      </div>
    </div>

    <div v-show="activePane === 'history'" class="definition-history-pane">
      <div class="definition-history-pane__intro">
        <strong>已保存的挖掘指标</strong>
      </div>

      <div v-if="miningState.historyLoading" class="definition-history-pane__empty">
        正在读取历史记录…
      </div>

      <div v-else-if="miningState.historyError" class="definition-history-pane__empty">
        <span>{{ miningState.historyError }}</span>
        <button class="btn btn-secondary btn-sm" type="button" @click="$emit('refresh-history')">
          重新加载
        </button>
      </div>

      <div v-else-if="!historyItems.length" class="definition-history-pane__empty">
        暂无历史记录。完成挖掘并在「指标体系浏览」中保存后，会出现在这里。
      </div>

      <ul v-else class="definition-history-pane__list">
        <li v-for="item in historyItems" :key="item.task_id">
          <div class="definition-history-pane__item-main">
            <strong>{{ item.title }}</strong>
            <span>{{ item.meta }}</span>
          </div>
          <button
            class="btn btn-secondary btn-sm"
            type="button"
            @click="$emit('view-history', item.task_id)"
          >
            查看指标
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { parseMiningInputFiles } from '@/api/definition'
import type { DefinitionFormState, DefinitionMiningState } from '@/types/definition'
import type { DefinitionTabConfig } from '@/utils/definitionConfig'

type InputPane = 'mining' | 'history'

const props = defineProps<{
  config: DefinitionTabConfig
  state: DefinitionFormState
  miningState: DefinitionMiningState
  formatTimestamp?: (value?: string | null) => string
}>()

const emit = defineEmits<{
  (e: 'update:state', value: DefinitionFormState): void
  (e: 'next'): void
  (e: 'view-history', taskId: string): void
  (e: 'refresh-history'): void
}>()

const activePane = ref<InputPane>('mining')
const isUploading = ref(false)
const isDragover = ref(false)

const miningDemandOptions = [{ value: 'level3', label: '三级指标挖掘' }]

const historyItems = computed(() => {
  const formatter = props.formatTimestamp || ((value?: string | null) => value || '')
  return (props.miningState?.history || []).map((item) => {
    const time = formatter(item.saved_at || item.finished_at || item.created_at)
    const count = item.candidate_count ?? item.stats?.candidate_count ?? 0
    return {
      task_id: item.task_id,
      title: item.history_title || `挖掘记录 ${item.task_id.slice(0, 8)}`,
      meta: `${time || '未知时间'} · 候选 ${count} 条`,
    }
  })
})

function selectPane(pane: InputPane) {
  activePane.value = pane
  if (pane === 'history') emit('refresh-history')
}

function updateField(field: keyof DefinitionFormState, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  emit('update:state', { ...props.state, [field]: target.value })
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  void uploadFiles(Array.from(target.files ?? []))
  target.value = ''
}

function handleFileDrop(event: DragEvent) {
  isDragover.value = false
  void uploadFiles(Array.from(event.dataTransfer?.files ?? []))
}

async function uploadFiles(files: File[]) {
  if (!files.length) return

  isUploading.value = true
  try {
    const result = await parseMiningInputFiles(files)
    const existingIds = new Set(props.state.uploadedDocuments.map((doc) => doc.id))
    const merged = [
      ...props.state.uploadedDocuments,
      ...result.files.filter((doc) => !existingIds.has(doc.id)),
    ]
    emit('update:state', { ...props.state, uploadedDocuments: merged })
    if (result.failures?.length) {
      ElMessage.warning(
        `已接收 ${result.count} 个文档，其中 ${result.failures.length} 个文件文本提取不完整，可补充文档链接或文本版材料。`,
      )
    } else {
      ElMessage.success(`已解析 ${result.count} 个文档`)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文档上传解析失败')
  } finally {
    isUploading.value = false
  }
}

function removeUploadedDocument(id: number) {
  emit('update:state', {
    ...props.state,
    uploadedDocuments: props.state.uploadedDocuments.filter((doc) => doc.id !== id),
  })
}
</script>

<style scoped>
.definition-input-subtabs {
  display: flex;
  gap: 8px;
  margin: 0 0 14px;
  padding: 4px;
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  background: #f5f8fc;
}

.definition-input-subtab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #5b6d80;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.definition-input-subtab.active {
  background: #fff;
  color: #1f3348;
  box-shadow: 0 1px 2px rgba(31, 51, 72, 0.08);
}

.definition-input-subtab-count {
  min-width: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #e8eef6;
  color: #3f556c;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

.definition-history-pane {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  background: #f8fbff;
}

.definition-history-pane__intro strong {
  display: block;
  color: #1f3348;
  font-size: 14px;
}

.definition-history-pane__intro p {
  margin: 6px 0 0;
  color: #66788c;
  font-size: 12px;
  line-height: 1.5;
}

.definition-history-pane__empty {
  padding: 28px 8px;
  color: #7a8b9c;
  font-size: 13px;
  text-align: center;
}

.definition-history-pane__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.definition-history-pane__list li {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #e6edf5;
}

.definition-history-pane__list li:last-child {
  border-bottom: 0;
}

.definition-history-pane__item-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.definition-history-pane__item-main strong {
  color: #1f3348;
  font-size: 13px;
}

.definition-history-pane__item-main span {
  color: #66788c;
  font-size: 12px;
}

@media (max-width: 640px) {
  .definition-history-pane__list li {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
