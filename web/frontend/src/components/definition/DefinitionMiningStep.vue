<template>
  <section class="step-panel active">
    <div class="def-mining-banner">
      <strong class="banner-title">本环节产出说明：</strong>
      基于上一节点上传的依据材料、网页链接和挖掘要求，展示多智能体协同挖掘过程，
      产出候选指标并支持逐条审核。
    </div>

    <div class="def-mining-context">
      <span>当前挖掘输入</span>
      <strong>{{ miningContext }}</strong>
      <span v-if="miningState.taskId" class="def-mining-task">任务 {{ shortTaskId }}</span>
    </div>

    <div v-if="miningState.error" class="def-mining-error">
      <span>{{ miningState.error }}</span>
      <button
        v-if="miningState.timedOut && miningState.taskId"
        class="btn btn-secondary btn-sm"
        type="button"
        :disabled="miningState.loading"
        @click="$emit('refresh-task')"
      >
        {{ miningState.loading ? '正在刷新' : '刷新任务结果' }}
      </button>
    </div>

    <div
      class="def-task-progress"
      :class="{ failed: miningState.status === 'failed' }"
      aria-label="挖掘任务进度"
    >
      <div class="def-task-progress-meta">
        <span>{{ taskStatusLabel }}</span>
        <strong>{{ normalizedProgress }}%</strong>
      </div>
      <div class="def-task-progress-track">
        <div class="def-task-progress-bar" :style="{ width: `${normalizedProgress}%` }"></div>
      </div>
    </div>

    <div class="agent-board">
      <article v-for="agent in agentCards" :key="agent.id" class="agent-card">
        <div class="agent-header">
          <div class="agent-avatar" :class="agent.avatar" aria-hidden="true">
            <svg
              v-if="agent.id === 'agent-extract'"
              class="agent-avatar-icon"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle cx="10.5" cy="10.5" r="5.5" />
              <path d="M15 15l4.5 4.5" />
              <path d="M8.5 10.5h4" />
            </svg>
            <svg
              v-else-if="agent.id === 'agent-match'"
              class="agent-avatar-icon"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle cx="6" cy="7" r="2.5" />
              <circle cx="18" cy="7" r="2.5" />
              <circle cx="12" cy="17" r="2.5" />
              <path d="M8.2 8.3l2.9 6.3" />
              <path d="M15.8 8.3l-2.9 6.3" />
            </svg>
            <svg v-else class="agent-avatar-icon" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 4l1.7 4.1 4.3.4-3.2 2.9 1 4.2L12 13.4 8.2 15.6l1-4.2L6 8.5l4.3-.4L12 4z"
              />
              <path d="M8 19l2 2 5-5" />
            </svg>
          </div>
          <div>
            <div class="agent-name">{{ agent.name }}</div>
            <div class="agent-status" :class="agent.statusClass">{{ agent.statusLabel }}</div>
          </div>
        </div>
        <div class="agent-progress">
          <div
            class="agent-progress-bar"
            :class="agent.progressClass"
            :style="{ width: `${agent.progressPercent}%` }"
          ></div>
        </div>
        <div class="agent-log">{{ agent.desc }}</div>
      </article>
    </div>

    <div class="input-section">
      <div class="input-section-title">
        <span>智能体协作时间线</span>
      </div>
      <div v-if="timelineItems.length" class="timeline">
        <article
          v-for="item in timelineItems"
          :key="item.id"
          class="timeline-item"
          :class="timelineStatusClass(item.status)"
        >
          <div class="timeline-time">{{ item.time }}</div>
          <div class="timeline-title">
            {{ item.title }}
            <span
              v-if="item.status"
              class="timeline-status-pill"
              :class="timelineStatusClass(item.status)"
            >
              {{ timelineStatusLabel(item.status) }}
            </span>
          </div>
          <div class="timeline-desc">{{ item.desc }}</div>
        </article>
      </div>
      <div v-else class="def-data-empty">暂无后端任务日志。</div>
    </div>

    <div class="input-section">
      <div class="input-section-title">
        <span>{{ config.summaryTitle }}</span>
      </div>
      <div v-if="summaryItems.length" class="lineage-summary-grid">
        <article v-for="summary in summaryItems" :key="summary.id" class="lineage-summary-card">
          <div class="ls-val">{{ summary.value }}</div>
          <div class="ls-label">{{ summary.label }}</div>
        </article>
      </div>
      <div v-else class="def-data-empty">暂无后端统计数据。</div>
    </div>

    <div class="def-review-shell">
      <div class="def-review-head">
        <div>
          <div class="def-review-title">指标审核</div>
          <p class="def-review-desc">
            左侧同时展示预定三级指标与新挖掘候选；仅新挖掘项可审核，预定项只读浏览。
          </p>
        </div>
        <div class="def-review-head-actions">
          <button
            class="btn btn-primary btn-sm def-l3-next-btn"
            type="button"
            :disabled="!canEnterMindmap"
            @click="$emit('next')"
          >
            进入指标体系浏览
          </button>
        </div>
      </div>

      <div class="def-review-legend">
        <span class="def-review-legend-pill is-predefined">预定指标（只读）</span>
        <span class="def-review-legend-pill is-mined">新挖掘（可审核）</span>
      </div>

      <div v-if="!reviewStandards.length" class="def-candidate-empty">
        暂无可展示指标。请确认当前 tab 已配置预定指标，或等待挖掘任务返回候选。
      </div>

      <div v-else class="def-review-layout">
        <section class="def-review-tree-panel" aria-label="候选指标框架树">
          <div class="def-review-stats">
            <div class="def-review-stat">
              <span>预定</span>
              <strong>{{ reviewStats.predefined }}</strong>
            </div>
            <div class="def-review-stat">
              <span>新挖掘</span>
              <strong>{{ reviewStats.mined }}</strong>
            </div>
            <div class="def-review-stat">
              <span>待审核</span>
              <strong class="pending">{{ reviewStats.pending }}</strong>
            </div>
            <div class="def-review-stat">
              <span>已采纳</span>
              <strong class="adopted">{{ reviewStats.adopted }}</strong>
            </div>
          </div>

          <div class="def-review-tree">
            <article v-for="level1 in reviewTree" :key="level1.id" class="def-review-branch">
              <div class="def-review-branch-head">
                <span class="def-review-toggle">-</span>
                <strong>{{ level1.label }}</strong>
                <span class="def-review-count">{{ level1.count }}项</span>
              </div>
              <div class="def-review-level2">
                <div v-for="level2 in level1.children" :key="level2.id" class="def-review-subtree">
                  <div class="def-review-level2-head">
                    <span class="def-review-toggle">-</span>
                    <span>{{ level2.label }}</span>
                    <span class="def-review-count">{{ level2.items.length }}项</span>
                  </div>
                  <button
                    v-for="item in level2.items"
                    :key="item.id"
                    class="def-review-leaf"
                    :class="{
                      active: selectedStandard?.id === item.id,
                      'is-predefined-leaf': !isMinedStandard(item),
                      'is-mined-leaf': isMinedStandard(item),
                    }"
                    type="button"
                    @click="selectCandidate(item.id)"
                  >
                    <span class="def-review-leaf-main">
                      <span
                        class="def-review-kind-badge"
                        :class="isMinedStandard(item) ? 'is-mined' : 'is-predefined'"
                      >
                        {{ isMinedStandard(item) ? '新挖掘' : '预定' }}
                      </span>
                      <span>{{ item.level3 }}</span>
                    </span>
                    <span class="def-review-status-dot" :class="statusClass(item.status)"></span>
                    <span class="def-review-status-text">
                      {{ isMinedStandard(item) ? stateLabel(item.status) : '内置' }}
                    </span>
                  </button>
                </div>
              </div>
            </article>
          </div>
        </section>

        <aside class="def-review-detail-panel" aria-label="指标详情面板">
          <div v-if="selectedStandard" class="def-review-detail-content">
            <div class="def-review-detail-head">
              <div>
                <div class="def-review-detail-title">指标详情面板</div>
                <strong>{{ selectedStandard.name }}</strong>
              </div>
              <span
                class="def-review-status-pill"
                :class="
                  isMinedStandard(selectedStandard)
                    ? statusClass(selectedStandard.status)
                    : 'is-predefined'
                "
              >
                {{
                  isMinedStandard(selectedStandard)
                    ? stateLabel(selectedStandard.status)
                    : '预定指标'
                }}
              </span>
            </div>

            <template v-if="editingId === selectedStandard.id && isMinedStandard(selectedStandard)">
              <div class="def-candidate-edit-grid">
                <input v-model="editDraft.name" type="text" placeholder="指标名称" />
                <input v-model="editDraft.level1" type="text" placeholder="一级指标" />
                <input v-model="editDraft.level2" type="text" placeholder="二级指标" />
                <input v-model="editDraft.level3" type="text" placeholder="三级指标" />
                <textarea v-model="editDraft.definition" rows="4" placeholder="指标定义"></textarea>
              </div>
              <div class="def-review-actions">
                <button
                  class="btn btn-success btn-sm"
                  type="button"
                  @click="saveEdit(selectedStandard)"
                >
                  保存修改
                </button>
                <button class="btn btn-secondary btn-sm" type="button" @click="cancelEdit">
                  取消
                </button>
              </div>
            </template>

            <template v-else>
              <div class="def-review-detail-table">
                <div class="def-review-detail-row">
                  <span>类型</span>
                  <strong>
                    {{ isMinedStandard(selectedStandard) ? '新挖掘候选' : '预定指标体系' }}
                  </strong>
                </div>
                <div class="def-review-detail-row">
                  <span>名称</span>
                  <strong>{{ selectedStandard.name }}</strong>
                </div>
                <div class="def-review-detail-row">
                  <span>维度层级</span>
                  <strong>
                    {{ selectedStandard.level1 }} / {{ selectedStandard.level2 }} /
                    {{ selectedStandard.level3 }}
                  </strong>
                </div>
                <div class="def-review-detail-row">
                  <span>定义</span>
                  <strong>{{ displayValue(selectedStandard.definition) }}</strong>
                </div>
                <div class="def-review-detail-row">
                  <span>可解释原因</span>
                  <strong>{{ displayValue(selectedStandard.rationale) }}</strong>
                </div>
                <div class="def-review-detail-row">
                  <span>计算公式</span>
                  <strong>{{ displayValue(selectedStandard.formula) }}</strong>
                </div>
                <div class="def-review-detail-row">
                  <span>来源</span>
                  <strong>
                    {{
                      displayValue(
                        selectedStandard.source ||
                          selectedStandard.evidenceText ||
                          selectedStandard.tag,
                      )
                    }}
                  </strong>
                </div>
              </div>

              <template v-if="isMinedStandard(selectedStandard)">
                <label class="def-review-opinion">
                  <span>审核意见：</span>
                  <textarea
                    v-model="reviewComment"
                    rows="3"
                    placeholder="输入审核意见（可选）"
                  ></textarea>
                </label>

                <div class="def-review-actions">
                  <button
                    class="btn btn-success btn-sm"
                    type="button"
                    :disabled="miningState.loading || selectedStandard.status === 'adopted'"
                    @click="emitCandidate('adopt-candidate', selectedStandard)"
                  >
                    {{ selectedStandard.status === 'adopted' ? '已采纳' : '采纳' }}
                  </button>
                  <button
                    class="btn btn-warning btn-sm"
                    type="button"
                    :disabled="miningState.loading || selectedStandard.status === 'ignored'"
                    @click="startEdit(selectedStandard)"
                  >
                    修改
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    type="button"
                    :disabled="miningState.loading || selectedStandard.status === 'ignored'"
                    @click="emitCandidate('reject-candidate', selectedStandard)"
                  >
                    {{ selectedStandard.status === 'ignored' ? '已忽略' : '忽略' }}
                  </button>
                </div>
              </template>
              <div v-else class="def-review-readonly-hint">
                该指标来自预定指标体系，默认纳入后续展示，无需在此审核。
              </div>
            </template>
          </div>
        </aside>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { DefinitionFormState, DefinitionMiningState } from '@/types/definition'
