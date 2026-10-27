<template>
  <main class="integration-page page-wide">
    <section class="integration-overview">
      <div class="integration-overview__text">
        <h1>跨课题 Demo 集成总入口</h1>
        <p>
          先把课题一、课题二、课题三当前分散运行的系统收口到平台里，后续再按成熟度逐步回归到原生的治理标准、输入语料和输出内容页面。
        </p>
      </div>
      <div class="integration-overview__stats">
        <div class="integration-overview__stat">
          <span class="value">{{ topicCount }}</span>
          <span class="label">课题分组</span>
        </div>
        <div class="integration-overview__stat">
          <span class="value">{{ systemCount }}</span>
          <span class="label">系统入口</span>
        </div>
      </div>
    </section>

    <section class="integration-layout">
      <TopicSystemNav
        :topics="topicGroups"
        :active-system-id="selectedSystemId"
        @select-system="handleSelectSystem"
      />
      <SystemEmbedPanel :system="selectedSystem" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import TopicSystemNav from '@/components/integration/TopicSystemNav.vue'
import SystemEmbedPanel from '@/components/integration/SystemEmbedPanel.vue'
import {
  getDefaultIntegrationSystem,
  getIntegrationSystemById,
  groupIntegrationSystems,
  integrationSystems,
  integrationTopics,
} from '@/utils/integrationConfig'

const topicGroups = groupIntegrationSystems()
const selectedSystemId = ref(getDefaultIntegrationSystem()?.id ?? '')

const selectedSystem = computed(() => getIntegrationSystemById(selectedSystemId.value))
const topicCount = integrationTopics.length
const systemCount = integrationSystems.length

function handleSelectSystem(systemId: string) {
  selectedSystemId.value = systemId
}
</script>

<style scoped>
.integration-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.integration-overview {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 26px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(13, 71, 161, 0.05), rgba(66, 165, 245, 0.08)), #fff;
  box-shadow: var(--shadow);
}

.integration-overview__text {
  max-width: 860px;
}

.integration-overview__text h1 {
  margin: 0 0 10px;
  font-size: 30px;
  color: var(--text-primary);
}

.integration-overview__text p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.integration-overview__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 14px;
  min-width: 280px;
}

.integration-overview__stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 18px 20px;
  border: 1px solid rgba(21, 101, 192, 0.14);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.integration-overview__stat .value {
  font-size: 28px;
  font-weight: 800;
  color: var(--accent-blue);
  line-height: 1;
}

.integration-overview__stat .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.integration-layout {
  display: grid;
  grid-template-columns: minmax(300px, 340px) minmax(0, 1fr);
  gap: 20px;
  align-items: stretch;
}

@media (max-width: 1200px) {
  .integration-overview {
    flex-direction: column;
  }

  .integration-overview__stats {
    min-width: 0;
  }
}

@media (max-width: 960px) {
  .integration-layout {
    grid-template-columns: 1fr;
  }
}
</style>
