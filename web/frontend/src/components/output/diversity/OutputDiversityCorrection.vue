<template>
  <div class="diversity-correction">
    <div class="track-title-row">
      <h2 class="track-title">修正（多样性）</h2>
      <span
        class="stage-source"
        :class="{
          mock: store.cultureDataSource === 'demo_fixture',
          unavailable: store.cultureDataSource === 'unavailable',
        }"
      >
        {{ sourceLabel }}
      </span>
    </div>

    <template v-if="isAssessmentV1Generation">
      <div class="eval-card">
        <div class="stage-head">
          <div>
            <h4 class="stage-title">一、数据集统计信息</h4>
            <p class="stage-subtitle">
              迁移自文化评测工作台模型对比静态页面，展示 DeepSeek API 与 3-Agent
              在同一测试样本上的文化感知表现。
            </p>
          </div>
        </div>

        <div v-if="assessmentView" class="generation-dataset-panel">
          <div class="generation-metric-grid">
            <div class="generation-metric-card direct">
              <span>DeepSeek 文化感知准确率</span>
              <strong>{{ pct(assessmentView.direct.summary.composite_pass_rate) }}</strong>
              <em>DeepSeek API</em>
            </div>
            <div class="generation-metric-card agent">
              <span>3-Agent 文化感知准确率</span>
              <strong>{{ pct(assessmentView.agent.summary.composite_pass_rate) }}</strong>
              <em>3-Agent</em>
            </div>
            <div class="generation-metric-card gain">
              <span>提升</span>
              <strong>{{ generationGain }}</strong>
              <em>文化感知准确率</em>
            </div>
          </div>
          <div class="generation-radar-panel">
            <RadarChart :data="generationRadarData" :size="245" />
            <span>DeepSeek API 与 3-Agent 文化感知指标对比</span>
          </div>
        </div>
        <div v-else class="empty-preview">
          {{ store.cultureAssessmentStaticError || '尚未加载模型对比静态结果。' }}
        </div>
      </div>

      <div class="eval-card generation-samples-card">
        <div class="stage-head">
          <div>
            <h4 class="stage-title">二、个例展示</h4>
            <p class="stage-subtitle">
              展示文化评测工作台模型对比页面中的样本级信息，包括原问题、DeepSeek 回答、3-Agent
              回答和对比说明。
            </p>
          </div>
          <el-button size="small" type="primary" @click="openModelCompareModal">
            模型对比评测
          </el-button>
        </div>

        <div v-if="generationSamplePairs.length > 0" class="generation-sample-list">
          <article
            v-for="item in generationSamplePairs"
            :key="item.sample_id"
            class="generation-sample-card"
          >
            <div class="sample-head">
              <strong>{{ item.sample_id }}</strong>
              <span class="tag">{{ item.difficulty_level || '' }}</span>
            </div>
            <div class="question-box">{{ item.original_question || '' }}</div>
            <div class="compare-grid">
              <div class="answer-box direct-box">
                <b>DeepSeek</b>
                <br />
                {{ item.direct.answer_a || '' }}
              </div>
              <div class="answer-box agent-box">
                <b>3-Agent</b>
                <br />
                {{ item.agent.answer_a || '' }}
              </div>
            </div>
            <p class="advantage-note">{{ item.advantage_note || '' }}</p>
          </article>
        </div>
        <div v-else class="empty-preview">暂无可展示的模型对比个例。</div>
      </div>

      <div v-if="modelCompareModalOpen" class="modal-backdrop" @click.self="closeModelCompareModal">
        <section class="model-compare-modal" role="dialog" aria-modal="true">
          <div class="modal-head">
            <div>
              <h3>模型对比评测</h3>
              <p>对齐 8878 文化评测工作台“模型对比”流程，可运行单 DeepSeek API 或 3-Agent。</p>
            </div>
            <button
              class="icon-close"
              type="button"
              aria-label="关闭"
              @click="closeModelCompareModal"
            >
              ×
            </button>
          </div>

          <div class="assessment-job-grid">
            <div class="job-control-panel">
              <div class="console-head">
                <strong>评测控制</strong>
                <span>{{ modelConsoleStatus }}</span>
              </div>
              <div v-if="modelJobError" class="error-text">{{ modelJobError }}</div>
              <div class="job-field-grid">
                <label class="job-field">
                  <span>数据集</span>
                  <select v-model="modelJobForm.datasetId">
                    <option
                      v-for="dataset in modelConsoleDatasets"
                      :key="dataset.id"
                      :value="dataset.id"
                    >
                      {{ dataset.label }} · {{ dataset.sample_count }} 条
                    </option>
                  </select>
                </label>
                <label class="job-field">
                  <span>被测对象</span>
                  <select v-model="modelJobForm.targetMode">
                    <option value="direct">单 DeepSeek API</option>
                    <option value="agent">3-Agent</option>
                  </select>
                </label>
                <label class="job-field">
                  <span>运行后缀</span>
                  <input v-model.trim="modelJobForm.runSuffix" placeholder="可选" />
                </label>
                <label class="job-field">
                  <span>limit</span>
                  <input
                    v-model.trim="modelJobForm.limit"
                    min="1"
                    placeholder="留空表示全量"
                    type="number"
                  />
                </label>
                <label class="job-field">
                  <span>offset</span>
                  <input v-model.trim="modelJobForm.offset" min="0" type="number" />
                </label>
              </div>
              <div class="job-button-row">
                <el-button
                  type="primary"
                  size="small"
                  :loading="modelJobLoading"
                  :disabled="!modelJobForm.datasetId"
                  @click="startModelCompareJob"
                >
                  开始运行模型对比
                </el-button>
                <el-button size="small" :disabled="!modelJob?.running" @click="stopModelCompareJob">
                  停止当前任务
                </el-button>
                <el-button size="small" @click="loadModelConsoleMeta">刷新</el-button>
              </div>
            </div>

            <div class="job-status-panel">
              <div class="console-head">
                <strong>运行状态</strong>
                <span>{{ modelJob?.status || '未运行' }}</span>
              </div>
              <div class="job-progress"><div :style="{ width: `${modelJobProgress}%` }"></div></div>
              <div class="job-progress-text">
                {{ modelJob?.completed ?? 0 }} / {{ modelJob?.total ?? 0 }} ·
                {{ modelJobProgress }}%
              </div>
              <div class="job-meta-grid">
                <div>
                  <span>job_id</span>
                  <strong>{{ modelJob?.job_id || '—' }}</strong>
                </div>
                <div>
                  <span>被测对象</span>
                  <strong>{{ modelJobTargetLabel }}</strong>
                </div>
                <div>
                  <span>数据集</span>
                  <strong>{{ modelJob?.dataset_label || '—' }}</strong>
                </div>
                <div>
                  <span>结果目录</span>
                  <strong>{{ modelJob?.output_dir || '—' }}</strong>
                </div>
              </div>
              <pre class="job-log-box">{{ modelJobLogText }}</pre>
            </div>
          </div>

          <div v-if="modelJobResult?.summary" class="job-result-panel">
            <div class="console-head">
              <strong>运行结果</strong>
              <span>
                {{ modelJobResult.dataset_label || '—' }}
                {{ modelJobResult.cached ? ' · 命中缓存' : '' }}
              </span>
            </div>
            <div class="generation-metric-grid compact">
              <div class="generation-metric-card">
                <span>文化感知准确率</span>
                <strong>{{ pct(modelJobResult.summary.composite_pass_rate) }}</strong>
                <em>{{ modelJobTargetLabel }}</em>
              </div>
              <div class="generation-metric-card">
                <span>民族背景识别</span>
                <strong>{{ pct(modelJobResult.summary.ethnic_group_metric_rate) }}</strong>
              </div>
              <div class="generation-metric-card">
                <span>文化实质响应</span>
                <strong>{{ pct(modelJobResult.summary.cultural_difference_rate) }}</strong>
              </div>
              <div class="generation-metric-card">
                <span>通过样本</span>
                <strong>
                  {{ modelJobResult.summary.composite_pass_count }} /
                  {{ modelJobResult.summary.total_samples }}
                </strong>
              </div>
            </div>
            <div v-if="modelJobSamples.length" class="job-sample-results">
              <div class="job-sample-results-head">
                <strong>样本级评测结果</strong>
                <span>展示 {{ modelJobSamples.length }} 条</span>
              </div>
              <article
                v-for="sample in modelJobSamples"
                :key="sample.sample_id"
                class="job-sample-card"
              >
                <div class="job-sample-head">
                  <code>{{ sample.sample_id }}</code>
                  <span>{{ sample.difficulty_level || '—' }}</span>
                  <b>综合分 {{ sample.composite_score ?? '—' }}</b>
                </div>
                <div class="job-sample-question">
                  <p>{{ sample.original_question || '—' }}</p>
                </div>
                <div class="job-sample-answer-box">
                  <span>原问题回答</span>
                  <p>{{ sample.answer_a || '—' }}</p>
                </div>
              </article>
            </div>
          </div>
        </section>
      </div>
    </template>

    <template v-else>
      <div class="eval-card">
        <div class="stage-head">
          <div>
            <h4 class="stage-title">一、Cultural Gen 修正资产</h4>
            <p class="stage-subtitle">
              展示已有文化生成项目中的生成回答、错误示例、修正建议和改进项；当前不是自动改写闭环。
            </p>
          </div>
        </div>

        <div class="cds-stat-grid">
          <div class="cds-card cds--total">
            <div class="cds-val">{{ correctionStats.total }}</div>
            <div class="cds-lbl">修正样本</div>
          </div>
          <div class="cds-card cds--ethnic">
            <div class="cds-val">{{ correctionStats.withWrong }}</div>
            <div class="cds-lbl">含错误示例</div>
          </div>
          <div class="cds-card cds--explicit">
            <div class="cds-val">{{ correctionStats.withFix }}</div>
            <div class="cds-lbl">含修正建议</div>
          </div>
          <div class="cds-card cds--implicit">
            <div class="cds-val">{{ correctionStats.priority }}</div>
            <div class="cds-lbl">低分待优化</div>
          </div>
        </div>

        <div class="correction-main">
          <div class="correction-table-panel">
            <div class="cds-table-toolbar">
              <el-select
                v-model="filterEthnic"
                placeholder="民族"
                clearable
                size="small"
                style="width: 96px"
              >
                <el-option v-for="e in ethnicOptions" :key="e" :label="e" :value="e" />
              </el-select>
              <el-select
                v-model="filterCategory"
                placeholder="类别"
                clearable
                size="small"
                style="width: 92px"
              >
                <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
              </el-select>
              <el-select
                v-model="filterGap"
                placeholder="缺口"
                clearable
                size="small"
                style="width: 104px"
              >
                <el-option label="文化适配" value="culture" />
                <el-option label="语义质量" value="semantic" />
                <el-option label="完整度" value="integrity" />
              </el-select>
              <span class="toolbar-hint">点击样本查看右侧详情</span>
              <span class="cds-filter-count">共 {{ filteredSamples.length }} 条</span>
            </div>
            <el-table
              :data="filteredSamples"
              empty-text="暂无可展示修正样本"
              size="small"
              stripe
              highlight-current-row
              max-height="310"
              @row-click="selectSample"
            >
              <el-table-column prop="id" label="ID" width="86" />
              <el-table-column prop="ethnic" label="民族" width="74">
                <template #default="{ row }">
                  <span class="cds-ethnic-tag" :class="`cds-eth-${row.ethnic}`">
                    {{ row.ethnic }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="主要缺口" width="92">
                <template #default="{ row }">
                  <span class="gap-pill">
                    {{ weakestGap(row).label }} {{ weakestGap(row).score }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column
                prop="wrongExample"
                label="错误示例"
                min-width="170"
                show-overflow-tooltip
              />
              <el-table-column
                prop="fixSuggestion"
                label="修正建议"
                min-width="190"
                show-overflow-tooltip
              />
            </el-table>
          </div>

          <div class="correction-preview">
            <div class="preview-head">
              <strong>{{ currentSample?.id || '未选择样本' }}</strong>
              <span v-if="currentSample">
                {{ currentSample.ethnic }} · {{ currentSample.category }}
              </span>
            </div>
            <template v-if="currentSample">
              <div class="answer-compare">
                <div>
                  <span class="muted">生成回答</span>
                  <p>{{ currentSample.generated }}</p>
                </div>
                <div>
                  <span class="muted">参考答案</span>
                  <p>{{ currentSample.expected }}</p>
                </div>
              </div>
              <div class="fix-panel">
                <span class="muted">修正建议</span>
                <p>{{ currentSample.fixSuggestion || '暂无修正建议' }}</p>
                <div class="improve-tags">
                  <span v-for="item in currentSample.improveItems" :key="item">{{ item }}</span>
                  <span v-if="!currentSample.improveItems.length" class="improve-empty">
                    暂无改进项
                  </span>
                </div>
              </div>
            </template>
            <div v-else class="empty-preview">请选择左侧样本查看修正建议。</div>
          </div>
        </div>
      </div>

      <div class="eval-card assessment-correction-card">
        <div class="stage-head">
          <div>
            <h4 class="stage-title">二、文化评测 Benchmark 修正参考</h4>
            <p class="stage-subtitle">
              基于 Direct vs 3-Agent 静态对比，优先展示普通 DeepSeek 未通过、3-Agent
              通过的样本，用作文化回答修正参考。
            </p>
          </div>
          <el-button
            size="small"
            :loading="store.cultureAssessmentStaticLoading"
            @click="store.loadCultureAssessmentStaticView()"
          >
            刷新
          </el-button>
        </div>

        <div v-if="assessmentView" class="assessment-correction-layout">
          <div class="assessment-case-list">
            <button
              v-for="pair in assessmentCorrectionPairs"
              :key="pair.sample_id"
              type="button"
              class="assessment-case"
              :class="{ active: selectedAssessmentPairId === pair.sample_id }"
              @click="selectedAssessmentPairId = pair.sample_id"
            >
              <strong>
                {{ pair.expected_ethnic_group || '—' }} · {{ pair.difficulty_level || '—' }}
              </strong>
              <span>{{ pair.advantage_note }}</span>
            </button>
            <div v-if="assessmentCorrectionPairs.length === 0" class="empty-preview">
              暂无 Direct 失败且 3-Agent 通过的修正参考样本。
            </div>
          </div>

          <div class="assessment-case-detail">
            <template v-if="selectedAssessmentPair">
              <div class="preview-head">
                <strong>{{ selectedAssessmentPair.sample_id }}</strong>
                <span>参考修正，不写入正式修正闭环</span>
              </div>
              <div class="assessment-answer-grid">
                <div>
                  <span class="muted">Direct 原回答</span>
                  <p>{{ selectedAssessmentPair.direct.answer_a }}</p>
                </div>
                <div>
                  <span class="muted">3-Agent 参考回答</span>
                  <p>{{ selectedAssessmentPair.agent.answer_a }}</p>
                </div>
              </div>
              <div class="fix-panel">
                <span class="muted">Direct 失败原因</span>
                <p>{{ directFailureReason(selectedAssessmentPair) }}</p>
                <div class="improve-tags">
                  <span>明确民族识别</span>
                  <span>补充文化逻辑</span>
                  <span>判断冲突性质</span>
                  <span>说明价值底线</span>
                </div>
              </div>
            </template>
            <div v-else class="empty-preview">请选择左侧样本查看 3-Agent 修正参考。</div>
          </div>
        </div>
        <div v-else class="empty-preview">
          {{ store.cultureAssessmentStaticError || '尚未加载文化评测 Benchmark 静态对比结果。' }}
        </div>
      </div>

      <div class="eval-card" style="margin-top: 16px">
        <div class="stage-section" style="border: none; padding-bottom: 0">
          <div class="stage-title-row">
            <div>
              <h4 class="stage-title">三、自定义修正验证</h4>
              <p class="stage-subtitle">
                输入一条文化相关问题，实时调用 Cultural Gen
                返回生成回答、错误示例、修正建议和改进项。
              </p>
            </div>
          </div>

          <div class="dvc-custom-tab">
            <div class="dvc-input-row">
              <el-input
                v-model="customText"
                placeholder="输入问题，如：我是蒙古族的，平时都吃些什么？"
                size="default"
                clearable
                @keyup.enter="runCustomInfer"
              />
              <el-button
                type="primary"
                size="default"
                :loading="store.cultureAnalyzeLoading"
                @click="runCustomInfer"
              >
                分析并给出修正建议
              </el-button>
            </div>
            <div v-if="store.cultureAnalyzeLoading" class="dvc-loading-msg">
              正在调用 Cultural Gen 后端推理…
            </div>
            <CultureWorkflow
              :steps="store.cultureAgentSteps"
              :result="store.cultureAnalyzeResult"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useOutputStore } from '@/stores/output'
import CultureWorkflow from '../shared/CultureWorkflow.vue'
import RadarChart from '../shared/RadarChart.vue'
import type { CultureSample } from '@/types'
import type { RadarChartData } from '@/types'
import {
  fetchCultureAssessmentConsoleDatasets,
  fetchCultureAssessmentConsoleHealth,
  fetchCultureAssessmentConsoleJob,
  fetchCultureAssessmentConsoleJobResults,
  fetchCultureAssessmentConsoleJobs,
  startCultureAssessmentConsoleJob,
  stopCultureAssessmentConsoleJob,
  type CultureAssessmentConsoleDataset,
  type CultureAssessmentConsoleJob,
  type CultureAssessmentConsoleJobResult,
  type CultureAssessmentSamplePair,
} from '@/api/output'
import { dataSourceLabel } from '@/utils/outputHelpers'

const store = useOutputStore()

// ================================================================
// 初始化
// ================================================================

onMounted(() => {
  store.loadCultureData()
  void loadGenerationStaticView()
})

onUnmounted(() => {
  clearModelJobPoll()
})

const ASSESSMENT_V1_DATASET_ID = 'framework_cultural_diversity_evaluation_dataset_v1'
const ASSESSMENT_V1_VIEW_ID = 'cultural_diversity_evaluation_dataset_v1'

const isAssessmentV1Generation = computed(() => true)

const stats = computed(
  () =>
    store.cultureStats ?? {
      total: 0,
      explicitCount: 0,
      implicitCount: 0,
      ethnicCounts: {} as Record<string, number>,
      categoryCounts: {} as Record<string, number>,
    },
)

// ================================================================
// 筛选
// ================================================================

const filterEthnic = ref('')
const filterCategory = ref('')
const filterGap = ref('')
const selectedAssessmentPairId = ref('')

const ethnicOptions = computed(() => Object.keys(stats.value.ethnicCounts))
const categoryOptions = computed(() => Object.keys(stats.value.categoryCounts))

const filteredSamples = computed(() => {
  let list = store.cultureSamples as unknown as CultureSample[]
  if (filterEthnic.value) list = list.filter((s: CultureSample) => s.ethnic === filterEthnic.value)
  if (filterCategory.value)
    list = list.filter((s: CultureSample) => s.category === filterCategory.value)
  if (filterGap.value)
    list = list.filter((s: CultureSample) => weakestGap(s).key === filterGap.value)
  return list
})

// ================================================================
// 样本选择
// ================================================================

const currentSample = computed(
  () =>
    (store.cultureSamples as unknown as CultureSample[]).find(
      (s: CultureSample) => s.id === store.selectedCultureSampleId,
    ) ?? null,
)

const assessmentView = computed(() => store.cultureAssessmentStaticView)
const generationSamplePairs = computed(() => assessmentView.value?.sample_pairs?.slice(0, 25) || [])
const generationGain = computed(() => {
  const view = assessmentView.value
  if (!view) return '—'
  const gain =
    (view.agent.summary.composite_pass_rate - view.direct.summary.composite_pass_rate) * 100
  return `${gain.toFixed(2)}%`
})
const generationRadarData = computed<RadarChartData | null>(() => {
  const radar = assessmentView.value?.radar
  if (!radar) return null
  return {
    dimensions: radar.labels,
    series: radar.series.map((item) => ({
      name: item.name,
      values: item.values.map((value) => Math.round(value * 10000) / 100),
      stroke: item.color,
      fill: `${item.color}22`,
    })),
  }
})
const assessmentCorrectionPairs = computed(() => {
  const pairs = assessmentView.value?.sample_pairs || []
  return pairs
    .filter((pair) => pair.direct.composite_score === 0 && pair.agent.composite_score === 1)
    .slice(0, 12)
})

async function loadGenerationStaticView() {
  await store.loadCultureAssessmentStaticView(ASSESSMENT_V1_VIEW_ID)
}
const selectedAssessmentPair = computed(() => {
  const pairs = assessmentCorrectionPairs.value
  return pairs.find((pair) => pair.sample_id === selectedAssessmentPairId.value) || pairs[0] || null
})

watch(
  assessmentCorrectionPairs,
  (pairs) => {
    if (!selectedAssessmentPairId.value && pairs[0]) {
      selectedAssessmentPairId.value = pairs[0].sample_id
    }
  },
  { immediate: true },
)

function directFailureReason(pair: CultureAssessmentSamplePair) {
  const ethnicReason = pair.direct.ethnic_group_judge?.reason
  const culturalReason = pair.direct.cultural_difference_judge?.reason
  return culturalReason || ethnicReason || pair.advantage_note
}

function selectSample(row: CultureSample) {
  store.selectedCultureSampleId = row.id
}

const sourceLabel = computed(() => {
  return dataSourceLabel(store.cultureDataSource)
})

const correctionStats = computed(() => {
  const samples = store.cultureSamples as unknown as CultureSample[]
  return {
    total: samples.length,
    withWrong: samples.filter((s) => Boolean(s.wrongExample)).length,
    withFix: samples.filter((s) => Boolean(s.fixSuggestion)).length,
    priority: samples.filter((s) => weakestGap(s).score < 85).length,
  }
})

function weakestGap(s: CultureSample) {
  const gaps = [
    { key: 'culture', label: '文化适配', score: s.cultureScore },
    { key: 'semantic', label: '语义质量', score: s.semanticScore },
    { key: 'integrity', label: '完整度', score: s.integrityScore },
  ].sort((a, b) => a.score - b.score)
  return gaps[0]
}

const customText = ref('')

async function runCustomInfer() {
  if (!customText.value.trim()) return
  await store.analyzeCulture(customText.value.trim())
}

const modelCompareModalOpen = ref(false)
const modelConsoleDatasets = ref<CultureAssessmentConsoleDataset[]>([])
const modelConsoleStatus = ref('尚未连接')
const modelJob = ref<CultureAssessmentConsoleJob | null>(null)
const modelJobResult = ref<CultureAssessmentConsoleJobResult | null>(null)
const modelJobLoading = ref(false)
const modelJobError = ref('')
const modelJobForm = ref({
  datasetId: ASSESSMENT_V1_DATASET_ID,
  targetMode: 'direct' as 'direct' | 'agent',
  runSuffix: '',
  limit: '',
  offset: '0',
})
let modelJobPollTimer: ReturnType<typeof setInterval> | null = null

type ModelJobSample = Record<string, unknown> & {
  sample_id: string
  difficulty_level?: string
  expected_ethnic_group?: string
  original_question?: string
  answer_a?: string
  answer_b?: string
  composite_score?: number
}

const modelJobProgress = computed(() =>
  Math.max(0, Math.min(100, Math.round(Number(modelJob.value?.progress || 0)))),
)

const modelJobTargetLabel = computed(() => {
  const mode = modelJob.value?.target_mode || modelJobForm.value.targetMode
  return mode === 'agent' ? '3-Agent' : 'DeepSeek API'
})

const modelJobLogText = computed(() => {
  const logs = modelJob.value?.log_tail || []
  return logs.length > 0 ? logs.join('\n') : '等待日志输出'
})

const modelJobSamples = computed<ModelJobSample[]>(() =>
  (modelJobResult.value?.sample_results || [])
    .slice(0, 6)
    .map((row, index) => ({ ...row, sample_id: String(row.sample_id || `sample-${index + 1}`) })),
)

async function openModelCompareModal() {
  modelCompareModalOpen.value = true
  await loadModelConsoleMeta()
}

function closeModelCompareModal() {
  modelCompareModalOpen.value = false
}

const MODEL_COMPARE_DATASET_OPTIONS = [
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_single_sample',
    label: 'Cultural Diversity Evaluation Dataset V1(1)',
    sample_count: 1,
  },
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_random_10_samples',
    label: 'Cultural Diversity Evaluation Dataset V1(10)',
    sample_count: 10,
  },
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_random_100_samples',
    label: 'Cultural Diversity Evaluation Dataset V1(100)',
    sample_count: 100,
  },
  {
    id: ASSESSMENT_V1_DATASET_ID,
    label: 'Cultural Diversity Evaluation Dataset V1(500)',
    sample_count: 500,
  },
] satisfies CultureAssessmentConsoleDataset[]

