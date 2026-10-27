<template>
  <el-drawer
    v-model="visible"
    size="860px"
    :title="drawerTitle"
    destroy-on-close
    @open="loadSummary"
  >
    <div v-if="asset" class="live-run-drawer">
      <el-alert
        v-if="errorMessage"
        type="warning"
        :title="errorMessage"
        :closable="false"
        show-icon
      />

      <BenchmarkLiveRunIdentitySection
        :asset="asset"
        :summary="summary"
        :is-loading="isLoading"
        @refresh="loadSummary"
      />

      <BenchmarkTopic3LiveRunSummaryBody
        v-if="isTopic3DifficultySummary"
        :asset="asset"
        :summary="summary"
      />
      <BenchmarkTopic1ValueQaLiveRunSummaryBody
        v-else-if="isTopic1ValueQaSummary"
        :asset="asset"
        :summary="summary"
      />
      <BenchmarkTopic3CulturalLiveRunSummaryBody
        v-else-if="isTopic3CulturalSummary"
        :asset="asset"
        :summary="summary"
        @open-samples="emit('open-samples')"
      />
      <BenchmarkAutoBenchLiveRunSummaryBody
        v-else
        :asset="asset"
        :summary="summary"
        :is-loading="isLoading"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BenchmarkAutoBenchLiveRunSummaryBody from './BenchmarkAutoBenchLiveRunSummaryBody.vue'
import BenchmarkLiveRunIdentitySection from './BenchmarkLiveRunIdentitySection.vue'
import BenchmarkTopic1ValueQaLiveRunSummaryBody from './BenchmarkTopic1ValueQaLiveRunSummaryBody.vue'
import BenchmarkTopic3CulturalLiveRunSummaryBody from './BenchmarkTopic3CulturalLiveRunSummaryBody.vue'
import BenchmarkTopic3LiveRunSummaryBody from './BenchmarkTopic3LiveRunSummaryBody.vue'
import './benchmarkLiveRunSummary.css'
import { getBenchmarkLiveRunSummary } from '@/api/benchmark'
import type { BenchmarkArtifactItem, BenchmarkLiveRunSummaryResponse } from '@/types'

const props = defineProps<{
  modelValue: boolean
  asset: BenchmarkArtifactItem | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'open-samples'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const summary = ref<BenchmarkLiveRunSummaryResponse | null>(null)
const isLoading = ref(false)
const errorMessage = ref('')

const isTopic3DifficultySummary = computed(() =>
  Boolean(props.asset?.manifest.benchmark_type === 'dynamic_difficulty'),
)
const isTopic1ValueQaSummary = computed(() =>
  Boolean(props.asset?.manifest.benchmark_type === 'value_qa'),
)
const isTopic3CulturalSummary = computed(() =>
  Boolean(props.asset?.manifest.benchmark_type === 'cultural_diversity_generation'),
)

const drawerTitle = computed(() => {
  if (!props.asset) {
    return '运行摘要'
  }
  if (isTopic3DifficultySummary.value) {
    return '课题三动态难度 live_run 运行摘要'
  }
  if (isTopic1ValueQaSummary.value) {
    return '课题一价值评测语料生成 live_run 运行摘要'
  }
  if (isTopic3CulturalSummary.value) {
    return '课题三文化多样性语料生成 live_run 运行摘要'
  }
  return 'AutoBench live_run 运行摘要'
})

watch(
  () => props.asset?.asset_id,
  () => {
    summary.value = null
    errorMessage.value = ''
    if (visible.value) {
      void loadSummary()
    }
  },
)

async function loadSummary() {
  if (!props.asset?.asset_id) {
    summary.value = null
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  try {
    summary.value = await getBenchmarkLiveRunSummary(props.asset.asset_id, { sample_limit: 20 })
  } catch (error) {
    summary.value = null
    errorMessage.value = error instanceof Error ? error.message : '运行摘要读取失败'
  } finally {
    isLoading.value = false
  }
}
</script>
