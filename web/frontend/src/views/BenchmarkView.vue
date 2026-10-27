<template>
  <main class="benchmark-page page-wide">
    <BenchmarkAssetResourceView
      v-if="assetResourceId"
      :asset-id="assetResourceId"
      :sample-id="sampleResourceId || undefined"
    />

    <template v-else-if="isExpert">
      <el-alert class="benchmark-expert-banner" type="info" :closable="false" show-icon>
        <template #title>
          当前为专家视图；对外请使用标准模式链接。
          <button type="button" class="benchmark-mode-link" @click="goStandard">
            返回标准模式
          </button>
        </template>
      </el-alert>

      <section class="benchmark-header">
        <div>
          <div class="benchmark-header__eyebrow">Dynamic Benchmark</div>
          <h1>动态 Benchmark 多 Agent 集成系统</h1>
          <p>
            面向内容安全评测的动态 Benchmark 生成与评估系统，统一呈现数据生成、资产入库、
            质量校验、模型评估与结果对比。当前支持现场小预算生成、预跑资产展示和评测入口说明，
            并严格区分现场运行、预跑快照、可信资产与评测待导入等来源状态。
          </p>
        </div>
        <div class="benchmark-header__metrics">
          <div class="benchmark-metric">
            <span class="value">5</span>
            <span class="label">现场可跑链路</span>
          </div>
          <div class="benchmark-metric">
            <span class="value">3</span>
            <span class="label">已导入资产类型</span>
          </div>
          <div class="benchmark-metric">
            <span class="value">5</span>
            <span class="label">题库 Agent 方向</span>
          </div>
          <div class="benchmark-metric">
            <span class="value">资产闭环</span>
            <span class="label">演示阶段</span>
          </div>
        </div>
      </section>

      <section class="benchmark-workspace">
        <el-tabs v-model="activeTab" class="benchmark-tabs">
          <el-tab-pane label="总览" name="overview">
            <BenchmarkOverview @start-agent-run="handleStartAgentRun" />
          </el-tab-pane>
          <el-tab-pane label="生成任务" name="tasks">
            <BenchmarkTaskRunner
              v-model:selected-agent="selectedBenchmarkAgent"
              :task="task"
              :logs="logs"
              :artifacts="artifacts"
              :is-polling="isPolling"
              :polling-error="errorMessage"
              @task-created="handleTaskCreated"
              @reset="resetActivePolling"
              @view-assets="handleViewAssets"
            />
          </el-tab-pane>
          <el-tab-pane label="资产管理" name="assets">
            <BenchmarkAssetPanel
              :artifacts="artifacts"
              :registry-assets="registryAssets"
              :is-loading="isLoadingAssets"
              :is-active-tab="activeTab === 'assets'"
              :error-message="assetError"
              :focus-request="pendingAssetFocus"
              @refresh="loadBenchmarkAssets"
              @view-evaluations="activeTab = 'evaluations'"
              @focus-consumed="handleAssetFocusConsumed"
            />
          </el-tab-pane>
          <el-tab-pane label="模型评测" name="evaluations">
            <BenchmarkEvaluationPanel
              :registry-assets="registryAssets"
              @view-assets="handleViewAssets"
            />
          </el-tab-pane>
        </el-tabs>
      </section>
    </template>

    <BenchmarkStandardWorkbench v-else @go-expert="goExpert" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getBenchmarkAssets, getBenchmarkTask } from '@/api/benchmark'
import BenchmarkAssetPanel from '@/components/benchmark/BenchmarkAssetPanel.vue'
import BenchmarkAssetResourceView from '@/components/benchmark/BenchmarkAssetResourceView.vue'
import BenchmarkEvaluationPanel from '@/components/benchmark/BenchmarkEvaluationPanel.vue'
import BenchmarkOverview from '@/components/benchmark/BenchmarkOverview.vue'
import BenchmarkStandardWorkbench from '@/components/benchmark/BenchmarkStandardWorkbench.vue'
import BenchmarkTaskRunner from '@/components/benchmark/BenchmarkTaskRunner.vue'
import {
  useBenchmarkTaskPolling,
  type BenchmarkTaskPolling,
} from '@/composables/benchmark/useBenchmarkTaskPolling'
import { useBenchmarkViewMode } from '@/composables/benchmark/useBenchmarkViewMode'
import { canonicalizeLegacyBenchmarkAssetQuery } from '@/utils/benchmark/benchmarkAssetRoute'
import { emitBenchmarkResourceResolution } from '@/utils/benchmark/benchmarkResourceTelemetry'
import type {
  BenchmarkAgentId,
  BenchmarkArtifactItem,
  BenchmarkAssetFocusRequest,
  BenchmarkTask,
  BenchmarkViewAssetsPayload,
} from '@/types'

