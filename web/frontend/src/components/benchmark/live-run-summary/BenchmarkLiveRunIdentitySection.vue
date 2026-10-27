<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>运行摘要</h3>
        <p>现场链路验证，不等同于正式 simple/hard 预跑结论。</p>
      </div>
      <el-button v-if="showRefresh" size="small" :loading="isLoading" @click="$emit('refresh')">
        刷新
      </el-button>
    </div>

    <BenchmarkFieldGrid :items="identityItems" />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BenchmarkFieldGrid from './BenchmarkFieldGrid.vue'
import { compactHash, valueLabel } from '@/utils/benchmarkLiveRunFormatters'
import { formatApiDate } from '@/utils/datetime'
import type { BenchmarkArtifactItem, BenchmarkLiveRunSummaryResponse } from '@/types'

const props = withDefaults(
  defineProps<{
    asset: BenchmarkArtifactItem
    summary: BenchmarkLiveRunSummaryResponse | null
    isLoading?: boolean
    showRefresh?: boolean
  }>(),
  {
    isLoading: false,
    showRefresh: true,
  },
)

defineEmits<{
  (event: 'refresh'): void
}>()

const identityItems = computed(() => [
  {
    key: 'asset_id',
    label: 'Asset ID',
    value: props.summary?.asset_id ?? props.asset.asset_id,
    mono: true,
  },
  {
    key: 'task_id',
    label: 'Task ID',
    value: props.summary?.task_id ?? props.asset.task_id,
    mono: true,
  },
  {
    key: 'agent_id',
    label: 'Agent',
    value: props.summary?.agent_id || manifestString('agent_id'),
  },
  {
    key: 'created_at',
    label: 'Created At',
    value: formatApiDate(props.summary?.created_at ?? props.asset.created_at),
  },
  {
    key: 'source_commit',
    label: 'Source Commit',
    value: props.summary?.source_commit || manifestString('source_commit'),
    mono: true,
  },
  {
    key: 'artifact_sha256',
    label: 'Artifact SHA-256',
    value: compactHash(props.summary?.artifact_sha256 ?? props.asset.artifact_sha256),
    mono: true,
  },
])

function manifestString(key: string) {
  return valueLabel(props.asset.manifest[key])
}
</script>
