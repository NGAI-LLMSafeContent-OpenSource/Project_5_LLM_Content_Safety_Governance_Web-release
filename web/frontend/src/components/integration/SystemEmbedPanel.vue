<template>
  <section class="embed-panel">
    <template v-if="system">
      <header class="embed-panel__header">
        <div class="embed-panel__meta">
          <div class="embed-panel__eyebrow">当前系统</div>
          <h2>{{ system.title }}</h2>
          <p>{{ system.description }}</p>
        </div>

        <div class="embed-panel__actions">
          <span class="embed-panel__status" :class="`status-${system.status}`">
            {{ statusLabelMap[system.status] }}
          </span>
          <el-button size="default" :disabled="!canRefresh" @click="handleRefresh">刷新</el-button>
          <el-button size="default" :disabled="!canOpenExternal" @click="handleOpenNewWindow">
            新窗口打开
          </el-button>
          <el-button
            v-if="system.openMode === 'route' && system.route"
            type="primary"
            size="default"
            @click="handleGoNative"
          >
            进入原生页面
          </el-button>
        </div>
      </header>

      <div class="embed-panel__body">
        <div v-if="showIframe" class="embed-panel__frame-wrap">
          <div v-if="isLoading" class="embed-panel__loading">正在加载系统，请稍候...</div>
          <iframe
            :key="iframeKey"
            :src="system.url"
            class="embed-panel__frame"
            title="课题系统集成预览"
            @load="handleLoad"
            @error="handleError"
          />
        </div>

        <div v-else class="embed-panel__empty">
          <el-empty :description="emptyDescription">
            <template #image>
              <div class="embed-panel__empty-icon">{{ emptyIcon }}</div>
            </template>
            <el-button
              v-if="system.openMode === 'route' && system.route"
              type="primary"
              @click="handleGoNative"
            >
              打开平台原生页面
            </el-button>
            <el-button v-else-if="canOpenExternal" @click="handleOpenNewWindow">
              尝试新窗口打开
            </el-button>
          </el-empty>
        </div>
      </div>
    </template>

    <div v-else class="embed-panel__empty embed-panel__empty--full">
      <el-empty description="请选择左侧系统以开始查看集成内容。" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { IntegrationSystemItem, IntegrationSystemStatus } from '@/utils/integrationConfig'
import {
  canOpenIntegrationSystemExternally,
  canRefreshIntegrationSystem,
} from '@/utils/integrationSystemCapabilities'

const props = defineProps<{
  system: IntegrationSystemItem | null
}>()

const router = useRouter()
const iframeKey = ref(0)
const isLoading = ref(false)
const hasFrameError = ref(false)

const statusLabelMap: Record<IntegrationSystemStatus, string> = {
  ready: '在线',
  offline: '离线',
  pending: '待接入',
  native: '已平台化',
}

watch(
  () => props.system?.id,
  () => {
    iframeKey.value += 1
    hasFrameError.value = false
    isLoading.value = props.system?.status === 'ready' && props.system.openMode === 'iframe'
  },
  { immediate: true },
)

const showIframe = computed(() => {
  return Boolean(
    props.system &&
    props.system.openMode === 'iframe' &&
    props.system.status === 'ready' &&
    props.system.url &&
    !hasFrameError.value,
  )
})

const canOpenExternal = computed(() => {
  return canOpenIntegrationSystemExternally(props.system)
})

const canRefresh = computed(() => {
  return canRefreshIntegrationSystem(props.system)
})

const emptyDescription = computed(() => {
  if (!props.system) {
    return '请选择左侧系统以开始查看集成内容。'
  }

  if (hasFrameError.value) {
    return '当前 iframe 加载失败，可先尝试刷新，或使用新窗口打开该系统。'
  }

  if (props.system.status === 'pending') {
    return '该系统已纳入平台集成清单，但当前尚未完成接入配置。'
  }

  if (props.system.status === 'offline') {
    return '该系统当前未在线，待服务启动后可恢复集成访问。'
  }

  if (props.system.status === 'native') {
    return '该能力已平台化，建议直接进入平台原生页面。'
  }

  return '当前系统暂不可在页面内嵌展示。'
})

const emptyIcon = computed(() => {
  if (hasFrameError.value) {
    return '⚠'
  }

  switch (props.system?.status) {
    case 'pending':
      return '⌛'
    case 'offline':
      return '⛔'
    case 'native':
      return '↗'
    default:
      return '🧩'
  }
})

function handleRefresh() {
  if (!canRefresh.value) {
    return
  }

  hasFrameError.value = false
  isLoading.value = true
  iframeKey.value += 1
}

function handleOpenNewWindow() {
  if (!props.system?.url) {
    return
  }

  window.open(props.system.url, '_blank', 'noopener,noreferrer')
}

function handleGoNative() {
  if (!props.system?.route) {
    return
  }

  void router.push(props.system.route)
}

function handleLoad() {
  isLoading.value = false
}

function handleError() {
  isLoading.value = false
  hasFrameError.value = true
}
</script>

<style scoped>
.embed-panel {
  min-width: 0;
  height: 100%;
  border: 1px solid var(--border-color);
  border-radius: 22px;
  background: #fff;
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.embed-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px 20px;
  border-bottom: 1px solid #e2ebf5;
  background: linear-gradient(180deg, rgba(21, 101, 192, 0.04), rgba(255, 255, 255, 0.98));
}

.embed-panel__meta h2 {
  margin: 4px 0 8px;
  font-size: 24px;
  color: var(--text-primary);
}

.embed-panel__meta p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.embed-panel__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-blue);
}

.embed-panel__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  min-width: 240px;
}

.embed-panel__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  min-height: 34px;
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

.embed-panel__body {
  flex: 1;
  min-height: 0;
  background:
    radial-gradient(circle at top right, rgba(21, 101, 192, 0.05), transparent 28%), #f6f9fe;
}

.embed-panel__frame-wrap {
  position: relative;
  height: 100%;
  min-height: 640px;
  padding: 18px;
}

.embed-panel__loading {
  position: absolute;
  top: 30px;
  right: 30px;
  z-index: 1;
  padding: 8px 12px;
  border: 1px solid #cfe0f4;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-secondary);
  font-size: 12px;
  box-shadow: 0 8px 20px rgba(21, 101, 192, 0.08);
}

.embed-panel__frame {
  width: 100%;
  height: 100%;
  min-height: 640px;
  border: 1px solid #d8e3ef;
  border-radius: 18px;
  background: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.embed-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 640px;
  padding: 32px;
}

.embed-panel__empty--full {
  min-height: 760px;
}

.embed-panel__empty-icon {
  width: 88px;
  height: 88px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(21, 101, 192, 0.12), rgba(21, 101, 192, 0.04));
  color: var(--accent-blue);
  font-size: 42px;
}

@media (max-width: 1100px) {
  .embed-panel__header {
    flex-direction: column;
  }

  .embed-panel__actions {
    justify-content: flex-start;
    min-width: 0;
  }
}
</style>
