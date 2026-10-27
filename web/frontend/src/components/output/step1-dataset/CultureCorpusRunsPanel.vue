<template>
  <section class="runs-panel">
    <div class="runs-head">
      <div>
        <div class="runs-title">批次历史与复用</div>
        <div class="runs-desc">读取课题三文化语料 runs，用于预览和更新集合资产的批次筛选项。</div>
      </div>
      <button class="runs-refresh" type="button" :disabled="loading" @click="refreshHistory">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="runs-error">{{ error }}</div>
    <div v-else-if="loading && runs.length === 0" class="runs-empty">正在加载批次历史...</div>
    <div v-else-if="runs.length === 0" class="runs-empty">暂无可复用批次</div>

    <div v-else class="runs-list">
      <article v-for="run in runs" :key="run.runId" class="run-card">
        <div class="run-card-head">
          <div class="run-id" :title="run.runId">{{ run.runId }}</div>
          <span class="run-source" :class="run.source">
            {{ run.source === 'live' ? '实时生成' : '预跑批次' }}
          </span>
        </div>
        <div class="run-meta">
          <span>{{ run.count }} 条样本</span>
          <span>{{ countSummary(run.ethnicCounts) || '民族未标注' }}</span>
          <span>{{ countSummary(run.difficultyCounts) || '难度未标注' }}</span>
        </div>
        <div class="run-preview">
          <div v-for="sample in run.previewSamples" :key="sample.id" class="preview-line">
            <strong>{{ sample.ethnic || '未标注' }}</strong>
            <span>{{ sample.fullQuestion }}</span>
          </div>
        </div>
        <div class="run-sync-note">
          {{
            selectedRunIds.has(run.runId)
              ? '当前已选集合正在使用该批次'
              : '可在右侧已选数据中按批次筛选'
          }}
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useOutputStore } from '@/stores/output'

const store = useOutputStore()
const {
  cultureCorpusRunSummaries: runs,
  cultureCorpusRunHistoryLoading: loading,
  cultureCorpusRunHistoryError: error,
} = storeToRefs(store)

const selectedRunIds = computed(
  () =>
    new Set(
      store.selectedDatasets
        .filter((dataset) => dataset.dataSource === 'corpus_static')
        .flatMap((dataset) => dataset.cultureCorpusFilters?.runIds || []),
    ),
)

function countSummary(counts: Record<string, number>) {
  return Object.entries(counts)
    .slice(0, 3)
    .map(([key, value]) => `${key} ${value}`)
    .join(' / ')
}

async function refreshHistory() {
  await store.loadCultureCorpusRunHistory(true)
}

onMounted(() => {
  void store.loadCultureCorpusRunHistory()
})
</script>

<style src="./CultureCorpusRunsPanel.css" scoped></style>
