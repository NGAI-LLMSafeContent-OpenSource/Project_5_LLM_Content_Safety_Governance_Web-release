<template>
  <div v-if="payload" class="cultural-record-list" aria-label="文化多样性系统预跑记录列表">
    <p class="cultural-record-list__badge">系统预跑记录 · 非本次用户执行结果</p>
    <div v-if="filterEntries.length" class="cultural-record-list__filters">
      <span v-for="entry in filterEntries" :key="entry.key" class="cultural-record-list__filter">
        {{ entry.key }}：{{ entry.label }}
      </span>
    </div>
    <div v-if="payload.total === 0" class="cultural-record-list__empty">无匹配记录。</div>
    <template v-else>
      <div v-if="sourceSummary" class="cultural-record-list__summary">
        <span class="cultural-record-list__source">来源：{{ sourceSummary }}</span>
      </div>
      <ol class="cultural-record-list__items">
        <li v-for="record in payload.records" :key="record.record_id" class="cultural-record">
          <div class="cultural-record__head">
            <strong>{{ record.name || record.record_id }}</strong>
            <span class="cultural-record__chip">{{ record.record_type_label }}</span>
            <span
              class="cultural-record__chip"
              :class="record.has_evaluation ? 'is-done' : 'is-pending'"
            >
              {{ record.status_label }}
            </span>
          </div>
          <p class="cultural-record__id">
            <span class="cultural-record__id-label">记录 ID</span>
            <span class="cultural-record__id-value">{{ record.record_id }}</span>
            <button
              type="button"
              class="cultural-record__copy"
              :aria-label="`复制记录 ID ${record.record_id}`"
              @click="copyRecordId(record.record_id)"
            >
              复制
            </button>
          </p>
          <div class="cultural-record__meta">
            <span>来源：{{ sourceText(record) }}</span>
            <span>样本：{{ record.sample_count }}</span>
            <span>审校通过：{{ record.review_passed_count }}（{{ passRate(record) }}）</span>
            <span v-if="record.difficulty_levels.length">
              语境难度：{{ record.difficulty_levels.join('、') }}
            </span>
            <span v-if="record.ethnic_groups.length">
              民族：{{ record.ethnic_groups.join('、') }}
            </span>
            <span v-if="record.background_types.length">
              背景类型：{{ record.background_types.join('、') }}
            </span>
            <span v-if="record.query_types.length">
              问题类型：{{ record.query_types.join('、') }}
            </span>
            <span>完成时间：{{ formatGovernanceTime(record.completed_at) }}</span>
          </div>
          <div class="cultural-record__actions">
            <button
              type="button"
              class="cultural-record__open"
              @click="$emit('open', record.record_id)"
            >
              打开详情
            </button>
          </div>
        </li>
      </ol>
      <div v-if="canLoadMore" class="cultural-record-list__more">
        <span>
          第 {{ payload.offset + 1 }}–{{ payload.offset + payload.records.length }} 条 / 共
          {{ payload.total }} 条
        </span>
        <button type="button" class="cultural-record-list__more-button" @click="$emit('load-more')">
          加载更多
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  GovernanceCulturalRecordItem,
  GovernanceCulturalRecordSearchPayload,
  GovernanceSessionMessage,
} from '@/types'
import { formatGovernanceTime } from '@/utils/governance-format'

const props = defineProps<{
  message: GovernanceSessionMessage
  isLast?: boolean
}>()

defineEmits<{
  (event: 'load-more'): void
  (event: 'open', recordId: string): void
}>()

const FILTER_LABELS: Record<string, string> = {
  source: '来源',
  status: '状态',
  completed_after: '完成时间起',
  completed_before: '完成时间止',
  difficulty_level: '语境难度',
  ethnic_group: '民族',
  background_type: '背景类型',
  query_type: '问题类型',
}

const STATUS_DISPLAY: Record<string, string> = {
  evaluation_imported: '评测结果已导入',
  evaluation_pending: '评测结果待导入',
}

const payload = computed<GovernanceCulturalRecordSearchPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'cultural_system_record_search' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceCulturalRecordSearchPayload
})

const canLoadMore = computed(() => {
  const value = payload.value
  if (!value || !props.isLast) return false
  return value.offset + value.records.length < value.total
})

const filterEntries = computed(() =>
  Object.entries(payload.value?.filters ?? {}).map(([key, value]) => ({
    key: FILTER_LABELS[key] ?? key,
    label: key === 'status' ? (STATUS_DISPLAY[String(value)] ?? String(value)) : String(value),
  })),
)

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  const repos = refs
    .map((ref) => [ref.source_repo, ref.source_commit].filter(Boolean).join('@'))
    .filter(Boolean)
  return Array.from(new Set(repos)).join('、')
})

function sourceText(record: GovernanceCulturalRecordItem) {
  return [record.source_repo, record.source_commit].filter(Boolean).join('@') || '未标注'
}

function passRate(record: GovernanceCulturalRecordItem) {
  return `${Math.round((record.review_passed_rate || 0) * 100)}%`
}

async function copyRecordId(recordId: string) {
  try {
    await navigator.clipboard?.writeText(recordId)
  } catch {
    // Clipboard permission is optional; the id stays selectable on screen.
  }
}
</script>
