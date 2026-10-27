<template>
  <div class="correction-card" :class="`correction-card--${mode}`">
    <div class="card-head">
      <code>{{ sample.id }}</code>
      <span class="badge" :class="`badge--${levelBadgeClass}`">{{ sample.overallLevel }}</span>
      <span class="card-dims">{{ formatDims }}</span>
    </div>

    <div class="preview-meta">样例原文（测试语料）</div>
    <!-- eslint-disable-next-line vue/no-v-html -- 高亮标记来自受控转义逻辑，非用户输入 -->
    <div class="original-text" v-html="highlightedOriginal"></div>

    <div class="card-actions-bar">
      <el-button
        :type="mode === 'risk' ? 'primary' : 'success'"
        size="small"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : mode === 'risk' ? '风险修正' : '多样性对齐' }}
      </el-button>
    </div>

    <div v-if="expanded" class="correction-panel">
      <div class="preview-meta">修正后（可编辑）</div>
      <textarea v-model="editedText" class="correction-textarea" />
      <div class="action-buttons">
        <el-button type="success" size="small" @click="setStatus(CorrectionStatus.ADOPTED)">
          采纳本稿
        </el-button>
        <el-button size="small" @click="setStatus(CorrectionStatus.CLARIFY)">澄清标注</el-button>
        <el-button size="small" @click="setStatus(CorrectionStatus.SKIP)">跳过</el-button>
      </div>
      <div class="status-bar" :class="`status-bar--${sample.status}`">
        状态：{{ statusLabel }} · {{ sample.operateTime || '—' }} · 操作人：{{
          sample.operator || '当前会话'
        }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useOutputStore } from '@/stores/output'
import { CorrectionStatus } from '@/types'
import type { CorrectionSample } from '@/types'

const props = defineProps<{
  sample: CorrectionSample
  mode: 'risk' | 'diversity'
}>()

const store = useOutputStore()
const expanded = ref(false)
const editedText = ref(props.sample.correctedText)

const formatDims = computed(() =>
  Object.entries(props.sample.dimensionScores)
    .map(([k, v]) => `${k} ${v}`)
    .join(' · '),
)

const levelBadgeClass = computed(() => {
  const s = props.sample.overallLevel
  if (s === '高风险' || s === '待提升' || s === 'HIGH') return 'red'
  if (s === '中风险' || s === '良' || s === 'MEDIUM') return 'orange'
  return 'green'
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    [CorrectionStatus.PENDING]: '待处理',
    [CorrectionStatus.ADOPTED]: '已采纳修正稿',
    [CorrectionStatus.CLARIFY]: '已标注需澄清',
    [CorrectionStatus.SKIP]: '已跳过（保留待办）',
  }
  return map[props.sample.status] ?? '待处理'
})

const highlightedOriginal = computed(() => {
  if (props.mode !== 'risk' || props.sample.highlightedMarks.length === 0) {
    return props.sample.originalText
  }
  let text = props.sample.originalText
  for (const m of props.sample.highlightedMarks) {
    text = text.replace(m.text, `<mark class="hl-${m.level}">${m.text}</mark>`)
  }
  return text
})

function setStatus(status: CorrectionStatus) {
  store.updateCorrectionStatus(props.sample.id, status)
}
</script>

<style scoped>
.correction-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.card-head code {
  font-size: 13px;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
}

.badge--red {
  background: rgba(239, 68, 68, 0.15);
  color: var(--accent-red);
}
.badge--orange {
  background: rgba(245, 158, 11, 0.15);
  color: var(--accent-orange);
}
.badge--green {
  background: rgba(63, 185, 129, 0.15);
  color: var(--accent-green);
}

.card-dims {
  font-size: 11px;
  color: var(--text-secondary);
}

.preview-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin: 4px 0;
}

.original-text {
  font-size: 13px;
  line-height: 1.7;
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: 6px;
  margin-bottom: 10px;
}

.original-text :deep(mark.hl-high) {
  background: rgba(239, 68, 68, 0.15);
  color: var(--accent-red);
}
.original-text :deep(mark.hl-medium) {
  background: rgba(245, 158, 11, 0.15);
  color: var(--accent-orange);
}

.card-actions-bar {
  margin-bottom: 4px;
}

.correction-panel {
  margin-top: 10px;
}

.correction-textarea {
  width: 100%;
  min-height: 72px;
  padding: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 12px;
  resize: vertical;
  font-family: inherit;
}

.action-buttons {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.status-bar {
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

.status-bar--pending {
  background: rgba(128, 128, 128, 0.06);
}
.status-bar--adopted {
  background: rgba(63, 185, 129, 0.08);
  color: var(--accent-green);
}
.status-bar--clarify {
  background: rgba(245, 158, 11, 0.08);
  color: var(--accent-orange);
}
.status-bar--skip {
  background: rgba(239, 68, 68, 0.06);
  color: var(--accent-red);
}
</style>
