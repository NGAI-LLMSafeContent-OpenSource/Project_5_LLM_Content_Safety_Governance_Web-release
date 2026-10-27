<template>
  <section class="corpus-panel">
    <div class="corpus-head">
      <div>
        <div class="corpus-title">文化语料实时生成</div>
        <div class="corpus-desc">
          对接课题三文化语料生成
          Agent，支持单样本联调和批量生成；生成结果统一进入“文化语料生成批次集合”复用。
        </div>
      </div>
      <span class="corpus-badge" :class="statusClass">{{ statusLabel }}</span>
    </div>

    <div class="mode-tabs" role="tablist" aria-label="生成模式">
      <button
        class="mode-tab"
        :class="{ active: generationMode === 'single' }"
        type="button"
        :disabled="isRunning"
        @click="setMode('single')"
      >
        单样本生成
      </button>
      <button
        class="mode-tab"
        :class="{ active: generationMode === 'batch' }"
        type="button"
        :disabled="isRunning"
        @click="setMode('batch')"
      >
        批量生成
      </button>
    </div>

    <div class="corpus-layout">
      <section class="config-card">
        <div class="card-title">
          <strong>基础配置</strong>
          <span>沿用 8766 原始项目口径</span>
        </div>
        <div class="form-grid two">
          <label class="field field-wide">
            <span>运行批次 ID</span>
            <input
              v-model.trim="runId"
              type="text"
              :disabled="isRunning"
              placeholder="自动生成批次 ID"
            />
          </label>
          <label class="field field-wide">
            <span>输出目录</span>
            <input v-model.trim="outputDir" type="text" :disabled="isRunning" />
          </label>
          <label class="field">
            <span>Skill</span>
            <select v-model="skillPath" :disabled="isRunning">
              <option value="skills">文化多样性评测数据生成 Skill</option>
            </select>
          </label>
          <label class="field">
            <span>数据来源</span>
            <select v-model="dataSourceMode" :disabled="isRunning">
              <option value="cultural_knowledge_library">民族文化知识库</option>
              <option value="seed_input_json">兼容旧 seed_input JSON</option>
            </select>
          </label>
          <label class="field field-wide">
            <span>知识库路径</span>
            <input
              v-model.trim="knowledgePath"
              type="text"
              :disabled="isRunning"
              placeholder="seed_data/cultural_knowledge"
            />
          </label>
          <label class="field field-wide">
            <span>Source 过滤</span>
            <input
              v-model.trim="seedSourcesText"
              type="text"
              :disabled="isRunning"
              placeholder="留空读取全部，可用英文逗号分隔 source_name"
            />
          </label>
        </div>
      </section>

      <section class="config-card">
        <div class="card-title">
          <strong>{{ generationMode === 'single' ? '单样本参数' : '批量参数' }}</strong>
          <span>{{ modeHint }}</span>
        </div>
        <div class="form-grid two">
          <label v-if="generationMode === 'single'" class="field">
            <span>民族</span>
            <select v-model="singleEthnic" :disabled="isRunning">
              <option v-for="ethnic in ethnicOptions" :key="ethnic" :value="ethnic">
                {{ ethnic }}
              </option>
            </select>
          </label>
          <label v-if="generationMode === 'single'" class="field">
            <span>难度</span>
            <select v-model="singleLevel" :disabled="isRunning">
              <option value="L1">L1 显式背景</option>
              <option value="L2">L2 隐式强线索</option>
              <option value="L3">L3 隐式弱线索</option>
            </select>
          </label>

          <template v-else>
            <label class="field">
              <span>L1 数量</span>
              <input
                v-model.number="difficultyCounts.L1"
                type="number"
                min="0"
                max="50"
                :disabled="isRunning"
              />
            </label>
            <label class="field">
              <span>L2 数量</span>
              <input
                v-model.number="difficultyCounts.L2"
                type="number"
                min="0"
                max="50"
                :disabled="isRunning"
              />
            </label>
            <label class="field">
              <span>L3 数量</span>
              <input
                v-model.number="difficultyCounts.L3"
                type="number"
                min="0"
                max="50"
                :disabled="isRunning"
              />
            </label>
            <label class="field">
              <span>批大小</span>
              <input
                v-model.number="batchSize"
                type="number"
                min="1"
                max="10"
                :disabled="isRunning"
              />
            </label>
          </template>

          <label class="field">
            <span>随机种子</span>
            <input
              v-model.number="randomSeed"
              type="number"
              min="0"
              max="999999999"
              :disabled="isRunning"
              placeholder="留空自动生成"
            />
          </label>
          <label class="field">
            <span>并发</span>
            <input
              v-model.number="composerConcurrency"
              type="number"
              min="1"
              max="16"
              :disabled="isRunning"
            />
          </label>
        </div>

        <div v-if="generationMode === 'batch'" class="ethnic-block">
          <div class="ethnic-toolbar">
            <strong>民族范围</strong>
            <div>
              <button class="tiny-btn" type="button" :disabled="isRunning" @click="selectAllEthnic">
                全选
              </button>
              <button class="tiny-btn" type="button" :disabled="isRunning" @click="clearEthnic">
                清空
              </button>
            </div>
          </div>
          <div class="ethnic-row">
            <label v-for="ethnic in ethnicOptions" :key="ethnic" class="ethnic-check">
              <input
                v-model="selectedEthnicGroups"
                type="checkbox"
                :value="ethnic"
                :disabled="isRunning"
              />
              <span>{{ ethnic }}</span>
            </label>
          </div>
        </div>
      </section>
    </div>

    <details class="advanced-config">
      <summary>模型与审核参数</summary>
      <div class="form-grid five">
        <label class="field field-wide">
          <span>API Base</span>
          <input v-model.trim="apiBase" type="text" :disabled="isRunning" />
        </label>
        <label class="field">
          <span>模型</span>
          <input v-model.trim="model" type="text" :disabled="isRunning" />
        </label>
        <label class="field">
          <span>Max tokens</span>
          <input
            v-model.number="maxTokens"
            type="number"
            min="128"
            max="4096"
            :disabled="isRunning"
          />
        </label>
        <label class="field">
          <span>温度</span>
          <input
            v-model.number="temperature"
            type="number"
            min="0"
            max="2"
            step="0.1"
            :disabled="isRunning"
          />
        </label>
        <label class="field">
          <span>超时秒</span>
          <input v-model.number="timeout" type="number" min="30" max="600" :disabled="isRunning" />
        </label>
        <label class="field">
          <span>丢弃重试</span>
          <input
            v-model.number="discardRetryLimit"
            type="number"
            min="1"
            max="50"
            :disabled="isRunning"
          />
        </label>
      </div>
    </details>

    <div class="param-summary">
      <span>当前配置</span>
      <strong>{{ parameterSummary }}</strong>
    </div>

    <div class="corpus-actions">
      <button
        class="btn btn-primary"
        :disabled="store.cultureCorpusJobLoading || isRunning || !canStart"
        @click="startJob"
      >
        {{ store.cultureCorpusJobLoading ? '启动中...' : '开始生成' }}
      </button>
      <button class="btn" :disabled="!isRunning || store.cultureCorpusJobLoading" @click="stopJob">
        停止
      </button>
      <button class="btn" :disabled="!canSyncRun" @click="syncGeneratedRun">同步批次集合</button>
    </div>

    <div v-if="store.cultureCorpusJob" class="job-box">
      <div class="job-top">
        <div>
          <span class="job-kicker">任务状态</span>
          <strong>{{ store.cultureCorpusJob.job_id }}</strong>
        </div>
        <span>{{ jobModeLabel }}</span>
      </div>
      <div class="job-progress">
        <div class="job-progress-bar" :style="{ width: `${safeProgress}%` }"></div>
      </div>
      <div class="job-meta">
        <span>{{ store.cultureCorpusJob.generated }} / {{ store.cultureCorpusJob.total }} 条</span>
        <span>{{ safeProgress }}%</span>
      </div>
      <div class="job-stats">
        <div>
          <span>运行模式</span>
          <strong>{{ jobModeHint }}</strong>
        </div>
        <div v-if="store.cultureCorpusJob.config_path">
          <span>配置文件</span>
          <code>{{ store.cultureCorpusJob.config_path }}</code>
        </div>
        <div v-if="store.cultureCorpusJob.samples_path">
          <span>样本文件</span>
          <code>{{ store.cultureCorpusJob.samples_path }}</code>
        </div>
      </div>
      <div v-if="latestSamples.length > 0" class="sample-preview">
        <article v-for="sample in latestSamples" :key="sample.id" class="sample-card">
          <div class="sample-head">
            <strong>{{ sample.ethnic || sample.inferred || '未标注民族' }}</strong>
            <span>{{ sample.difficultyLevel || '未标注难度' }}</span>
          </div>
          <p>{{ sample.fullQuestion || sample.expected || '暂无问题文本' }}</p>
          <small>{{ sample.knowledge || '暂无知识点摘要' }}</small>
        </article>
      </div>
      <details v-if="store.cultureCorpusJob.log_tail" class="job-log">
        <summary>查看运行日志</summary>
        <pre>{{ store.cultureCorpusJob.log_tail }}</pre>
      </details>
    </div>

    <div v-if="store.cultureCorpusJobError" class="corpus-error">
      {{ store.cultureCorpusJobError }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useOutputStore } from '@/stores/output'
