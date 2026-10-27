<template>
  <div class="input-section">
    <div class="input-section-title">
      <span class="icon">🔗</span>
      <span>血缘图谱生成</span>
    </div>

    <div class="lineage-source-switch" aria-label="血缘建图语料来源">
      <span class="lineage-source-switch__label">建图语料来源</span>
      <div class="lineage-source-switch__btns">
        <button
          type="button"
          class="btn btn-sm"
          :class="lineageCorpusSource === 'topic4_static' ? 'btn-primary' : 'btn-secondary'"
          :disabled="topic4Status.loading"
          @click="$emit('change-lineage-source', 'topic4_static')"
        >
          课题四静态预跑（默认）
        </button>
        <button
          type="button"
          class="btn btn-sm"
          :class="lineageCorpusSource === 'risk' ? 'btn-primary' : 'btn-secondary'"
          :disabled="!riskCorpusReady || topic4Status.loading"
          @click="$emit('change-lineage-source', 'risk')"
        >
          风险侧语料
        </button>
        <button
          type="button"
          class="btn btn-sm"
          :class="lineageCorpusSource === 'value' ? 'btn-primary' : 'btn-secondary'"
          :disabled="!valueCorpusReady || topic4Status.loading"
          @click="$emit('change-lineage-source', 'value')"
        >
          价值侧语料
        </button>
      </div>
      <span class="lineage-source-switch__hint">
        当前：{{ sourceLabel }}
        ·
        {{
          lineageCorpusSource === 'topic4_static'
            ? '读取课题五内置静态预跑资产，无需启动课题四仓库'
            : '需课题四在线服务；切换后会按所选语料重建图谱'
        }}
      </span>
    </div>

    <DataInputServiceStatusCard
      :title="
        lineageCorpusSource === 'topic4_static' ? '课题四静态血缘预跑' : '课题四输入侧血缘图谱服务'
      "
      :status="topic4Status"
      :badges="topic4Badges"
      :disconnected-label="
        lineageCorpusSource === 'topic4_static' ? '静态资产未就绪' : '课题四服务未连接'
      "
      :connected-label="
        lineageCorpusSource === 'topic4_static' ? '静态预跑已就绪' : '已连接课题四服务'
      "
      tone="blue"
    />

    <div class="lineage-pipeline-row" aria-label="图谱构建流水线">
      <div class="lineage-pipeline-step done">
        <span class="lp-num">✓</span>
        <span>{{ lineageCorpusSource === 'topic4_static' ? '预跑结果读取' : '输入语料组织' }}</span>
      </div>
      <span class="lineage-pipeline-arrow">→</span>
      <div class="lineage-pipeline-step done">
        <span class="lp-num">✓</span>
        <span>血缘图谱构建</span>
      </div>
      <span class="lineage-pipeline-arrow">→</span>
      <div :class="['lineage-pipeline-step', isTopic4BuildGraphFallback ? 'warn' : 'done']">
        <span class="lp-num">{{ isTopic4BuildGraphFallback ? '!' : '✓' }}</span>
        <span>
          {{
            isTopic4BuildGraphFallback
              ? lineageCorpusSource === 'value'
                ? '待提升标注未执行'
                : '风险标注未执行'
              : lineageCorpusSource === 'value'
                ? '待提升标注合并'
                : '风险标注合并'
          }}
        </span>
      </div>
      <span class="lineage-pipeline-arrow">→</span>
      <div class="lineage-pipeline-step done">
        <span class="lp-num">✓</span>
        <span>节点详情归一化</span>
      </div>
    </div>

    <DataInputLineageSummary :summary="summary" :lineage-corpus-source="lineageCorpusSource" />

    <div v-if="workflowStages.length" class="topic4-workflow-panel">
      <div class="topic4-workflow-panel__head">
        <strong>图谱生成进度</strong>
        <span>
          {{ lineageCorpusSource === 'value' ? '待提升标注' : '风险标注' }}
          {{ annotationCount }} 条 · 清洗动作 {{ cleaningActionCount }} 条
        </span>
      </div>
      <div class="topic4-workflow-steps">
        <div v-for="stage in workflowStages" :key="stage.key" class="topic4-workflow-step">
          <span class="topic4-workflow-step__dot"></span>
          <div>
            <strong>{{ stage.label }}</strong>
            <p>{{ stage.description }}</p>
          </div>
        </div>
      </div>
      <div v-if="reportSummary" class="topic4-report-summary">
        {{ reportSummary }}
      </div>
    </div>

    <div v-if="hasLineageResult" class="lineage-main-split">
      <div>
        <DataInputLineageGraph
          :nodes="nodes"
          :edges="edges"
          :selected-node-id="selectedNodeId"
          @select-node="$emit('update:selected-node-id', $event)"
        />
        <div class="lineage-legend-bar">
          <span>
            <span class="lg-dot lg-dot--chunk"></span>
            Chunk
          </span>
          <span>
            <span class="lg-dot lg-dot--question"></span>
            Question
          </span>
          <span>
            <span class="lg-dot lg-dot--answer"></span>
            Answer
          </span>
          <span>
            <span class="lg-dot lg-dot--cleaned"></span>
            Cleaned Chunk
          </span>
          <span>
            <span class="lg-dot lg-dot--meta"></span>
            Meta
          </span>
          <span>
            <span
              class="lg-dot"
              :class="lineageCorpusSource === 'value' ? 'lg-dot--improve' : 'lg-dot--risk'"
            ></span>
            {{ lineageCorpusSource === 'value' ? '待提升节点高亮' : '风险节点高亮' }}
          </span>
        </div>
      </div>
      <DataInputLineageNodePanel
        :nodes="nodes"
        :selected-node="selectedNode"
        :selected-node-id="selectedNodeId"
        :lineage-corpus-source="lineageCorpusSource"
        @update:selected-node-id="$emit('update:selected-node-id', $event)"
      />
    </div>

    <div v-else class="lineage-empty-state">
      <strong>
        {{
          lineageCorpusSource === 'topic4_static'
            ? '等待加载课题四静态预跑图谱'
            : '等待课题四返回血缘图谱'
        }}
      </strong>
      <span>
        <template v-if="lineageCorpusSource === 'topic4_static'">
          进入本节点后会自动读取课题五内置静态资产，无需启动课题四仓库。
        </template>
        <template v-else>
          当前未展示图谱。进入本节点会自动调用课题四在线服务；如服务不可达，请改选「课题四静态预跑（默认）」。
        </template>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Topic4LineageEdge, Topic4LineageNode, Topic4WorkflowStage } from '@/api/dataInput'