import type {
  DefinitionStandard,
  DefinitionStandardStatus,
  DefinitionTabConfig,
  DefinitionTimelineItem,
} from '@/utils/definitionConfig'

interface CandidateEditDraft {
  name: string
  level1: string
  level2: string
  level3: string
  definition: string
}

interface CandidateTreeLevel2 {
  id: string
  label: string
  items: DefinitionStandard[]
}

interface CandidateTreeLevel1 {
  id: string
  label: string
  count: number
  children: CandidateTreeLevel2[]
}

const props = defineProps<{
  config: DefinitionTabConfig
  formState: DefinitionFormState
  miningState: DefinitionMiningState
  predefinedStandards: DefinitionStandard[]
  candidateStandards: DefinitionStandard[]
}>()

const emit = defineEmits<{
  (e: 'refresh-task'): void
  (e: 'adopt-candidate', candidateId: number, comment: string): void
  (e: 'reject-candidate', candidateId: number, comment: string): void
  (e: 'update-candidate', candidateId: number, payload: CandidateEditDraft): void
  (e: 'next'): void
}>()

const agentLogAliasesById: Record<string, string[]> = {
  'agent-extract': ['PolicyTextExtractor', 'InformationExtractor'],
  'agent-match': ['DimensionMatcher', 'DimensionExtractorAgent'],
  'agent-generate': ['IndicatorGenerator'],
}

