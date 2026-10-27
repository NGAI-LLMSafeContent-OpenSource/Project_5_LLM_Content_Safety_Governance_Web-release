<template>
  <section class="standard-workbench">
    <header class="standard-workbench__header">
      <div>
        <div class="standard-workbench__eyebrow">Dynamic Benchmark</div>
        <h1>动态 Benchmark</h1>
        <p>选择方向并生成评测数据，完成后可下载评测集。</p>
      </div>
      <button type="button" class="standard-workbench__link" @click="emit('go-expert')">
        完整视图
      </button>
    </header>

    <div class="standard-workbench__section">
      <h2 class="standard-workbench__section-title">1. 选择生成方向</h2>
      <div class="direction-cards" role="radiogroup" aria-label="生成方向">
        <button
          v-for="card in directionCards"
          :key="card.id"
          type="button"
          class="direction-card"
          :class="{
            'is-active': direction === card.id,
            'is-disabled': card.disabled,
          }"
          role="radio"
          :aria-checked="direction === card.id"
          :disabled="card.disabled || isBusy"
          @click="selectDirection(card.id)"
        >
          <span class="direction-card__title">{{ card.title }}</span>
          <span class="direction-card__desc">{{ card.description }}</span>
          <span class="direction-card__status">{{ card.disabled ? '后续开放' : '可生成' }}</span>
        </button>
      </div>
    </div>

    <div class="standard-workbench__section">
      <h2 class="standard-workbench__section-title">2. 配置</h2>
      <el-form label-position="top" class="standard-workbench__form" @submit.prevent>
        <el-form-item label="规模">
          <el-radio-group v-model="scale" :disabled="isBusy">
            <el-radio-button label="trial">试跑</el-radio-button>
            <el-radio-button label="standard" :disabled="direction === 'risk_content'">
              标准
            </el-radio-button>
            <el-radio-button label="large" :disabled="direction === 'risk_content'">
              大批量
            </el-radio-button>
          </el-radio-group>
          <div class="field-help">{{ scaleCountHelp }}</div>
        </el-form-item>

        <el-form-item
          v-if="direction === 'value_qa'"
          :label="isValueQaLarge ? '主题（可多选）' : '主题'"
        >
          <el-select
            v-if="!isValueQaLarge"
            v-model="topic"
            class="topic-select"
            filterable
            allow-create
            default-first-option
            :disabled="isBusy"
            :loading="topicOptionsLoading"
            placeholder="从列表选择或输入自定义主题"
          >
            <el-option v-for="item in topicCatalog" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select
            v-else
            v-model="topics"
            class="topic-select"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            allow-create
            default-first-option
            :disabled="isBusy"
            :loading="topicOptionsLoading"
            placeholder="从列表选择至少 2 个主题"
          >
            <el-option v-for="item in topicCatalog" :key="item" :label="item" :value="item" />
          </el-select>
          <div v-if="topicCatalogUnavailable" class="field-help">
            完整主题词表暂不可用，请手动输入主题后继续。
          </div>
          <div v-else-if="isValueQaLarge" class="field-help">
            每个主题约 6 条；选得越多耗时越长。请至少选 2 个，不设上限。
          </div>
          <div v-else class="field-help">
            优先从内置主题列表选择；也可输入自定义主题。自定义主题需公开资料较完整，否则可能生成 0
            条。
          </div>
          <div v-if="isCustomTopic" class="field-help field-help--warn">
            当前为自定义主题，若资料不足可能生成 0 条。
          </div>
        </el-form-item>

        <el-form-item v-if="direction === 'dynamic_difficulty'">
          <template #label>
            <span class="form-label-with-tip">
              结构层级
              <el-tooltip
                content="H1–H4 是有害/无害怎么混合，不是风险高低。标准模式默认四档均衡覆盖。"
                placement="top"
                :show-after="200"
              >
                <el-icon class="form-label-tip" tabindex="0" aria-label="结构层级说明">
                  <QuestionFilled />
                </el-icon>
              </el-tooltip>
            </span>
          </template>
          <div class="field-help">默认均衡覆盖 H1–H4，不按「简单/困难」拆档。</div>
          <ul class="level-glossary" aria-label="H1 到 H4 分级说明">
            <li v-for="row in H_LEVEL_GLOSSARY" :key="row.level" class="is-covered">
              <strong>{{ row.level }}</strong>
              {{ row.text }}
            </li>
          </ul>
          <div class="field-help">H2 和 H3 不是谁一定更难；H4 才是结构最复杂的一档。</div>
        </el-form-item>

        <el-form-item v-if="direction === 'anomaly_rewrite'" label="改写强度">
          <el-radio-group v-model="rewriteStrength" :disabled="isBusy">
            <el-radio-button label="light">简单</el-radio-button>
            <el-radio-button label="strong">困难</el-radio-button>
          </el-radio-group>
          <div class="field-help">一次只选一档；表示改写强度（轮数上限），不是题目难度。</div>
        </el-form-item>

        <el-form-item v-if="direction === 'cultural_diversity'">
          <template #label>
            <span class="form-label-with-tip">
              难度等级
              <el-tooltip
                content="这里的低/中/高，指文化语境难度（L1–L3），不是风险高低，也不是 H1–H4。"
                placement="top"
                :show-after="200"
              >
                <el-icon class="form-label-tip" tabindex="0" aria-label="难度等级说明">
                  <QuestionFilled />
                </el-icon>
              </el-tooltip>
            </span>
          </template>
          <el-radio-group v-model="structureBand" :disabled="isBusy">
            <el-radio-button label="explicit">低难度为主（L1）</el-radio-button>
            <el-radio-button label="mixed">混合（L1–L3）</el-radio-button>
            <el-radio-button label="implicit_heavy">中高难度（L2–L3）</el-radio-button>
          </el-radio-group>
          <div class="field-help">这里的低/中/高，指文化语境难度（L1–L3），不是风险高低。</div>
          <div class="field-help">{{ structureBandHelp }}</div>
          <el-button
            link
            type="primary"
            class="glossary-toggle"
            @click="lGlossaryOpen = !lGlossaryOpen"
          >
            低/中/高难度是什么
            <el-icon class="more-options__arrow" :class="{ 'is-open': lGlossaryOpen }">
              <ArrowRight />
            </el-icon>
          </el-button>
          <el-collapse-transition>
            <ul v-show="lGlossaryOpen" class="level-glossary" aria-label="低中高难度分级说明">
              <li v-for="row in L_LEVEL_GLOSSARY" :key="row.level">
                <strong>{{ row.level }}</strong>
                {{ row.text }}
              </li>
            </ul>
          </el-collapse-transition>
          <div
            v-if="structureBand === 'mixed' || structureBand === 'implicit_heavy'"
            class="field-help field-help--warn"
          >
            中高难度档依赖课题三质量红线；若生成失败（红线/超时），请改回「低难度为主」或反馈任务
            ID。
          </div>
        </el-form-item>

        <div
          v-if="direction === 'cultural_diversity' || direction === 'dynamic_difficulty'"
          class="more-options"
        >
          <el-button
            link
            type="primary"
            class="more-options__toggle"
            @click="moreOptionsOpen = !moreOptionsOpen"
          >
            更多选项
            <el-icon class="more-options__arrow" :class="{ 'is-open': moreOptionsOpen }">
              <ArrowRight />
            </el-icon>
          </el-button>
          <el-collapse-transition>
            <div v-show="moreOptionsOpen" class="more-options__body">
              <el-form-item v-if="direction === 'cultural_diversity'" label="民族">
                <el-checkbox-group v-model="ethnicGroups" :disabled="isBusy">
                  <el-checkbox v-for="group in culturalEthnicOptions" :key="group" :label="group">
                    {{ group }}
                  </el-checkbox>
                </el-checkbox-group>
                <div class="field-help">默认四民族全选；至少保留 1 个。</div>
              </el-form-item>
              <el-form-item v-if="direction === 'dynamic_difficulty'" label="抽样范围">
                <el-checkbox-group
                  v-model="riskCategories"
                  class="risk-category-group"
                  :disabled="isBusy"
                >
                  <el-checkbox
                    v-for="item in riskCategoryOptions"
                    :key="item.code"
                    :label="item.code"
                  >
                    {{ item.code }} {{ item.name }}
                  </el-checkbox>
                </el-checkbox-group>
                <div class="field-help">
                  默认 17 类全选，按约定条数随机抽样。缩小范围请取消不需要的类；至少保留 1 个。
                </div>
              </el-form-item>
            </div>
          </el-collapse-transition>
        </div>

        <div class="standard-workbench__actions">
          <el-button
            type="primary"
            size="large"
            :loading="isStarting || isPolling"
            :disabled="!direction || isBusy"
            @click="handleStart"
          >
            开始生成
          </el-button>
          <span v-if="!direction" class="field-help">请先选择生成方向</span>
        </div>
      </el-form>
    </div>

    <div class="standard-workbench__section result-panel">
      <h2 class="standard-workbench__section-title">3. 进度与结果</h2>

      <div v-if="resultPhase === 'idle'" class="result-state">
        <p class="result-state__title">生成结果将显示在这里</p>
        <p class="result-state__desc">选择方向并点击「开始生成」后，可在此查看进度与结果。</p>
      </div>

      <div v-else-if="resultPhase === 'running'" class="result-state">
        <p class="result-state__title">{{ runActivity }}</p>
        <p class="result-state__desc">
          任务 ID：{{ task?.task_id || '创建中' }}
          <template v-if="elapsedLabel">· 已运行 {{ elapsedLabel }}</template>
        </p>
        <el-steps class="run-steps" :active="runStepIndex" finish-status="success" align-center>
          <el-step v-for="title in STANDARD_RUN_STEP_TITLES" :key="title" :title="title" />
        </el-steps>
        <p v-if="scaleHint" class="result-state__hint">{{ scaleHint }}</p>
      </div>

      <div v-else-if="resultPhase === 'success'" class="result-state result-state--success">
        <p class="result-state__title">生成完成</p>
        <p class="result-state__desc">
          任务 {{ task?.task_id }} 已完成。
          <template v-if="artifactCount > 0">已冻结 {{ artifactCount }} 个资产。</template>
        </p>
        <div class="result-state__actions">
          <el-button
            type="primary"
            :loading="isDownloading"
            :disabled="!task?.task_id"
            @click="handleDownloadEvalset"
          >
            下载评测集
          </el-button>
          <el-button :disabled="isDownloading" @click="handleStart">再生成一批</el-button>
        </div>
      </div>

      <div v-else class="result-state result-state--error">
        <p class="result-state__title">生成未完成</p>
        <p class="result-state__desc">{{ displayError }}</p>
        <p v-if="feedbackTaskId" class="result-state__meta">任务 ID：{{ feedbackTaskId }}</p>
        <div class="result-state__actions">
          <el-button type="primary" :loading="isStarting" @click="handleStart">重试</el-button>
          <el-button @click="openExpertForTask">查看任务详情（专家模式）</el-button>
        </div>
      </div>
    </div>

    <footer class="standard-workbench__footer">
      详见
      <button
        type="button"
        class="standard-workbench__guide-link"
        aria-haspopup="dialog"
        @click="guideDrawerVisible = true"
      >
        使用说明
      </button>
    </footer>

    <BenchmarkStandardGuideDrawer v-model="guideDrawerVisible" />
  </section>
