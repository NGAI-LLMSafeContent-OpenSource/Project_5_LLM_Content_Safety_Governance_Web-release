<template>
  <div class="governance-timeline">
    <div class="governance-timeline__heading">
      <p>{{ domainLabel }} · 已保存的治理会话</p>
      <h1>{{ session.title }}</h1>
      <span>治理助手已接入，按业务域执行受控治理能力。</span>
    </div>
    <ol class="governance-timeline__messages" aria-label="会话消息">
      <li
        v-for="(message, index) in session.messages"
        :key="message.id"
        class="governance-timeline__message"
        :class="messageClass(message)"
      >
        <div class="governance-timeline__message-meta">
          <strong>{{ roleLabel(message) }}</strong>
          <time :datetime="message.created_at">{{ formatTime(message.created_at) }}</time>
        </div>
        <p>{{ message.content }}</p>
        <GovernanceValueCorpusCard
          v-if="message.kind === 'value_corpus_overview'"
          :message="message"
        />
        <GovernanceTopic1ToolCatalogCard
          v-else-if="message.kind === 'topic1_corpus_tool_catalog'"
          :message="message"
        />
        <GovernanceValueQaSearchCard
          v-else-if="message.kind === 'value_qa_search'"
          :message="message"
        />
        <GovernanceValueQaGroupCard
          v-else-if="message.kind === 'value_qa_group_detail'"
          :message="message"
        />
        <GovernanceCbrneDiscoverCard
          v-else-if="message.kind === 'cbrne_dataset_discover'"
          :message="message"
        />
        <GovernanceCbrneOverviewCard
          v-else-if="message.kind === 'cbrne_dataset_overview'"
          :message="message"
        />
        <GovernanceCbrneSearchCard
          v-else-if="message.kind === 'cbrne_dataset_search'"
          :message="message"
          :is-last="index === lastCbrneSearchIndex"
          @load-more="$emit('load-more')"
        />
        <GovernanceCbrneFullTextCard
          v-else-if="message.kind === 'cbrne_dataset_full_text'"
          :message="message"
        />
        <GovernanceRiskCorpusCard
          v-else-if="message.kind === 'risk_corpus_overview'"
          :message="message"
        />
        <GovernanceRiskSearchCard
          v-else-if="message.kind === 'risk_corpus_search'"
          :message="message"
          :is-last="index === lastRiskSearchIndex"
          :show-filter-row="index === lastRiskSearchIndex"
          :filter-groups="index === lastRiskSearchIndex ? riskFilterGroups : []"
          :busy="filterBusy"
          @load-more="$emit('load-more')"
          @select-filter="$emit('select-filter', $event)"
          @request-overview="$emit('request-overview')"
        />
        <GovernanceRiskRescanConfirmCard
          v-else-if="message.kind === 'risk_corpus_rescan' && message.payload?.phase === 'preview'"
          :message="message"
        />
        <GovernanceRiskRescanResultCard
          v-else-if="message.kind === 'risk_corpus_rescan'"
          :message="message"
        />
        <GovernanceSystemRecordListCard
          v-else-if="message.kind === 'risk_system_record_search'"
          :message="message"
          :is-last="index === lastSystemRecordIndex"
          @load-more="$emit('load-more')"
          @open="
            $emit('open-system-record', {
              capability: 'risk_system_record_detail',
              recordId: $event,
            })
          "
        />
        <GovernanceSystemRecordDetailCard
          v-else-if="message.kind === 'risk_system_record_detail'"
          :message="message"
        />
        <GovernanceCulturalRecordListCard
          v-else-if="message.kind === 'cultural_system_record_search'"
          :message="message"
          :is-last="index === lastCulturalRecordIndex"
          @load-more="$emit('load-more')"
          @open="
            $emit('open-system-record', {
              capability: 'cultural_system_record_detail',
              recordId: $event,
            })
          "
        />
        <GovernanceCulturalRecordDetailCard
          v-else-if="message.kind === 'cultural_system_record_detail'"
          :message="message"
        />
        <GovernanceCulturalPrerunReviewCard
          v-else-if="message.kind === 'cultural_prerun_review'"
          :message="message"
        />
        <GovernanceRiskPrerunReviewCard
          v-else-if="message.kind === 'risk_prerun_review'"
          :message="message"
        />
        <GovernanceSkillPlanCard
          v-else-if="message.kind === 'governance_skill_plan'"
          :message="message"
        />
      </li>
    </ol>

    <GovernanceTaskSuggestionList
      :suggestions="sessionSuggestions"
      :disabled="filterBusy"
      @select="$emit('select-suggestion', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  GovernanceSessionDetail,
  GovernanceSessionMessage,
  GovernanceSystemRecordOpenRequest,
  GovernanceTaskSuggestion,
} from '@/types'
import GovernanceValueCorpusCard from '@/components/governance/GovernanceValueCorpusCard.vue'
import GovernanceTopic1ToolCatalogCard from '@/components/governance/GovernanceTopic1ToolCatalogCard.vue'
import GovernanceValueQaSearchCard from '@/components/governance/GovernanceValueQaSearchCard.vue'
import GovernanceValueQaGroupCard from '@/components/governance/GovernanceValueQaGroupCard.vue'
import GovernanceCbrneDiscoverCard from '@/components/governance/GovernanceCbrneDiscoverCard.vue'
import GovernanceCbrneOverviewCard from '@/components/governance/GovernanceCbrneOverviewCard.vue'
import GovernanceCbrneSearchCard from '@/components/governance/GovernanceCbrneSearchCard.vue'
import GovernanceCbrneFullTextCard from '@/components/governance/GovernanceCbrneFullTextCard.vue'
import GovernanceRiskCorpusCard from '@/components/governance/GovernanceRiskCorpusCard.vue'
import GovernanceRiskSearchCard from '@/components/governance/GovernanceRiskSearchCard.vue'
import GovernanceRiskRescanConfirmCard from '@/components/governance/GovernanceRiskRescanConfirmCard.vue'
import GovernanceRiskRescanResultCard from '@/components/governance/GovernanceRiskRescanResultCard.vue'
import GovernanceSystemRecordListCard from '@/components/governance/GovernanceSystemRecordListCard.vue'
import GovernanceSystemRecordDetailCard from '@/components/governance/GovernanceSystemRecordDetailCard.vue'
import GovernanceCulturalRecordListCard from '@/components/governance/GovernanceCulturalRecordListCard.vue'
import GovernanceCulturalRecordDetailCard from '@/components/governance/GovernanceCulturalRecordDetailCard.vue'
import GovernanceCulturalPrerunReviewCard from '@/components/governance/GovernanceCulturalPrerunReviewCard.vue'
import GovernanceRiskPrerunReviewCard from '@/components/governance/GovernanceRiskPrerunReviewCard.vue'
import GovernanceSkillPlanCard from '@/components/governance/GovernanceSkillPlanCard.vue'
import GovernanceTaskSuggestionList from '@/components/governance/GovernanceTaskSuggestionList.vue'
import { buildRiskFilterGroups, type RiskFilterKey } from '@/utils/governance-risk-filters'

