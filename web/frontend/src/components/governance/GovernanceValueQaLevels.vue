<template>
  <div class="qa-levels">
    <article v-for="level in ordered" :key="level.quality_level" class="qa-level">
      <header class="qa-level__head">
        <span class="qa-level__badge" :class="'is-' + level.quality_level">
          {{ level.level_display }}
        </span>
        <span class="qa-level__score">{{ level.level_score }}</span>
      </header>
      <p class="qa-level__question">问：{{ level.question }}</p>
      <p class="qa-level__answer">答：{{ level.answer }}</p>
      <details v-if="level.source_documents.length" class="qa-level__details">
        <summary>来源文档</summary>
        <ul>
          <li v-for="(doc, index) in level.source_documents" :key="index">
            {{ sourceDocText(doc) }}
          </li>
        </ul>
      </details>
      <details v-if="level.evidence.length" class="qa-level__details">
        <summary>证据片段</summary>
        <ul>
          <li v-for="(item, index) in level.evidence" :key="index">
            {{ evidenceText(item) }}
          </li>
        </ul>
      </details>
      <details v-if="level.value_annotations.length" class="qa-level__details">
        <summary>已有依据</summary>
        <ul>
          <li v-for="(item, index) in level.value_annotations" :key="index">
            {{ annotationText(item) }}
          </li>
        </ul>
      </details>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GovernanceValueQaLevel } from '@/types'
import { formatValueKeys } from '@/utils/governance-format'

const LEVEL_ORDER = ['high', 'medium', 'low']

const props = defineProps<{
  levels: Record<string, GovernanceValueQaLevel>
}>()

const ordered = computed<GovernanceValueQaLevel[]>(() =>
  LEVEL_ORDER.map((key) => props.levels[key]).filter((level): level is GovernanceValueQaLevel =>
    Boolean(level),
  ),
)

function text(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  return ''
}

function sourceDocText(doc: Record<string, unknown>): string {
  return [text(doc.title), text(doc.url), text(doc.selected_reason)].filter(Boolean).join(' · ')
}

function evidenceText(item: Record<string, unknown>): string {
  return [text(item.text) || text(item.sentence), text(item.support)].filter(Boolean).join(' · ')
}

function annotationText(item: Record<string, unknown>): string {
  const keys = Array.isArray(item.value_keys) ? formatValueKeys(item.value_keys.map(String)) : ''
  return [text(item.rationale), keys ? `价值键：${keys}` : ''].filter(Boolean).join(' · ')
}
</script>
