<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成目标</h3>
        <p>课题三文化多样性语料按规模档和难度等级现场生成多民族评测样本。</p>
      </div>
      <span class="source-pill is-live">{{ culturalSummary?.readiness ?? 'live_run' }}</span>
    </div>
    <BenchmarkFieldGrid :items="goalItems" />
    <el-alert
      v-if="culturalSummary?.readiness_note"
      type="info"
      :title="culturalSummary.readiness_note"
      :closable="false"
      show-icon
    />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成结果</h3>
        <p>按实际冻结样本统计 L1–L3、民族分布和文化审核通过情况。</p>
      </div>
      <span class="summary-hint">
        {{ culturalSummary?.generated ?? 0 }} / {{ culturalSummary?.requested ?? 0 }} 条
      </span>
    </div>
    <BenchmarkStatGrid :items="resultStatItems" />
    <BenchmarkDistributionGrid :groups="distributionGroups" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>样本预览</h3>
        <p>先看几条现场样本，完整列表请打开文化样本抽屉。</p>
      </div>
      <el-button type="primary" link @click="emit('open-samples')">查看全部样本</el-button>
    </div>
    <el-table
      v-if="samplePreviews.length"
      :data="samplePreviews"
      size="small"
      class="compact-table"
    >
      <el-table-column prop="ethnic_group" label="民族" width="90" />
      <el-table-column prop="difficulty_level" label="难度" width="70" />
      <el-table-column prop="background_type" label="背景类型" width="100" />
      <el-table-column prop="persona" label="人设" min-width="120" show-overflow-tooltip />
      <el-table-column
        prop="prompt_preview"
        label="Prompt 摘要"
        min-width="240"
        show-overflow-tooltip
      />
    </el-table>
    <el-empty v-else description="本次资产没有解析到可预览的文化多样性样本。" />
  </section>

  <BenchmarkArtifactFilesSection
    :files="summary?.artifact_files ?? culturalSummary?.artifact_files ?? {}"
    :expected-files="expectedArtifactFiles"
    :warnings="summary?.warnings ?? []"
    title="冻结产物"
    description="固定到本次文化多样性 artifact zip 内的真实产物，不展示 AutoBench 专属 results / dynbench 文件。"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BenchmarkArtifactFilesSection from './BenchmarkArtifactFilesSection.vue'
import BenchmarkDistributionGrid, {
  type BenchmarkDistributionGroup,
} from './BenchmarkDistributionGrid.vue'
import BenchmarkFieldGrid, { type BenchmarkFieldGridItem } from './BenchmarkFieldGrid.vue'
import BenchmarkStatGrid, { type BenchmarkStatGridItem } from './BenchmarkStatGrid.vue'
import {
  SCALE_LABELS,
  CULTURAL_STRUCTURE_BAND_LABELS,
  type CulturalStructureBand,
  type StandardBenchmarkScale,
} from '@/utils/benchmark/standardTaskPayload'
import {
  distributionItems,
  numberLabel,
  percentLabel,
  valueLabel,
} from '@/utils/benchmarkLiveRunFormatters'
import type {
  BenchmarkArtifactItem,
  BenchmarkLiveRunSummaryResponse,
  BenchmarkTopic3CulturalLiveRunSummary,
  BenchmarkTopic3CulturalSamplePreview,
} from '@/types'

const props = defineProps<{
  asset: BenchmarkArtifactItem
  summary: BenchmarkLiveRunSummaryResponse | null
}>()

const emit = defineEmits<{
  (event: 'open-samples'): void
}>()

const expectedArtifactFiles = [
  'samples.jsonl',
  'manifest.json',
  'generation_config.json',
  'worker_state.json',
  'worker.log',
]

const culturalSummary = computed(() => props.summary?.topic3_cultural_summary ?? null)
const samplePreviews = computed<BenchmarkTopic3CulturalSamplePreview[]>(() =>
  (culturalSummary.value?.sample_previews ?? []).slice(0, 5),
)

const goalItems = computed<BenchmarkFieldGridItem[]>(() => {
  const cultural = culturalSummary.value
  return [
    { key: 'scale', label: '规模档', value: scaleLabel(cultural?.scale) },
    {
      key: 'structure_band',
      label: '难度等级',
      value: structureBandLabel(cultural?.structure_band),
    },
    {
      key: 'difficulty_counts',
      label: 'L1–L3 配额',
      value: levelCountLabel(cultural?.difficulty_counts),
    },
    {
      key: 'allowed_ethnic_groups',
      label: '民族',
      value: valueLabel(cultural?.allowed_ethnic_groups),
    },
    { key: 'language', label: '语言', value: valueLabel(cultural?.language) },
    { key: 'batch_size', label: 'Batch', value: numberLabel(cultural?.batch_size) },
    { key: 'random_seed', label: 'Seed', value: numberLabel(cultural?.random_seed), mono: true },
  ]
})

const resultStatItems = computed<BenchmarkStatGridItem[]>(() => {
  const cultural = culturalSummary.value
  return [
    { label: '请求条数', value: numberLabel(cultural?.requested) },
    { label: '完成条数', value: numberLabel(cultural?.generated) },
    { label: '样本总数', value: numberLabel(cultural?.sample_count) },
    { label: 'L1', value: numberLabel(cultural?.difficulty_distribution?.L1) },
    { label: 'L2', value: numberLabel(cultural?.difficulty_distribution?.L2) },
    { label: 'L3', value: numberLabel(cultural?.difficulty_distribution?.L3) },
    { label: '审核通过', value: reviewLabel(cultural) },
  ]
})

const distributionGroups = computed<BenchmarkDistributionGroup[]>(() => {
  const cultural = culturalSummary.value
  return [
    { title: 'L1–L3', items: distributionItems(cultural?.difficulty_distribution) },
    { title: '民族', items: distributionItems(cultural?.ethnic_distribution) },
    { title: '背景类型', items: distributionItems(cultural?.background_type_distribution) },
    { title: '人设', items: distributionItems(cultural?.persona_distribution) },
    { title: '问法', items: distributionItems(cultural?.query_type_distribution) },
  ]
})

function scaleLabel(value?: string) {
  if (value && value in SCALE_LABELS) {
    return SCALE_LABELS[value as StandardBenchmarkScale]
  }
  return valueLabel(value)
}

function structureBandLabel(value?: string) {
  if (value && value in CULTURAL_STRUCTURE_BAND_LABELS) {
    return CULTURAL_STRUCTURE_BAND_LABELS[value as CulturalStructureBand]
  }
  return valueLabel(value)
}

function levelCountLabel(value?: Record<string, number>) {
  const counts = value ?? {}
  const parts = ['L1', 'L2', 'L3']
    .map((level) => `${level}:${numberLabel(counts[level])}`)
    .filter((part) => !part.endsWith(':0'))
  return parts.length > 0 ? parts.join(' / ') : '-'
}

function reviewLabel(cultural: BenchmarkTopic3CulturalLiveRunSummary | null | undefined) {
  if (!cultural) {
    return '-'
  }
  return `${numberLabel(cultural.review_passed_count)} / ${numberLabel(cultural.sample_count)}（${percentLabel(cultural.review_passed_rate)}）`
}
</script>