const agentNameLabels: Record<string, string> = {
  System: '系统调度',
  PolicyTextExtractor: '材料解析智能体',
  InformationExtractor: '信息提取智能体',
  DimensionMatcher: '维度匹配智能体',
  DimensionExtractorAgent: '维度抽取智能体',
  IndicatorGenerator: '指标生成智能体',
}

const editingId = ref('')
const selectedCandidateId = ref('')
const reviewComment = ref('')
const editDraft = reactive<CandidateEditDraft>({
  name: '',
  level1: '',
  level2: '',
  level3: '',
  definition: '',
})

const normalizedProgress = computed(() =>
  Math.max(0, Math.min(100, Math.round(props.miningState.progress || 0))),
)

const shortTaskId = computed(() => props.miningState.taskId.slice(0, 8))

const taskStatusLabel = computed(() => {
  const labels: Record<string, string> = {
    idle: '等待启动',
    pending: '等待执行',
    running: '后端挖掘中',
    completed: '挖掘完成',
    failed: '执行失败',
  }
  return labels[props.miningState.status] ?? '后端挖掘中'
})

const miningContext = computed(() => {
  const fileCount = props.formState.uploadedDocuments.length
  const linkCount = props.formState.webLinksText
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean).length
  return `已解析 ${fileCount} 个文件 / ${linkCount} 条链接 / ${demandLabel(props.formState.miningDemand)}`
})

