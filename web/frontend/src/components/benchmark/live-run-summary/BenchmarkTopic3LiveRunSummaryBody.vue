<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成配置</h3>
        <p>课题三 4.4 使用样本预算和 H1-H4 配额生成动态难度编辑题库。</p>
      </div>
      <span class="source-pill is-live">{{ topic3Summary?.readiness ?? 'live_run' }}</span>
    </div>
    <BenchmarkFieldGrid :items="topic3ConfigItems" />
    <el-alert
      v-if="topic3Summary?.readiness_note"
      type="info"
      :title="topic3Summary.readiness_note"
      :closable="false"
      show-icon
    />
  </section>

  <BenchmarkArtifactFilesSection
    :files="summary?.artifact_files ?? {}"
    :expected-files="expectedArtifactFiles"
    :warnings="summary?.warnings ?? []"
    description="固定到课题三 artifact zip 内的文件，避免读取运行台 latest 导致错配。"
  />

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>质量观察项</h3>
        <p>展示本次生成过程中的丢弃、Guard、桥接审核和风险类别分布。</p>
      </div>
      <span class="summary-hint">
        样本 {{ topic3Summary?.generated ?? 0 }} / {{ topic3Summary?.requested ?? 0 }}
      </span>
    </div>
    <el-alert
      class="topic3-quality-note"
      type="info"
      title="以下字段来自题库生成阶段的质量检查，用于说明样本是否自然、风险是否保留、span 标注是否可信；不代表后续被测模型的最终评测得分。"
      :closable="false"
      show-icon
    />
    <BenchmarkStatGrid :items="topic3StatItems" />
    <BenchmarkDistributionGrid :groups="topic3DistributionGroups" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成题库样本</h3>
        <p>实际生成的动态难度编辑题库。点击样本查看 harmful / harmless span 高亮。</p>
      </div>
      <span class="summary-hint">
        展示 {{ topic3SampleRows.length }} / {{ topic3Summary?.total ?? 0 }} 条
      </span>
    </div>
    <el-table
      v-if="topic3SampleRows.length"
      :data="topic3SampleRows"
      size="small"
      class="compact-table"
      max-height="300"
      highlight-current-row
      @row-click="selectTopic3Sample"
    >
      <el-table-column prop="sample_id" label="样本" min-width="210" show-overflow-tooltip />
      <el-table-column prop="difficulty_level" label="H" width="70" />
      <el-table-column label="结构" width="90">
        <template #default="{ row }">{{ row.harmful_count }}H/{{ row.harmless_count }}S</template>
      </el-table-column>
      <el-table-column
        prop="risk_category"
        label="风险类别"
        min-width="170"
        show-overflow-tooltip
      />
      <el-table-column prop="bridge_review_label" width="100">
        <template #header>
          <el-tooltip :content="topic3TermTooltip('Bridge')" placement="top" :show-after="200">
            <span class="term-trigger">Bridge</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="final_guard_label" width="110">
        <template #header>
          <el-tooltip :content="topic3TermTooltip('Final Guard')" placement="top" :show-after="200">
            <span class="term-trigger">Guard</span>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="本次资产未解析到 samples.jsonl 样本。" />

    <BenchmarkTopic3SampleDetail v-if="selectedTopic3Sample" :sample="selectedTopic3Sample" />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BenchmarkArtifactFilesSection from './BenchmarkArtifactFilesSection.vue'
import BenchmarkDistributionGrid, {
  type BenchmarkDistributionGroup,
} from './BenchmarkDistributionGrid.vue'
import BenchmarkFieldGrid, { type BenchmarkFieldGridItem } from './BenchmarkFieldGrid.vue'
import BenchmarkStatGrid, { type BenchmarkStatGridItem } from './BenchmarkStatGrid.vue'
import BenchmarkTopic3SampleDetail from './BenchmarkTopic3SampleDetail.vue'
import { getBenchmarkManifestParameters, topic3TermTooltip } from '@/utils/benchmarkLiveRunHelpers'
import {
  difficultyCountLabel,
  distributionItems,
  numberLabel,
  valueLabel,
} from '@/utils/benchmarkLiveRunFormatters'
import type {
  BenchmarkArtifactItem,
  BenchmarkLiveRunSummaryResponse,
  BenchmarkTopic3DifficultySample,
} from '@/types'

const props = defineProps<{
  asset: BenchmarkArtifactItem
  summary: BenchmarkLiveRunSummaryResponse | null
}>()

