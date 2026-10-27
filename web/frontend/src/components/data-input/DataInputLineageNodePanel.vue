<template>
  <div class="lineage-node-panel">
    <div class="input-section-title lineage-node-title">
      <span class="icon">☰</span>
      <span>节点详情</span>
    </div>
    <div class="ln-picker-wrap">
      <label class="form-label">选择节点</label>
      <select
        :value="selectedNodeId"
        @change="$emit('update:selected-node-id', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="node in nodes" :key="node.id" :value="node.id">
          {{ node.id }} · {{ node.type }}
        </option>
      </select>
    </div>
    <div class="ln-risk-title">基本信息</div>
    <div class="hint lineage-node-summary">{{ selectedNode?.summary }}</div>
    <div class="ln-detail-grid">
      <div class="lnk">节点 ID</div>
      <div class="lnv">{{ selectedNode?.id }}</div>
      <div class="lnk">类型</div>
      <div class="lnv">{{ selectedNode?.type }}</div>
      <div class="lnk">{{ isValueSource ? '质量标记' : '风险等级' }}</div>
      <div class="lnv">
        <span class="lineage-risk-pill" :class="statusClass(selectedNode?.riskLevel)">
          {{ statusLabel(selectedNode?.riskLevel) }}
        </span>
      </div>
      <div class="lnk">{{ isValueSource ? '关联维度' : '风险类型' }}</div>
      <div class="lnv">{{ selectedNode?.riskTypes?.join('、') || '无' }}</div>
      <div class="lnk">所属文档</div>
      <div class="lnv">{{ selectedNode?.docName || '未绑定上传文档' }}</div>
      <div class="lnk">文档 ID</div>
      <div class="lnv">{{ selectedNode?.docId }}</div>
      <div class="lnk">节点主题</div>
      <div class="lnv">{{ selectedNode?.topic }}</div>
    </div>
    <div class="ln-risk-block">
      <div class="risk-meta-disclaimer">
        {{
          isValueSource
            ? '当前节点详情来自血缘图谱分析结果，待提升标记用于辅助人工复核。'
            : '当前节点详情来自血缘图谱分析结果，风险标记用于辅助人工复核。'
        }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Topic4LineageNode } from '@/api/dataInput'

const props = defineProps<{
  nodes: Topic4LineageNode[]
  selectedNode?: Topic4LineageNode
  selectedNodeId: string
  lineageCorpusSource?: 'value' | 'risk' | 'topic4_static'
}>()

defineEmits<{
  (e: 'update:selected-node-id', value: string): void
}>()

const isValueSource = computed(() => props.lineageCorpusSource === 'value')

function statusLabel(level = 'none') {
  if (level === 'Improve') return '待提升'
  if (level === 'High') return '高风险'
  if (level === 'Medium') return '中风险'
  if (level === 'Low') return '低风险'
  return isValueSource.value ? '正常' : '无风险'
}

function statusClass(level = 'none') {
  if (level === 'Improve') return 'lineage-risk-pill--improve'
  if (level === 'High') return 'lineage-risk-pill--high'
  if (level === 'Medium') return 'lineage-risk-pill--medium'
  if (level === 'Low') return 'lineage-risk-pill--low'
  return 'lineage-risk-pill--none'
}
</script>
