<template>
  <section v-if="loading" class="gov-review-state" role="status">
    <span class="gov-review-state__spinner" aria-hidden="true" />
    <p>正在加载评审内容…</p>
  </section>

  <section
    v-else-if="errorMessage"
    class="gov-review-state gov-review-state--error"
    role="alert"
  >
    <h2>无法打开此评审链接</h2>
    <p>{{ errorMessage }}</p>
    <p class="gov-review-state__hint">
      链接可能已过期、被撤销或不存在。请向分享方索取新的有效链接。
    </p>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  errorMessage: string
}>()
</script>

<style scoped>
.gov-review-state {
  display: grid;
  gap: 0.5rem;
  max-width: 36rem;
  padding: 1.5rem 1.25rem;
  border: 1px solid #d5e0da;
  border-radius: 8px;
  background: #ffffff;
}

.gov-review-state h2 {
  margin: 0;
  font-size: 1.15rem;
}

.gov-review-state p {
  margin: 0;
  color: #5d6f66;
  line-height: 1.5;
}

.gov-review-state--error {
  border-color: #e2b4b4;
  background: #fff8f8;
}

.gov-review-state__hint {
  font-size: 0.9rem;
}

.gov-review-state__spinner {
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid #d5e0da;
  border-top-color: #1f6b4a;
  border-radius: 50%;
  animation: gov-review-spin 0.8s linear infinite;
}

@keyframes gov-review-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