</template>

<script setup lang="ts">
import { ArrowRight, QuestionFilled } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import BenchmarkStandardGuideDrawer from './BenchmarkStandardGuideDrawer.vue'
import {
  createBenchmarkTask,
  downloadBenchmarkEvalset,
  getTopic1ValueQaTopics,
  getTopic3RiskTaxonomy,
} from '@/api/benchmark'
import {
  useBenchmarkTaskPolling,
  type BenchmarkTaskPolling,
} from '@/composables/benchmark/useBenchmarkTaskPolling'
import type { BenchmarkAgentId, BenchmarkRiskCategory, BenchmarkTask } from '@/types'
import { mapStandardBenchmarkFailure } from '@/utils/benchmark/mapStandardBenchmarkFailure'
import {
  formatStandardRunElapsed,
  resolveStandardRunActivity,
  resolveStandardRunElapsedMs,
  resolveStandardRunStepIndex,
  resolveStandardScaleHint,
  STANDARD_RUN_STEP_TITLES,
} from '@/utils/benchmark/mapStandardBenchmarkRunProgress'
import {
  buildStandardBenchmarkTaskPayload,
  DEFAULT_CULTURAL_ETHNIC_GROUPS,
  estimateStandardSampleCount,
  STANDARD_DIRECTION_TO_AGENT,
  TOPIC2_DURATION_HINT_BY_SCALE,
  TOPIC3_DIFFICULTY_DURATION_HINT_BY_SCALE,
  TOPIC3_RISK_CATEGORY_FALLBACK,
  type CulturalStructureBand,
  type StandardBenchmarkDirection,
  type StandardBenchmarkScale,
  type StandardRewriteStrength,
} from '@/utils/benchmark/standardTaskPayload'

