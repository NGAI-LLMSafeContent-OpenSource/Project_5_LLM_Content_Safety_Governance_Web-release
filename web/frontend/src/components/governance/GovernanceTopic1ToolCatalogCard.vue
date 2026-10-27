<template>
  <section v-if="payload" class="topic1-tool-result" aria-label="课题一训练语料工具状态">
    <div v-if="!payload.available" class="topic1-tool-result__unavailable" role="alert">
      <strong>工具状态暂时不可用</strong>
      <span>{{ payload.message }}</span>
    </div>

    <div v-else class="topic1-tool-result__summary">
      <span>
        <strong>{{ payload.tools.length }}</strong>
        项输入工具
      </span>
      <span>
        <strong>{{ deliveredCount }}</strong>
        项源码已交付
      </span>
      <span>
        <strong>{{ executableCount }}</strong>
        项当前可运行
      </span>
    </div>

    <ul v-if="payload.available" class="topic1-tool-result__list">
      <li v-for="tool in payload.tools" :key="tool.tool_key">
        <div class="topic1-tool-result__heading">
          <div>
            <strong>{{ tool.display_name }}</strong>
            <small>{{ tool.implementation_name }}</small>
          </div>
          <span :class="`is-${tool.runtime_status}`">
            {{ topic1ToolRuntimeStatusLabel(tool.runtime_status) }}
          </span>
        </div>
        <p>{{ tool.purpose }}</p>
        <div class="topic1-tool-result__meta">
          <span>{{ topic1ToolWorkflowStageLabel(tool.workflow_stage) }}</span>
          <span>{{ topic1ToolDeliveryStatusLabel(tool.delivery_status) }}</span>
        </div>
        <dl
          v-if="topic1ToolMetadataRows(tool).length"
          class="topic1-tool-result__metadata"
          aria-label="已核验数据元信息"
        >
          <div v-for="row in topic1ToolMetadataRows(tool)" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>
        <details>
          <summary>查看接入边界</summary>
          <dl>
            <div>
              <dt>输入</dt>
              <dd>{{ tool.input_contract }}</dd>
            </div>
            <div>
              <dt>输出</dt>
              <dd>{{ tool.output_contract }}</dd>
            </div>
            <div>
              <dt>下一步</dt>
              <dd>{{ tool.next_action }}</dd>
            </div>
          </dl>
        </details>
      </li>
    </ul>
    <p v-if="payload.available" class="topic1-tool-result__note">
      未就绪工具不会进入执行型 Skill，也不会返回模拟结果。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { GovernanceSessionMessage } from '@/types'
import type { GovernanceTopic1CorpusToolCatalogPayload } from '@/types/topic1CorpusTools'
import {
  topic1ToolDeliveryStatusLabel,
  topic1ToolMetadataRows,
  topic1ToolRuntimeStatusLabel,
  topic1ToolWorkflowStageLabel,
} from '@/utils/topic1CorpusTools'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceTopic1CorpusToolCatalogPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'topic1_corpus_tool_catalog' || !raw) return null
  if (!Array.isArray(raw.tools)) return null
  return raw as unknown as GovernanceTopic1CorpusToolCatalogPayload
})

const deliveredCount = computed(
  () =>
    payload.value?.tools.filter((tool) => tool.delivery_status === 'source_delivered').length ?? 0,
)
const executableCount = computed(
  () => payload.value?.tools.filter((tool) => tool.executable).length ?? 0,
)
</script>

<style scoped>
.topic1-tool-result {
  margin-top: 12px;
  border: 1px solid #d9e2ec;
  background: #fff;
}

.topic1-tool-result__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  padding: 12px 14px;
  border-bottom: 1px solid #e5eaf0;
  background: #f7f9fc;
  color: #667085;
  font-size: 12px;
}

.topic1-tool-result__summary strong {
  color: #172b4d;
}

.topic1-tool-result__unavailable {
  display: flex;
  flex-direction: column;
  gap: 5px;
  border-left: 3px solid #c2413b;
  padding: 12px 14px;
  background: #fff7f6;
  color: #8c2f2a;
  font-size: 12px;
  line-height: 1.5;
}

.topic1-tool-result__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.topic1-tool-result__list > li {
  min-width: 0;
  padding: 14px;
  border-bottom: 1px solid #edf1f5;
}

.topic1-tool-result__list > li:nth-child(odd) {
  border-right: 1px solid #edf1f5;
}

.topic1-tool-result__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.topic1-tool-result__heading div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.topic1-tool-result__heading strong {
  color: #172b4d;
  font-size: 14px;
}

.topic1-tool-result__heading small {
  color: #667085;
}

.topic1-tool-result__heading > span {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 8px;
  background: #eef2f6;
  color: #475467;
  font-size: 11px;
}

.topic1-tool-result__heading > span.is-metadata_ready {
  background: #e8f5ee;
  color: #137a4b;
}

.topic1-tool-result__heading > span.is-source_only {
  background: #eaf2ff;
  color: #2459a9;
}

.topic1-tool-result__heading > span.is-blocked_missing_artifacts {
  background: #fff2df;
  color: #8a5408;
}

.topic1-tool-result__list p,
.topic1-tool-result__note {
  margin: 10px 0 0;
  color: #475467;
  font-size: 12px;
  line-height: 1.55;
}

.topic1-tool-result__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 9px;
  color: #667085;
  font-size: 11px;
}

.topic1-tool-result__metadata {
  display: grid;
  gap: 5px;
  margin: 9px 0 0;
}

.topic1-tool-result__metadata div {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 8px;
}

.topic1-tool-result__metadata dt,
.topic1-tool-result__metadata dd {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.topic1-tool-result__metadata dt {
  color: #667085;
}

.topic1-tool-result__metadata dd {
  color: #344054;
  overflow-wrap: anywhere;
}

.topic1-tool-result details {
  margin-top: 10px;
}

.topic1-tool-result summary {
  cursor: pointer;
  color: #2459a9;
  font-size: 11px;
}

.topic1-tool-result dl {
  display: grid;
  gap: 7px;
  margin: 8px 0 0;
}

.topic1-tool-result dl div {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px;
}

.topic1-tool-result dt,
.topic1-tool-result dd {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.topic1-tool-result dt {
  color: #667085;
}

.topic1-tool-result dd {
  color: #344054;
  overflow-wrap: anywhere;
}

.topic1-tool-result__note {
  margin: 0;
  padding: 10px 14px;
  background: #f9fafb;
}

@media (max-width: 760px) {
  .topic1-tool-result__list {
    grid-template-columns: 1fr;
  }

  .topic1-tool-result__list > li:nth-child(odd) {
    border-right: 0;
  }
}
</style>
