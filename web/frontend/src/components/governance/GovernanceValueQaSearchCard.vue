<template>
  <div v-if="payload" class="qa-search-card" aria-label="价值问题组检索结果">
    <div v-if="payload.total === 0" class="qa-search-card__empty">{{ message.content }}</div>
    <template v-else>
      <div class="qa-search-card__summary">
        {{ message.content }}
        <span v-if="sourceSummary" class="qa-search-card__source">来源：{{ sourceSummary }}</span>
      </div>
      <div class="qa-group-nav">
        <button type="button" class="qa-group-nav__btn" :disabled="!canPrev" @click="goPrev">
          上一组
        </button>
        <span class="qa-group-nav__pos">第 {{ activeIndex + 1 }} / {{ groups.length }} 组</span>
        <button type="button" class="qa-group-nav__btn" :disabled="!canNext" @click="goNext">
          下一组
        </button>
      </div>
      <ol v-if="groups.length > 1" class="qa-search-card__groups">
        <li v-for="(group, index) in groups" :key="group.group_id">
          <button
            type="button"
            class="qa-search-card__jump"
            :class="{ 'is-active': index === activeIndex }"
            @click="activeIndex = index"
          >
            {{ group.topic || group.group_id }}
          </button>
        </li>
      </ol>
      <div v-if="activeGroup" class="qa-search-card__active">
        <h4>{{ activeGroup.topic || '未标注主题' }}</h4>
        <p class="qa-search-card__dims">
          {{ activeGroup.primary_dimension }} · {{ activeGroup.secondary_dimension }}
        </p>
        <GovernanceValueQaLevels :levels="activeGroup.levels" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { GovernanceSessionMessage, GovernanceValueQaSearchPayload } from '@/types'
import GovernanceValueQaLevels from '@/components/governance/GovernanceValueQaLevels.vue'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceValueQaSearchPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'value_qa_search' || !raw) return null
  if (typeof raw.total !== 'number') return null
  return raw as unknown as GovernanceValueQaSearchPayload
})

const groups = computed(() => payload.value?.groups ?? [])
const activeIndex = ref(0)
const activeGroup = computed(() => groups.value[activeIndex.value])

const canPrev = computed(() => activeIndex.value > 0)
const canNext = computed(() => activeIndex.value < groups.value.length - 1)

function goPrev() {
  if (canPrev.value) activeIndex.value -= 1
}
function goNext() {
  if (canNext.value) activeIndex.value += 1
}

const sourceSummary = computed(() => {
  const refs = payload.value?.source_refs ?? []
  return refs
    .map((ref) => [ref.source_repo, ref.source_commit].filter(Boolean).join('@'))
    .filter(Boolean)
    .join('、')
})
</script>