const props = defineProps<{
  session: GovernanceSessionDetail
  domainLabel: string
  filterBusy?: boolean
}>()

defineEmits<{
  (event: 'load-more'): void
  (event: 'select-filter', payload: { key: RiskFilterKey; value: string }): void
  (event: 'request-overview'): void
  (event: 'open-system-record', payload: GovernanceSystemRecordOpenRequest): void
  (event: 'select-suggestion', suggestion: GovernanceTaskSuggestion): void
}>()

// #65: evidence-based follow-up suggestions travel with the session detail
// (`suggestions` may be absent on older backends, so default to none).
const sessionSuggestions = computed(() => props.session.suggestions ?? [])

// Clickable filter values come from this session's most recent
// `risk_corpus_overview` result, so they survive a refresh or history restore
// without any frontend-only cache (#60).
const latestRiskOverviewPayload = computed(() => {
  let payload: unknown = null
  for (const message of props.session.messages) {
    if (message.kind === 'risk_corpus_overview' && message.payload) payload = message.payload
  }
  return payload
})

const riskFilterGroups = computed(() => buildRiskFilterGroups(latestRiskOverviewPayload.value))

// Only the newest risk result can extend its page range; earlier pages stay
// immutable snapshots and must not offer a stale "load more".
const lastRiskSearchIndex = computed(() => {
  let index = -1
  props.session.messages.forEach((message, position) => {
    if (message.kind === 'risk_corpus_search') index = position
  })
  return index
})

