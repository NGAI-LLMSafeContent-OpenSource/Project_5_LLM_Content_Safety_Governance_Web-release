<template>
  <div id="app-root">
    <AppHeader v-if="route.path !== '/' && route.name !== 'governance'" />
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

import AppHeader from '@/components/common/AppHeader.vue'

// 根组件仅保留业务外壳；Toast / Loading / Dialog / Drawer 按页面和 API 调用使用 Element Plus。
const route = useRoute()
</script>
