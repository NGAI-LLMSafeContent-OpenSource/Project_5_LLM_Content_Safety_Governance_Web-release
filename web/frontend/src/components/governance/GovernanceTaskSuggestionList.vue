<template>
  <section v-if="visible.length >= 2" class="governance-task-suggestions" aria-label="后续建议">
    <h3 class="governance-task-suggestions__title">后续建议</h3>
    <ul class="governance-task-suggestions__list">
      <li
        v-for="suggestion in visible"
        :key="suggestion.id"
        class="governance-task-suggestions__item"
      >
        <button
          type="button"
          class="governance-task-suggestions__button"
          :disabled="disabled"
          @click="$emit('select', suggestion)"
        >
          <span class="governance-task-suggestions__head">
            <span class="governance-task-suggestions__item-title">{{ suggestion.title }}</span>
            <span
              class="governance-task-suggestions__handling"
              :class="suggestion.handling === 'direct' ? 'is-direct' : 'is-plan'"
            >
              {{ handlingLabel(suggestion) }}
            </span>
          </span>
          <span v-if="suggestion.reason" class="governance-task-suggestions__reason">
            {{ suggestion.reason }}
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { GovernanceTaskSuggestion } from '@/types'

const props = withDefaults(
  defineProps<{
    suggestions?: GovernanceTaskSuggestion[] | null
    disabled?: boolean
  }>(),
  {
    suggestions: null,
    disabled: false,
  },
)

defineEmits<{
  (event: 'select', suggestion: GovernanceTaskSuggestion): void
}>()

// 服务端稳定结果后返回 0 条或 2–4 条；不足 2 条不渲染，最多展示 4 条。
// #96: clickable chips must bind a registered capability or skill.
const visible = computed(() =>
  (props.suggestions ?? [])
    .filter((item) => Boolean(item.capability || item.skill_key))
    .slice(0, 4),
)

function handlingLabel(suggestion: GovernanceTaskSuggestion) {
  return suggestion.handling === 'direct' ? '直接执行' : '加入计划并确认'
}
</script>