const minedStandards = computed(() =>
  props.candidateStandards.filter((item) => Boolean(item.candidateId)),
)

const reviewStandards = computed(() => {
  const minedKeys = new Set(
    minedStandards.value.map((item) => `${item.level1}||${item.level2}||${item.level3}`),
  )
  const predefined = props.predefinedStandards.filter((item) => {
    const key = `${item.level1}||${item.level2}||${item.level3}`
    return !minedKeys.has(key)
  })
  return [...predefined, ...minedStandards.value]
})

const selectedStandard = computed(
  () =>
    reviewStandards.value.find((item) => item.id === selectedCandidateId.value) ??
    reviewStandards.value.find((item) => isMinedStandard(item) && item.status === 'pending') ??
    minedStandards.value[0] ??
    reviewStandards.value[0] ??
    null,
)

const reviewStats = computed(() => {
  const mined = minedStandards.value
  return {
    predefined: props.predefinedStandards.length,
    mined: mined.length,
    pending: mined.filter((item) => item.status === 'pending' || item.status === 'edited').length,
    adopted: mined.filter((item) => item.status === 'adopted').length,
  }
})

const reviewTree = computed<CandidateTreeLevel1[]>(() => {
  const level1Map = new Map<string, CandidateTreeLevel1>()

  reviewStandards.value.forEach((item) => {
    const level1Label = item.level1 || '未分组'
    const level2Label = item.level2 || '未分组'
    const level1Id = `level1-${level1Label}`
    const level2Id = `${level1Id}-level2-${level2Label}`

    if (!level1Map.has(level1Id)) {
      level1Map.set(level1Id, {
        id: level1Id,
        label: level1Label,
        count: 0,
        children: [],
      })
    }

    const level1 = level1Map.get(level1Id)!
    let level2 = level1.children.find((child) => child.id === level2Id)
    if (!level2) {
      level2 = {
        id: level2Id,
        label: level2Label,
        items: [],
      }
      level1.children.push(level2)
    }

    level2.items.push(item)
    level1.count += 1
  })

  return Array.from(level1Map.values())
})

