<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成目标</h3>
        <p>课题一 value_qa 现场生成三档问答样本，并进行结构校验和资产冻结。</p>
      </div>
      <span class="source-pill is-live">{{ topic1Summary?.readiness ?? 'live_run' }}</span>
    </div>
    <BenchmarkFieldGrid :items="generationItems" />
    <el-alert
      v-if="topic1Summary?.readiness_note"
      type="info"
      :title="topic1Summary.readiness_note"
      :closable="false"
      show-icon
    />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>语料来源</h3>
        <p>corpus 是本次生成 Agent 检索和抽取事实的材料包，应与主题保持一致。</p>
      </div>
    </div>
    <BenchmarkFieldGrid :items="retrievalItems" />
    <el-alert
      v-if="corpusMismatchWarning"
      type="warning"
      :title="corpusMismatchWarning"
      :closable="false"
      show-icon
    />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>生成结果</h3>
        <p>最小现场规模按三档组统计，1 组包含 high / medium / low 三条样本。</p>
      </div>
      <span class="summary-hint">
        {{ topic1Summary?.generated_group_count ?? 0 }} /
        {{ topic1Summary?.requested_group_count ?? 0 }} 组
      </span>
    </div>
    <BenchmarkStatGrid :items="resultStatItems" />
  </section>

  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>三档样本预览</h3>
        <p>按三档组展示问题和 high / medium / low 回答，便于现场说明生成结果。</p>
      </div>
      <span class="summary-hint">
        展示 {{ sampleGroups.length }} / {{ topic1Summary?.generated_group_count ?? 0 }} 组
      </span>
    </div>
    <div v-if="sampleGroups.length" class="topic1-group-list">
      <article v-for="group in sampleGroups" :key="group.group_id" class="topic1-group-card">
        <div class="topic1-group-card__head">
          <div>
            <b>{{ group.topic || '-' }}</b>
            <p>{{ group.primary_dimension || '-' }} / {{ group.secondary_dimension || '-' }}</p>
          </div>
          <span>{{ group.group_id }}</span>
        </div>
        <div class="topic1-level-grid">
          <div v-for="level in valueLevels" :key="level" :class="['topic1-level', `is-${level}`]">
            <span>{{ level }}</span>
            <b>{{ group.levels[level]?.question || '-' }}</b>
            <p>{{ group.levels[level]?.answer || '-' }}</p>
          </div>
        </div>
      </article>
    </div>
    <el-empty v-else description="本次资产没有解析到 group_preview.jsonl 三档组预览。" />
  </section>

  <BenchmarkArtifactFilesSection
    :files="summary?.artifact_files ?? topic1Summary?.artifact_files ?? {}"
    :expected-files="expectedArtifactFiles"
    :warnings="summary?.warnings ?? []"
    title="冻结产物"
    description="固定到本次 topic1 value_qa artifact zip 内的真实产物，不展示 AutoBench 专属 results / dynbench 文件。"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BenchmarkArtifactFilesSection from './BenchmarkArtifactFilesSection.vue'
import BenchmarkFieldGrid, { type BenchmarkFieldGridItem } from './BenchmarkFieldGrid.vue'
import BenchmarkStatGrid, { type BenchmarkStatGridItem } from './BenchmarkStatGrid.vue'
import { numberLabel, valueLabel } from '@/utils/benchmarkLiveRunFormatters'
import { getBenchmarkManifestParameters } from '@/utils/benchmarkLiveRunHelpers'
import type {
  BenchmarkArtifactItem,
  BenchmarkLiveRunSummaryResponse,
  BenchmarkTopic1ValueQaGroupPreview,
} from '@/types'

const props = defineProps<{
  asset: BenchmarkArtifactItem
  summary: BenchmarkLiveRunSummaryResponse | null
}>()

const expectedArtifactFiles = [
  'manifest.json',
  'samples.jsonl',
  'group_preview.jsonl',
  'quality_report.json',
  'lineage.jsonl',
  'worker.log',
]
const valueLevels = ['high', 'medium', 'low'] as const

