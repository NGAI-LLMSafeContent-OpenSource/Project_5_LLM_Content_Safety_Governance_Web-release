<template>
  <section class="topic1-evaluation evaluation-section">
    <div class="topic1-evaluation__header">
      <div>
        <h2>课题一 value_qa Benchmark 评测</h2>
        <p>
          面向主流价值语料质量判别与问题溯因，展示动态 Benchmark
          的生成配置、核心评测指标、预跑资产证据，以及后续本项目算法与 baseline
          方法的跑分对比入口。当前 baseline 跑分尚未导入。
        </p>
      </div>
      <div class="topic1-status-tags">
        <span class="source-pill is-valueqa">value_qa</span>
        <span class="source-pill" :class="{ 'is-muted': !primaryAsset }">
          {{ primaryAsset ? '预跑资产已导入' : '预跑资产待导入' }}
        </span>
        <span class="source-pill is-warning">评测结果待补充</span>
      </div>
    </div>

    <el-empty
      v-if="!primaryAsset"
      description="尚未导入课题一 value_qa 预跑资产，模型评测第一版 section 暂无可展示证据。"
    />

    <template v-else>
      <div class="topic1-config-card">
        <div class="topic1-config-card__main">
          <div>
            <span class="section-kicker">Benchmark 生成配置 / Agent 配置</span>
            <h3>从 Agent 配置到预跑资产</h3>
          </div>
          <el-button size="small" type="primary" @click="emit('view-assets')">
            前往资产管理
          </el-button>
        </div>
        <div class="topic1-config-grid">
          <article v-for="item in agentConfigItems" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <p>{{ item.desc }}</p>
          </article>
        </div>
      </div>

      <div class="topic1-subsection">
        <div class="section-title-row">
          <div>
            <h3>核心评测指标说明</h3>
          </div>
        </div>
        <div class="topic1-metric-notes">
          <article v-for="metric in metricNotes" :key="metric.name">
            <b>{{ metric.name }}</b>
            <span>{{ metric.desc }}</span>
          </article>
        </div>
      </div>

      <div class="topic1-subsection">
        <div class="section-title-row">
          <div>
            <h3>模型 / Baseline 跑分对比</h3>
            <p>当前展示对比框架；待课题一提供 baseline / SOTA 结果资产后补齐柱状图或雷达图。</p>
          </div>
          <span class="source-pill is-warning">待导入</span>
        </div>
        <div class="topic1-baseline-layout">
          <div class="topic1-score-placeholder">
            <div class="topic1-placeholder-bars">
              <span v-for="item in baselineRows" :key="item.name">
                <i :style="{ width: item.width }"></i>
              </span>
            </div>
            <p>baseline 跑分尚未导入，第一版仅保留图表位置和对比口径。</p>
          </div>
          <div class="topic1-baseline-table">
            <div class="topic1-baseline-row is-head">
              <span>方法</span>
              <span>类型</span>
              <span>档位判别</span>
              <span>状态</span>
            </div>
            <div v-for="row in baselineRows" :key="row.name" class="topic1-baseline-row">
              <span>
                <b>{{ row.name }}</b>
                <small>{{ row.note }}</small>
              </span>
              <span>{{ row.type }}</span>
              <span>{{ row.score }}</span>
              <span>{{ row.status }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="topic1-subsection">
        <div class="section-title-row">
          <div>
            <h3>动态 Benchmark 价值说明</h3>
            <p>这部分解释为什么需要动态生成评测样本，以及为什么这些分数后续具有参考意义。</p>
          </div>
        </div>
        <div class="topic1-value-grid">
          <article v-for="item in benchmarkValueItems" :key="item.title">
            <b>{{ item.title }}</b>
            <p>{{ item.desc }}</p>
          </article>
        </div>
      </div>

      <div class="topic1-evidence-card">
        <div class="topic1-evidence-card__header">
          <div>
            <span class="section-kicker">预跑资产与复判证据</span>
            <h3>当前已导入证据</h3>
            <p>当前结果来自 Data_predictions.jsonl，可作为预跑复判证据。</p>
          </div>
          <span class="source-pill">Data_predictions.jsonl</span>
        </div>

        <p v-if="isSummaryLoading" class="topic1-state">复判证据读取中...</p>
        <p v-else-if="summaryError" class="topic1-state">复判证据暂不可用：{{ summaryError }}</p>
        <template v-else>
          <div class="topic1-evidence-grid">
            <article v-for="item in evidenceItems" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>

          <div class="topic1-distribution-grid">
            <article>
              <b>原始档位分布</b>
              <div class="topic1-distribution-bars">
                <div v-for="item in goldDistributionItems" :key="item.level">
                  <span>{{ item.level }}</span>
                  <i :style="{ width: item.width }"></i>
                  <b>{{ item.count }}</b>
                </div>
              </div>
            </article>
            <article>
              <b>复判档位分布</b>
              <div class="topic1-distribution-bars">
                <div v-for="item in predictedDistributionItems" :key="item.level">
                  <span>{{ item.level }}</span>
                  <i :style="{ width: item.width }"></i>
                  <b>{{ item.count }}</b>
                </div>
              </div>
            </article>
          </div>

          <div class="topic1-issue-panel">
            <div>
              <b>复判问题类型分布</b>
              <p>issues 来自复判 Agent 返回的问题片段、类型和原因。</p>
            </div>
            <div class="topic1-issue-bars">
              <div v-for="item in issueItems" :key="item.type">
                <span>{{ item.type }}</span>
                <i :style="{ width: item.width }"></i>
                <b>{{ item.count }}</b>
              </div>
              <p v-if="issueItems.length === 0" class="topic1-state">暂无复判问题类型分布。</p>
            </div>
          </div>
        </template>
      </div>

      <div class="topic1-subsection">
        <div class="section-title-row">
          <div>
            <h3>代表样本案例</h3>
          </div>
          <el-button size="small" type="primary" @click="openValueQaSamples">
            查看三档样本
          </el-button>
        </div>
        <div class="topic1-sample-entry-grid">
          <article v-for="item in sampleEntryItems" :key="item.title">
            <b>{{ item.title }}</b>
            <p>{{ item.desc }}</p>
          </article>
        </div>
      </div>
    </template>

    <BenchmarkTopic1ValueQaSampleDrawer v-model="sampleDrawerVisible" :asset="primaryAsset" />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getTopic1ValueQaRecheckSummary } from '@/api/benchmark'
