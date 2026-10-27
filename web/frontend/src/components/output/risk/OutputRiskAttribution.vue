<template>
  <div class="risk-attrib">
    <h2 class="track-title">
      归因（风险）
      <span v-if="store.riskAttributionSource === 'live'" class="source-badge live">实时数据</span>
      <span v-else class="source-badge mock">本地样例</span>
    </h2>

    <div class="eval-card">
      <!-- 统计概览 -->
      <div class="stage-section">
        <h4 class="stage-title">一、数据集统计信息</h4>
        <div class="stats-row">
          <div class="stat-item stat-total">
            <span class="stat-num">{{ stats.total }}</span>
            <span class="stat-label">展示样本</span>
          </div>
          <div class="stat-item stat-high">
            <span class="stat-num">{{ stats.high }}</span>
            <span class="stat-label">高风险</span>
          </div>
          <div class="stat-item stat-med">
            <span class="stat-num">{{ stats.medium }}</span>
            <span class="stat-label">中风险</span>
          </div>
          <div class="stat-item stat-low">
            <span class="stat-num">{{ stats.low }}</span>
            <span class="stat-label">低风险</span>
          </div>
          <div class="stat-item stat-cats">
            <span class="stat-num">{{ stats.categoryCount }}</span>
            <span class="stat-label">预测类别覆盖</span>
          </div>
          <div class="stat-item stat-evidence">
            <span class="stat-num">{{ stats.evidenceCount }}</span>
            <span class="stat-label">含风险标记</span>
          </div>
        </div>
        <div class="filter-bar">
          <span>筛选</span>
          <select v-model="previewFilter">
            <option value="all">全部 ({{ nodes.length }})</option>
            <option value="HIGH">仅高风险</option>
            <option value="MEDIUM">仅中风险</option>
            <option value="LOW">仅低风险</option>
          </select>
          <span v-if="store.riskAttributionLoading" class="filter-hint">加载中...</span>
          <span v-else-if="store.riskAttributionError" class="filter-hint err">
            {{ store.riskAttributionError }}
          </span>
        </div>
      </div>

      <!-- 归因卡片 -->
      <div class="stage-section">
        <h4 class="stage-title">二、个例展示</h4>
        <div class="attrib-list">
          <div
            v-for="node in filteredNodes"
            :key="node.id"
            class="attrib-card"
            :class="'card-' + (node.overall || 'LOW').toLowerCase()"
          >
            <!-- 头部 -->
            <div class="card-head">
              <code>{{ node.id }}</code>
              <span class="overall-tag" :class="levelClass(node.overall || 'LOW')">
                {{ node.overall || 'LOW' }}
              </span>
              <span class="weight-badge">权重 {{ (node.weight * 100).toFixed(0) }}%</span>
              <span v-for="c in node.predCategories" :key="c" class="cat-label">{{ c }}</span>
              <!-- 证据标记按钮 -->
              <button
                class="evidence-btn"
                :disabled="evidenceLoading[node.id]"
                @click="runEvidenceMark(node)"
              >
                <span v-if="evidenceLoading[node.id]" class="btn-spinner"></span>
                {{
                  evidenceLoading[node.id]
                    ? '标记中...'
                    : evidenceData[node.id]
                      ? '刷新标记'
                      : '证据标记'
                }}
              </button>
            </div>

            <!-- 风险证据标签 -->
            <div v-if="node.riskEvidence && node.riskEvidence.length" class="evidence-strip">
              <span class="evidence-label">风险标记</span>
              <span v-for="(ev, ei) in node.riskEvidence" :key="ei" class="evidence-chip">
                {{ ev }}
              </span>
            </div>

            <!-- 推理证据错误 / 提示 -->
            <div
              v-if="evidenceError[node.id]"
              class="evidence-msg"
              :class="evidenceMsgType[node.id] || 'err'"
            >
              {{ evidenceError[node.id] }}
            </div>
            <div v-else-if="evidenceLoading[node.id]" class="evidence-msg info">
              正在调用远端 V7 动态推理与证据生成，通常需要数分钟；长文本会更慢。
            </div>

            <!-- 文本展示区（支持证据高亮） -->
            <div class="card-text" :class="'risk-' + (node.overall || 'LOW').toLowerCase()">
              <!-- 有证据标记：在原文本内直接高亮风险片段 -->
              <div v-if="evidenceData[node.id]" class="marked-text">
                <template v-for="(seg, si) in evidenceData[node.id].segments" :key="si">
                  <mark v-if="seg.level !== 'neutral'" :class="'evidence-mark mark-' + seg.level">
                    {{ seg.text }}
                  </mark>
                  <span v-else>{{ seg.text }}</span>
                </template>
              </div>
              <!-- 无证据：纯文本 -->
              <div v-else class="text-full">{{ node.text || '（无文本）' }}</div>
            </div>

            <!-- 证据图例 -->
            <div v-if="evidenceData[node.id]" class="evidence-legend">
              <span class="legend-item critical">▎▎ 高关联</span>
              <span class="legend-item warning">▎ 中关联</span>
              <span class="legend-item context">· 低关联</span>
              <span class="legend-item neutral">· 无明显风险</span>
              <span class="legend-source">来源：Benchmark 推理证据管线</span>
            </div>

            <!-- 归因链 -->
            <div class="card-chain">
              <div class="chain-row">
                <span class="label">归因链</span>
                <span class="chain-text">{{ node.chain }}</span>
              </div>
              <div v-if="node.reasonPath" class="chain-row">
                <span class="label">依据</span>
                <span class="chain-detail">{{ node.reasonPath }}</span>
              </div>
            </div>
          </div>

          <div v-if="nodes.length === 0 && !store.riskAttributionLoading" class="empty-hint">
            暂无归因数据，请确认 Benchmark 服务可用并已生成预测结果。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useOutputStore } from '@/stores/output'