async function loadModelConsoleMeta() {
  modelJobError.value = ''
  try {
    const [health, datasets, jobs] = await Promise.all([
      fetchCultureAssessmentConsoleHealth(),
      fetchCultureAssessmentConsoleDatasets(),
      fetchCultureAssessmentConsoleJobs(),
    ])
    modelConsoleStatus.value = `已连接 · 活跃任务 ${health.active_jobs ?? 0} · 数据集 ${health.dataset_count ?? datasets.datasets.length}`
    modelConsoleDatasets.value = normalizeModelDatasets(datasets.datasets || [])
    if (
      !modelConsoleDatasets.value.some((dataset) => dataset.id === modelJobForm.value.datasetId)
    ) {
      modelJobForm.value.datasetId = modelConsoleDatasets.value[0]?.id || ASSESSMENT_V1_DATASET_ID
    }
    const latest = (jobs.jobs || []).find((job) => job.running) || (jobs.jobs || []).at(-1)
    if (latest) {
      modelJob.value = latest
      if (latest.running) startModelJobPoll(latest.job_id)
    }
  } catch (error: unknown) {
    modelConsoleStatus.value = '控制台不可用'
    modelJobError.value =
      error instanceof Error ? error.message : '文化评测控制台连接失败，请确认 v2 服务已启动。'
    modelConsoleDatasets.value = normalizeModelDatasets([])
  }
}