const expectedArtifactFiles = [
  'samples.jsonl',
  'manifest.json',
  'worker_state.json',
  'generation_config.json',
  'worker.log',
  'batches',
]

const selectedTopic3Sample = ref<BenchmarkTopic3DifficultySample | null>(null)
const topic3Summary = computed(() => props.summary?.topic3_difficulty_summary ?? null)
const topic3SampleRows = computed(() => topic3Summary.value?.samples ?? [])

const topic3ConfigItems = computed<BenchmarkFieldGridItem[]>(() => {
  const parameters = props.summary?.parameters ?? getBenchmarkManifestParameters(props.asset)
  const configuredCounts = topic3Summary.value?.configured_difficulty_counts ?? {}
  return [
    {
      key: 'total_sample_count',
      label: '样本预算',
      value: valueLabel(parameters.total_sample_count ?? topic3Summary.value?.requested),
    },
    {
      key: 'generated',
      label: '已生成',
      value: `${topic3Summary.value?.generated ?? 0} / ${topic3Summary.value?.requested ?? 0}`,
    },
    { key: 'language', label: 'Language', value: valueLabel(parameters.language) },
    {
      key: 'difficulty_preset',
      label: '难度配置',
      value: valueLabel(parameters.difficulty_preset),
    },
    {
      key: 'difficulty_counts',
      label: 'H1-H4 配额',
      value: difficultyCountLabel(configuredCounts),
    },
    { key: 'seed_dataset', label: 'Seed 数据集', value: valueLabel(parameters.seed_dataset) },
    {
      key: 'generation_model',
      label: 'Generation Model',
      value: valueLabel(parameters.generation_model),
    },
    { key: 'guard_model', label: 'Guard Model', value: valueLabel(parameters.guard_model) },
    {
      key: 'random_seed',
      label: 'Random Seed',
      value: valueLabel(topic3Summary.value?.random_seed),
    },
    {
      key: 'sample_mode',
      label: 'Sample Mode',
      value: valueLabel(topic3Summary.value?.sample_mode),
    },
  ]
})

const topic3StatItems = computed<BenchmarkStatGridItem[]>(() => {
  const topic3 = topic3Summary.value
  const discard = topic3?.discard_counts ?? {}
  const bridge = topic3?.bridge_review_counts ?? {}
  const guard = topic3?.final_guard_counts ?? {}
  return [
    { label: '样本总数', value: numberLabel(topic3?.total) },
    { label: 'H1-H4', value: difficultyCountLabel(topic3?.difficulty_counts ?? {}) },
    {
      label: 'Bridge accepted',
      value: numberLabel(bridge.accepted),
      tooltip: topic3TermTooltip('Bridge accepted'),
    },
    {
      label: 'Bridge advisory',
      value: numberLabel(bridge.advisory),
      tooltip: topic3TermTooltip('Bridge advisory'),
    },
    {
      label: 'Guard Unsafe',
      value: numberLabel(guard.Unsafe),
      tooltip: topic3TermTooltip('Unsafe'),
    },
    {
      label: 'Guard Controversial',
      value: numberLabel(guard.Controversial),
      tooltip: topic3TermTooltip('Controversial'),
    },
    { label: '桥接丢弃', value: numberLabel(discard.bridge_review_rejected) },
    { label: '无害生成丢弃', value: numberLabel(discard.harmless_companion_rejected) },
    { label: '最终 Guard 丢弃', value: numberLabel(discard.final_guard_rejected) },
  ]
})

const topic3DistributionGroups = computed<BenchmarkDistributionGroup[]>(() => {
  const topic3 = topic3Summary.value
  return [
    { title: 'H Level', items: distributionItems(topic3?.difficulty_counts) },
    { title: 'Risk', items: distributionItems(topic3?.risk_category_counts) },
    { title: 'Risk Level', items: distributionItems(topic3?.risk_level_counts) },
    {
      title: 'Final Guard',
      items: distributionItems(topic3?.final_guard_counts),
      tooltip: topic3TermTooltip('Final Guard'),
    },
  ]
})

watch(
  topic3SampleRows,
  (rows) => {
    selectedTopic3Sample.value = rows[0] ?? null
  },
  { immediate: true },
)

function selectTopic3Sample(row: BenchmarkTopic3DifficultySample) {
  selectedTopic3Sample.value = row
}
</script>