import { inferRiskEvidenceWithCache, type RiskEvidenceItem } from '@/api/output'
import type { AttributionNode } from '@/types'

const store = useOutputStore()
const previewFilter = ref('all')

const activeAttributionDatasetId = computed(
  () => store.staticResultMeta?.dataset_id || store.selectedRiskDatasets[0]?.datasetId || '',
)

async function refreshRiskAttribution() {
  if (!activeAttributionDatasetId.value) return
  await store.loadRiskAttribution(activeAttributionDatasetId.value)
}

// 证据标记状态（按 node.id）
const evidenceLoading = reactive<Record<string, boolean>>({})
const evidenceError = reactive<Record<string, string>>({})
const evidenceMsgType = reactive<Record<string, 'err' | 'info'>>({})
const evidenceData = reactive<Record<string, { segments: EvidenceSegment[] }>>({})

interface EvidenceSegment {
  text: string
  level: string
}

interface EvidenceResultPayload {
  evidence?: { items?: RiskEvidenceItem[] }
  risk_evidence?: RiskEvidenceItem[]
  safe_type?: string
}

function asEvidenceResultPayload(value: unknown): EvidenceResultPayload {
  return value && typeof value === 'object' ? (value as EvidenceResultPayload) : {}
}

function pickEvidenceItems(...groups: Array<RiskEvidenceItem[] | undefined>): RiskEvidenceItem[] {
  return groups.find((items) => Array.isArray(items) && items.length > 0) || []
}

function evidencePriority(level: string | undefined): number {
  if (level === 'critical') return 4
  if (level === 'warning') return 3
  if (level === 'context') return 2
  return 1
}

function normalizeEvidenceLevel(level: string | undefined): string {
  if (level === 'critical' || level === 'warning' || level === 'context') return level
  return 'warning'
}

function findEvidenceStart(
  text: string,
  evidenceText: string,
): { start: number; length: number } | null {
  const normalized = evidenceText.trim()
  if (!normalized) return null

  const exact = text.indexOf(normalized)
  if (exact >= 0) return { start: exact, length: normalized.length }

  const compactEvidence = normalized.replace(/\s+/g, ' ')
  const compact = text.indexOf(compactEvidence)
  if (compact >= 0) return { start: compact, length: compactEvidence.length }

  for (const size of [80, 60, 40, 24]) {
    if (normalized.length < size) continue
    const snippet = normalized.slice(0, size)
    const idx = text.indexOf(snippet)
    if (idx >= 0) return { start: idx, length: snippet.length }
  }
  return null
}