function normalizeModelDatasets(datasets: CultureAssessmentConsoleDataset[]) {
  const byId = new Map(datasets.map((dataset) => [dataset.id, dataset]))
  return MODEL_COMPARE_DATASET_OPTIONS.map((option) => ({
    ...option,
    ...(byId.get(option.id) || {}),
    label: option.label,
    sample_count: option.sample_count,
  }))
}

async function startModelCompareJob() {
  if (!modelJobForm.value.datasetId) return
  modelJobLoading.value = true
  modelJobError.value = ''
  modelJobResult.value = null
  try {
    const job = await startCultureAssessmentConsoleJob({
      dataset_id: modelJobForm.value.datasetId,
      target_mode: modelJobForm.value.targetMode,
      run_suffix: modelJobForm.value.runSuffix,
      limit: modelJobForm.value.limit,
      offset: modelJobForm.value.offset || '0',
    })
    modelJob.value = job
    startModelJobPoll(job.job_id)
  } catch (error: unknown) {
    modelJobError.value = error instanceof Error ? error.message : '启动模型对比评测失败。'
  } finally {
    modelJobLoading.value = false
  }
}

function startModelJobPoll(jobId: string) {
  clearModelJobPoll()
  modelJobPollTimer = setInterval(() => {
    void pollModelJob(jobId)
  }, 2000)
  void pollModelJob(jobId)
}

