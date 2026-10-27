<template>
  <div class="evaluation-panel">
    <section class="evaluation-hero">
      <div>
        <h3>模型评测结果面板</h3>
        <p>
          本区只消费已冻结的 Benchmark 资产或已导入的预跑评测结果。生成任务完成不代表模型评测完成；
          每条结果都需要独立的模型、运行时间和来源标识。正式 simple / hard
          结果导入前不展示模拟跑分。
        </p>
      </div>
      <span class="source-pill" :class="{ 'is-muted': scoreRows.length === 0 }">
        {{ scoreRows.length > 0 ? 'prerun_snapshot' : 'unavailable' }}
      </span>
    </section>

    <BenchmarkTopic1ValueQaEvaluationSection
      :registry-assets="registryAssets"
      @view-assets="$emit('view-assets')"
    />

    <section v-if="primaryTopic2Asset" class="evaluation-section topic2-evaluation-section">
      <div class="topic2-section-header">
        <div>
          <h2>课题二异常语料改写评测</h2>
          <p>
            基于 simple / hard 配对样本，展示异常语料改写后对不同 Moderator
            拦截能力的影响。当前展示的是已导入的 prerun_snapshot 结果，不触发在线评测。
          </p>
        </div>
        <span class="source-pill">prerun_snapshot</span>
      </div>

      <div class="topic2-metric-notes">
        <article v-for="metric in topic2MetricHighlights" :key="metric.name">
          <b>{{ metric.name }}</b>
          <span>{{ metric.desc }}</span>
        </article>
      </div>

      <div class="topic2-summary-card">
        <div class="topic2-summary-card__main">
          <div>
            <span class="section-kicker">课题二 / simple-hard 预跑资产</span>
            <h3>预跑资产概览</h3>
            <p>
              {{ primaryTopic2Asset.name }} 已作为正式 prerun_snapshot 导入；simple / hard
              使用同源配对样本和同一套指标脚本，用于展示改写后难度变化对 Moderator 拦截能力的影响。
            </p>
          </div>
          <div class="topic2-summary-actions">
            <span class="source-pill">prerun_snapshot</span>
            <el-button size="small" type="primary" @click="openTopic2Samples(primaryTopic2Asset)">
              查看未拦截样本
            </el-button>
          </div>
        </div>

        <div class="topic2-summary-grid">
          <article>
            <span>总样本</span>
            <strong>{{ getTopic2TotalCount(primaryTopic2Asset) }}</strong>
          </article>
          <article>
            <span>simple</span>
            <strong>{{ getTopic2DifficultyCount(primaryTopic2Asset, 'simple') }}</strong>
          </article>
          <article>
            <span>hard</span>
            <strong>{{ getTopic2DifficultyCount(primaryTopic2Asset, 'hard') }}</strong>
          </article>
          <article>
            <span>配对组</span>
            <strong>{{ getTopic2PairCount(primaryTopic2Asset) }}</strong>
          </article>
          <article>
            <span>Moderator</span>
            <strong>{{ getTopic2ModeratorCount(primaryTopic2Asset) }}</strong>
          </article>
          <article>
            <span>ASR 口径</span>
            <strong>{{ getTopic2AsrDefinition(primaryTopic2Asset) }}</strong>
          </article>
        </div>

        <dl class="topic2-trace-grid">
          <div>
            <dt>Evaluator Version</dt>
            <dd>{{ getTopic2EvaluatorVersion(primaryTopic2Asset) }}</dd>
          </div>
          <div>
            <dt>Source Commit</dt>
            <dd class="mono">{{ getManifestString(primaryTopic2Asset, 'source_commit') }}</dd>
          </div>
          <div>
            <dt>Artifact SHA-256</dt>
            <dd class="mono">{{ primaryTopic2Asset.artifact_sha256 || '-' }}</dd>
          </div>
          <div>
            <dt>Asset ID</dt>
            <dd class="mono">{{ primaryTopic2Asset.asset_id }}</dd>
          </div>
        </dl>
      </div>

      <div v-if="comparisonRows.length > 0" class="topic2-subsection">
        <div class="section-title-row">
          <div>
            <h3>ASR / Recall 对比</h3>
            <p>
              同属课题二异常语料改写预跑数据；ASR 越高表示 unsafe 样本越容易被判 safe，Recall
              越高表示 unsafe 样本越容易被正确拦截。
            </p>
          </div>
          <span class="source-pill">simple vs hard</span>
        </div>
        <div class="topic2-bar-grid">
          <article v-for="row in comparisonRows" :key="`${row.assetId}-${row.model}`">
            <div class="topic2-bar-card__header">
              <div>
                <h4>{{ row.model }}</h4>
                <p>{{ row.provider || row.modelVersion || '异常语料改写预跑评测' }}</p>
              </div>
              <span class="delta-pill" :class="{ 'is-positive': (row.delta.asr ?? 0) > 0 }">
                Delta ASR {{ formatDelta(row.delta.asr) }}
              </span>
            </div>
            <div class="topic2-metric-bars">
              <div class="topic2-metric-bar">
                <span>simple ASR</span>
                <div>
                  <i class="is-simple" :style="{ width: `${toPercent(row.simple.asr)}%` }"></i>
                </div>
                <b>{{ formatMetric(row.simple.asr) }}</b>
              </div>
              <div class="topic2-metric-bar">
                <span>hard ASR</span>
                <div>
                  <i class="is-hard" :style="{ width: `${toPercent(row.hard.asr)}%` }"></i>
                </div>
                <b>{{ formatMetric(row.hard.asr) }}</b>
              </div>
              <div class="topic2-metric-bar">
                <span>simple Recall</span>
                <div>
                  <i class="is-recall" :style="{ width: `${toPercent(row.simple.recall)}%` }"></i>
                </div>
                <b>{{ formatMetric(row.simple.recall) }}</b>
              </div>
              <div class="topic2-metric-bar">
                <span>hard Recall</span>
                <div>
                  <i
                    class="is-hard-recall"
                    :style="{ width: `${toPercent(row.hard.recall)}%` }"
                  ></i>
                </div>
                <b>{{ formatMetric(row.hard.recall) }}</b>
              </div>
            </div>
            <div class="topic2-card-actions">
              <el-button size="small" @click="openTopic2SamplesByAssetId(row.assetId)">
                查看未拦截样本
              </el-button>
            </div>
          </article>
        </div>
      </div>

      <div class="topic2-subsection">
        <div class="section-title-row">
          <div>
            <h3>Moderator 排名表</h3>
            <p>同属课题二异常语料改写预跑数据；默认按 hard ASR 降序展示。</p>
          </div>
        </div>
        <div class="score-table" :class="{ 'is-empty': rankingRows.length === 0 }">
          <div class="score-row score-row--head score-row--ranking">
            <span>模型 / Baseline</span>
            <span>类型</span>
            <span>simple Recall</span>
            <span>hard Recall</span>
            <span>simple ASR</span>
            <span>hard ASR</span>
            <span>Delta ASR</span>
            <span>来源</span>
            <span>样本</span>
          </div>
          <template v-if="rankingRows.length > 0">
            <div
              v-for="row in rankingRows"
              :key="`${row.assetId}-${row.model}`"
              class="score-row score-row--ranking"
              :class="{ 'is-baseline': row.isBaseline }"
            >
              <span>
                <b>{{ row.model }}</b>
                <small>{{ row.provider || row.modelVersion || '异常语料改写预跑评测' }}</small>
              </span>
              <span>{{ row.isBaseline ? '弱 baseline' : row.provider || 'moderator' }}</span>
              <span>{{ formatMetric(row.simple.recall) }}</span>
              <span>{{ formatMetric(row.hard.recall) }}</span>
              <span>{{ formatMetric(row.simple.asr) }}</span>
              <span>{{ formatMetric(row.hard.asr) }}</span>
              <span>{{ formatDelta(row.delta.asr) }}</span>
              <span>prerun_snapshot</span>
              <span>
                <el-button
                  size="small"
                  text
                  type="primary"
                  @click="openTopic2SamplesByAssetId(row.assetId)"
                >
                  未拦截
                </el-button>
              </span>
            </div>
          </template>
          <el-empty
            v-else
            description="等待导入课题二正式 prerun_snapshot 评测结果。缺少模型版本、运行时间或 simple / hard 血缘字段时不展示跑分。"
          />
        </div>
      </div>

      <details class="topic2-metric-detail">
        <summary>完整指标口径说明</summary>
        <div class="topic2-metric-detail__grid">
          <article v-for="metric in metricDetails" :key="metric.name">
            <b>{{ metric.name }}</b>
            <span>{{ metric.desc }}</span>
          </article>
        </div>
      </details>
    </section>

    <section class="evaluation-section">
      <div class="risk-evaluation-title">
        <div>
          <h3>课题三动态风险评测入口</h3>
          <p>
            动态风险 Benchmark 资产已就绪时，可作为 safe / low / medium / high
            四档风险识别评测输入；评测结果按服务端登记的同版本资产展示。
          </p>
        </div>
        <span class="source-pill" :class="{ 'is-muted': topic3RiskAssets.length === 0 }">
          {{ topic3RiskAssets.length > 0 ? 'asset ready' : 'asset unavailable' }}
        </span>
      </div>

      <el-empty
        v-if="topic3RiskAssets.length === 0"
        description="尚未导入课题三动态风险 safe/low Benchmark 资产。"
      />
      <div v-else class="risk-evaluation-grid">
        <article
          v-for="asset in topic3RiskAssets"
          :key="asset.asset_id"
          class="risk-evaluation-card"
        >
          <div class="risk-evaluation-card__header">
            <div>
              <h4>{{ asset.name }}</h4>
              <span class="risk-asset-id">{{ asset.asset_id }}</span>
            </div>
            <span
              class="risk-status-pill"
              :class="{ 'is-imported': getTopic3Summary(asset)?.available }"
            >
              {{
                getTopic3Summary(asset)?.available ? 'evaluation imported' : 'evaluation pending'
              }}
            </span>
          </div>

          <p class="risk-pending-copy">
            {{
              getTopic3Summary(asset)?.available
                ? '已导入同版本预跑评测结果，展示服务端返回的 baseline 与当前算法对比，不启用在线 live_eval。'
                : '动态风险 Benchmark 资产已就绪，可用于风险识别评测；当前尚未导入模型评测结果。'
            }}
          </p>

          <dl class="risk-asset-fields">
            <div>
              <dt>Safe Count</dt>
              <dd>{{ getManifestFirstString(asset, ['safe_count', 'safe_total']) }}</dd>
            </div>
            <div>
              <dt>Risk Count</dt>
              <dd>{{ getManifestFirstString(asset, ['risk_total', 'low_count']) }}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{{ getManifestString(asset, 'sample_count') }}</dd>
            </div>
            <div>
              <dt>Taxonomy</dt>
              <dd>{{ getManifestString(asset, 'taxonomy_schema') }}</dd>
            </div>
            <div>
              <dt>QA Issues</dt>
              <dd>{{ getRiskQaIssueCount(asset) }}</dd>
            </div>
            <div>
              <dt>Source Mode</dt>
              <dd>{{ asset.source_mode }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>Created At</dt>
              <dd>{{ formatDate(asset.created_at) }}</dd>
            </div>
          </dl>

          <div v-if="getTopic3Summary(asset)?.available" class="topic3-result-panel">
            <div class="risk-metric-structure__header">
              <div>
                <b>课题三预跑导入结果</b>
                <p>
                  {{ getTopic3Summary(asset)?.source_label }}，首屏按课题三任务书三项主指标展示。
                </p>
              </div>
              <span class="source-pill">imported_result</span>
            </div>
            <div class="topic3-model-grid">
              <article
                v-for="result in getTopic3Summary(asset)?.results || []"
                :key="result.model_run_id"
                class="topic3-model-card"
                :class="{ 'is-primary': result.role === 'primary' }"
              >
                <div class="topic3-model-card__title">
                  <div>
                    <h4>{{ result.display_name }}</h4>
                    <p>
                      {{ result.role }} · {{ result.model_version }} ·
                      {{ formatDate(result.evaluated_at) }}
                    </p>
                  </div>
                  <span class="source-pill">{{ result.role }}</span>
                </div>
                <div class="topic3-primary-metrics">
                  <div
                    v-for="metric in getTopic3Summary(asset)?.primary_metrics || []"
                    :key="`${result.model_id}-${metric.key}`"
                  >
                    <span>{{ metric.display_name }}</span>
                    <strong>{{ formatOptionalMetric(result.primary_metrics[metric.key]) }}</strong>
                  </div>
                </div>
                <p class="topic3-model-note">
                  predictions {{ result.predictions_count }} 条；C01-C17 分类表现作为展开分析保留。
                </p>
              </article>
            </div>
          </div>

          <div class="risk-metric-structure">
            <div class="risk-metric-structure__header">
              <div>
                <b>可评测指标结构</b>
                <p>以下为结果导入后的计算口径，本阶段不产生分数。</p>
              </div>
              <el-button size="small" type="primary" @click="$emit('view-assets')">
                查看资产样本
              </el-button>
            </div>
            <div class="risk-metric-grid">
              <article v-for="metric in riskMetricStructures" :key="metric.name">
                <h4>{{ metric.name }}</h4>
                <p>{{ metric.desc }}</p>
              </article>
            </div>
          </div>

          <p class="risk-asset-note">
            当前可在资产管理页查看 safe/low 样本、taxonomy 覆盖、QA 报告和 label_reason。
          </p>
        </article>
      </div>
    </section>

    <section class="evaluation-section">
      <div class="risk-evaluation-title">
        <div>
          <h3>课题三文化多样性评测入口</h3>
          <p>
            文化多样性资产已导入后可作为评测输入候选；当前阶段仅展示语料构成统计，模型评测保持
            pending_import。
          </p>
        </div>
        <span class="source-pill" :class="{ 'is-muted': topic3CulturalAssets.length === 0 }">
          {{ topic3CulturalAssets.length > 0 ? 'asset ready' : 'asset unavailable' }}
        </span>
      </div>

      <el-empty
        v-if="topic3CulturalAssets.length === 0"
        description="尚未导入课题三文化多样性预跑资产。"
      />
      <div v-else class="risk-evaluation-grid">
        <article
          v-for="asset in topic3CulturalAssets"
          :key="asset.asset_id"
          class="risk-evaluation-card"
        >
          <div class="risk-evaluation-card__header">
            <div>
              <h4>{{ asset.name }}</h4>
              <span class="risk-asset-id">{{ asset.asset_id }}</span>
            </div>
            <span class="risk-status-pill">evaluation pending</span>
          </div>
          <p class="risk-pending-copy">
            资产可用于文化感知准确率评测输入；待导入正式结果后再展示模型分数和对比。
          </p>
          <dl class="risk-asset-fields">
            <div>
              <dt>Total</dt>
              <dd>{{ getManifestString(asset, 'sample_count') }}</dd>
            </div>
            <div>
              <dt>Difficulty</dt>
              <dd>{{ getCulturalDistributionLabel(asset, 'difficulty_distribution') }}</dd>
            </div>
            <div>
              <dt>Ethnic</dt>
              <dd>{{ getCulturalDistributionLabel(asset, 'ethnic_distribution') }}</dd>
            </div>
            <div>
              <dt>Background Type</dt>
              <dd>{{ getCulturalDistributionLabel(asset, 'background_type_distribution') }}</dd>
            </div>
            <div>
              <dt>Review Passed</dt>
              <dd>
                {{ getManifestString(asset, 'review_passed_count') }}/{{
                  getManifestString(asset, 'sample_count')
                }}
              </dd>
            </div>
            <div>
              <dt>Model Eval</dt>
              <dd>{{ getManifestString(asset, 'model_eval_status') }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>Created At</dt>
              <dd>{{ formatDate(asset.created_at) }}</dd>
            </div>
          </dl>
          <div class="risk-metric-structure">
            <div class="risk-metric-structure__header">
              <div>
                <b>评测输入候选已就绪</b>
                <p>可在资产页查看详细样本，再按评测方案导入文化评测结果。</p>
              </div>
              <el-button size="small" type="primary" @click="$emit('view-assets')">
                查看资产样本
              </el-button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section v-if="baselineRows.length > 0" class="evaluation-section">
      <h3>Baseline 跑分面板</h3>
      <div class="baseline-grid">
        <article v-for="row in baselineRows" :key="row.model" class="baseline-card">
          <div>
            <h4>{{ row.model }}</h4>
            <p>keyword 仅作为弱 baseline / smoke test，不代表正式效果上限。</p>
          </div>
          <div class="baseline-metrics">
            <span>simple ASR {{ formatMetric(row.simple.asr) }}</span>
            <span>hard ASR {{ formatMetric(row.hard.asr) }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="evaluation-section">
      <h3>结果来源标识</h3>
      <div class="source-row">
        <span v-for="source in sources" :key="source.key" class="source-pill">
          {{ source.label }}
        </span>
      </div>
    </section>

    <BenchmarkTopic2PrerunSampleDrawer
      v-model="topic2SampleDrawerVisible"
      :asset="selectedTopic2Asset"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getTopic3RiskEvaluationSummary } from '@/api/benchmark'
import { formatApiDate } from '@/utils/datetime'
import BenchmarkTopic1ValueQaEvaluationSection from './BenchmarkTopic1ValueQaEvaluationSection.vue'
import BenchmarkTopic2PrerunSampleDrawer from './BenchmarkTopic2PrerunSampleDrawer.vue'
import type { BenchmarkArtifactItem, BenchmarkTopic3RiskEvaluationSummary } from '@/types'

type BenchmarkMetricKey = 'recall' | 'fnr' | 'fpr' | 'f1' | 'asr'
type DifficultyKey = 'simple' | 'hard'
type MetricMap = Record<BenchmarkMetricKey, number | null>

interface EvaluationModerator {
  name?: unknown
  provider?: unknown
  model_version?: unknown
  run_at?: unknown
  by_difficulty?: unknown
  delta?: unknown
}

interface ScoreRow {
  assetId: string
  assetName: string
  model: string
  provider: string
  modelVersion: string
  difficulty: DifficultyKey
  metrics: MetricMap
  source: string
  isBaseline: boolean
}

interface ComparisonRow {
  assetId: string
  assetName: string
  model: string
  provider: string
  modelVersion: string
  simple: MetricMap
  hard: MetricMap
  delta: MetricMap
  isBaseline: boolean
}

const props = defineProps<{
  registryAssets: BenchmarkArtifactItem[]
}>()

defineEmits<{
  (event: 'view-assets'): void
}>()

const metricKeys: BenchmarkMetricKey[] = ['recall', 'fnr', 'fpr', 'f1', 'asr']

const topic3RiskSummaries = ref<Record<string, BenchmarkTopic3RiskEvaluationSummary | null>>({})
const topic2SampleDrawerVisible = ref(false)
const selectedTopic2Asset = ref<BenchmarkArtifactItem | null>(null)

const topic2MetricHighlights = [
  { name: 'Recall', desc: '风险样本被正确识别并拦截的比例，越高越好。' },
  { name: 'ASR', desc: '风险样本绕过 Moderator、被判为 safe 的比例，越低越好。' },
  { name: 'Delta ASR', desc: 'hard 相比 simple 的 ASR 增量，用于观察改写后的绕过难度变化。' },
]

const metricDetails = [
  { name: 'Recall', desc: '风险样本被正确识别并拦截的比例，越高越好。' },
  { name: 'ASR', desc: '风险样本绕过 Moderator、被判为 safe 的比例，越低越好。' },
  { name: 'Delta ASR', desc: 'hard 相比 simple 的 ASR 增量，用于观察改写后的绕过难度变化。' },
  { name: 'FNR', desc: '风险样本未被识别的比例，越低越好。' },
  { name: 'FPR', desc: '正常样本被误判为风险的比例，越低越好。' },
  { name: 'F1', desc: '综合 Precision 与 Recall 的平衡指标，越高越好。' },
]

const sources = [
  { key: 'live_eval', label: 'live_eval' },
  { key: 'prerun_snapshot', label: 'prerun_snapshot' },
  { key: 'imported_result', label: 'imported_result' },
  { key: 'demo_fixture', label: 'demo_fixture' },
  { key: 'unavailable', label: 'unavailable' },
]

const riskMetricStructures = [
  {
    name: 'Safe 误报率',
    desc: 'safe 样本被误判为风险的比例。',
  },
  {
    name: 'Low 风险识别率',
    desc: 'low 样本被识别为风险或边界风险的比例。',
  },
  {
    name: 'C01-C17 分类命中率',
    desc: '预测类别与标注类别的匹配情况。',
  },
  {
    name: '边界解释一致性',
    desc: 'safe / low / medium / high 分级解释是否与标注理由一致。',
  },
  {
    name: '样本级对照',
    desc: 'prediction 与 label_reason 的逐条比较。',
  },
]

const hiddenTopic3RiskAssetIds = new Set(['topic3_risk_workflow_v3_safe_low_400'])

const topic3RiskAssets = computed(() =>
  props.registryAssets.filter((asset) => {
    if (hiddenTopic3RiskAssetIds.has(asset.asset_id)) {
      return false
    }
    if (asset.manifest.benchmark_type !== 'risk_content_generation') {
      return false
    }
    if (asset.manifest.agent_id !== 'topic3-risk-benchmark-generation') {
      return false
    }
    // 评测面板只展示预跑正式集；标准模式 live_run 试跑不得冒充 17×60 评测资产
    if (asset.source_mode !== 'prerun_snapshot') {
      return false
    }
    if (asset.manifest.release_kind === 'live_run_trial') {
      return false
    }
    return true
  }),
)

const topic3CulturalAssets = computed(() =>
  props.registryAssets.filter(
    (asset) =>
      asset.manifest.benchmark_type === 'cultural_diversity_generation' &&
      asset.manifest.agent_id === 'topic3-cultural-corpus-generation',
  ),
)

watch(
  () => topic3RiskAssets.value.map((asset) => asset.asset_id).join('|'),
  () => {
    void loadTopic3RiskSummaries()
  },
  { immediate: true },
)

const topic2PrerunAssets = computed(() =>
  props.registryAssets.filter(
    (asset) =>
      asset.source_mode === 'prerun_snapshot' &&
      asset.manifest.benchmark_type !== 'risk_content_generation',
  ),
)

const topic2EvaluationAssets = computed(() =>
  topic2PrerunAssets.value.filter((asset) => getEvaluationSummary(asset) !== null),
)

const primaryTopic2Asset = computed(() => topic2EvaluationAssets.value[0] || null)

const scoreRows = computed<ScoreRow[]>(() => {
  return topic2PrerunAssets.value.flatMap((asset) => {
    const summary = getEvaluationSummary(asset)
    const moderators = Array.isArray(summary?.moderators) ? summary.moderators : []
    return moderators.flatMap((moderator) =>
      buildScoreRows(asset, moderator as EvaluationModerator),
    )
  })
})

const comparisonRows = computed<ComparisonRow[]>(() => {
  return topic2PrerunAssets.value.flatMap((asset) => {
    const summary = getEvaluationSummary(asset)
    const moderators = Array.isArray(summary?.moderators) ? summary.moderators : []
    return moderators
      .map((moderator) => buildComparisonRow(asset, moderator as EvaluationModerator))
      .filter((row): row is ComparisonRow => row !== null)
  })
})

const baselineRows = computed(() =>
  comparisonRows.value.filter((row) => row.model.toLowerCase() === 'keyword'),
)

const rankingRows = computed(() =>
  [...comparisonRows.value].sort((a, b) => {
    if (a.isBaseline !== b.isBaseline) {
      return a.isBaseline ? 1 : -1
    }
    return (b.hard.asr ?? -1) - (a.hard.asr ?? -1)
  }),
)

function formatDate(value?: string | null) {
  return formatApiDate(value)
}

function getManifestString(asset: BenchmarkArtifactItem, key: string) {
  const value = asset.manifest[key]
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '-'
}

function getManifestFirstString(asset: BenchmarkArtifactItem, keys: string[]) {
  for (const key of keys) {
    const value = asset.manifest[key]
    if (Array.isArray(value)) {
      return value.join(', ')
    }
    if (typeof value === 'string' || typeof value === 'number') {
      return String(value)
    }
  }
  return '-'
}

function getManifestObject(asset: BenchmarkArtifactItem, key: string) {
  const value = asset.manifest[key]
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function getCulturalDistributionLabel(asset: BenchmarkArtifactItem, key: string) {
  const distribution = getManifestObject(asset, key)
  if (!distribution) {
    return '-'
  }
  const entries = Object.entries(distribution)
    .filter(([, value]) => typeof value === 'number')
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
  if (entries.length === 0) {
    return '-'
  }
  return entries.map(([name, value]) => `${name} ${toDisplayNumber(value)}`).join(' / ')
}

function getRiskQaIssueCount(asset: BenchmarkArtifactItem) {
  const qa = getManifestObject(asset, 'qa')
  return toDisplayNumber(qa?.issue_count)
}

async function loadTopic3RiskSummaries() {
  const next = { ...topic3RiskSummaries.value }
  await Promise.all(
    topic3RiskAssets.value.map(async (asset) => {
      if (next[asset.asset_id] !== undefined) {
        return
      }
      try {
        next[asset.asset_id] = await getTopic3RiskEvaluationSummary(asset.asset_id)
      } catch {
        next[asset.asset_id] = null
      }
    }),
  )
  topic3RiskSummaries.value = next
}

function getTopic3Summary(asset: BenchmarkArtifactItem) {
  return topic3RiskSummaries.value[asset.asset_id] || null
}

function buildScoreRows(asset: BenchmarkArtifactItem, moderator: EvaluationModerator) {
  const byDifficulty = getRecord(moderator.by_difficulty)
  const rows: ScoreRow[] = []
  for (const difficulty of ['simple', 'hard'] as const) {
    const metrics = normalizeMetrics(byDifficulty?.[difficulty])
    if (!metrics) {
      continue
    }
    rows.push({
      assetId: asset.asset_id,
      assetName: asset.name,
      model: stringValue(moderator.name) || 'unknown',
      provider: stringValue(moderator.provider),
      modelVersion: stringValue(moderator.model_version),
      difficulty,
      metrics,
      source: 'prerun_snapshot',
      isBaseline: (stringValue(moderator.name) || '').toLowerCase() === 'keyword',
    })
  }
  return rows
}

function buildComparisonRow(
  asset: BenchmarkArtifactItem,
  moderator: EvaluationModerator,
): ComparisonRow | null {
  const byDifficulty = getRecord(moderator.by_difficulty)
  const simple = normalizeMetrics(byDifficulty?.simple)
  const hard = normalizeMetrics(byDifficulty?.hard)
  if (!simple || !hard) {
    return null
  }
  const delta = normalizeMetrics(moderator.delta) || buildMetricDelta(simple, hard)
  return {
    assetId: asset.asset_id,
    assetName: asset.name,
    model: stringValue(moderator.name) || 'unknown',
    provider: stringValue(moderator.provider),
    modelVersion: stringValue(moderator.model_version),
    simple,
    hard,
    delta,
    isBaseline: (stringValue(moderator.name) || '').toLowerCase() === 'keyword',
  }
}

function buildMetricDelta(simple: MetricMap, hard: MetricMap) {
  return metricKeys.reduce<MetricMap>((acc, key) => {
    const simpleValue = simple[key]
    const hardValue = hard[key]
    acc[key] =
      typeof hardValue === 'number' && typeof simpleValue === 'number'
        ? hardValue - simpleValue
        : null
    return acc
  }, {} as MetricMap)
}

function getEvaluationSummary(asset: BenchmarkArtifactItem) {
  const summary = getRecord(asset.manifest.evaluation_summary)
  if (summary === null) {
    return null
  }
  if (summary.available !== true) {
    return null
  }
  return summary
}

function getTopic2TotalCount(asset: BenchmarkArtifactItem) {
  const summary = getManifestObject(asset, 'platform_summary')
  const counts = getNestedObject(summary, 'difficulty_counts')
  const total = toDisplayNumber(counts.simple) + toDisplayNumber(counts.hard)
  return total || toDisplayNumber(asset.manifest.sample_count)
}

function getTopic2DifficultyCount(asset: BenchmarkArtifactItem, difficulty: DifficultyKey) {
  const summary = getManifestObject(asset, 'platform_summary')
  const counts = getNestedObject(summary, 'difficulty_counts')
  const summaryValue = toDisplayNumber(counts[difficulty])
  if (summaryValue > 0) {
    return summaryValue
  }
  const manifestCounts = getManifestObject(asset, 'sample_count_by_difficulty')
  return toDisplayNumber(manifestCounts?.[difficulty])
}

function getTopic2PairCount(asset: BenchmarkArtifactItem) {
  const summary = getManifestObject(asset, 'platform_summary')
  return toDisplayNumber(summary?.pair_count)
}

function getTopic2ModeratorCount(asset: BenchmarkArtifactItem) {
  const moderators = asset.manifest.moderators
  if (Array.isArray(moderators)) {
    return moderators.length
  }
  const summary = getEvaluationSummary(asset)
  const results = summary?.moderators
  return Array.isArray(results) ? results.length : 0
}

function getTopic2AsrDefinition(asset: BenchmarkArtifactItem) {
  const summary = getEvaluationSummary(asset)
  return stringValue(summary?.asr_definition) || getManifestString(asset, 'asr_definition')
}

function getTopic2EvaluatorVersion(asset: BenchmarkArtifactItem) {
  const summary = getEvaluationSummary(asset)
  return stringValue(summary?.evaluator_version) || getManifestString(asset, 'evaluator_version')
}

function openTopic2Samples(asset: BenchmarkArtifactItem) {
  selectedTopic2Asset.value = asset
  topic2SampleDrawerVisible.value = true
}

function openTopic2SamplesByAssetId(assetId: string) {
  const asset = topic2PrerunAssets.value.find((item) => item.asset_id === assetId)
  if (asset) {
    openTopic2Samples(asset)
  }
}

function normalizeMetrics(value: unknown): MetricMap | null {
  const record = getRecord(value)
  if (!record) {
    return null
  }
  const recall = numberValue(record.recall)
  const asr = numberValue(record.asr)
  if (recall === null || asr === null) {
    return null
  }
  return {
    recall,
    asr,
    fnr: numberValue(record.fnr),
    fpr: numberValue(record.fpr),
    f1: numberValue(record.f1),
  }
}

function getRecord(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function getNestedObject(value: Record<string, unknown> | null, key: string) {
  const item = value?.[key]
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    return {}
  }
  return item as Record<string, unknown>
}

function numberValue(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function formatMetric(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }
  return `${Math.round(value * 1000) / 10}%`
}

function formatOptionalMetric(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }
  return formatMetric(value)
}

function formatDelta(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatMetric(value)}`
}

function toPercent(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.min(100, value * 100))
}

function toDisplayNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}
</script>

<style scoped>
.evaluation-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.evaluation-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  background: #f8fbff;
}

.evaluation-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.evaluation-section h3,
.evaluation-hero h3,
.baseline-card h4,
.comparison-card h4,
.metric-bar-card h4,
.risk-evaluation-card h4,
.risk-metric-grid h4 {
  margin: 0;
  color: var(--text-primary);
}

.evaluation-hero p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.risk-evaluation-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.risk-evaluation-title p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.risk-evaluation-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.risk-evaluation-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  background: #fff;
}

.risk-evaluation-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-asset-id {
  display: inline-flex;
  margin-top: 6px;
  color: var(--text-muted);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.risk-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(251, 140, 0, 0.12);
  color: #b86600;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.risk-status-pill.is-imported {
  background: rgba(36, 162, 111, 0.12);
  color: #11724f;
}

.risk-pending-copy,
.risk-asset-note {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.risk-asset-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.risk-asset-fields div {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.risk-asset-fields dt {
  color: var(--text-muted);
  font-size: 12px;
}

.risk-asset-fields dd {
  margin: 5px 0 0;
  color: var(--text-primary);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.risk-metric-structure {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.topic3-result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  border: 1px solid #cfe7dc;
  border-radius: 10px;
  background: #f7fcf9;
}

.topic3-model-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.topic3-model-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.topic3-model-card.is-primary {
  border-color: #b8dccd;
  background: #fbfffd;
}

.topic3-model-card__title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.topic3-model-card__title h4 {
  margin: 0;
  font-size: 14px;
}

.topic3-model-card__title p,
.topic3-model-note {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.topic3-primary-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.topic3-primary-metrics div {
  min-width: 0;
  padding: 9px;
  border-radius: 8px;
  background: #f3f8fb;
}

.topic3-primary-metrics span {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.topic3-primary-metrics strong {
  display: block;
  margin-top: 5px;
  color: var(--text-primary);
  font-size: 17px;
}

.risk-metric-structure__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-metric-structure__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.risk-metric-structure__header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.risk-metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.risk-metric-grid article {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.risk-metric-grid h4 {
  font-size: 13px;
}

.risk-metric-grid p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.section-title-row,
.topic2-summary-card__main,
.topic2-summary-actions,
.topic2-bar-card__header,
.topic2-card-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.section-title-row p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.section-kicker {
  display: block;
  margin-bottom: 7px;
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
}

.topic2-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding-bottom: 2px;
}

.topic2-section-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 22px;
}

.topic2-section-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.topic2-metric-notes {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.topic2-metric-notes article {
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.topic2-metric-notes b,
.topic2-metric-detail b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.topic2-metric-notes span,
.topic2-metric-detail span {
  display: block;
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.topic2-summary-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid #cddff3;
  border-radius: 12px;
  background: #f8fbff;
}

.topic2-summary-card__main p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.topic2-subsection {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 4px;
}

.topic2-metric-detail {
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.topic2-metric-detail summary {
  cursor: pointer;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 800;
}

.topic2-metric-detail__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.topic2-metric-detail__grid article {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.topic2-summary-actions {
  flex-shrink: 0;
  align-items: center;
}

.topic2-summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.topic2-summary-grid article,
.topic2-trace-grid div {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.topic2-summary-grid span,
.topic2-trace-grid dt {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
}

.topic2-summary-grid strong {
  display: block;
  margin-top: 5px;
  color: var(--text-primary);
  font-size: 18px;
  overflow-wrap: anywhere;
}

.topic2-trace-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.topic2-trace-grid dd {
  margin: 5px 0 0;
  color: var(--text-primary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.topic2-bar-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.topic2-bar-grid article {
  min-width: 0;
  padding: 16px;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  background: #fff;
}

.topic2-bar-card__header h4 {
  margin: 0;
  color: var(--text-primary);
}

.topic2-bar-card__header p {
  margin: 5px 0 0;
  color: var(--text-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.delta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(91, 107, 125, 0.12);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.delta-pill.is-positive {
  background: rgba(198, 40, 40, 0.1);
  color: #c62828;
}

.topic2-metric-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.topic2-metric-bar {
  display: grid;
  grid-template-columns: 110px minmax(90px, 1fr) 48px;
  gap: 10px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 12px;
}

.topic2-metric-bar div {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f7;
}

.topic2-metric-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.topic2-metric-bar i.is-simple {
  background: #6b8bbd;
}

.topic2-metric-bar i.is-hard {
  background: #c45f45;
}

.topic2-metric-bar i.is-recall {
  background: #2f8f71;
}

.topic2-metric-bar i.is-hard-recall {
  background: #8c6bb1;
}

.topic2-metric-bar b {
  color: var(--text-primary);
  text-align: right;
}

.topic2-card-actions {
  margin-top: 14px;
}

.score-table {
  overflow-x: auto;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
}

.score-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.4fr) 90px repeat(5, 82px) 140px;
  gap: 10px;
  align-items: center;
  min-width: 910px;
  padding: 12px 14px;
  border-top: 1px solid #edf2f7;
  color: var(--text-primary);
  font-size: 13px;
}

.score-row--ranking {
  grid-template-columns: minmax(190px, 1.5fr) 100px repeat(5, 96px) 130px 80px;
  min-width: 1100px;
}

.score-row:first-child {
  border-top: 0;
}

.score-row--head {
  background: #f8fbff;
  color: var(--text-secondary);
  font-weight: 800;
}

.score-row.is-baseline {
  background: rgba(251, 140, 0, 0.08);
}

.score-row b,
.score-row small {
  display: block;
}

.score-row small {
  margin-top: 4px;
  color: var(--text-muted);
}

.baseline-grid,
.comparison-grid,
.metric-bars {
  display: grid;
  gap: 14px;
}

.baseline-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.comparison-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-bars {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.baseline-card,
.comparison-card,
.metric-bar-card {
  padding: 16px;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  background: #fff;
}

.baseline-card p,
.comparison-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.delta-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.delta-grid span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.delta-grid em {
  color: var(--text-muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.delta-grid strong {
  color: var(--text-primary);
  font-size: 15px;
}

.baseline-card {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.baseline-metrics {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 110px;
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
}

.bar-pair {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
}

.bar-pair span {
  display: block;
  min-width: 34%;
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.12);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
}

.bar-pair span + span {
  background: rgba(251, 140, 0, 0.14);
  color: #b86600;
}

.metric-bar-row {
  display: grid;
  grid-template-columns: minmax(68px, 1fr) 1.2fr 42px;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.metric-bar-row div {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f7;
}

.metric-bar-row i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent-blue);
}

.metric-bar-row b {
  color: var(--text-primary);
  text-align: right;
}

.source-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.source-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 700;
}

.source-pill.is-muted {
  background: rgba(91, 107, 125, 0.12);
  color: var(--text-secondary);
  white-space: nowrap;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
}

@media (max-width: 980px) {
  .risk-evaluation-grid,
  .risk-asset-fields,
  .baseline-grid,
  .comparison-grid,
  .delta-grid,
  .metric-bars,
  .risk-metric-grid,
  .topic3-model-grid,
  .topic3-primary-metrics,
  .topic2-summary-grid,
  .topic2-trace-grid,
  .topic2-bar-grid,
  .topic2-metric-notes,
  .topic2-metric-detail__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evaluation-hero,
  .risk-evaluation-title,
  .topic2-section-header,
  .section-title-row,
  .topic2-summary-card__main {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .risk-evaluation-grid,
  .risk-asset-fields,
  .baseline-grid,
  .comparison-grid,
  .delta-grid,
  .metric-bars,
  .risk-metric-grid,
  .topic3-model-grid,
  .topic3-primary-metrics,
  .topic2-summary-grid,
  .topic2-trace-grid,
  .topic2-bar-grid,
  .topic2-metric-notes,
  .topic2-metric-detail__grid {
    grid-template-columns: 1fr;
  }

  .baseline-card,
  .risk-evaluation-card__header,
  .risk-metric-structure__header,
  .topic2-summary-actions,
  .topic2-bar-card__header,
  .topic3-model-card__title {
    flex-direction: column;
  }

  .topic2-metric-bar {
    grid-template-columns: 1fr;
  }

  .topic2-metric-bar b {
    text-align: left;
  }
}
</style>
