<template>
  <span class="breakable-text">
    <!-- prettier-ignore -->
    <template v-for="(part, index) in parts" :key="index">{{ part }}<wbr v-if="index < parts.length - 1" /></template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { splitAfterSeparators } from '@/utils/breakable-text'

const props = defineProps<{
  text: string
}>()

const parts = computed(() => splitAfterSeparators(props.text))
</script>