import { useToast } from '@/composables/common/useToast'

type GenerationMode = 'single' | 'batch'
type DifficultyLevel = 'L1' | 'L2' | 'L3'

const store = useOutputStore()
const toast = useToast()

const generationMode = ref<GenerationMode>('single')
const runId = ref(defaultRunId('single'))
const outputDir = ref(`runs/${runId.value}`)
const skillPath = ref('skills')
const dataSourceMode = ref<'cultural_knowledge_library' | 'seed_input_json'>(
  'cultural_knowledge_library',
)
const knowledgePath = ref('seed_data/cultural_knowledge')
const seedSourcesText = ref('')
const singleEthnic = ref('蒙古族')
const singleLevel = ref<DifficultyLevel>('L1')
const batchSize = ref(5)
const randomSeed = ref<number | null>(null)
const difficultyCounts = reactive<Record<DifficultyLevel, number>>({ L1: 5, L2: 0, L3: 0 })
const selectedEthnicGroups = ref<string[]>(['回族', '蒙古族', '藏族', '维吾尔族'])
const ethnicOptions = ['回族', '蒙古族', '藏族', '维吾尔族']
const apiBase = ref('https://api.deepseek.com/v1')
const model = ref('deepseek-chat')
const maxTokens = ref(1024)
const temperature = ref(0.2)
const timeout = ref(180)
const composerConcurrency = ref(4)
const discardRetryLimit = ref(12)

