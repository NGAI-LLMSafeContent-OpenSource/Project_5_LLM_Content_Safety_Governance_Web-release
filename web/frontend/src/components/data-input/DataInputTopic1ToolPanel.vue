<template>
  <section class="topic1-tool-panel" aria-labelledby="topic1-tool-panel-title">
    <header class="topic1-tool-panel__header">
      <div>
        <div class="topic1-tool-panel__title-row">
          <el-icon aria-hidden="true"><SetUp /></el-icon>
          <h3 id="topic1-tool-panel-title">训练语料处理工具</h3>
        </div>
        <p>课题一提供的稀缺度评估、数据去噪、数据去害与数据选择能力。</p>
      </div>
      <button
        type="button"
        class="btn btn-secondary btn-sm topic1-tool-panel__refresh"
        :disabled="loading"
        @click="$emit('refresh')"
      >
        <el-icon aria-hidden="true"><Refresh /></el-icon>
        <span>{{ loading ? '刷新中…' : '刷新状态' }}</span>
      </button>
    </header>

    <div v-if="loading && !catalog" class="topic1-tool-panel__notice" aria-live="polite">
      正在获取工具接入状态…
    </div>
    <div v-else-if="error" class="topic1-tool-panel__notice is-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-secondary btn-sm" @click="$emit('refresh')">
        重新加载
      </button>
    </div>
    <template v-else-if="catalog">
      <div class="topic1-tool-panel__summary" aria-label="工具接入概况">
        <span>
          <strong>{{ catalog.tools.length }}</strong>
          项工具
        </span>
        <span>
          <strong>{{ deliveredCount }}</strong>
          项源码已交付
        </span>
        <span>
          <strong>{{ executableCount }}</strong>
          项当前可运行
        </span>
        <span>源码核验于 {{ catalog.source_snapshot_date }}</span>
      </div>

      <ul class="topic1-tool-list">
        <li v-for="tool in catalog.tools" :key="tool.tool_key" class="topic1-tool-row">
          <div class="topic1-tool-row__identity">
            <strong>{{ tool.display_name }}</strong>
            <span>{{ tool.implementation_name }}</span>
          </div>
          <span class="topic1-tool-row__stage">
            {{ topic1ToolWorkflowStageLabel(tool.workflow_stage) }}
          </span>
          <div class="topic1-tool-row__body">
            <p>{{ tool.purpose }}</p>
            <dl
              v-if="topic1ToolMetadataRows(tool).length"
              class="topic1-tool-row__metadata"
              aria-label="已核验数据元信息"
            >
              <div v-for="row in topic1ToolMetadataRows(tool)" :key="row.label">
                <dt>{{ row.label }}</dt>
                <dd>{{ row.value }}</dd>
              </div>
            </dl>
            <details>
              <summary>查看输入输出</summary>
              <dl>
                <div>
                  <dt>输入</dt>
                  <dd>{{ tool.input_contract }}</dd>
                </div>
                <div>
                  <dt>输出</dt>
                  <dd>{{ tool.output_contract }}</dd>
                </div>
              </dl>
            </details>
          </div>
          <div class="topic1-tool-row__status">
            <span :class="`is-${tool.runtime_status}`">
              {{ topic1ToolRuntimeStatusLabel(tool.runtime_status) }}
            </span>
            <small>{{ tool.executable ? '可用于当前流程' : tool.next_action }}</small>
            <small v-if="tool.service_status" class="topic1-tool-row__service" role="status">
              {{ tool.service_status.message }}
            </small>
          </div>
        </li>
      </ul>

      <p class="topic1-tool-panel__footnote">
        未达到可执行条件的工具仅展示已核验状态，不会生成模拟处理结果。
      </p>
    </template>
    <DataInputTopic1Execution />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Refresh, SetUp } from '@element-plus/icons-vue'
import DataInputTopic1Execution from './DataInputTopic1Execution.vue'

import type { Topic1CorpusToolCatalogResult } from '@/types/topic1CorpusTools'
import {
  topic1ToolMetadataRows,
  topic1ToolRuntimeStatusLabel,
  topic1ToolWorkflowStageLabel,
} from '@/utils/topic1CorpusTools'

const props = defineProps<{
  catalog: Topic1CorpusToolCatalogResult | null
  loading: boolean
  error: string
}>()

defineEmits<{
  (event: 'refresh'): void
}>()

const deliveredCount = computed(
  () =>
    props.catalog?.tools.filter((tool) => tool.delivery_status === 'source_delivered').length ?? 0,
)
const executableCount = computed(
  () => props.catalog?.tools.filter((tool) => tool.executable).length ?? 0,
)
</script>