const activeTab = ref('overview')
const route = useRoute()
const router = useRouter()
const { isExpert, goExpert, goStandard } = useBenchmarkViewMode()
const assetResourceId = computed(() => readRouteValue(route.params.assetId))
const sampleResourceId = computed(() => readRouteValue(route.params.sampleId))
const selectedBenchmarkAgent = ref<BenchmarkAgentId>('topic2-autobench')
const registryAssets = ref<BenchmarkArtifactItem[]>([])
const isLoadingAssets = ref(false)
const assetError = ref('')
const pendingAssetFocus = ref<BenchmarkAssetFocusRequest | null>(null)
const handledFocusKeys = ref(new Set<string>())
const hydratedExpertTaskId = ref('')
const EXPERT_TABS = ['overview', 'tasks', 'assets', 'evaluations'] as const
const benchmarkAgents: BenchmarkAgentId[] = [
  'topic2-autobench',
  'topic3-difficulty-generation',
  'topic1-value-qa',
  'topic3-cultural-corpus-generation',
  'topic3-risk-benchmark-generation',
]
const pollingByAgent: Record<BenchmarkAgentId, BenchmarkTaskPolling> = {
  'topic2-autobench': useBenchmarkTaskPolling(),
  'topic3-difficulty-generation': useBenchmarkTaskPolling(),
  'topic1-value-qa': useBenchmarkTaskPolling(),
  'topic3-cultural-corpus-generation': useBenchmarkTaskPolling(),
  'topic3-risk-benchmark-generation': useBenchmarkTaskPolling(),
}
const activePolling = computed(() => pollingByAgent[selectedBenchmarkAgent.value])
const task = computed(() => activePolling.value.task.value)
const logs = computed(() => activePolling.value.logs.value)
const artifacts = computed(() => activePolling.value.artifacts.value)
const isPolling = computed(() => activePolling.value.isPolling.value)
const errorMessage = computed(() => activePolling.value.errorMessage.value)

onMounted(() => {
  if (normalizeLegacyAssetRoute()) return
  if (isExpert.value) {
    hydrateFocusRequestFromQuery()
    hydrateExpertFromQuery()
    void loadBenchmarkAssets()
  }
})

watch(
  () => route.query.focusAsset,
  () => {
    normalizeLegacyAssetRoute()
  },
)

watch(isExpert, (expert) => {
  if (expert) {
    hydrateFocusRequestFromQuery()
    hydrateExpertFromQuery()
    void loadBenchmarkAssets()
  }
})

watch(
  () => [route.query.tab, route.query.agent, route.query.task],
  () => {
    if (isExpert.value) {
      hydrateExpertFromQuery()
    }
  },
)

watch(activeTab, (tab) => {
  if (tab === 'assets' && isExpert.value) {
    void loadBenchmarkAssets()
  }
})

function handleTaskCreated(nextTask: BenchmarkTask) {
  const polling = isBenchmarkAgentId(nextTask.agent_id)
    ? pollingByAgent[nextTask.agent_id]
    : activePolling.value
  polling.task.value = nextTask
  polling.logs.value = []
  polling.artifacts.value = []
  polling.errorMessage.value = ''
  polling.startPolling(nextTask.task_id)
}

function handleStartAgentRun(agentId: BenchmarkAgentId) {
  selectedBenchmarkAgent.value = agentId
  activeTab.value = 'tasks'
}

function handleViewAssets(payload?: BenchmarkViewAssetsPayload) {
  activeTab.value = 'assets'
  const request = createFocusRequest(payload)
  pendingAssetFocus.value = request
  syncFocusAssetQuery(request.focusAssetId)
}

function handleAssetFocusConsumed(focusKey: string) {
  if (handledFocusKeys.value.has(focusKey)) {
    return
  }
  handledFocusKeys.value.add(focusKey)
  if (pendingAssetFocus.value && buildFocusKey(pendingAssetFocus.value) === focusKey) {
    pendingAssetFocus.value = null
  }
}

function resetActivePolling() {
  activePolling.value.resetPolling()
}

function isBenchmarkAgentId(value: string): value is BenchmarkAgentId {
  return benchmarkAgents.includes(value as BenchmarkAgentId)
}

function readQueryParam(raw: unknown): string {
  return readRouteValue(raw)
}

function readRouteValue(raw: unknown): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeLegacyAssetRoute(): boolean {
  if (route.name !== 'benchmark' && route.name !== 'benchmark-asset') return false
  const target = canonicalizeLegacyBenchmarkAssetQuery(route.query)
  if (!target) return false
  emitBenchmarkResourceResolution('legacy-normalized', target)
  if (target.sampleId) {
    void router.replace({
      name: 'benchmark-sample',
      params: { assetId: target.assetId, sampleId: target.sampleId },
      query: target.query,
    })
  } else {
    void router.replace({
      name: 'benchmark-asset',
      params: { assetId: target.assetId },
      query: target.query,
    })
  }
  return true
}

