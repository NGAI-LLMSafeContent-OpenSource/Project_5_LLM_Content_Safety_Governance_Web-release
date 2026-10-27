<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>运行配置</h3>
        <p>来自冻结 manifest 或任务参数。</p>
      </div>
      <span class="source-pill is-live">live_run</span>
    </div>
    <BenchmarkFieldGrid :items="parameterItems" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>本次生成内容</h3>
        <p>先说明这次现场运行的样本池快照、评测批次和产物状态，再展开证据链。</p>
      </div>
      <span class="summary-hint">{{ generatedBadge }}</span>
    </div>
    <div class="run-narrative">
      <p>{{ runNarrative }}</p>
      <p v-if="isSmallBudgetRun" class="run-narrative__note">
        本次为小预算现场链路验证，结果用于证明采样、Moderator
        调用、报告生成和产物冻结可运行，不作为正式 simple / hard 评测结论。
      </p>
    </div>
    <BenchmarkStatGrid :items="generatedStatItems" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>本次评测结果</h3>
        <p>results.json 记录本次实际参与打分的评测批次，不替代正式预跑结论。</p>
      </div>
      <span class="summary-hint">{{ resultBadge }}</span>
    </div>
    <div v-if="moderatorRows.length" class="summary-notice">
      本轮 {{ moderatorNames.length }} 个 Moderator 各评测
      {{ evaluatedSamplesPerModerator }} 条样本；样本池快照总量为
      {{ samplePool?.total ?? 0 }}，两者不是同一个计数口径。
    </div>
    <el-table v-if="moderatorRows.length" :data="moderatorRows" size="small" class="compact-table">
      <el-table-column prop="name" label="Moderator" min-width="150" />
      <el-table-column prop="total_samples" label="样本" width="80" />
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.accuracy" placement="top" effect="dark">
            <span class="metric-header">ACC</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'accuracy') }}</template>
      </el-table-column>
      <el-table-column width="100">
        <template #header>
          <el-tooltip :content="metricTooltips.precision" placement="top" effect="dark">
            <span class="metric-header">Precision</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'precision') }}</template>
      </el-table-column>
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.f1" placement="top" effect="dark">
            <span class="metric-header">F1</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'f1') }}</template>
      </el-table-column>
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.recall" placement="top" effect="dark">
            <span class="metric-header">Recall</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'recall') }}</template>
      </el-table-column>
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.fpr" placement="top" effect="dark">
            <span class="metric-header">FPR</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'fpr') }}</template>
      </el-table-column>
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.fnr" placement="top" effect="dark">
            <span class="metric-header">FNR</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ metricValueLabel(row, 'fnr') }}</template>
      </el-table-column>
      <el-table-column width="90">
        <template #header>
          <el-tooltip :content="metricTooltips.errors" placement="top" effect="dark">
            <span class="metric-header">Errors</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <el-tooltip
            v-if="isAllErrorModerator(row)"
            content="该 Moderator 本轮全部样本调用失败，常见原因是 API Key、解析格式或本地 vLLM guard 服务未就绪。"
            placement="top"
            effect="dark"
          >
            <span class="error-count is-all-error">{{ numberLabel(row.n_errors) }}</span>
          </el-tooltip>
          <span v-else>{{ numberLabel(row.n_errors) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="延迟" width="100">
        <template #default="{ row }">{{ msLabel(row.avg_latency_ms) }}</template>
      </el-table-column>
    </el-table>
    <div v-if="moderatorRows.length" class="summary-notice">
      指标来自冻结 results.json，仅代表本次 live_run 小预算运行；正式 simple / hard 结论以
      prerun_snapshot 为准。
    </div>
    <el-empty v-else description="本次资产内没有可解析的 results.json，暂时无法展示评测指标。" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>样本池快照</h3>
        <p>
          {{ samplePool?.total ?? 0 }} 表示冻结 dynbench.jsonl 中的样本池快照总量；下方仅展示
          preview，不展开完整风险样本。
        </p>
      </div>
      <span class="summary-hint">
        预览 {{ sampleRows.length }} / 总计 {{ samplePool?.total ?? 0 }}
      </span>
    </div>
    <BenchmarkDistributionGrid :groups="distributionGroups" />
    <article v-if="originSummaryItems.length" class="source-breakdown">
      <div>
        <h4>样本来源</h4>
        <p>Origin 分布说明样本池快照由历史飞轮样本和生成链路沉淀样本共同组成。</p>
      </div>
      <div class="source-breakdown__items">
        <span v-for="item in originSummaryItems" :key="item.key">
          {{ item.label }} {{ item.value }}
        </span>
      </div>
    </article>
    <article v-if="firstSample" class="sample-highlight">
      <div class="sample-highlight__head">
        <div>
          <b class="mono">{{ firstSample.id || 'unknown' }}</b>
          <p>{{ firstSample.query_preview || '暂无 query preview' }}</p>
        </div>
        <span>{{ firstSample.label || '-' }}</span>
      </div>
      <div class="sample-highlight__meta">
        <span>SeedBank {{ firstSample.seedbank_id || '-' }}</span>
        <span>{{ firstSample.harm_category_l1 || '-' }}</span>
        <span>{{ firstSample.harm_category_l2 || 'L2 未记录' }}</span>
        <span>{{ firstSample.attack_vector || 'Attack 未记录' }}</span>
        <span>{{ firstSample.language || 'Language 未记录' }}</span>
        <span>{{ challengeLabel(firstSample) }}</span>
      </div>
    </article>
    <el-table
      v-if="sampleRows.length"
      :data="sampleRows"
      size="small"
      class="compact-table"
      max-height="320"
    >
      <el-table-column prop="id" label="样本" min-width="130" />
      <el-table-column prop="seedbank_id" label="SeedBank" min-width="130" />
      <el-table-column prop="label" label="Label" width="90" />
      <el-table-column prop="harm_category_l1" label="L1" min-width="150" />
      <el-table-column prop="harm_category_l2" label="L2" min-width="130" />
      <el-table-column prop="attack_vector" label="Attack" min-width="120" />
      <el-table-column prop="language" label="Language" width="100" />
      <el-table-column prop="test_count" label="Test" width="80" />
      <el-table-column label="命中结果" min-width="130">
        <template #default="{ row }">{{ challengeLabel(row) }}</template>
      </el-table-column>
      <el-table-column
        prop="query_preview"
        label="Query Preview"
        min-width="260"
        show-overflow-tooltip
      />
    </el-table>
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>报告摘要</h3>
        <p>{{ reportHint }}</p>
      </div>
    </div>
    <div v-if="summary?.report.available" class="report-preview">
      <pre>{{ summary.report.markdown }}</pre>
    </div>
    <el-empty v-else description="本次 live_run 未冻结 report.md。" />
  </section>

  <BenchmarkArtifactFilesSection
    :files="summary?.artifact_files ?? {}"
    :expected-files="expectedArtifactFiles"
    :warnings="summary?.warnings ?? []"
  />

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>事件流证据</h3>
        <p>用日志证明采样、工具调用、报告生成和收尾链路实际发生。</p>
      </div>
    </div>
    <BenchmarkStatGrid :items="eventStatItems" />
    <el-table
      v-if="timelineRows.length"
      :data="timelineRows"
      size="small"
      class="compact-table"
      max-height="260"
    >
      <el-table-column prop="event_type" label="事件" width="120" />
      <el-table-column prop="stage" label="阶段" min-width="130" />
      <el-table-column prop="tool_name" label="工具" min-width="140" />
      <el-table-column prop="message" label="消息" min-width="220" show-overflow-tooltip />
      <el-table-column prop="created_at" label="时间" width="150">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生命周期样本</h3>
        <p>默认只展示 preview，帮助观众理解现场运行确实经过了样本生命周期。</p>
      </div>
    </div>
    <el-empty
      v-if="!isLoading && lifecycleSamples.length === 0"
      description="本次 live_run 未记录 lifecycle 样本，或日志中暂无可解析的生命周期事件。"
    />
    <div v-else class="lifecycle-list">
      <article v-for="item in lifecycleSamples" :key="`${item.sample_id}-${item.stage}`">
        <div class="lifecycle-list__head">
          <b class="mono">{{ item.sample_id }}</b>
          <span>{{ item.stage }}</span>
        </div>
        <p>{{ lifecycleMeta(item) }}</p>
        <pre v-if="item.query_preview">{{ item.query_preview }}</pre>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BenchmarkArtifactFilesSection from './BenchmarkArtifactFilesSection.vue'
import BenchmarkDistributionGrid, {
  type BenchmarkDistributionGroup,
} from './BenchmarkDistributionGrid.vue'
import BenchmarkFieldGrid, { type BenchmarkFieldGridItem } from './BenchmarkFieldGrid.vue'
import BenchmarkStatGrid, { type BenchmarkStatGridItem } from './BenchmarkStatGrid.vue'
import { getBenchmarkManifestParameters } from '@/utils/benchmarkLiveRunHelpers'
import {
  distributionItems,
  lifecycleMeta,
  msLabel,
  numberLabel,
  percentLabel,
  valueLabel,
} from '@/utils/benchmarkLiveRunFormatters'
import { formatApiDate } from '@/utils/datetime'
import type {
  BenchmarkArtifactItem,
  BenchmarkLiveRunPreviewSample,
  BenchmarkLiveRunSummaryResponse,
} from '@/types'

const props = defineProps<{
  asset: BenchmarkArtifactItem
  summary: BenchmarkLiveRunSummaryResponse | null
  isLoading: boolean
}>()

const expectedArtifactFiles = ['manifest.json', 'report.md', 'results.json', 'dynbench.jsonl']

type ModeratorMetricKey = 'accuracy' | 'precision' | 'f1' | 'recall' | 'fpr' | 'fnr'
type ModeratorRow = BenchmarkLiveRunSummaryResponse['result_summary']['moderators'][number]

const metricTooltips = {
  accuracy: 'ACC 准确率：(TP + TN) / 全部有效样本，表示整体判对比例。',
  precision: 'Precision 精确率：TP / (TP + FP)，表示判为违规的样本里有多少真的违规。',
  f1: 'F1：2 * Precision * Recall / (Precision + Recall)，综合衡量精确率和召回率。',
  recall: 'Recall 召回率：TP / (TP + FN)，表示真实违规样本里有多少被识别出来。',
  fpr: 'FPR 误报率：FP / (FP + TN)，表示真实安全样本被误拦的比例。',
  fnr: 'FNR 漏报率：FN / (FN + TP)，表示真实违规样本被错误放行的比例。',
  errors: 'Errors：评测调用失败或返回不可解析的样本数，不等同于模型判错。',
} as const

const parameters = computed(
  () => props.summary?.parameters ?? getBenchmarkManifestParameters(props.asset),
)

const parameterItems = computed<BenchmarkFieldGridItem[]>(() => [
  { key: 'budget', label: 'Budget', value: valueLabel(parameters.value.budget) },
  { key: 'language', label: 'Language', value: valueLabel(parameters.value.language) },
  { key: 'l1', label: 'L1 风险域', value: valueLabel(parameters.value.l1) },
  { key: 'l2', label: 'L2 子类', value: valueLabel(parameters.value.l2) },
  { key: 'moderators', label: 'Moderators', value: valueLabel(parameters.value.moderators) },
  { key: 'model', label: 'Agent Model', value: valueLabel(parameters.value.model) },
  {
    key: 'sampling_seed',
    label: 'Sampling Seed',
    value: valueLabel(parameters.value.sampling_seed),
  },
  { key: 'max_turns', label: 'Max Turns', value: valueLabel(parameters.value.max_turns) },
])

const eventStatItems = computed<BenchmarkStatGridItem[]>(() => {
  const eventCounts = props.summary?.event_counts ?? {}
  const toolCounts = props.summary?.tool_counts ?? {}
  return [
    { label: '总事件', value: numberLabel(eventCounts.total) },
    { label: 'thinking', value: numberLabel(eventCounts.thinking) },
    { label: 'tool_call', value: numberLabel(eventCounts.tool_call) },
    { label: 'tool_result', value: numberLabel(eventCounts.tool_result) },
    { label: 'lifecycle', value: numberLabel(eventCounts.lifecycle) },
    { label: 'done', value: numberLabel(eventCounts.done) },
    { label: 'error', value: numberLabel(eventCounts.error) },
    { label: 'test_samples', value: numberLabel(toolCounts.test_samples) },
    { label: 'generate_report', value: numberLabel(toolCounts.generate_report) },
  ]
})

const generatedStatItems = computed<BenchmarkStatGridItem[]>(() => {
  const artifactFiles = props.summary?.artifact_files ?? {}
  const eventCounts = props.summary?.event_counts ?? {}
  const toolCounts = props.summary?.tool_counts ?? {}
  return [
    { label: '样本池快照', value: numberLabel(samplePool.value?.total) },
    { label: '评测样本/Moderator', value: numberLabel(evaluatedSamplesPerModerator.value) },
    { label: '测试批次', value: numberLabel(toolCounts.test_samples) },
    { label: 'Moderator', value: numberLabel(moderatorNames.value.length) },
    { label: 'report.md', value: artifactFiles['report.md'] ? '已生成' : '缺失' },
    { label: 'results.json', value: artifactFiles['results.json'] ? '已生成' : '缺失' },
    { label: 'dynbench.jsonl', value: artifactFiles['dynbench.jsonl'] ? '已生成' : '缺失' },
    { label: '运行错误', value: numberLabel(eventCounts.error) },
  ]
})

const timelineRows = computed(() => props.summary?.event_timeline ?? [])
const moderatorRows = computed(() => props.summary?.result_summary?.moderators ?? [])
const samplePool = computed(() => props.summary?.sample_pool_summary ?? null)
const sampleRows = computed(() => samplePool.value?.preview_samples ?? [])
const firstSample = computed(() => (samplePool.value?.total === 1 ? sampleRows.value[0] : null))
const lifecycleSamples = computed(() => props.summary?.lifecycle_samples ?? [])

const moderatorNames = computed(() => {
  const fromResults = moderatorRows.value.map((item) => item.name).filter(Boolean)
  if (fromResults.length > 0) {
    return fromResults
  }
  const value = parameters.value.moderators
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean)
  }
  if (typeof value === 'string' && value.trim()) {
    return [value]
  }
  return []
})