import BenchmarkTopic1ValueQaSampleDrawer from './BenchmarkTopic1ValueQaSampleDrawer.vue'
import {
  baselineRows,
  benchmarkValueItems,
  metricNotes,
  sampleEntryItems,
} from './BenchmarkTopic1ValueQaEvaluationSection.constants'
import type { BenchmarkArtifactItem, BenchmarkTopic1ValueQaRecheckSummary } from '@/types'

const props = defineProps<{
  registryAssets: BenchmarkArtifactItem[]
}>()

const emit = defineEmits<{
  (event: 'view-assets'): void
}>()

const valueQaLevels = ['high', 'medium', 'low'] as const
const recheckSummary = ref<BenchmarkTopic1ValueQaRecheckSummary | null>(null)
const isSummaryLoading = ref(false)
const summaryError = ref('')
const sampleDrawerVisible = ref(false)

const topic1ValueQaAssets = computed(() =>
  props.registryAssets.filter((asset) => asset.manifest.benchmark_type === 'value_qa'),
)

const primaryAsset = computed(() => {
  const recheckAssets = topic1ValueQaAssets.value.filter((asset) => isRiskCauseRecheckAsset(asset))
  return recheckAssets[0] ?? topic1ValueQaAssets.value[0] ?? null
})

const agentConfigItems = computed(() => [
  {
    label: 'Agent',
    value: '价值评测语料生成 Agent',
    desc: '围绕主题、价值维度和文档库生成三档回答对照样本。',
  },
  {
    label: '输入',
    value: '主题 / 价值维度 / 政策语料 / 文档库',
    desc: '第一版展示配置口径，现场小样本跑入口放在资产管理底部。',
  },
  {
    label: '输出',
    value: 'high / medium / low 三档回答对照',
    desc: `${formatCount(getManifestNumber(primaryAsset.value, 'sample_count'))} 条样本，${formatCount(
      getManifestNumber(primaryAsset.value, 'group_count'),
    )} 组三档问答。`,
  },
  {
    label: '复判 Agent',
    value: '档位复判与 low 问题溯因',
    desc: '读取 Data_predictions.jsonl，返回复判档位、问题类型、问题片段和原因。',
  },
])

