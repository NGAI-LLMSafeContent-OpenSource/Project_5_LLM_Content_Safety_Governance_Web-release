<template>
  <article class="topic3-sample-detail">
    <div class="topic3-sample-detail__head">
      <div>
        <b class="mono">{{ sample.sample_id }}</b>
        <p>
          {{ sample.difficulty_level }} / {{ sample.difficulty_strategy }} /
          {{ sample.risk_category }}
        </p>
      </div>
      <el-tooltip :content="topic3TermTooltip('Final Guard')" placement="top" :show-after="200">
        <span>{{ sample.final_guard_label }}</span>
      </el-tooltip>
    </div>
    <div class="topic3-sample-meta">
      <el-tooltip
        v-for="item in metaItems"
        :key="item.label"
        :content="item.tooltip"
        placement="top"
        :disabled="!item.tooltip"
        :show-after="200"
      >
        <span :class="{ 'term-trigger': item.tooltip }">{{ item.label }}：{{ item.value }}</span>
      </el-tooltip>
    </div>
    <div class="topic3-span-legend">
      <span class="is-harmless">harmless span</span>
      <span class="is-harmful">harmful span</span>
    </div>
    <p class="topic3-marked-text">
      <template
        v-for="segment in spanSegments"
        :key="`${segment.start}-${segment.end}-${segment.kind}`"
      >
        <mark v-if="segment.kind !== 'plain'" :class="`is-${segment.kind}`">
          {{ segment.text }}
        </mark>
        <span v-else>{{ segment.text }}</span>
      </template>
    </p>
    <BenchmarkFieldGrid :items="detailItems" />
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BenchmarkFieldGrid, { type BenchmarkFieldGridItem } from './BenchmarkFieldGrid.vue'
import { topic3TermTooltip } from '@/utils/benchmarkLiveRunHelpers'
import { markedSegments } from '@/utils/benchmarkLiveRunFormatters'
import type { BenchmarkTopic3DifficultySample } from '@/types'

const props = defineProps<{
  sample: BenchmarkTopic3DifficultySample
}>()

const metaItems = computed(() => [
  { label: '结构', value: `${props.sample.harmful_count}H / ${props.sample.harmless_count}S` },
  {
    label: 'Interleaving',
    value: props.sample.interleaving ? 'true' : 'false',
    tooltip: topic3TermTooltip('Interleaving'),
  },
  { label: 'Risk Level', value: props.sample.risk_level || '-' },
  {
    label: 'Bridge',
    value: props.sample.bridge_review_label || '-',
    tooltip: topic3TermTooltip('Bridge'),
  },
  {
    label: 'Coherence',
    value: props.sample.coherence_label || '-',
    tooltip: topic3TermTooltip('Coherence'),
  },
])

const spanSegments = computed(() =>
  markedSegments(props.sample.edited_input, [
    ...props.sample.harmless_spans.map((span) => ({ ...span, kind: 'harmless' as const })),
    ...props.sample.harmful_spans.map((span) => ({ ...span, kind: 'harmful' as const })),
  ]),
)

const detailItems = computed<BenchmarkFieldGridItem[]>(() => [
  {
    key: 'bridge_review_reason',
    label: 'Bridge Reason',
    value: props.sample.bridge_review_reason || '-',
    tooltip: topic3TermTooltip('Bridge Reason'),
  },
  {
    key: 'coherence_reason',
    label: 'Coherence Reason',
    value: props.sample.coherence_reason || '-',
    tooltip: topic3TermTooltip('Coherence Reason'),
  },
  {
    key: 'bridge_texts',
    label: 'Bridge Texts',
    value: props.sample.bridge_texts.join(' / ') || '-',
    tooltip: topic3TermTooltip('Bridge Texts'),
  },
  {
    key: 'final_guard_categories',
    label: 'Final Guard Categories',
    value: props.sample.final_guard_categories.join(', ') || '-',
    tooltip: topic3TermTooltip('Final Guard Categories'),
  },
])
</script>
