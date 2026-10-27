<template>
  <section class="step-panel active">
    <div class="mindmap-toolbar">
      <div v-if="branches.length" class="mindmap-summary-grid">
        <article class="mindmap-summary-card">
          <strong>{{ summary.level1 }}</strong>
          <span>一级指标</span>
        </article>
        <article class="mindmap-summary-card">
          <strong>{{ summary.level2 }}</strong>
          <span>二级指标</span>
        </article>
        <article class="mindmap-summary-card">
          <strong>{{ summary.level3 }}</strong>
          <span>三级指标</span>
        </article>
        <article class="mindmap-summary-card">
          <strong>{{ summary.predefined }}</strong>
          <span>预定</span>
        </article>
        <article class="mindmap-summary-card">
          <strong>{{ summary.mined }}</strong>
          <span>新挖掘</span>
        </article>
        <article class="mindmap-summary-card">
          <strong>{{ summary.adopted }}</strong>
          <span>已采纳挖掘项</span>
        </article>
      </div>

      <div class="mindmap-toolbar-actions">
        <div v-if="branches.length" class="mindmap-filters">
          <button
            v-for="option in filterOptions"
            :key="option.id"
            type="button"
            class="mindmap-filter-chip"
            :class="{ active: activeFilter === option.id }"
            @click="activeFilter = option.id"
          >
            {{ option.label }}
          </button>
        </div>
        <button
          v-if="canSaveToHistory"
          class="btn btn-primary btn-sm"
          type="button"
          :disabled="savingDisabled"
          @click="$emit('save-history')"
        >
          {{ savedToHistory ? '已保存到历史记录' : '保存到历史记录' }}
        </button>
      </div>
    </div>

    <div v-if="filteredBranches.length" class="mindmap-legend">
      <span class="legend-pill">点击三级指标查看定义与来源</span>
      <span class="legend-pill legend-pill--predefined">预定三级</span>
      <span class="legend-pill legend-pill--ignored">新挖掘忽略</span>
      <span class="legend-pill legend-pill--adopted">新挖掘已采纳</span>
    </div>

    <div v-if="filteredBranches.length" class="mindmap-browse-layout">
      <div class="mindmap-container">
        <div class="mindmap">
          <div class="mindmap-node">
            <div class="mindmap-root">{{ rootTitle }}</div>
            <div class="mindmap-branch">
              <div v-for="branch in filteredBranches" :key="branch.id" class="mindmap-level1">
                <div class="node-level1">{{ branch.title }}</div>
                <div class="mindmap-level2">
                  <div
                    v-for="group in branch.childGroups"
                    :key="group.id"
                    class="mindmap-level2-group"
                  >
                    <div class="node-level2">{{ group.label }}</div>
                    <div class="mindmap-level3">
                      <div v-for="node in group.leafNodes" :key="node.id" class="node-level3-wrap">
                        <button
                          type="button"
                          class="node-level3"
                          :class="[
                            nodeToneClass(node),
                            selectedNodeId === node.id ? 'is-selected' : '',
                          ]"
                          @click="selectNode(node)"
                        >
                          <span>{{ node.label }}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <aside class="mindmap-detail-panel">
        <div v-if="selectedNode" class="mindmap-detail-content">
          <div class="mindmap-detail-eyebrow">
            {{ selectedNode.kind === 'mined' ? '新挖掘指标' : '预定指标' }}
          </div>
          <h3>{{ selectedNode.label }}</h3>
          <div class="mindmap-detail-path">
            {{ selectedNode.level1 }} / {{ selectedNode.level2 }} / {{ selectedNode.label }}
          </div>
          <dl class="mindmap-detail-list">
            <div>
              <dt>状态</dt>
              <dd>{{ detailStatusLabel(selectedNode) }}</dd>
            </div>
            <div>
              <dt>定义</dt>
              <dd>{{ selectedNode.definition?.trim() || '暂无定义说明' }}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{{ selectedNode.source?.trim() || '-' }}</dd>
            </div>
            <div>
              <dt>公式</dt>
              <dd>{{ selectedNode.formula?.trim() || '-' }}</dd>
            </div>
            <div>
              <dt>依据说明</dt>
              <dd>{{ selectedNode.rationale?.trim() || '-' }}</dd>
            </div>
            <div>
              <dt>证据片段</dt>
              <dd>{{ selectedNode.evidenceText?.trim() || '-' }}</dd>
            </div>
            <div>
              <dt>标签</dt>
              <dd>{{ selectedNode.tag?.trim() || '-' }}</dd>
            </div>
          </dl>
        </div>
        <div v-else class="mindmap-detail-empty">
          <strong>选择一个三级指标</strong>
          <span>可查看定义、路径、来源与证据，便于对照审核结果。</span>
        </div>
      </aside>
    </div>

    <div v-else class="def-mindmap-empty">
      <strong>暂无可展示的指标体系</strong>
      <span>请先确认当前 tab 是否已有固定指标配置，或在节点 2 等待后端返回候选指标。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  DefinitionBranch,
  DefinitionBranchNode,
  DefinitionStandardStatus,
} from '@/utils/definitionConfig'