const canEnterMindmap = computed(
  () => props.miningState.status === 'completed' || props.miningState.status === 'failed',
)

const agentCards = computed(() => {
  const logsByAgent = new Map(props.miningState.logs.map((log) => [log.agent_name, log]))
  return props.config.agents.map((agent, index) => {
    const matchedLogs = (agentLogAliasesById[agent.id] ?? [])
      .map((name) => logsByAgent.get(name))
      .filter(Boolean)
    const matchedLog = matchedLogs[matchedLogs.length - 1]
    const status =
      matchedLog?.status ??
      (props.miningState.status === 'idle' ? 'pending' : props.miningState.status)
    const done =
      status === 'completed' || (props.miningState.status === 'completed' && Boolean(matchedLog))
    const failed = status === 'failed' || props.miningState.status === 'failed'
    const running = status === 'running' || status === 'started'
    const progressPercent = progressForAgent(index, Boolean(matchedLog), done, failed)

    return {
      ...agent,
      desc: matchedLog ? displayLogMessage(matchedLog.message) : agent.desc,
      statusLabel: failed
        ? '失败'
        : done
          ? '完成'
          : running || props.miningState.loading
            ? '运行中'
            : '待执行',
      statusClass: failed
        ? 'failed'
        : done
          ? 'done'
          : running || props.miningState.loading
            ? 'pending'
            : 'pending',
      progressClass: failed ? 'failed' : done ? 'done' : 'pending',
      progressPercent,
    }
  })
})

const timelineItems = computed<DefinitionTimelineItem[]>(() => {
  if (!props.miningState.logs.length && props.miningState.loading) {
    return [
      {
        id: 'running',
        time: formatNowTime(),
        title: '系统调度',
        desc: '挖掘任务已提交，正在等待后端返回日志与候选指标。',
        status: 'running',
      },
    ]
  }

  if (!props.miningState.logs.length) return []

  return [...props.miningState.logs]
    .sort((a, b) => {
      const timeDiff = parseLogTime(a.created_at).getTime() - parseLogTime(b.created_at).getTime()
      return timeDiff !== 0 ? timeDiff : a.id - b.id
    })
    .map((log) => ({
      id: String(log.id),
      time: formatLogTime(log.created_at),
      title: displayAgentName(log.agent_name),
      desc: displayLogMessage(log.message),
      status: log.status,
    }))
})

const summaryItems = computed(() => {
  const stats = props.miningState.stats
  if (!Object.keys(stats).length) return []

  return [
    { id: 'input', label: '输入文本段数', value: stats.input_text_count ?? 0 },
    { id: 'matched', label: '匹配路径数', value: stats.matched_path_count ?? 0 },
    {
      id: 'candidate',
      label: '新挖掘候选数',
      value: stats.candidate_count ?? minedStandards.value.length,
    },
    { id: 'predefined', label: '预定三级指标', value: props.predefinedStandards.length },
    { id: 'mode', label: '算法适配模式', value: adapterModeLabel(stats.adapter_mode) },
  ]
})

watch(
  reviewStandards,
  (items) => {
    if (!items.length) {
      selectedCandidateId.value = ''
      return
    }
    if (!items.some((item) => item.id === selectedCandidateId.value)) {
      const preferred =
        items.find((item) => isMinedStandard(item) && item.status === 'pending') ??
        items.find((item) => isMinedStandard(item)) ??
        items[0]
      selectedCandidateId.value = preferred.id
    }
  },
  { immediate: true },
)

watch(selectedCandidateId, () => {
  editingId.value = ''
  reviewComment.value = ''
})

function isMinedStandard(item: DefinitionStandard) {
  return Boolean(item.candidateId)
}