const emit = defineEmits<{
  (event: 'go-expert', payload?: { tab?: string; agent?: BenchmarkAgentId; task?: string }): void
}>()

const guideDrawerVisible = ref(false)

const directionCards: Array<{
  id: StandardBenchmarkDirection
  title: string
  description: string
  disabled?: boolean
}> = [
  {
    id: 'value_qa',
    title: '价值语料',
    description: '生成高/中/低价值样本，用于价值判别评测',
  },
  {
    id: 'dynamic_difficulty',
    title: '动态难度',
    description: '生成有害/无害混合文本，用于合规编辑评测（结构层级 H1–H4）',
  },
  {
    id: 'anomaly_rewrite',
    title: '异常改写',
    description: '生成简单或困难档异常样本，用于污染识别评测',
  },
  {
    id: 'cultural_diversity',
    title: '文化多样性',
    description: '生成多民族语境评测语料；按低/中/高难度（L1–L3）',
  },
  {
    id: 'risk_content',
    title: '风险内容',
    description: '生成 safe / low 风险评测样本（本期仅试跑 10 条）',
  },
]

const H_LEVEL_GLOSSARY = [
  {
    level: 'H1',
    text: '一段有害 + 一段无害，边界较清楚。测能不能把有害和无害分开看，别整段一刀切。',
  },
  {
    level: 'H2',
    text: '两段有害 + 一段无害。测多个风险点会不会漏掉。',
  },
  {
    level: 'H3',
    text: '一段有害 + 两段无害。测会不会把无害内容误判成风险。',
  },
  {
    level: 'H4',
    text: '有害和无害多段交错。当前结构最复杂，不能只靠关键词判断。',
  },
] as const

