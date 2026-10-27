<template>
  <div v-if="payload" class="qa-group-card" aria-label="价值问题组详情">
    <div v-if="!payload.available" class="qa-group-card__empty">{{ message.content }}</div>
    <template v-else>
      <div class="qa-group-card__summary">
        {{ message.content }}
        <span v-if="sourceSummary" class="qa-group-card__source">来源：{{ sourceSummary }}</span>
      </div>
      <p class="qa-group-card__pos">
        第 {{ payload.group_index + 1 }} / {{ payload.groups.length }} 组
      </p>
      <h4>{{ payload.topic || '未标注主题' }}</h4>
      <p class="qa-group-card__dims">
        {{ payload.primary_dimension }} · {{ payload.secondary_dimension }}
      </p>
      <GovernanceValueQaLevels :levels="payload.levels" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GovernanceSessionMessage, GovernanceValueQaGroupDetailPayload } from '@/types'
import GovernanceValueQaLevels from '@/components/governance/GovernanceValueQaLevels.vue'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceValueQaGroupDetailPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'value_qa_group_detail' || !raw) return null
  if (typeof raw.group_id !== 'string') return null
  return raw as unknown as GovernanceValueQaGroupDetailPayload
})

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref) => [ref.source_repo, ref.source_commit].filter(Boolean).join('@'))
    .filter(Boolean)
    .join('、')
})
</script>
