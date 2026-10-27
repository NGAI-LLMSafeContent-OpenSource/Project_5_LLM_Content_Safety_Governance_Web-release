<template>
  <section class="dip-value-detail" aria-labelledby="dip-value-question">
    <header class="dip-value-detail__head">
      <div>
        <span>
          {{ group.topic }} · {{ group.primaryDimension }} / {{ group.secondaryDimension }}
        </span>
        <h2 id="dip-value-question">{{ group.answers.high.question }}</h2>
      </div>
      <span class="dip-record-id">{{ group.id }}</span>
    </header>

    <div class="dip-value-columns">
      <article v-for="level in levels" :key="level" :class="`is-${level}`">
        <div class="dip-value-columns__label">
          <span aria-hidden="true"></span>
          <strong>{{ valueLevelLabels[level] }}</strong>
        </div>
        <p>{{ group.answers[level].answer }}</p>
        <div class="dip-value-columns__rationale">
          <span>档位说明</span>
          {{ group.answers[level].rationale }}
        </div>
      </article>
    </div>

    <details class="dip-disclosure" :open="evidenceOpen">
      <summary>查看来源信息与样本依据</summary>
      <dl>
        <div>
          <dt>来源文档</dt>
          <dd>{{ group.source }}</dd>
        </div>
        <div>
          <dt>证据片段</dt>
          <dd>{{ group.evidence }}</dd>
        </div>
      </dl>
    </details>
  </section>
</template>

<script setup lang="ts">
import type { ValueGroup, ValueLevel } from './prototypeData'
import { valueLevelLabels } from './prototypeData'

withDefaults(defineProps<{ group: ValueGroup; evidenceOpen?: boolean }>(), {
  evidenceOpen: false,
})

const levels: ValueLevel[] = ['high', 'medium', 'low']
</script>