const lastCbrneSearchIndex = computed(() => {
  let index = -1
  props.session.messages.forEach((message, position) => {
    if (message.kind === 'cbrne_dataset_search') index = position
  })
  return index
})

const lastSystemRecordIndex = computed(() => {
  let index = -1
  props.session.messages.forEach((message, position) => {
    if (message.kind === 'risk_system_record_search') index = position
  })
  return index
})

const lastCulturalRecordIndex = computed(() => {
  let index = -1
  props.session.messages.forEach((message, position) => {
    if (message.kind === 'cultural_system_record_search') index = position
  })
  return index
})

function roleLabel(message: GovernanceSessionMessage) {
  if (message.role === 'user') return '我的请求'
  if (message.kind === 'clarify') return '治理助手 · 待补充'
  if (message.kind === 'boundary') return '治理助手 · 边界提示'
  if (message.kind === 'value_corpus_overview') return '治理助手 · 价值语料概览'
  if (message.kind === 'topic1_corpus_tool_catalog') return '治理助手 · 课题一输入工具状态'
  if (message.kind === 'value_qa_search') return '治理助手 · 价值问题组检索'
  if (message.kind === 'value_qa_group_detail') return '治理助手 · 价值问题组详情'
  if (message.kind === 'cbrne_dataset_discover') return '治理助手 · CBRNE 资产发现'
  if (message.kind === 'cbrne_dataset_overview') return '治理助手 · CBRNE 资产总览'
  if (message.kind === 'cbrne_dataset_search') return '治理助手 · CBRNE 摘要查询'
  if (message.kind === 'cbrne_dataset_full_text') return '治理助手 · CBRNE 全文披露'
  if (message.kind === 'risk_corpus_overview') return '治理助手 · 风险语料概览'
  if (message.kind === 'risk_corpus_search') return '治理助手 · 风险样本浏览'
  if (message.kind === 'risk_corpus_rescan') {
    return message.payload?.phase === 'preview'
      ? '治理助手 · 输入风险语料在线二次检测待确认'
      : '治理助手 · 输入风险语料在线二次检测'
  }
  if (message.kind === 'risk_system_record_search') return '系统预跑记录 · 列表'
  if (message.kind === 'risk_system_record_detail') return '系统预跑记录 · 详情'
  if (message.kind === 'governance_skill_plan') return '治理助手 · 执行计划'
  if (message.kind === 'cultural_system_record_search') return '文化多样性系统预跑记录 · 列表'
  if (message.kind === 'cultural_system_record_detail') return '文化多样性系统预跑记录 · 详情'
  if (message.kind === 'cultural_prerun_review') return '文化预跑记录审阅任务'
  if (message.kind === 'risk_prerun_review') return '风险预跑记录审阅任务'
  return '治理助手'
}

function messageClass(message: GovernanceSessionMessage) {
  return {
    'is-assistant': message.role === 'assistant',
    'is-boundary': message.kind === 'boundary',
    'is-clarify': message.kind === 'clarify',
  }
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>
