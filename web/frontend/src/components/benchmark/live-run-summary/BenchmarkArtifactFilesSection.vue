<template>
  <section class="summary-section">
    <div class="section-head">
      <div>
        <h3>{{ title }}</h3>
        <p>{{ description }}</p>
      </div>
    </div>
    <div class="artifact-grid">
      <span
        v-for="item in fileItems"
        :key="item.name"
        :class="['artifact-chip', item.available ? 'is-ok' : 'is-missing']"
      >
        {{ item.name }} / {{ item.available ? '已冻结' : '缺失' }}
      </span>
    </div>
    <el-alert
      v-if="warnings.length"
      type="warning"
      :title="warnings.join('；')"
      :closable="false"
      show-icon
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    files: Record<string, boolean>
    expectedFiles: string[]
    warnings?: string[]
    title?: string
    description?: string
  }>(),
  {
    warnings: () => [],
    title: '可信锚点',
    description: '固定到本次 artifact zip 内的文件，避免读取运行台 latest 导致错配。',
  },
)

const fileItems = computed(() =>
  props.expectedFiles.map((name) => ({
    name,
    available: Boolean(props.files[name]),
  })),
)
</script>
