<template>
  <div class="lineage-vis-wrap" aria-label="课题四血缘图谱交互预览">
    <div ref="containerRef" class="lineage-vis-canvas"></div>
    <div v-if="stabilizing" class="lineage-vis-loading">
      <div class="lineage-vis-loading__bar">
        <div class="lineage-vis-loading__fill" :style="{ width: `${stabilizeProgress}%` }"></div>
      </div>
      <span>图谱布局中 {{ stabilizeProgress }}%</span>
    </div>
    <div class="lineage-vis-footer">
      交互式血缘图谱 · {{ nodes.length }} 节点 / {{ edges.length }} 边 ·
      可拖拽、缩放；点击节点查看详情
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Network } from 'vis-network/standalone'
import type { Data, Edge, Node, Options } from 'vis-network'
import type { Topic4LineageEdge, Topic4LineageNode } from '@/api/dataInput'
import 'vis-network/styles/vis-network.min.css'

const props = defineProps<{
  nodes: Topic4LineageNode[]
  edges: Topic4LineageEdge[]
  selectedNodeId?: string
}>()

const emit = defineEmits<{
  (e: 'select-node', id: string): void
}>()

const containerRef = ref<HTMLElement | null>(null)
const stabilizing = ref(false)
const stabilizeProgress = ref(0)

let network: Network | null = null

const NODE_COLORS: Record<string, string> = {
  Meta: '#ff5733',
  Chunk: '#33ff57',
  CleanedChunk: '#3357ff',
  'Cleaned Chunk': '#3357ff',
  Question: '#f1c40f',
  Answer: '#8e44ad',
}

const LABEL_MAP: Record<string, string> = {
  Meta: 'Meta',
  Chunk: 'Chunk',
  CleanedChunk: 'Cleaned',
  'Cleaned Chunk': 'Cleaned',
  Question: 'Question',
  Answer: 'Answer',
}

const EDGE_LABEL_MAP: Record<string, string> = {
  contains: '包含',
  cleaned_to: '清洗生成',
  has_question: '生成问题',
  answers: '回答',
  answers_question_from: '来源回答',
  related: '',
}

const RISK_LEVEL_LABELS: Record<string, string> = {
  Improve: '待提升',
  High: '高风险',
  Medium: '中风险',
  Low: '低风险',
}

const networkOptions: Options = {
  configure: { enabled: false },
  nodes: {
    shape: 'dot',
    font: { color: '#ffffff', size: 12, face: 'Segoe UI, sans-serif' },
    borderWidth: 1,
    shadow: true,
  },
  edges: {
    color: { color: '#8a97a8', highlight: '#ff8a65', hover: '#b0bec5', inherit: false },
    font: { color: '#c5cdd8', size: 9, strokeWidth: 0 },
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    smooth: { enabled: true, type: 'dynamic', roundness: 0.5 },
  },
  interaction: {
    dragNodes: true,
    dragView: true,
    zoomView: true,
    hover: true,
    tooltipDelay: 120,
    hideEdgesOnDrag: false,
    hideNodesOnDrag: false,
  },
  physics: {
    enabled: true,
    barnesHut: {
      gravitationalConstant: -8000,
      centralGravity: 0.3,
      springLength: 250,
      springConstant: 0.001,
      damping: 0.09,
      avoidOverlap: 0,
    },
    stabilization: {
      enabled: true,
      iterations: 500,
      updateInterval: 40,
      onlyDynamicEdges: false,
      fit: true,
    },
  },
}

function normalizeType(type: string) {
  if (type === 'Cleaned Chunk') return 'CleanedChunk'
  return type
}

function buildTooltip(node: Topic4LineageNode) {
  const lines = [
    `【${LABEL_MAP[normalizeType(node.type)] || node.type}】 ${node.id}`,
    node.docName ? `文档: ${node.docName}` : '',
    node.topic ? `主题: ${node.topic}` : '',
    node.summary ? `摘要: ${node.summary}` : '',
    node.isRisky
      ? `风险: ${RISK_LEVEL_LABELS[node.riskLevel] || '需复核'}${node.riskTypes?.length ? ` / ${node.riskTypes.join('、')}` : ''}`
      : '',
  ]
  return lines.filter(Boolean).join('\n')
}

