<template>
  <main class="gov-review" aria-label="治理任务匿名评审">
    <header class="gov-review__header">
      <p class="gov-review__eyebrow">匿名只读评审</p>
      <h1 class="gov-review__title">治理任务评审</h1>
      <p class="gov-review__lede">
        本页仅展示分享范围内的结论与证据，不含确认、取消或重试等可执行操作。
      </p>
    </header>

    <GovernanceReviewShareStates :loading="loading" :error-message="errorMessage" />

    <template v-if="!loading && !errorMessage && payload">
      <GovernanceReviewShareMeta
        :task-id="payload.task_id"
        :expires-at="payload.expires_at"
        :show-sample-text="showSampleText"
      />
      <GovernanceReviewTaskPlaceholder
        :task="payload.task"
        :show-sample-text="showSampleText"
      />
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getGovernanceShareReview } from '@/api/governance'
import GovernanceReviewShareMeta from '@/components/governance/review/GovernanceReviewShareMeta.vue'
import GovernanceReviewShareStates from '@/components/governance/review/GovernanceReviewShareStates.vue'
import GovernanceReviewTaskPlaceholder from '@/components/governance/review/GovernanceReviewTaskPlaceholder.vue'
import type { GovernanceShareReviewPayload } from '@/types'

const route = useRoute()
const loading = ref(true)
const errorMessage = ref('')
const payload = ref<GovernanceShareReviewPayload | null>(null)

const shareToken = computed(() => {
  const raw = route.params.shareToken
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : ''
})

/** Reserved for #65: mode='review' + showSampleText passed into placeholder / future projection */
const showSampleText = computed(() => Boolean(payload.value?.show_sample_text))

async function loadReview() {
  const token = shareToken.value.trim()
  loading.value = true
  errorMessage.value = ''
  payload.value = null

  if (!token) {
    loading.value = false
    errorMessage.value = '评审链接无效：缺少分享令牌。'
    return
  }

  try {
    payload.value = await getGovernanceShareReview(token)
  } catch (error) {
    const message = error instanceof Error ? error.message.trim() : ''
    errorMessage.value =
      message || '评审分享不存在或已失效。链接可能已过期、被撤销，或令牌不正确。'
  } finally {
    loading.value = false
  }
}

onMounted(loadReview)
watch(shareToken, loadReview)
</script>

<style scoped>
.gov-review {
  --gov-review-bg: #f3f6f4;
  --gov-review-ink: #1c2b24;
  --gov-review-muted: #5d6f66;
  --gov-review-accent: #1f6b4a;
  min-height: 100vh;
  box-sizing: border-box;
  padding: 2.5rem clamp(1.25rem, 4vw, 3.5rem) 3.5rem;
  color: var(--gov-review-ink);
  background:
    radial-gradient(circle at 12% 0%, rgba(31, 107, 74, 0.12), transparent 42%),
    linear-gradient(180deg, #eef5f1 0%, var(--gov-review-bg) 48%, #f7faf8 100%);
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.gov-review__header {
  max-width: 56rem;
  margin-bottom: 1.75rem;
}

.gov-review__eyebrow {
  margin: 0 0 0.35rem;
  color: var(--gov-review-accent);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.gov-review__title {
  margin: 0;
  font-size: clamp(1.75rem, 3vw, 2.25rem);
  line-height: 1.2;
}

.gov-review__lede {
  margin: 0.65rem 0 0;
  max-width: 40rem;
  color: var(--gov-review-muted);
  line-height: 1.55;
}

@media (max-width: 640px) {
  .gov-review {
    padding: 1.5rem 1rem 2.5rem;
  }
}
</style>
