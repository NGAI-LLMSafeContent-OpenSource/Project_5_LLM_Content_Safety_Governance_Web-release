<template>
  <div v-if="isDevelopment" class="dip-switcher" aria-label="原型方案切换">
    <button type="button" title="上一个方案" aria-label="上一个原型方案" @click="cycle(-1)">
      <ArrowLeft />
    </button>
    <div class="dip-switcher__label" aria-live="polite">
      <strong>{{ variantNames[current] }}</strong>
      <span>{{ current === 'D' ? '建议方案' : '对照方案' }}</span>
    </div>
    <button type="button" title="下一个方案" aria-label="下一个原型方案" @click="cycle(1)">
      <ArrowRight />
    </button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const props = defineProps<{ current: 'C' | 'D' }>()
const router = useRouter()
const isDevelopment = import.meta.env.DEV
const variants = ['C', 'D'] as const
const variantNames = { C: '数据工作台', D: '输入治理助手' }

function cycle(offset: number) {
  const currentIndex = variants.indexOf(props.current)
  const next = variants[(currentIndex + offset + variants.length) % variants.length]
  void router.replace({ query: { ...router.currentRoute.value.query, variant: next } })
}

function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.matches('input, textarea, select, [contenteditable="true"]')) return
  if (event.key === 'ArrowLeft') cycle(-1)
  if (event.key === 'ArrowRight') cycle(1)
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>