const L_LEVEL_GLOSSARY = [
  {
    level: 'L1',
    text: '低难度：背景直接点名民族。测文化事实对不对。',
  },
  {
    level: 'L2',
    text: '中难度：多个文化特征，较容易锁定民族。测不点名时会不会还答对。',
  },
  {
    level: 'L3',
    text: '高难度：只有很隐蔽的一条线索。测最容易误判的语境。',
  },
] as const

const culturalEthnicOptions = [...DEFAULT_CULTURAL_ETHNIC_GROUPS]
const fallbackRiskCategories: BenchmarkRiskCategory[] = TOPIC3_RISK_CATEGORY_FALLBACK.map(
  (item) => ({ code: item.code, name: item.name }),
)

const direction = ref<StandardBenchmarkDirection | null>(null)
const scale = ref<StandardBenchmarkScale>('trial')
const rewriteStrength = ref<StandardRewriteStrength>('light')
const topic = ref('中秋节')
const topics = ref<string[]>([])
const topicCatalog = ref<string[]>([])
const topicCatalogSource = ref<'keywords_5001' | 'unavailable' | 'pending'>('pending')
const topicOptionsLoading = ref(false)
const ethnicGroups = ref<string[]>([...DEFAULT_CULTURAL_ETHNIC_GROUPS])
const structureBand = ref<CulturalStructureBand>('explicit')
const moreOptionsOpen = ref(false)
const riskCategoryOptions = ref<BenchmarkRiskCategory[]>([...fallbackRiskCategories])
const riskCategories = ref<string[]>(fallbackRiskCategories.map((item) => item.code))
const lGlossaryOpen = ref(false)
const isStarting = ref(false)
const isDownloading = ref(false)
const startError = ref('')