const isRunning = computed(() => Boolean(store.cultureCorpusJob?.running))
const latestSamples = computed(() => store.cultureCorpusJobSamples.slice(-4).reverse())
const canSyncRun = computed(() =>
  Boolean(store.cultureCorpusJob && store.cultureCorpusJob.generated > 0),
)
const safeProgress = computed(() =>
  Math.min(100, Math.max(0, Number(store.cultureCorpusJob?.progress || 0))),
)
const canStart = computed(() => resolvedTotal.value > 0 && selectedEthnicForMode.value.length > 0)

const selectedEthnicForMode = computed(() =>
  generationMode.value === 'single'
    ? [singleEthnic.value].filter(Boolean)
    : selectedEthnicGroups.value,
)

const normalizedCounts = computed(() => {
  if (generationMode.value === 'single') {
    return {
      L1: singleLevel.value === 'L1' ? 1 : 0,
      L2: singleLevel.value === 'L2' ? 1 : 0,
      L3: singleLevel.value === 'L3' ? 1 : 0,
    }
  }
  return {
    L1: normalizedCount(difficultyCounts.L1, 0),
    L2: normalizedCount(difficultyCounts.L2, 0),
    L3: normalizedCount(difficultyCounts.L3, 0),
  }
})

const resolvedTotal = computed(
  () => normalizedCounts.value.L1 + normalizedCounts.value.L2 + normalizedCounts.value.L3,
)

const statusLabel = computed(() => {
  const job = store.cultureCorpusJob
  if (!job) return '未启动'
  if (job.running) return '生成中'
  if (job.status === 'completed') return '已完成'
  if (job.status === 'failed') return '失败'
  if (job.status === 'stopped') return '已停止'
  return job.status || '已停止'
})

const statusClass = computed(() => {
  const job = store.cultureCorpusJob
  if (!job) return 'idle'
  if (job.running) return 'running'
  if (job.status === 'completed') return 'done'
  if (job.status === 'failed') return 'error'
  return 'idle'
})

const modeHint = computed(() =>
  generationMode.value === 'single'
    ? '固定 1 条样本，用于快速端到端验证'
    : '按民族范围和 L1/L2/L3 难度分布生成',
)

const jobModeLabel = computed(() => {
  const mode = store.cultureCorpusJob?.integration_mode
  if (mode === 'upstream_service') return '上游 8766 Job API'
  if (mode === 'local_demo_adapter') return '本地脚本适配'
  return '接入模式未标注'
})

const jobModeHint = computed(() => {
  const runner = store.cultureCorpusJob?.runner
  if (runner === 'topic3_http_job_api') return '任务生命周期由课题三 8766 服务管理'
  if (runner === 'local_subprocess_adapter') return 'Project5 后端临时启动课题三脚本'
  return '等待后端返回运行边界'
})