function buildVisNodes(selectedId?: string): Node[] {
  return props.nodes.map((node) => {
    const type = normalizeType(node.type)
    const baseColor = NODE_COLORS[type] || '#999999'
    const isImprove = node.isRisky && String(node.riskLevel || '') === 'Improve'
    const isRisky = node.isRisky && !isImprove
    const selected = selectedId === node.id
    return {
      id: node.id,
      label: LABEL_MAP[type] || type,
      title: buildTooltip(node),
      color: {
        background: baseColor,
        border: selected ? '#ffffff' : isRisky ? '#ff1744' : isImprove ? '#ffb300' : baseColor,
        highlight: {
          background: baseColor,
          border: '#ffffff',
        },
        hover: {
          background: baseColor,
          border: '#ffffff',
        },
      },
      borderWidth: selected ? 3 : isRisky || isImprove ? 3 : 1,
      size: selected ? 18 : isRisky || isImprove ? 16 : type === 'Meta' ? 14 : 11,
      font: { color: '#ffffff' },
      shape: 'dot',
    }
  })
}

function buildVisEdges(): Edge[] {
  const nodeIds = new Set(props.nodes.map((node) => node.id))
  const showLabels = props.edges.length <= 120
  const result: Edge[] = []
  const seen = new Set<string>()
  props.edges.forEach((edge, index) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return
    const key = `${edge.source}->${edge.target}:${edge.type || ''}`
    if (seen.has(key)) return
    seen.add(key)
    const label = EDGE_LABEL_MAP[edge.type] ?? '关联'
    result.push({
      id: edge.id || `e-${index}`,
      from: edge.source,
      to: edge.target,
      label: showLabels && label ? label : undefined,
      title: label || '关联',
      arrows: 'to',
    })
  })
  return result
}

function destroyNetwork() {
  if (network) {
    network.destroy()
    network = null
  }
}

function renderNetwork() {
  if (!containerRef.value) return
  destroyNetwork()
  if (!props.nodes.length) return

  const data: Data = {
    nodes: buildVisNodes(props.selectedNodeId),
    edges: buildVisEdges(),
  }

  stabilizing.value = true
  stabilizeProgress.value = 0
  network = new Network(containerRef.value, data, networkOptions)

  network.on('stabilizationProgress', (params) => {
    const total = Math.max(params.total || 1, 1)
    stabilizeProgress.value = Math.min(100, Math.round((params.iterations / total) * 100))
  })
  network.once('stabilizationIterationsDone', () => {
    stabilizing.value = false
    stabilizeProgress.value = 100
    network?.setOptions({ physics: false })
    network?.fit({ animation: false })
  })
  network.on('click', (params) => {
    const nodeId = params.nodes?.[0]
    if (typeof nodeId === 'string' || typeof nodeId === 'number') {
      emit('select-node', String(nodeId))
    }
  })

  if (props.selectedNodeId) {
    try {
      network.selectNodes([props.selectedNodeId])
    } catch {
      // ignore missing selection
    }
  }
}

watch(
  () => [props.nodes, props.edges] as const,
  async () => {
    await nextTick()
    renderNetwork()
  },
  { deep: true, immediate: true },
)

watch(
  () => props.selectedNodeId,
  (nodeId) => {
    if (!network || !nodeId) return
    try {
      network.selectNodes([nodeId])
      network.focus(nodeId, {
        scale: 1.05,
        animation: { duration: 280, easingFunction: 'easeInOutQuad' },
      })
    } catch {
      // ignore
    }
  },
)

onBeforeUnmount(() => {
  destroyNetwork()
})
</script>

<style scoped>
.lineage-vis-wrap {
  position: relative;
  overflow: hidden;
  border: 1px solid #2a3340;
  border-radius: 12px;
  background: #1b222c;
  min-height: 640px;
}

.lineage-vis-canvas {
  width: 100%;
  height: 640px;
  background: #222222;
}

.lineage-vis-loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-content: center;
  gap: 10px;
  background: rgba(20, 24, 30, 0.72);
  color: #e8eef6;
  font-size: 13px;
  pointer-events: none;
}

.lineage-vis-loading__bar {
  width: 240px;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
}

.lineage-vis-loading__fill {
  height: 100%;
  border-radius: inherit;
  background: #00adf6;
  transition: width 0.12s linear;
}

.lineage-vis-footer {
  border-top: 1px solid #323b48;
  color: #9aa8b8;
  font-size: 12px;
  line-height: 1.45;
  padding: 8px 12px;
  background: #1b222c;
}

@media (max-width: 900px) {
  .lineage-vis-wrap,
  .lineage-vis-canvas {
    min-height: 520px;
    height: 520px;
  }
}
</style>