const topic1Summary = computed(() => props.summary?.topic1_value_qa_summary ?? null)
const sampleGroups = computed<BenchmarkTopic1ValueQaGroupPreview[]>(
  () => topic1Summary.value?.sample_groups ?? [],
)

const generationItems = computed<BenchmarkFieldGridItem[]>(() => {
  const parameters = props.summary?.parameters ?? getBenchmarkManifestParameters(props.asset)
  const topic1 = topic1Summary.value
  const mode = topic1?.generation_mode || valueLabel(parameters.generation_mode)
  return [
    { key: 'generation_mode', label: '生成模式', value: modeLabel(mode) },
    {
      key: 'topic',
      label: mode === 'dimension' ? '表单主题' : '主题',
      value: valueLabel(topic1?.topic || parameters.topic),
    },
    {
      key: 'dimension',
      label: '维度',
      value: valueLabel(topic1?.dimension || parameters.dimension),
    },
    {
      key: 'selected_topics',
      label: '实际抽到主题',
      value: valueLabel(topic1?.selected_topics),
    },
    {
      key: 'requested_group_count',
      label: '请求三档组',
      value: numberLabel(topic1?.requested_group_count),
    },
    { key: 'language', label: '语言', value: valueLabel(topic1?.language || parameters.language) },
    { key: 'model', label: 'LLM 模型', value: valueLabel(topic1?.model) },
    {
      key: 'llm_api_base',
      label: 'LLM Endpoint',
      value: valueLabel(topic1?.llm_api_base),
      mono: true,
    },
    { key: 'seed', label: 'Seed', value: valueLabel(topic1?.seed || parameters.seed) },
  ]
})

const retrievalItems = computed<BenchmarkFieldGridItem[]>(() => [
  {
    key: 'retrieval_mode',
    label: '检索方式',
    value: retrievalModeLabel(topic1Summary.value?.retrieval_mode),
  },
  {
    key: 'corpus_jsonl',
    label: 'Corpus JSONL',
    value: valueLabel(topic1Summary.value?.corpus_jsonl),
    mono: true,
  },
])

const resultStatItems = computed<BenchmarkStatGridItem[]>(() => {
  const topic1 = topic1Summary.value
  const distribution = topic1?.quality_level_distribution ?? {}
  return [
    { label: '请求组数', value: numberLabel(topic1?.requested_group_count) },
    { label: '完成组数', value: numberLabel(topic1?.generated_group_count) },
    { label: '样本总数', value: numberLabel(topic1?.sample_count) },
    { label: 'High', value: numberLabel(distribution.high) },
    { label: 'Medium', value: numberLabel(distribution.medium) },
    { label: 'Low', value: numberLabel(distribution.low) },
    { label: '结构校验', value: validationLabel(topic1?.validation) },
  ]
})

const corpusMismatchWarning = computed(() => {
  const topic1 = topic1Summary.value
  if (
    !topic1 ||
    topic1.retrieval_mode !== 'local_corpus' ||
    topic1.generation_mode !== 'dimension'
  ) {
    return ''
  }
  const corpus = topic1.corpus_jsonl || ''
  const selected = topic1.selected_topics.filter(Boolean)
  const mismatched = selected.filter((topic) => corpus && !corpus.includes(topic))
  if (!mismatched.length) {
    return ''
  }
  return `当前维度模式实际抽到“${mismatched.join('、')}”，但本地 corpus 为“${corpus}”，可能导致可提取事实不足。`
})

function modeLabel(value: unknown) {
  return value === 'dimension' ? '维度抽题' : '单主题'
}

function retrievalModeLabel(value: unknown) {
  if (value === 'local_corpus') {
    return '本地 corpus'
  }
  if (value === 'online_baike') {
    return '在线百科'
  }
  return valueLabel(value)
}

function validationLabel(value?: Record<string, unknown>) {
  if (!value) {
    return '-'
  }
  return value.passed === true ? '通过' : '未通过'
}
</script>