import DataInputLineageGraph from '@/components/data-input/DataInputLineageGraph.vue'
import DataInputServiceStatusCard from '@/components/data-input/DataInputServiceStatusCard.vue'
import DataInputLineageNodePanel from '@/components/data-input/DataInputLineageNodePanel.vue'
import DataInputLineageSummary from '@/components/data-input/DataInputLineageSummary.vue'
import type { ExternalServiceStatus, InputLineageSummary } from '@/stores/input'

export type LineageCorpusSource = 'value' | 'risk' | 'topic4_static'

const props = defineProps<{
  nodes: Topic4LineageNode[]
  edges: Topic4LineageEdge[]
  summary: InputLineageSummary
  topic4Status: ExternalServiceStatus
  workflowStages: Topic4WorkflowStage[]
  annotationCount: number
  cleaningActionCount: number
  reportSummary: string
  selectedNode?: Topic4LineageNode
  selectedNodeId: string
  lineageCorpusSource?: LineageCorpusSource
  valueCorpusReady?: boolean
  riskCorpusReady?: boolean
}>()

defineEmits<{
  (e: 'update:selected-node-id', value: string): void
  (e: 'change-lineage-source', source: LineageCorpusSource): void
}>()

const lineageCorpusSource = computed(() => props.lineageCorpusSource || 'topic4_static')
const valueCorpusReady = computed(() => Boolean(props.valueCorpusReady))
const riskCorpusReady = computed(() => Boolean(props.riskCorpusReady))
const sourceLabel = computed(() => {
  if (lineageCorpusSource.value === 'topic4_static') return '课题四静态预跑'
  if (lineageCorpusSource.value === 'value') return '价值侧'
  return '风险侧'
})

const hasLineageResult = computed(() => props.topic4Status.connected && props.nodes.length > 0)
const topic4Badges = computed(() => {
  const badges: string[] = []
  if (props.topic4Status.fallback) badges.push('基础建图结果')
  return badges
})
const isTopic4BuildGraphFallback = computed(
  () =>
    props.topic4Status.fallback ||
    props.workflowStages.some((stage) => stage.key === 'full_v2' && stage.status === 'failed'),
)
</script>

<style scoped>
.lineage-source-switch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 14px;
  padding: 12px 14px;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: #f8fbff;
}

.lineage-source-switch__label {
  font-size: 13px;
  font-weight: 700;
  color: #2f435a;
}

.lineage-source-switch__btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.lineage-source-switch__hint {
  font-size: 12px;
  color: #66788c;
}

.lg-dot--risk {
  background: #c62828;
  box-shadow: 0 0 0 2px rgba(198, 40, 40, 0.2);
}

.lg-dot--improve {
  background: #e6a23c;
  box-shadow: 0 0 0 2px rgba(230, 162, 60, 0.25);
}

.topic4-workflow-panel {
  display: grid;
  gap: 12px;
  margin: 14px 0;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: #f8fbff;
  padding: 14px;
}

.topic4-workflow-panel__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #2f435a;
}

.topic4-workflow-panel__head strong {
  font-size: 14px;
}

.topic4-workflow-panel__head span {
  color: #66788c;
  font-size: 12px;
}

.topic4-workflow-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.topic4-workflow-step {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  border: 1px solid #e0e9f3;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}

.topic4-workflow-step__dot {
  width: 9px;
  height: 9px;
  margin-top: 4px;
  border-radius: 50%;
  background: #2e7d32;
}

.topic4-workflow-step strong {
  display: block;
  color: #2f435a;
  font-size: 12px;
  line-height: 1.35;
}

.topic4-workflow-step p,
.topic4-report-summary {
  margin: 4px 0 0;
  color: #66788c;
  font-size: 12px;
  line-height: 1.55;
}

.topic4-report-summary {
  margin: 0;
  border-left: 3px solid #7fa7d9;
  background: #fff;
  padding: 9px 10px;
}

@media (max-width: 900px) {
  .topic4-workflow-steps {
    grid-template-columns: 1fr;
  }
}
</style>