const evaluatedSamplesPerModerator = computed(() => {
  const fromResult = props.summary?.result_summary?.total_samples
  if (typeof fromResult === 'number' && fromResult > 0) {
    return fromResult
  }
  return Math.max(...moderatorRows.value.map((item) => item.total_samples), 0)
})

const generatedBadge = computed(() => {
  const sampleCount = samplePool.value?.total ?? 0
  return `快照 ${sampleCount} / 评测 ${evaluatedSamplesPerModerator.value} 每 Moderator`
})

const isSmallBudgetRun = computed(() => {
  const budget = Number(parameters.value.budget)
  return Number.isFinite(budget) && budget <= 5
})

const runNarrative = computed(() => {
  const sampleCount = samplePool.value?.total ?? 0
  const batchCount = props.summary?.tool_counts?.test_samples ?? 0
  const moderatorCount = moderatorNames.value.length
  const evaluatedCount = evaluatedSamplesPerModerator.value
  const generatedFiles = ['report.md', 'results.json', 'dynbench.jsonl'].filter(
    (fileName) => props.summary?.artifact_files?.[fileName],
  )
  const fileText = generatedFiles.length ? generatedFiles.join('、') : '未记录可展示结果文件'
  const errorCount = props.summary?.event_counts?.error ?? 0
  return `本次 live_run 完成 ${batchCount} 个评测批次，调用 ${moderatorCount} 个 Moderator。冻结 dynbench.jsonl 中包含 ${sampleCount} 条样本池快照；results.json 中记录每个 Moderator 实际评测 ${evaluatedCount} 条样本。已生成 ${fileText}，运行错误数为 ${errorCount}。`
})

