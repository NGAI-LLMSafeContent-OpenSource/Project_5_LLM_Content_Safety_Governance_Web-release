<template>
  <aside class="governance-sidebar" aria-label="治理会话">
    <router-link class="governance-brand" to="/governance" aria-label="内容安全治理平台首页">
      <span class="governance-brand__mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M12 3.2 5.2 5.8v5.1c0 4.3 2.7 8.2 6.8 9.9 4.1-1.7 6.8-5.6 6.8-9.9V5.8L12 3.2Z" />
          <path d="M9.1 12.1 11 14l4-4" />
        </svg>
      </span>
      <span>内容安全治理</span>
    </router-link>

    <button class="governance-new-task" type="button" @click="$emit('new-task')">
      <Plus aria-hidden="true" />
      <span>新建治理任务</span>
    </button>

    <section class="governance-history" aria-labelledby="governance-history-title">
      <h2 id="governance-history-title">
        治理会话
        <span v-if="loading && sessions.length" class="governance-history__refresh" role="status">
          <span class="governance-history__spinner" aria-hidden="true"></span>
          <span class="sr-only">正在刷新会话历史…</span>
        </span>
      </h2>
      <p v-if="loading && !sessions.length" class="governance-history__status" role="status">
        正在载入会话历史…
      </p>
      <div v-else-if="!sessions.length" class="governance-history__empty">
        <Clock aria-hidden="true" />
        <p>发送第一条请求后，治理会话会显示在这里。</p>
      </div>
      <ul v-else class="governance-history__list" :aria-busy="loading">
        <li v-for="session in sessions" :key="session.session_id" class="governance-history__item">
          <button
            type="button"
            class="governance-history__open"
            :class="{ 'is-active': activeSessionId === session.session_id }"
            :aria-current="activeSessionId === session.session_id ? 'true' : undefined"
            @click="$emit('open-session', session.session_id)"
          >
            <span class="governance-history__item-title">{{ session.title }}</span>
            <span class="governance-history__item-meta">
              {{ getGovernanceDomain(session.domain).label }} · {{ formatTime(session.updated_at) }}
            </span>
          </button>
          <button
            type="button"
            class="governance-history__delete"
            :disabled="deletingSessionId === session.session_id"
            :aria-label="`删除治理会话：${session.title}`"
            @click="$emit('delete-session', session)"
          >
            <Delete aria-hidden="true" />
          </button>
        </li>
      </ul>
      <button
        v-if="sessions.length < total"
        type="button"
        class="governance-history__more"
        :disabled="loadingMore"
        @click="$emit('load-more')"
      >
        {{ loadingMore ? '正在载入…' : '加载更多会话' }}
      </button>
    </section>

    <p class="governance-sidebar__note">仅发送请求后创建会话；删除只会从历史隐藏。</p>
  </aside>
</template>

<script setup lang="ts">
import { Clock, Delete, Plus } from '@element-plus/icons-vue'
import type { GovernanceSessionSummary } from '@/types'
import { getGovernanceDomain } from '@/utils/governance-domains'

defineProps<{
  sessions: GovernanceSessionSummary[]
  total: number
  activeSessionId: string | null
  loading: boolean
  loadingMore: boolean
  deletingSessionId: string | null
}>()

defineEmits<{
  (event: 'new-task'): void
  (event: 'open-session', sessionId: string): void
  (event: 'delete-session', session: GovernanceSessionSummary): void
  (event: 'load-more'): void
}>()

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
}
</script>