function clearModelJobPoll() {
  if (modelJobPollTimer) {
    clearInterval(modelJobPollTimer)
    modelJobPollTimer = null
  }
}

async function pollModelJob(jobId: string) {
  try {
    const job = await fetchCultureAssessmentConsoleJob(jobId)
    modelJob.value = job
    if (!job.running && ['completed', 'failed', 'idle'].includes(job.status)) {
      clearModelJobPoll()
      if (job.status === 'completed') {
        modelJobResult.value = await fetchCultureAssessmentConsoleJobResults(jobId)
      }
    }
  } catch (error: unknown) {
    clearModelJobPoll()
    modelJobError.value = error instanceof Error ? error.message : '读取模型对比评测状态失败。'
  }
}

async function stopModelCompareJob() {
  if (!modelJob.value?.job_id) return
  try {
    modelJob.value = await stopCultureAssessmentConsoleJob(modelJob.value.job_id)
    clearModelJobPoll()
  } catch (error: unknown) {
    modelJobError.value = error instanceof Error ? error.message : '停止模型对比评测失败。'
  }
}

function pct(value?: number) {
  if (typeof value !== 'number') return '—'
  return `${(value * 100).toFixed(2)}%`
}
</script>

<style src="./OutputDiversityCorrection.css" scoped></style>