const pollingByAgent: Record<BenchmarkAgentId, BenchmarkTaskPolling> = {
  'topic2-autobench': useBenchmarkTaskPolling(),
  'topic3-difficulty-generation': useBenchmarkTaskPolling(),
  'topic1-value-qa': useBenchmarkTaskPolling(),
  'topic3-cultural-corpus-generation': useBenchmarkTaskPolling(),
  'topic3-risk-benchmark-generation': useBenchmarkTaskPolling(),
}

const activeAgentId = computed<BenchmarkAgentId | null>(() =>
  direction.value ? STANDARD_DIRECTION_TO_AGENT[direction.value] : null,
)
const activePolling = computed(() =>
  activeAgentId.value ? pollingByAgent[activeAgentId.value] : null,
)
const task = computed(() => activePolling.value?.task.value ?? null)
const logs = computed(() => activePolling.value?.logs.value ?? [])
const artifacts = computed(() => activePolling.value?.artifacts.value ?? [])
const isPolling = computed(() => activePolling.value?.isPolling.value ?? false)
const pollingError = computed(() => activePolling.value?.errorMessage.value ?? '')

const isBusy = computed(() => isStarting.value || isPolling.value)
const artifactCount = computed(() => artifacts.value.length)
const nowMs = ref(Date.now())
let elapsedTimer: ReturnType<typeof setInterval> | undefined

const runStepIndex = computed(() =>
  resolveStandardRunStepIndex(task.value?.status, { isStarting: isStarting.value }),
)
const runActivity = computed(() =>
  resolveStandardRunActivity({
    status: task.value?.status,
    logs: logs.value,
    isStarting: isStarting.value,
  }),
)
const elapsedLabel = computed(() => {
  if (!isBusy.value) {
    return ''
  }
  const elapsedMs = resolveStandardRunElapsedMs(task.value, nowMs.value)
  if (elapsedMs <= 0 && !task.value?.started_at && !task.value?.created_at) {
    return ''
  }
  return formatStandardRunElapsed(elapsedMs)
})
const scaleHint = computed(() => resolveStandardScaleHint(scale.value))

const structureBandHelp = computed(() => {
  if (structureBand.value === 'mixed') {
    return '低 / 中 / 高难度均分（L1 / L2 / L3）'
  }
  if (structureBand.value === 'implicit_heavy') {
    return '仅中、高难度（L2 / L3）'
  }
  return '低难度（L1）；试跑最稳'
})

const formInput = computed(() => ({
  direction: direction.value ?? 'value_qa',
  scale: scale.value,
  topic: topic.value,
  topics: topics.value,
  riskCategories: riskCategories.value,
  rewriteStrength: rewriteStrength.value,
  ethnicGroups: ethnicGroups.value,
  structureBand: structureBand.value,
}))