const parameterSummary = computed(() => {
  const difficulty = Object.entries(normalizedCounts.value)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => `${key} ${value}`)
    .join(' / ')
  const ethnics = selectedEthnicForMode.value.join('、') || '未选择民族'
  const batch = generationMode.value === 'single' ? 1 : normalizedBatchSize(resolvedTotal.value)
  const seed = normalizedSeed()
  return `${generationMode.value === 'single' ? '单样本' : '批量'} · ${resolvedTotal.value} 条 · 批大小 ${batch} · ${difficulty} · ${ethnics}${seed === undefined ? '' : ` · seed ${seed}`}`
})

watch(runId, (value) => {
  outputDir.value = `runs/${value || defaultRunId(generationMode.value)}`
})

function setMode(mode: GenerationMode) {
  generationMode.value = mode
  runId.value = defaultRunId(mode)
  if (mode === 'single') {
    batchSize.value = 1
  } else {
    batchSize.value = 5
  }
}

function defaultRunId(mode: GenerationMode) {
  const stamp = new Date()
    .toISOString()
    .replace(/[-:TZ.]/g, '')
    .slice(0, 14)
  return `topic5_culture_${mode}_${stamp}`
}

function normalizedCount(value: number, fallback: number) {
  const n = Number.isFinite(value) ? Math.floor(value) : fallback
  return Math.max(0, Math.min(n, 50))
}

function normalizedBatchSize(total: number) {
  const n = Number.isFinite(batchSize.value) ? Math.floor(batchSize.value) : Math.min(total, 5)
  return Math.max(1, Math.min(n, Math.min(total || 1, 10)))
}

function normalizedSeed() {
  const value: unknown = randomSeed.value
  if (value === null || value === undefined || value === '') return undefined
  const n = Number(value)
  if (!Number.isFinite(n)) return undefined
  return Math.max(0, Math.floor(n))
}

function seedSources() {
  return seedSourcesText.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function selectAllEthnic() {
  selectedEthnicGroups.value = [...ethnicOptions]
}

function clearEthnic() {
  selectedEthnicGroups.value = []
}

async function startJob() {
  if (!canStart.value) {
    toast.info('生成参数不完整', '请至少选择一个民族，并保证生成样本数大于 0。')
    return
  }
  const seed = normalizedSeed()
  const currentRunId = runId.value || defaultRunId(generationMode.value)
  try {
    await store.startCultureCorpusGeneration({
      run_id: currentRunId,
      output_dir: outputDir.value || `runs/${currentRunId}`,
      mode: generationMode.value,
      total_sample_count: resolvedTotal.value,
      batch_size: normalizedBatchSize(resolvedTotal.value),
      random_seed: seed,
      language: 'zh',
      sample_mode: 'cultural_mixed',
      skill_path: skillPath.value,
      data_source_mode: dataSourceMode.value,
      cultural_knowledge_library_path: knowledgePath.value,
      seed_sources: seedSources(),
      difficulty_counts: normalizedCounts.value,
      allowed_ethnic_groups: selectedEthnicForMode.value,
      api_base: apiBase.value,
      model: model.value,
      max_tokens: Number(maxTokens.value),
      temperature: Number(temperature.value),
      timeout: Number(timeout.value),
      composer_concurrency: Number(composerConcurrency.value),
      discard_retry_limit: Number(discardRetryLimit.value),
    })
    toast.success(
      '文化语料生成已启动',
      '可在当前窗口查看进度、日志和最近样本，完成后同步到批次集合。',
    )
  } catch {
    toast.error(
      '文化语料生成启动失败',
      store.cultureCorpusJobError || '请检查 8766 服务和后端环境变量。',
    )
  }
}

async function stopJob() {
  try {
    await store.stopCultureCorpusGeneration()
    toast.info('已停止生成任务', '已保留当前已经生成的样本。')
  } catch {
    toast.error('停止失败', store.cultureCorpusJobError || '任务状态不可用。')
  }
}

async function syncGeneratedRun() {
  const ok = await store.syncCultureCorpusGeneratedRun()
  if (ok) {
    toast.success(
      '批次集合已同步',
      '可在数据集列表选择“文化语料生成批次集合”，再在右侧按批次筛选。',
    )
  } else {
    toast.info('暂无可同步样本', '请等待至少生成 1 条样本后再同步。')
  }
}

onUnmounted(() => {
  store.clearCultureCorpusPolling()
})
</script>

<style src="./CultureCorpusGeneratorPanel.css" scoped></style>
