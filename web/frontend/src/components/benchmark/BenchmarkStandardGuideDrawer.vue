<template>
  <el-drawer
    :model-value="modelValue"
    :title="STANDARD_GUIDE_TITLE"
    direction="rtl"
    size="min(520px, 92vw)"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!-- Trusted repo-managed guide markdown only; not user input. -->
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="standard-guide-drawer__body" v-html="guideHtml" />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import guideMarkdown from '@repo-doc-guides/动态Benchmark-标准模式使用说明.md?raw'
import '@/assets/styles/benchmark-standard-guide.css'
import {
  renderStandardGuideMarkdown,
  STANDARD_GUIDE_TITLE,
} from '@/utils/benchmark/renderStandardGuideMarkdown'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const guideHtml = computed(() => renderStandardGuideMarkdown(guideMarkdown))
</script>
