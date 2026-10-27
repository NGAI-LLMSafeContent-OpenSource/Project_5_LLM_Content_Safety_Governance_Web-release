<template>
  <div v-if="payload" class="risk-search-card" aria-label="风险样本浏览结果">
    <div v-if="payload.total === 0" class="risk-search-card__empty">{{ message.content }}</div>
    <template v-else>
      <div class="risk-search-card__summary">
        {{ message.content }}
        <span v-if="sourceSummary" class="risk-search-card__source">来源：{{ sourceSummary }}</span>
      </div>
      <div v-if="filterEntries.length" class="risk-search-card__filters">
        <span v-for="entry in filterEntries" :key="entry.key" class="risk-search-card__filter">
          {{ entry.key }}：{{ entry.label }}
        </span>
      </div>
      <div v-if="showFilterRow" class="risk-filter-values" aria-label="可筛选取值">
        <template v-if="groups.length">
          <div v-for="group in groups" :key="group.key" class="risk-filter-values__group">
            <span class="risk-filter-values__label">{{ group.label }}</span>
            <button
              v-for="option in group.options"
              :key="`${group.key}:${option.value}`"
              type="button"
              class="risk-filter-values__chip"
              :disabled="busy"
              @click="$emit('select-filter', { key: group.key, value: option.value })"
            >
              {{ option.display }}
            </button>
          </div>
        </template>
        <div v-else class="risk-filter-values__empty">
          <span>本会话还没有风险语料构成，先查看构成后再点选筛选。</span>
          <button
            type="button"
            class="risk-filter-values__action"
            :disabled="busy"
            @click="$emit('request-overview')"
          >
            先查看风险语料构成
          </button>
        </div>
      </div>
      <ol class="risk-record-list">
        <li v-for="record in payload.records" :key="record.sample_id" class="risk-record">
          <p class="risk-record__text">{{ record.text }}</p>
          <div class="risk-record__badges">
            <span class="risk-record__label" :class="record.is_risky ? 'is-risky' : 'is-safe'">
              参考标注：{{ labelDisplay(record.reference_label) }}
            </span>
            <span class="risk-record__chip">{{ record.harm_category_L1 }}</span>
            <span class="risk-record__chip">{{ record.harm_category_L2 }}</span>
            <span class="risk-record__chip">来源：{{ record.source }}</span>
          </div>
        </li>
      </ol>
      <div v-if="canLoadMore" class="risk-search-card__more">
        <span>
          第 {{ payload.offset + 1 }}–{{ payload.offset + payload.records.length }} 条 / 共
          {{ payload.total }} 条
        </span>
        <button type="button" class="risk-search-card__more-button" @click="$emit('load-more')">
          加载更多
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GovernanceRiskCorpusSearchPayload, GovernanceSessionMessage } from '@/types'
import type { RiskFilterGroup, RiskFilterKey } from '@/utils/governance-risk-filters'

const props = defineProps<{
  message: GovernanceSessionMessage
  isLast?: boolean
  showFilterRow?: boolean
  filterGroups?: RiskFilterGroup[]
  busy?: boolean
}>()

defineEmits<{
  (event: 'load-more'): void
  (event: 'select-filter', payload: { key: RiskFilterKey; value: string }): void
  (event: 'request-overview'): void
}>()

const LABEL_DISPLAY: Record<string, string> = { safe: '安全', unsafe: '不安全' }

const FILTER_LABELS: Record<string, string> = {
  keyword: '关键词',
  reference_label: '参考标注',
  source: '来源',
  harm_category_L1: '一级分类',
  harm_category_L2: '二级分类',
}

const payload = computed<GovernanceRiskCorpusSearchPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_corpus_search' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceRiskCorpusSearchPayload
})

const groups = computed<RiskFilterGroup[]>(() => props.filterGroups ?? [])

const canLoadMore = computed(() => {
  const value = payload.value
  if (!value || !props.isLast) return false
  return value.offset + value.records.length < value.total
})

const filterEntries = computed(() =>
  Object.entries(payload.value?.filters ?? {}).map(([key, value]) => ({
    key: FILTER_LABELS[key] ?? key,
    label:
      key === 'reference_label' ? (LABEL_DISPLAY[String(value)] ?? String(value)) : String(value),
  })),
)

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref) => {
      const revision = [ref.source_repo, ref.source_commit].filter(Boolean).join('@')
      return revision || ref.name || ref.ref_id
    })
    .filter(Boolean)
    .join('、')
})

function labelDisplay(value: string) {
  return LABEL_DISPLAY[value] ?? value
}
</script>
