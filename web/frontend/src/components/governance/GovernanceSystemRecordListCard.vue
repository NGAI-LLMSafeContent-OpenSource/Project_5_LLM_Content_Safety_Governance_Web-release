<template>
  <div v-if="payload" class="system-record-list" aria-label="系统预跑记录列表">
    <p class="system-record-list__badge">系统预跑记录 · 非本次用户执行结果</p>
    <div v-if="filterEntries.length" class="system-record-list__filters">
      <span v-for="entry in filterEntries" :key="entry.key" class="system-record-list__filter">
        {{ entry.key }}：{{ entry.label }}
      </span>
    </div>
    <div v-if="payload.total === 0" class="system-record-list__empty">无匹配记录。</div>
    <template v-else>
      <div v-if="sourceSummary" class="system-record-list__summary">
        <span class="system-record-list__source">来源：{{ sourceSummary }}</span>
      </div>
      <ol class="system-record-list__items">
        <li v-for="record in payload.records" :key="record.record_id" class="system-record">
          <div class="system-record__head">
            <strong>{{ record.name || record.record_id }}</strong>
            <span class="system-record__chip">{{ record.record_type_label }}</span>
            <span
              class="system-record__chip"
              :class="record.has_evaluation ? 'is-done' : 'is-pending'"
            >
              {{ record.status_label }}
            </span>
            <span
              class="system-record__chip"
              :class="record.asset_status === 'current' ? 'is-done' : ''"
            >
              {{ assetLabel(record) }}
            </span>
          </div>
          <p class="system-record__id">
            <span class="system-record__id-label">记录 ID</span>
            <span class="system-record__id-value">{{ record.record_id }}</span>
            <button
              type="button"
              class="system-record__copy"
              :aria-label="`复制记录 ID ${record.record_id}`"
              @click="copyRecordId(record.record_id)"
            >
              复制
            </button>
          </p>
          <div class="system-record__meta">
            <span>来源：{{ sourceText(record) }}</span>
            <span>样本：{{ record.sample_count }}</span>
            <span v-if="record.model_names.length">模型：{{ record.model_names.join('、') }}</span>
            <span>完成时间：{{ formatGovernanceTime(record.completed_at) }}</span>
          </div>
          <div class="system-record__actions">
            <button
              type="button"
              class="system-record__open"
              @click="$emit('open', record.record_id)"
            >
              打开详情
            </button>
          </div>
        </li>
      </ol>
      <div v-if="canLoadMore" class="system-record-list__more">
        <span>
          第 {{ payload.offset + 1 }}–{{ payload.offset + payload.records.length }} 条 / 共
          {{ payload.total }} 条
        </span>
        <button type="button" class="system-record-list__more-button" @click="$emit('load-more')">
          加载更多
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  GovernanceSessionMessage,
  GovernanceSystemRecordItem,
  GovernanceSystemRecordSearchPayload,
} from '@/types'
import {
  formatAssetStatus,
  formatAssetVersion,
  formatGovernanceTime,
} from '@/utils/governance-format'

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
}

const STATUS_DISPLAY: Record<string, string> = {
  evaluation_imported: '评测结果已导入',
  evaluation_pending: '评测结果待导入',
}

const payload = computed<GovernanceSystemRecordSearchPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'risk_system_record_search' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceSystemRecordSearchPayload
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

function sourceText(record: GovernanceSystemRecordItem) {
  return [record.source_repo, record.source_commit].filter(Boolean).join('@') || '未标注'
}

function assetLabel(record: GovernanceSystemRecordItem): string {
  if (!record.asset_version) return '未登记系列'
  return `${formatAssetVersion(record.asset_version)} · ${formatAssetStatus(record.asset_status)}`
}

async function copyRecordId(recordId: string) {
  try {
    await navigator.clipboard?.writeText(recordId)
  } catch {
    // Clipboard permission is optional; the id stays selectable on screen.
  }
}
</script>