const resultBadge = computed(() => {
  const result = props.summary?.result_summary
  if (!result?.available) {
    return 'results.json 不可用'
  }
  return `${result.moderators_tested ?? result.moderators.length} 个 Moderator / 每个 ${
    result.total_samples ?? 0
  } 样本`
})

const reportHint = computed(() => {
  if (props.summary?.report.available) {
    return '来自冻结 report.md。'
  }
  return '没有冻结报告时，仍保留配置、事件流和样本池证据。'
})

const distributionGroups = computed<BenchmarkDistributionGroup[]>(() => {
  const pool = samplePool.value
  return [
    { title: 'Label', items: distributionItems(pool?.label_distribution) },
    { title: 'L1', items: distributionItems(pool?.l1_distribution) },
    { title: 'Attack', items: distributionItems(pool?.attack_vector_distribution) },
    { title: 'Language', items: distributionItems(pool?.language_distribution) },
    { title: 'Origin', items: distributionItems(pool?.origin_distribution) },
  ]
})

const originSummaryItems = computed(() =>
  distributionItems(samplePool.value?.origin_distribution).map((item) => ({
    ...item,
    label: originLabel(item.key),
  })),
)

function originLabel(value: string) {
  const labels: Record<string, string> = {
    flywheel: '历史飞轮样本',
    generated: '生成链路沉淀样本',
  }
  return labels[value] ?? value
}

function isAllErrorModerator(row: ModeratorRow) {
  const totalSamples = row.total_samples ?? 0
  const errorCount = row.n_errors ?? 0
  return totalSamples > 0 && errorCount >= totalSamples
}

function metricValueLabel(row: ModeratorRow, key: ModeratorMetricKey) {
  return isAllErrorModerator(row) ? '不可用' : percentLabel(row[key])
}

function challengeLabel(sample: BenchmarkLiveRunPreviewSample) {
  const names = sample.moderator_fooled
  if (sample.label === 'safe') {
    return names.length > 0 ? `误拦：${names.join(', ')}` : '未误拦'
  }
  if (sample.label === 'unsafe') {
    return names.length > 0 ? `绕过：${names.join(', ')}` : '未绕过'
  }
  return names.length > 0 ? `命中：${names.join(', ')}` : '未命中'
}

function formatDate(value?: string | null) {
  return formatApiDate(value)
}
</script>

<style scoped>
.metric-header {
  cursor: help;
  border-bottom: 1px dotted currentColor;
}

.error-count.is-all-error {
  color: var(--el-color-danger);
  cursor: help;
  font-weight: 600;
}
</style>