const isValueQaLarge = computed(() => direction.value === 'value_qa' && scale.value === 'large')

const isCustomTopic = computed(() => {
  if (topicCatalogSource.value !== 'keywords_5001' || topicCatalog.value.length === 0) {
    return false
  }
  const selected = isValueQaLarge.value ? topics.value : [topic.value]
  return selected.some((item) => {
    const value = (item ?? '').trim()
    return Boolean(value) && !topicCatalog.value.includes(value)
  })
})

const topicCatalogUnavailable = computed(() => topicCatalogSource.value === 'unavailable')

const estimatedCount = computed(() =>
  direction.value ? estimateStandardSampleCount(formInput.value) : 0,
)

const scaleCountHelp = computed(() => {
  if (!direction.value) {
    return '请先选择生成方向后再看预计条数'
  }
  if (direction.value === 'anomaly_rewrite') {
    const duration = TOPIC2_DURATION_HINT_BY_SCALE[scale.value]
    return `预计约 ${estimatedCount.value} 条 / ${duration}（约数，实际可能略有出入）`
  }
  if (direction.value === 'value_qa') {
    if (scale.value === 'large') {
      const n = topics.value.map((item) => item.trim()).filter(Boolean).length
      if (n < 2) {
        return '大批量请至少选择 2 个主题；每个主题约 6 条，选得越多耗时越长'
      }
      return `预计约 ${estimatedCount.value} 条（已选 ${n} 个主题，每主题约 6 条；资料不足时可能更少）`
    }
    return `预计约 ${estimatedCount.value} 条（一组高中低共 3 行；资料不足时可能为 0 条）`
  }
  if (direction.value === 'risk_content') {
    return '本期仅试跑 10 条（5 safe + 5 low）；标准 / 大批量待课题三确认。'
  }
  if (direction.value === 'dynamic_difficulty') {
    const duration = TOPIC3_DIFFICULTY_DURATION_HINT_BY_SCALE[scale.value]
    return `预计约 ${estimatedCount.value} 条 / ${duration}（4 卡 RTX Pro 5000 估计；H1–H4 均衡；实际随显卡变化）`
  }
  return `预计约 ${estimatedCount.value} 条（条数待跨课题确认后可能调整）`
})

const resultPhase = computed(() => {
  if (startError.value || pollingError.value) {
    return 'error' as const
  }
  if (isStarting.value || isPolling.value) {
    return 'running' as const
  }
  if (task.value?.status === 'completed') {
    return 'success' as const
  }
  if (task.value && (task.value.status === 'failed' || task.value.status === 'rejected')) {
    return 'error' as const
  }
  if (!task.value) {
    return 'idle' as const
  }
  return 'running' as const
})

const feedbackTaskId = computed(
  () => task.value?.task_id || activePolling.value?.currentTaskId.value || '',
)

const displayError = computed(() => {
  const raw = startError.value || pollingError.value || task.value?.error_message || ''
  return mapStandardBenchmarkFailure(raw)
})

