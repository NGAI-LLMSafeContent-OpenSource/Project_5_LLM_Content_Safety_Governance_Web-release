<template>
  <div class="corpus-context-bar" :class="`corpus-context-bar--${tone}`">
    <div class="corpus-context-bar__main">
      <span class="corpus-context-bar__kicker">本批训练语料</span>
      <strong class="corpus-context-bar__title">{{ title }}</strong>
      <p class="corpus-context-bar__desc">{{ description }}</p>
    </div>
    <div class="corpus-context-bar__chips">
      <span v-for="chip in chips" :key="chip" class="corpus-context-bar__chip">{{ chip }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description: string
    chips?: string[]
    tone?: 'blue' | 'neutral'
  }>(),
  {
    chips: () => [],
    tone: 'blue',
  },
)
</script>

<style scoped>
.corpus-context-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  border-radius: 12px;
  padding: 12px 14px;
}

.corpus-context-bar--blue {
  border: 1px solid rgba(21, 101, 192, 0.14);
  background: linear-gradient(180deg, #f7fbff 0%, #eef5ff 100%);
}

.corpus-context-bar--neutral {
  border: 1px solid var(--border-color);
  background: #f8fafc;
}

.corpus-context-bar__main {
  min-width: 0;
}

.corpus-context-bar__kicker {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.corpus-context-bar__title {
  display: block;
  margin-top: 2px;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.corpus-context-bar__desc {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.corpus-context-bar__chips {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 46%;
}

.corpus-context-bar__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.08);
  color: #1565c0;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}

@media (max-width: 860px) {
  .corpus-context-bar {
    flex-direction: column;
  }

  .corpus-context-bar__chips {
    max-width: none;
    justify-content: flex-start;
  }
}
</style>