function hydrateExpertFromQuery() {
  const tab = readQueryParam(route.query.tab)
  if ((EXPERT_TABS as readonly string[]).includes(tab)) {
    activeTab.value = tab
  }

  const agent = readQueryParam(route.query.agent)
  const taskId = readQueryParam(route.query.task)
  if (!taskId) {
    hydratedExpertTaskId.value = ''
    if (agent && isBenchmarkAgentId(agent)) {
      selectedBenchmarkAgent.value = agent
    }
    return
  }

  const hintedAgent = isBenchmarkAgentId(agent) ? agent : selectedBenchmarkAgent.value
  const polling = pollingByAgent[hintedAgent]
  const alreadyHydrated =
    hydratedExpertTaskId.value === taskId &&
    polling.currentTaskId.value === taskId &&
    (polling.isPolling.value || polling.task.value?.task_id === taskId)
  if (alreadyHydrated) {
    return
  }

  hydratedExpertTaskId.value = taskId
  void hydrateExpertTask(taskId, agent)
}

async function hydrateExpertTask(taskId: string, hintedAgent: string) {
  let agentId: BenchmarkAgentId | null = isBenchmarkAgentId(hintedAgent) ? hintedAgent : null
  let fetchedTask: BenchmarkTask | null = null
  try {
    const nextTask = await getBenchmarkTask(taskId)
    fetchedTask = nextTask
    if (isBenchmarkAgentId(nextTask.agent_id)) {
      agentId = nextTask.agent_id
    }
  } catch {
    // Keep hinted agent and still try polling so the runner can show the error.
  }
  if (!agentId) {
    return
  }
  selectedBenchmarkAgent.value = agentId
  const polling = pollingByAgent[agentId]
  if (fetchedTask) {
    polling.task.value = fetchedTask
  }
  if (polling.currentTaskId.value !== taskId) {
    polling.startPolling(taskId)
  }
}

async function loadBenchmarkAssets() {
  isLoadingAssets.value = true
  assetError.value = ''
  try {
    const [prerunResponse, datasetSnapshotResponse] = await Promise.all([
      getBenchmarkAssets({ source_mode: 'prerun_snapshot' }),
      getBenchmarkAssets({ source_mode: 'dataset_snapshot' }),
    ])
    registryAssets.value = [...prerunResponse.assets, ...datasetSnapshotResponse.assets]
  } catch (error) {
    assetError.value = error instanceof Error ? error.message : '资产注册表读取失败'
  } finally {
    isLoadingAssets.value = false
  }
}

function createFocusRequest(payload?: BenchmarkViewAssetsPayload): BenchmarkAssetFocusRequest {
  return {
    focusAssetId: payload?.focusAssetId,
    sourceTaskId: payload?.sourceTaskId,
    sourceAgentId: payload?.sourceAgentId,
    requestedAt: Date.now(),
  }
}

function buildFocusKey(request: BenchmarkAssetFocusRequest) {
  return `${request.focusAssetId || 'section'}::${request.requestedAt}`
}

function syncFocusAssetQuery(assetId?: string) {
  const nextQuery = { ...route.query }
  if (assetId) {
    nextQuery.focusAsset = assetId
  } else {
    delete nextQuery.focusAsset
  }
  void router.replace({ query: nextQuery })
}

function hydrateFocusRequestFromQuery() {
  const raw = route.query.focusAsset
  const focusAssetId = Array.isArray(raw) ? raw[0] : raw
  if (!focusAssetId || typeof focusAssetId !== 'string') {
    return
  }
  activeTab.value = 'assets'
  pendingAssetFocus.value = {
    focusAssetId,
    requestedAt: Date.now(),
  }
}
</script>

<style scoped>
.benchmark-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.benchmark-expert-banner {
  border-radius: 12px;
}

.benchmark-mode-link {
  margin-left: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent-blue);
  font: inherit;
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}

.benchmark-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 560px);
  gap: 20px;
  padding: 24px 26px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(13, 71, 161, 0.06), rgba(46, 125, 50, 0.05)), #fff;
  box-shadow: var(--shadow);
}

.benchmark-header__eyebrow {
  font-size: 12px;
  font-weight: 800;
  color: var(--accent-blue);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.benchmark-header h1 {
  margin: 6px 0 10px;
  font-size: 30px;
  color: var(--text-primary);
}

.benchmark-header p {
  margin: 0;
  max-width: 860px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.8;
}

.benchmark-header__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  align-items: stretch;
}

.benchmark-metric {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid rgba(21, 101, 192, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
}

.benchmark-metric .value {
  font-size: 24px;
  font-weight: 800;
  color: var(--accent-blue);
  line-height: 1;
}

.benchmark-metric .label {
  color: var(--text-secondary);
  font-size: 12px;
}

.benchmark-workspace {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow);
}

.benchmark-tabs {
  padding: 18px 22px 22px;
}

@media (max-width: 1180px) {
  .benchmark-header {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .benchmark-header__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .benchmark-header__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