type MindmapFilter = 'all' | 'predefined' | 'mined' | 'adopted'

const props = defineProps<{
  rootTitle: string
  branches: DefinitionBranch[]
  canSaveToHistory?: boolean
  savedToHistory?: boolean
  savingDisabled?: boolean
}>()

defineEmits<{
  (e: 'save-history'): void
}>()

const activeFilter = ref<MindmapFilter>('all')
const selectedNodeId = ref('')

const filterOptions: Array<{ id: MindmapFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'predefined', label: '仅预定' },
  { id: 'mined', label: '仅挖掘' },
  { id: 'adopted', label: '已采纳挖掘' },
]

const summary = computed(() => {
  const leaves = props.branches.flatMap((branch) =>
    branch.childGroups.flatMap((group) => group.leafNodes),
  )
  return {
    level1: props.branches.length,
    level2: props.branches.reduce((sum, branch) => sum + branch.childGroups.length, 0),
    level3: leaves.length,
    predefined: leaves.filter((item) => item.kind !== 'mined').length,
    mined: leaves.filter((item) => item.kind === 'mined').length,
    adopted: leaves.filter((item) => item.kind === 'mined' && item.status === 'adopted').length,
  }
})

const filteredBranches = computed(() => {
  if (activeFilter.value === 'all') return props.branches

  return props.branches
    .map((branch) => ({
      ...branch,
      childGroups: branch.childGroups
        .map((group) => ({
          ...group,
          leafNodes: group.leafNodes.filter((node) => {
            if (activeFilter.value === 'predefined') return node.kind !== 'mined'
            if (activeFilter.value === 'mined') return node.kind === 'mined'
            return node.kind === 'mined' && node.status === 'adopted'
          }),
        }))
        .filter((group) => group.leafNodes.length),
    }))
    .filter((branch) => branch.childGroups.length)
})

const selectedNode = computed(() => {
  for (const branch of filteredBranches.value) {
    for (const group of branch.childGroups) {
      const hit = group.leafNodes.find((node) => node.id === selectedNodeId.value)
      if (hit) return hit
    }
  }
  return null
})

watch(
  filteredBranches,
  (branches) => {
    if (selectedNode.value) return
    const first = branches[0]?.childGroups[0]?.leafNodes[0]
    selectedNodeId.value = first?.id ?? ''
  },
  { immediate: true },
)

function selectNode(node: DefinitionBranchNode) {
  selectedNodeId.value = node.id
}

/** 预定内置=蓝；新挖掘忽略=灰；新挖掘已采纳=绿 */
function nodeToneClass(node: DefinitionBranchNode) {
  if (node.kind !== 'mined') return 'node-level3--fixed'
  if (node.status === 'adopted') return 'node-level3--mined-adopted'
  if (node.status === 'ignored') return 'node-level3--mined-ignored'
  if (node.status === 'edited') return 'node-level3--mined-edited'
  return 'node-level3--mined-pending'
}

function detailStatusLabel(node: DefinitionBranchNode) {
  if (node.kind !== 'mined') return '预定内置'
  const labels: Record<DefinitionStandardStatus, string> = {
    pending: '待审核',
    adopted: '已采纳',
    ignored: '已忽略',
    edited: '已修改',
  }
  return labels[node.status] ?? node.status
}
</script>