const evidenceItems = computed(() => {
  const summary = recheckSummary.value
  return [
    { label: '样本数', value: formatCount(summary?.sample_count) },
    { label: '三档组', value: formatCount(getManifestNumber(primaryAsset.value, 'group_count')) },
    {
      label: '复判覆盖',
      value: summary ? `${summary.prediction_count} / ${summary.sample_count}` : '-',
    },
    {
      label: '档位一致',
      value: summary ? `${summary.correct_count} / ${summary.prediction_count}` : '-',
    },
    { label: '一致率', value: formatPercent(summary?.accuracy) },
    { label: '不一致样本', value: formatCount(summary?.mismatch_count) },
    { label: '复判问题', value: formatCount(summary?.issue_count) },
    { label: 'low 问题样本', value: formatCount(summary?.low_issue_sample_count) },
  ]
})

const goldDistributionItems = computed(() =>
  buildDistributionItems(
    recheckSummary.value?.gold_distribution ?? recheckSummary.value?.true_label_distribution ?? {},
  ),
)

const predictedDistributionItems = computed(() =>
  buildDistributionItems(recheckSummary.value?.predicted_label_distribution ?? {}),
)

const issueItems = computed(() => {
  const distribution = recheckSummary.value?.issue_type_distribution ?? {}
  const max = Math.max(...Object.values(distribution).map((value) => Number(value) || 0), 1)
  return Object.entries(distribution)
    .map(([type, count]) => {
      const numericCount = Number(count) || 0
      return {
        type,
        count: numericCount,
        width: `${Math.max(6, Math.round((numericCount / max) * 100))}%`,
      }
    })
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type))
})

watch(
  () => primaryAsset.value?.asset_id,
  () => {
    void loadRecheckSummary()
  },
  { immediate: true },
)

async function loadRecheckSummary() {
  if (!primaryAsset.value) {
    recheckSummary.value = null
    return
  }
  isSummaryLoading.value = true
  summaryError.value = ''
  try {
    recheckSummary.value = await getTopic1ValueQaRecheckSummary(primaryAsset.value.asset_id)
  } catch (error) {
    recheckSummary.value = null
    summaryError.value = error instanceof Error ? error.message : 'recheck summary unavailable'
  } finally {
    isSummaryLoading.value = false
  }
}

function isRiskCauseRecheckAsset(asset: BenchmarkArtifactItem) {
  return (
    asset.manifest.trace_source_file === 'Data_predictions.jsonl' ||
    asset.manifest.trace_source_schema === 'risk_cause_data_predictions_v1' ||
    asset.manifest.model_eval_status === 'imported_result'
  )
}

function buildDistributionItems(distribution: Record<string, number>) {
  const max = Math.max(...valueQaLevels.map((level) => Number(distribution[level]) || 0), 1)
  return valueQaLevels.map((level) => {
    const count = Number(distribution[level]) || 0
    return {
      level,
      count,
      width: `${Math.max(6, Math.round((count / max) * 100))}%`,
    }
  })
}

function openValueQaSamples() {
  sampleDrawerVisible.value = true
}

function getManifestNumber(asset: BenchmarkArtifactItem | null, key: string) {
  const value = asset?.manifest[key]
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function formatCount(value: number | null | undefined, fallback = '-') {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : fallback
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }
  return `${(value * 100).toFixed(2)}%`
}
</script>

<style scoped src="./BenchmarkTopic1ValueQaEvaluationSection.css"></style>
