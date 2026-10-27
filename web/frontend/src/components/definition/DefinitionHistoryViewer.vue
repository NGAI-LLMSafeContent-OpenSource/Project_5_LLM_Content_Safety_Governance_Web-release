<template>
  <div v-if="open" class="definition-history-drawer" @click.self="$emit('close')">
    <aside
      class="definition-history-drawer__panel definition-history-drawer__panel--wide"
      role="dialog"
      aria-modal="true"
    >
      <header class="definition-history-drawer__head">
        <div>
          <strong>{{ title }}</strong>
          <p v-if="subtitle">{{ subtitle }}</p>
          <div v-if="!loading && !error" class="definition-history-drawer__stats">
            <span>候选 {{ stats.mined }}</span>
            <span>已采纳 {{ stats.adopted }}</span>
            <span>已忽略 {{ stats.ignored }}</span>
            <span>待审核 {{ stats.pending }}</span>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm" type="button" @click="$emit('close')">关闭</button>
      </header>

      <div v-if="loading" class="definition-history-drawer__empty">正在加载历史指标体系…</div>
      <div v-else-if="error" class="definition-history-drawer__empty">{{ error }}</div>
      <div v-else class="definition-history-drawer__body">
        <DefinitionMindmapStep :root-title="rootTitle" :branches="branches" />
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DefinitionMindmapStep from '@/components/definition/DefinitionMindmapStep.vue'
import type { DefinitionBranch } from '@/utils/definitionConfig'

const props = defineProps<{
  open: boolean
  title: string
  subtitle: string
  rootTitle: string
  loading: boolean
  error: string
  branches: DefinitionBranch[]
}>()

defineEmits<{
  (e: 'close'): void
}>()

const stats = computed(() => {
  const leaves = props.branches.flatMap((branch) =>
    branch.childGroups.flatMap((group) => group.leafNodes),
  )
  const mined = leaves.filter((item) => item.kind === 'mined')
  return {
    mined: mined.length,
    adopted: mined.filter((item) => item.status === 'adopted').length,
    ignored: mined.filter((item) => item.status === 'ignored').length,
    pending: mined.filter((item) => item.status === 'pending' || item.status === 'edited').length,
  }
})
</script>

<style scoped>
.definition-history-drawer {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
}

.definition-history-drawer__panel {
  display: flex;
  flex-direction: column;
  width: min(1180px, 100%);
  height: 100%;
  max-height: calc(100vh - 48px);
  margin: auto;
  overflow: hidden;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
}

.definition-history-drawer__head {
  display: flex;
  flex-shrink: 0;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid #e6edf5;
}

.definition-history-drawer__head strong {
  display: block;
  color: #1f3348;
  font-size: 15px;
}

.definition-history-drawer__head p {
  margin: 6px 0 0;
  color: #66788c;
  font-size: 12px;
  line-height: 1.45;
}

.definition-history-drawer__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.definition-history-drawer__stats span {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef3f8;
  color: #3f556c;
  font-size: 11px;
}

.definition-history-drawer__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 18px 24px;
}

.definition-history-drawer__empty {
  padding: 28px 20px;
  color: #66788c;
  font-size: 13px;
}

@media (max-width: 640px) {
  .definition-history-drawer {
    padding: 0;
  }

  .definition-history-drawer__panel {
    max-height: 100vh;
    border-radius: 0;
  }

  .definition-history-drawer__head {
    padding: 14px;
  }

  .definition-history-drawer__body {
    padding: 12px;
  }
}
</style>