watch(
  isBusy,
  (busy) => {
    if (busy) {
      nowMs.value = Date.now()
      if (elapsedTimer === undefined) {
        elapsedTimer = setInterval(() => {
          nowMs.value = Date.now()
        }, 1000)
      }
      return
    }
    if (elapsedTimer !== undefined) {
      clearInterval(elapsedTimer)
      elapsedTimer = undefined
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (elapsedTimer !== undefined) {
    clearInterval(elapsedTimer)
    elapsedTimer = undefined
  }
})

watch(scale, (next, prev) => {
  if (direction.value !== 'value_qa') return
  if (next === 'large' && prev !== 'large') {
    const current = (topic.value ?? '').trim()
    if (current && topics.value.length === 0) {
      topics.value = [current]
    }
  }
  if (next !== 'large' && prev === 'large' && topics.value.length > 0) {
    topic.value = topics.value[0]
  }
})

watch(direction, (next) => {
  startError.value = ''
  moreOptionsOpen.value = false
  lGlossaryOpen.value = false
  if (next === 'risk_content') {
    scale.value = 'trial'
  }
  if (next === 'value_qa') {
    void loadValueQaTopics()
  }
  if (next === 'dynamic_difficulty') {
    void loadRiskTaxonomy()
  }
})

async function loadRiskTaxonomy() {
  try {
    const data = await getTopic3RiskTaxonomy()
    const categories = (data.categories ?? []).filter((item) => item.code && item.name)
    if (categories.length === 0) {
      return
    }
    riskCategoryOptions.value = categories
    const allowed = new Set(categories.map((item) => item.code))
    const kept = riskCategories.value.filter((code) => allowed.has(code))
    riskCategories.value = kept.length > 0 ? kept : categories.map((item) => item.code)
  } catch {
    riskCategoryOptions.value = [...fallbackRiskCategories]
    if (riskCategories.value.length === 0) {
      riskCategories.value = fallbackRiskCategories.map((item) => item.code)
    }
  }
}

async function loadValueQaTopics() {
  if (topicOptionsLoading.value) return
  topicOptionsLoading.value = true
  try {
    const data = await getTopic1ValueQaTopics()
    topicCatalog.value = data.topics ?? []
    topicCatalogSource.value = data.source === 'keywords_5001' ? 'keywords_5001' : 'unavailable'
    if (data.default_topic && !(topic.value ?? '').trim()) {
      topic.value = data.default_topic
    }
  } catch {
    topicCatalog.value = []
    topicCatalogSource.value = 'unavailable'
  } finally {
    topicOptionsLoading.value = false
  }
}

onMounted(() => {
  if (direction.value === 'value_qa') {
    void loadValueQaTopics()
  }
})

function selectDirection(id: StandardBenchmarkDirection) {
  direction.value = id
}

function bindTask(nextTask: BenchmarkTask) {
  const agentId = (STANDARD_DIRECTION_TO_AGENT[direction.value as StandardBenchmarkDirection] ||
    nextTask.agent_id) as BenchmarkAgentId
  const polling = pollingByAgent[agentId]
  polling.task.value = nextTask
  polling.logs.value = []
  polling.artifacts.value = []
  polling.errorMessage.value = ''
  polling.startPolling(nextTask.task_id)
}

async function handleStart() {
  if (!direction.value) {
    startError.value = '请先选择生成方向'
    return
  }
  startError.value = ''
  const built = buildStandardBenchmarkTaskPayload(formInput.value)
  if (!built.ok) {
    startError.value = built.error
    return
  }
  const agentId = STANDARD_DIRECTION_TO_AGENT[direction.value]
  pollingByAgent[agentId].resetPolling()
  isStarting.value = true
  try {
    const nextTask = await createBenchmarkTask(built.payload)
    bindTask(nextTask)
  } catch (error) {
    startError.value = error instanceof Error ? error.message : 'Benchmark 生成任务创建失败'
  } finally {
    isStarting.value = false
  }
}

function openExpertForTask() {
  const fromTask = task.value?.agent_id
  const agent =
    fromTask && isKnownBenchmarkAgent(fromTask)
      ? fromTask
      : direction.value
        ? STANDARD_DIRECTION_TO_AGENT[direction.value]
        : undefined
  emit('go-expert', {
    tab: 'tasks',
    agent,
    task: feedbackTaskId.value || undefined,
  })
}

function isKnownBenchmarkAgent(value: string): value is BenchmarkAgentId {
  return (Object.values(STANDARD_DIRECTION_TO_AGENT) as string[]).includes(value)
}

async function handleDownloadEvalset() {
  const taskId = task.value?.task_id
  if (!taskId) {
    ElMessage.warning('当前没有可下载的任务')
    return
  }
  isDownloading.value = true
  try {
    const blob = await downloadBenchmarkEvalset(taskId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${taskId}_evalset.zip`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('评测集已开始下载')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '下载评测集失败')
  } finally {
    isDownloading.value = false
  }
}
</script>

<style scoped>
.standard-workbench {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 26px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow);
}

.standard-workbench__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.standard-workbench__eyebrow {
  font-size: 12px;
  font-weight: 800;
  color: var(--accent-blue);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.standard-workbench__header h1 {
  margin: 6px 0 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.standard-workbench__header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.standard-workbench__link {
  flex-shrink: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent-blue);
  font: inherit;
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}

.standard-workbench__section {
  padding-top: 4px;
}

.standard-workbench__section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.direction-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.direction-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  min-height: 132px;
  padding: 16px;
  border: 1px solid rgba(21, 101, 192, 0.16);
  border-radius: 14px;
  background: rgba(13, 71, 161, 0.02);
  text-align: left;
  cursor: pointer;
}

.direction-card.is-active {
  border-color: var(--accent-blue);
  background: rgba(13, 71, 161, 0.08);
  box-shadow: inset 0 0 0 1px rgba(13, 71, 161, 0.25);
}

.direction-card.is-disabled,
.direction-card:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.direction-card__title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text-primary);
}

.direction-card__desc {
  flex: 1;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.direction-card__status {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-blue);
}

.field-help {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.topic-select {
  width: 100%;
  max-width: 420px;
}

.standard-workbench__form :deep(.el-form-item__content) > .field-help,
.standard-workbench__form :deep(.el-form-item__content) > .level-glossary,
.standard-workbench__form :deep(.el-form-item__content) > .glossary-toggle {
  flex-basis: 100%;
  margin-top: 8px;
}

.field-help--warn {
  color: #b26a00;
}

.glossary-toggle {
  display: inline-flex;
  justify-content: flex-start;
  width: fit-content;
  padding: 0;
  height: auto;
  margin-top: 8px;
  font-weight: 600;
}

.level-glossary {
  flex-basis: 100%;
  width: 100%;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.level-glossary li {
  margin: 0 0 6px;
  padding: 8px 10px;
  border: 1px solid rgba(21, 101, 192, 0.12);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.level-glossary li.is-covered {
  border-color: rgba(13, 71, 161, 0.28);
  background: rgba(13, 71, 161, 0.06);
  color: var(--text-primary);
}

.level-glossary strong {
  margin-right: 6px;
  color: var(--text-primary);
}

.form-label-with-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.form-label-tip {
  color: var(--text-secondary);
  font-size: 14px;
  cursor: help;
  outline: none;
}

.form-label-tip:hover,
.form-label-tip:focus-visible {
  color: var(--accent-blue);
}

.standard-workbench__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.more-options {
  margin-bottom: 4px;
}

.more-options__toggle {
  padding: 0;
  height: auto;
  font-weight: 600;
}

.more-options__arrow {
  margin-left: 2px;
  transition: transform 0.2s ease;
}

.more-options__arrow.is-open {
  transform: rotate(90deg);
}

.risk-category-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.more-options__body {
  padding-top: 8px;
}

.more-options :deep(.el-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.standard-workbench__guide-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--accent-blue);
  font: inherit;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

.result-panel {
  padding: 16px;
  border: 1px solid rgba(21, 101, 192, 0.12);
  border-radius: 14px;
  background: rgba(13, 71, 161, 0.02);
}

.result-state__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.result-state__desc,
.result-state__meta {
  margin: 0 0 12px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.result-state__hint {
  margin: 12px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.run-steps {
  margin-top: 8px;
}

.result-state__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.result-state--error .result-state__title {
  color: #c62828;
}

.standard-workbench__footer {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.standard-workbench__footer code {
  font-size: 12px;
}

@media (max-width: 900px) {
  .direction-cards {
    grid-template-columns: 1fr;
  }

  .standard-workbench__header {
    flex-direction: column;
  }
}
</style>