function buildMarkedSegments(text: string, items: RiskEvidenceItem[]): EvidenceSegment[] {
  const ranges = items
    .map((item) => {
      const match = findEvidenceStart(text, item.text || '')
      if (!match) return null
      return {
        start: match.start,
        end: match.start + match.length,
        level: normalizeEvidenceLevel(item.level),
      }
    })
    .filter((item): item is { start: number; end: number; level: string } => Boolean(item))
    .sort((a, b) => a.start - b.start || evidencePriority(b.level) - evidencePriority(a.level))

  const merged: Array<{ start: number; end: number; level: string }> = []
  for (const range of ranges) {
    const previous = merged[merged.length - 1]
    if (!previous || range.start >= previous.end) {
      merged.push({ ...range })
      continue
    }
    previous.end = Math.max(previous.end, range.end)
    if (evidencePriority(range.level) > evidencePriority(previous.level)) {
      previous.level = range.level
    }
  }

  const segments: EvidenceSegment[] = []
  let cursor = 0
  for (const range of merged) {
    if (range.start > cursor) {
      segments.push({ text: text.slice(cursor, range.start), level: 'neutral' })
    }
    segments.push({ text: text.slice(range.start, range.end), level: range.level })
    cursor = range.end
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), level: 'neutral' })
  }
  return segments.length ? segments : [{ text, level: 'neutral' }]
}

async function runEvidenceMark(node: AttributionNode) {
  const text = node.text
  if (!text) return

  evidenceLoading[node.id] = true
  evidenceError[node.id] = ''
  try {
    const data = await inferRiskEvidenceWithCache(
      {
        response: text,
        model_id: 'qwen3.5-9B-V7',
        task: 'joint_level_then_multilabel',
        use_vllm: true,
        use_api: false,
        max_new_tokens: 64,
        severity_max_new_tokens: 16,
        evidence_max_new_tokens: 1536,
        max_model_len: 32768,
      },
      {
        datasetId: activeAttributionDatasetId.value,
        sampleId: node.id,
      },
    )

    if (!data || !data.ok) {
      const errMsg =
        data?.stderr || data?.steps?.find((s) => s.status === 'error')?.detail || '推理失败'
      evidenceError[node.id] = typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg)
      evidenceMsgType[node.id] = 'err'
      return
    }

    const result = asEvidenceResultPayload(data.result)
    // evidence 可能嵌套在 result 中或顶层
    const items = pickEvidenceItems(
      data.evidence?.items,
      result.evidence?.items,
      data.risk_evidence,
      result.risk_evidence,
    )
    if (items.length === 0) {
      const safeType = result.safe_type || data.safe_type || data.pred_safe_type
      if (safeType === 'safe') {
        evidenceError[node.id] = '✓ 此文本被判定为安全，无需证据标记'
        evidenceMsgType[node.id] = 'info'
      } else {
        evidenceError[node.id] = '文本判定为风险，但证据生成未返回有效片段'
        evidenceMsgType[node.id] = 'err'
      }
      return
    }

    evidenceData[node.id] = {
      segments: buildMarkedSegments(text, items),
    }
    evidenceError[node.id] = data.cached ? '已复用本地缓存证据结果' : '已完成证据标记并写入本地缓存'
    evidenceMsgType[node.id] = 'info'
  } catch (e: unknown) {
    evidenceError[node.id] = e instanceof Error ? e.message : '证据标记请求失败'
    evidenceMsgType[node.id] = 'err'
  } finally {
    evidenceLoading[node.id] = false
  }
}

const nodes = computed(() => store.riskAttributionNodes)

const stats = computed(() => {
  let high = 0,
    medium = 0,
    low = 0
  const categories = new Set<string>()
  let evidenceCount = 0
  for (const n of nodes.value) {
    const o = n.overall || getOverallFromSignals(n.signals as Record<string, string>)
    if (o === 'HIGH') high++
    else if (o === 'MEDIUM') medium++
    else low++
    for (const c of n.predCategories || []) categories.add(c)
    if (n.riskEvidence?.length) evidenceCount++
  }
  return {
    total: nodes.value.length,
    high,
    medium,
    low,
    categoryCount: categories.size,
    evidenceCount,
  }
})

function getOverallFromSignals(signals: Record<string, string>): string {
  const vals = Object.values(signals)
  if (vals.some((v) => v === 'HIGH')) return 'HIGH'
  if (vals.some((v) => v === 'MEDIUM')) return 'MEDIUM'
  return 'LOW'
}

const filteredNodes = computed(() => {
  if (previewFilter.value === 'all') return nodes.value
  return nodes.value.filter((n) => {
    const o = n.overall || getOverallFromSignals(n.signals as Record<string, string>)
    return o === previewFilter.value
  })
})

function levelClass(lv: string): string {
  if (lv === 'HIGH') return 'red'
  if (lv === 'MEDIUM') return 'orange'
  return 'green'
}

onMounted(() => {
  void refreshRiskAttribution()
})

watch(activeAttributionDatasetId, () => {
  void refreshRiskAttribution()
})
</script>

<style src="./OutputRiskAttribution.css" scoped></style>