<style scoped>
.topic1-tool-panel {
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  background: #fff;
}

.topic1-tool-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #e7edf4;
}

.topic1-tool-panel__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topic1-tool-panel__title-row .el-icon {
  color: #1565c0;
  font-size: 18px;
}

.topic1-tool-panel h3,
.topic1-tool-panel p {
  margin: 0;
}

.topic1-tool-panel h3 {
  color: #1a2a44;
  font-size: 15px;
}

.topic1-tool-panel__header p {
  margin-top: 6px;
  color: #5c7188;
  font-size: 13px;
  line-height: 1.5;
}

.topic1-tool-panel__refresh {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  width: auto;
}

.topic1-tool-panel__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 12px 16px;
  background: #f7f9fc;
  color: #5c7188;
  font-size: 12px;
}

.topic1-tool-panel__summary strong {
  color: #1a2a44;
}

.topic1-tool-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.topic1-tool-row {
  display: grid;
  grid-template-columns: 132px 82px minmax(220px, 1fr) minmax(170px, 230px);
  gap: 14px;
  align-items: start;
  padding: 14px 16px;
}

.topic1-tool-row + .topic1-tool-row {
  border-top: 1px solid #edf1f5;
}

.topic1-tool-row__identity,
.topic1-tool-row__status {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.topic1-tool-row__identity strong {
  color: #1a2a44;
  font-size: 14px;
}

.topic1-tool-row__identity span,
.topic1-tool-row__status small {
  color: #6b7f95;
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.topic1-tool-row__stage {
  display: inline-flex;
  justify-content: center;
  border: 1px solid #cbd9e8;
  border-radius: 999px;
  padding: 3px 8px;
  color: #3c5f84;
  font-size: 11px;
  white-space: nowrap;
}

.topic1-tool-row__body p {
  color: #344f6c;
  font-size: 12px;
  line-height: 1.55;
}

.topic1-tool-row__body details {
  margin-top: 7px;
}

.topic1-tool-row__metadata {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
}

.topic1-tool-row__metadata div {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr);
  gap: 8px;
}

.topic1-tool-row__metadata dt,
.topic1-tool-row__metadata dd {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.topic1-tool-row__metadata dt {
  color: #71849a;
}

.topic1-tool-row__metadata dd {
  color: #344f6c;
  overflow-wrap: anywhere;
}

.topic1-tool-row__body summary {
  cursor: pointer;
  color: #1565c0;
  font-size: 11px;
}

.topic1-tool-row__body dl {
  display: grid;
  gap: 6px;
  margin: 8px 0 0;
}

.topic1-tool-row__body dl div {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 8px;
}

.topic1-tool-row__body dt,
.topic1-tool-row__body dd {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.topic1-tool-row__body dt {
  color: #71849a;
}

.topic1-tool-row__body dd {
  color: #425d78;
  overflow-wrap: anywhere;
}

.topic1-tool-row__status > span {
  align-self: flex-start;
  border-radius: 999px;
  padding: 3px 8px;
  background: #eef2f6;
  color: #475467;
  font-size: 11px;
  font-weight: 600;
}

.topic1-tool-row__status .topic1-tool-row__service {
  border-left: 2px solid #cbd9e8;
  padding-left: 8px;
  color: #425d78;
}

.topic1-tool-row__status > span.is-metadata_ready {
  background: #e8f5ee;
  color: #137a4b;
}

.topic1-tool-row__status > span.is-source_only {
  background: #eaf2ff;
  color: #2459a9;
}

.topic1-tool-row__status > span.is-blocked_missing_artifacts {
  background: #fff2df;
  color: #8a5408;
}

.topic1-tool-panel__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px;
  border: 1px dashed #cbd8e7;
  padding: 14px;
  color: #5c7188;
  font-size: 13px;
}

.topic1-tool-panel__notice.is-error {
  border-color: #efc5c5;
  background: #fff8f8;
  color: #9b2c2c;
}

.topic1-tool-panel__footnote {
  border-top: 1px solid #e7edf4;
  padding: 10px 16px;
  color: #71849a;
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .topic1-tool-row {
    grid-template-columns: minmax(120px, 0.8fr) minmax(220px, 1.7fr);
  }

  .topic1-tool-row__stage,
  .topic1-tool-row__status {
    grid-column: auto;
  }
}

@media (max-width: 640px) {
  .topic1-tool-panel__header,
  .topic1-tool-panel__notice {
    align-items: stretch;
    flex-direction: column;
  }

  .topic1-tool-panel__refresh {
    align-self: flex-start;
  }

  .topic1-tool-row {
    grid-template-columns: 1fr;
  }

  .topic1-tool-row__stage {
    justify-self: start;
  }
}
</style>
