<template>
  <section class="governance-welcome" aria-labelledby="governance-welcome-title">
    <div class="governance-welcome__eyebrow">
      <span class="governance-welcome__pulse" aria-hidden="true"></span>
      推荐任务
    </div>
    <h1 id="governance-welcome-title">{{ domain.heading }}</h1>
    <p>{{ domain.description }}</p>

    <div class="governance-suggestions" aria-label="推荐任务">
      <template v-for="suggestion in visibleSuggestions" :key="suggestion.id">
        <button
          v-if="isExecutableRecommend(suggestion)"
          class="governance-suggestion"
          type="button"
          @click="$emit('suggestion-select', suggestion)"
        >
          <span>{{ suggestion.title }}</span>
          <ArrowRight aria-hidden="true" />
        </button>
        <div v-else class="governance-suggestion governance-suggestion--explanation" role="note">
          <div class="governance-suggestion__body">
            <span class="governance-suggestion__title">{{ suggestion.title }}</span>
            <span class="governance-suggestion__badge">治理能力说明</span>
            <p v-if="suggestion.reason" class="governance-suggestion__reason">
              {{ suggestion.reason }}
            </p>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

import type { GovernanceDomain, GovernanceSuggestion } from '@/types'
import { isExecutableRecommend } from '@/utils/governance-domains'

const props = defineProps<{
  domain: GovernanceDomain
}>()

defineEmits<{
  (event: 'suggestion-select', suggestion: GovernanceSuggestion): void
}>()

// Clickable starters must be bound; explanation cards may omit bindings.
const visibleSuggestions = computed(() =>
  props.domain.suggestions.filter(
    (item) => item.kind === 'explanation' || isExecutableRecommend(item),
  ),
)
</script>