function progressForAgent(index: number, hasLog: boolean, done: boolean, failed: boolean) {
  if (done) return 100
  const current = normalizedProgress.value
  const start = [0, 35, 68][index] ?? 0
  const end = [34, 67, 99][index] ?? 100
  if (failed) return Math.max(hasLog ? 18 : 0, Math.min(92, current))
  if (current < start && !hasLog) return 0
  return Math.max(hasLog ? 18 : 0, Math.min(92, ((current - start) / (end - start + 1)) * 100))
}

function selectCandidate(id: string) {
  selectedCandidateId.value = id
}

function emitCandidate(event: 'adopt-candidate' | 'reject-candidate', item: DefinitionStandard) {
  if (!item.candidateId) return
  if (event === 'adopt-candidate') {
    emit('adopt-candidate', item.candidateId, reviewComment.value.trim())
    return
  }
  emit('reject-candidate', item.candidateId, reviewComment.value.trim())
}

function startEdit(item: DefinitionStandard) {
  if (!isMinedStandard(item)) return
  editingId.value = item.id
  editDraft.name = item.name
  editDraft.level1 = item.level1
  editDraft.level2 = item.level2
  editDraft.level3 = item.level3
  editDraft.definition = item.definition
}

function saveEdit(item: DefinitionStandard) {
  if (!item.candidateId) return
  emit('update-candidate', item.candidateId, { ...editDraft })
  cancelEdit()
}

function cancelEdit() {
  editingId.value = ''
}

function displayAgentName(name: string) {
  return agentNameLabels[name] ?? name
}

function parseLogTime(value: string) {
  if (!value) return new Date(NaN)
  const normalized =
    /Z$|[+-]\d{2}:\d{2}$/.test(value) || value.includes('T')
      ? value.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(value)
        ? value
        : `${value}Z`
      : value
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? new Date(value) : date
}

function formatLogTime(value: string) {
  const date = parseLogTime(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatNowTime() {
  return new Date().toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function timelineStatusClass(status?: string) {
  if (!status) return 'success'
  if (status === 'failed') return 'failed'
  if (status === 'running' || status === 'started') return 'running'
  if (status === 'completed') return 'success'
  return 'success'
}

function timelineStatusLabel(status?: string) {
  const labels: Record<string, string> = {
    started: '已启动',
    running: '进行中',
    completed: '已完成',
    failed: '失败',
  }
  return labels[status ?? ''] ?? status ?? ''
}

function displayLogMessage(message: string) {
  if (message === 'Task started with persisted input snapshot.') {
    return '任务已创建，并已保存本次输入快照。'
  }
  const completedMatch = message.match(
    /^Task completed and generated (\d+) candidate indicators\.$/,
  )
  if (completedMatch) {
    return `任务已完成，生成 ${completedMatch[1]} 个候选指标。`
  }
  const messageLabels: Record<string, string> = {
    'Extracting governance keywords from input materials.': '正在从输入材料中抽取治理关键词。',
    'Matching level 1 and level 2 framework dimensions.': '正在匹配一级、二级指标维度。',
    'Generating candidate indicators.': '正在生成候选指标。',
  }
  return messageLabels[message] ?? message
}

function adapterModeLabel(mode: string | number | undefined) {
  const labels: Record<string, string> = {
    local_adapter: '本地适配模式',
    project1_agents_api: '课题一系统接口',
    remote_algorithm_api: '远程算法接口',
  }
  return labels[String(mode ?? 'local_adapter')] ?? '本地适配模式'
}

function demandLabel(value: string) {
  const labels: Record<string, string> = {
    level3: '三级指标挖掘',
  }
  return labels[value] ?? '三级指标挖掘'
}

function stateLabel(state: DefinitionStandardStatus) {
  const labels: Record<DefinitionStandardStatus, string> = {
    pending: '待审核',
    adopted: '已采纳',
    ignored: '已忽略',
    edited: '已修改',
  }
  return labels[state]
}

function statusClass(state: DefinitionStandardStatus) {
  return `is-${state}`
}

function displayValue(value: string | undefined) {
  return value?.trim() || '-'
}
</script>
