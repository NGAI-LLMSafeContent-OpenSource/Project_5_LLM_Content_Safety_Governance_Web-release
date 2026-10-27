<template>
  <div class="service-status-card" :class="`service-status-card--${tone}`">
    <div class="service-status-card__content">
      <strong>{{ title }}</strong>
      <div class="service-status-card__badges">
        <span
          class="service-status-card__pill"
          :class="status.connected ? 'is-connected' : 'is-waiting'"
        >
          {{ status.connected ? connectedLabel : disconnectedLabel }}
        </span>
        <span v-for="badge in badges" :key="badge" class="service-status-card__badge">
          {{ badge }}
        </span>
      </div>
      <span v-if="status.message" class="service-status-card__message">{{ status.message }}</span>
      <span v-if="showTechnicalDetails && status.baseUrl" class="service-status-card__url">
        {{ status.baseUrl }}
      </span>
      <span
        v-if="showTechnicalDetails && status.blockingReason"
        class="service-status-card__blocking"
      >
        {{ status.blockingReason }}
      </span>
      <span v-if="status.nextAction" class="service-status-card__next">
        {{ status.nextAction }}
      </span>
      <div
        v-if="typeof status.progress === 'number' && status.progress > 0"
        class="service-progress"
      >
        <div class="service-progress__bar" :style="{ width: `${status.progress}%` }"></div>
      </div>
    </div>
    <div v-if="actionLabel" class="service-status-card__actions">
      <button
        class="btn"
        :class="buttonClass"
        type="button"
        :disabled="status.loading"
        @click="$emit('action')"
      >
        {{ status.loading ? loadingLabel : actionLabel }}
      </button>
      <button
        v-if="secondaryActionLabel"
        class="btn btn-secondary btn-sm"
        type="button"
        :disabled="!secondaryActionEnabled"
        @click="$emit('secondary-action')"
      >
        {{ secondaryActionLabel }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
interface ExternalServiceStatusView {
  connected: boolean
  loading: boolean
  baseUrl: string
  message: string
  blockingReason: string
  nextAction: string
  progress?: number
}

withDefaults(
  defineProps<{
    title: string
    status: ExternalServiceStatusView
    badges?: string[]
    actionLabel?: string
    loadingLabel?: string
    connectedLabel?: string
    disconnectedLabel?: string
    tone?: 'blue' | 'red'
    buttonClass?: string
    showTechnicalDetails?: boolean
    secondaryActionLabel?: string
    secondaryActionEnabled?: boolean
  }>(),
  {
    badges: () => [],
    actionLabel: '',
    loadingLabel: '加载中...',
    connectedLabel: '已连接真实服务',
    disconnectedLabel: '等待服务',
    tone: 'blue',
    buttonClass: 'btn-secondary btn-sm',
    showTechnicalDetails: false,
    secondaryActionLabel: '',
    secondaryActionEnabled: false,
  },
)

defineEmits<{
  (e: 'action'): void
  (e: 'secondary-action'): void
}>()
</script>

<style scoped>
.service-status-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
  border-radius: 10px;
  padding: 12px 14px;
}

.service-status-card--blue {
  border: 1px solid rgba(21, 101, 192, 0.16);
  background: #f8fbff;
}

.service-status-card--red {
  border: 1px solid rgba(198, 40, 40, 0.14);
  background: #fffafa;
}

.service-status-card__content {
  min-width: 0;
}

.service-status-card strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
}

.service-status-card span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.service-status-card__badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 2px 0 6px;
}

.service-status-card__pill,
.service-status-card__badge {
  display: inline-flex;
  align-items: center;
  width: max-content;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
}

.service-status-card__pill.is-connected {
  background: #e8f5e9;
  color: #2e7d32;
}

.service-status-card__pill.is-waiting {
  background: #fff7e6;
  color: #b26a00;
}

.service-status-card--blue .service-status-card__badge {
  background: #eef4ff;
  color: #1565c0;
}

.service-status-card--red .service-status-card__badge {
  background: #fff0f0;
  color: #c62828;
}

.service-status-card__url {
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace;
}

.service-status-card__next {
  margin-top: 4px;
}

.service-status-card__blocking {
  margin-top: 4px;
  color: #b26a00;
}

.service-status-card .btn {
  flex: 0 0 auto;
  width: auto;
  white-space: nowrap;
}

.service-status-card__actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.service-progress {
  overflow: hidden;
  width: min(360px, 100%);
  height: 6px;
  margin-top: 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.service-progress__bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #1565c0, #2e7d32);
  transition: width 0.24s ease;
}

@media (max-width: 860px) {
  .service-status-card {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
