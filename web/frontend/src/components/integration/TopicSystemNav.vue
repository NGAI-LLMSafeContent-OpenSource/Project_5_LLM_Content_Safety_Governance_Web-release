<template>
  <aside class="integration-nav">
    <div class="integration-nav__header">
      <h2>课题集成</h2>
      <p>先统一收口各课题 Demo，后续再逐步平台化。</p>
    </div>

    <section v-for="topic in topics" :key="topic.id" class="integration-topic">
      <div class="integration-topic__title">{{ topic.title }}</div>
      <div class="integration-topic__subtitle">{{ topic.subtitle }}</div>

      <div class="integration-topic__systems">
        <button
          v-for="system in topic.systems"
          :key="system.id"
          type="button"
          class="integration-system"
          :class="{ 'is-active': system.id === activeSystemId }"
          @click="$emit('select-system', system.id)"
        >
          <div class="integration-system__row">
            <span class="integration-system__title">{{ system.title }}</span>
            <span class="integration-system__status" :class="`status-${system.status}`">
              {{ statusLabelMap[system.status] }}
            </span>
          </div>
          <div class="integration-system__desc">{{ system.description }}</div>
        </button>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { IntegrationSystemStatus, IntegrationTopicGroup } from '@/utils/integrationConfig'

defineProps<{
  topics: IntegrationTopicGroup[]
  activeSystemId: string
}>()

defineEmits<{
  (e: 'select-system', systemId: string): void
}>()

const statusLabelMap: Record<IntegrationSystemStatus, string> = {
  ready: '在线',
  offline: '离线',
  pending: '待接入',
  native: '已平台化',
}
</script>

<style scoped>
.integration-nav {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.integration-nav__header {
  padding: 22px 20px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(21, 101, 192, 0.08), rgba(21, 101, 192, 0.02)), #fff;
  box-shadow: var(--shadow);
}

.integration-nav__header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--text-primary);
}

.integration-nav__header p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.integration-topic {
  padding: 18px 16px 16px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow);
}

.integration-topic__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.integration-topic__subtitle {
  margin-top: 6px;
  margin-bottom: 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-muted);
}

.integration-topic__systems {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.integration-system {
  width: 100%;
  padding: 14px 14px 14px 16px;
  border: 1px solid #dbe5f1;
  border-radius: 14px;
  background: linear-gradient(180deg, #fff, #fbfdff);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.integration-system:hover {
  transform: translateY(-1px);
  border-color: #bfd4ed;
  box-shadow: 0 10px 22px rgba(21, 101, 192, 0.08);
}

.integration-system.is-active {
  border-color: rgba(21, 101, 192, 0.35);
  background: linear-gradient(180deg, rgba(21, 101, 192, 0.08), rgba(255, 255, 255, 0.98));
  box-shadow: 0 12px 26px rgba(21, 101, 192, 0.12);
  position: relative;
}

.integration-system.is-active::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 999px;
  background: var(--accent-blue);
}

.integration-system__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.integration-system__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.integration-system__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
}

.status-ready {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.status-offline {
  background: rgba(198, 40, 40, 0.1);
  color: var(--accent-red);
}

.status-pending {
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
}

.status-native {
  background: rgba(92, 107, 192, 0.12);
  color: var(--accent-purple);
}

.integration-system__desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>
