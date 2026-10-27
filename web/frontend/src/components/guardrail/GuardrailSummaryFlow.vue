<template>
  <section class="guardrail-summary" aria-labelledby="guardrail-summary-title">
    <div class="guardrail-summary__header">
      <div>
        <p class="guardrail-summary__eyebrow">{{ eyebrow }}</p>
        <h1 id="guardrail-summary-title">{{ title }}</h1>
        <p class="guardrail-summary__subtitle">{{ subtitle }}</p>
        <p v-if="governanceLogic" class="guardrail-summary__logic">{{ governanceLogic }}</p>
      </div>

      <router-link v-if="legacyLink" class="guardrail-summary__legacy-link" :to="legacyLink">
        查看完整流程
      </router-link>
    </div>

    <div class="guardrail-summary__steps">
      <article
        v-for="(step, index) in steps"
        :key="step.key"
        class="guardrail-summary__step"
        :class="{ 'guardrail-summary__step--active': step.key === activeStepKey }"
        role="button"
        tabindex="0"
        @click="emit('select', step.key)"
        @keydown.enter.prevent="emit('select', step.key)"
      >
        <div class="guardrail-summary__step-index">{{ index + 1 }}</div>
        <div>
          <h2>{{ step.title }}</h2>
          <p>{{ step.description }}</p>
        </div>
      </article>
    </div>

    <div class="guardrail-summary__dimensions" aria-label="检测维度">
      <span v-for="tag in dimensionTags" :key="tag" class="guardrail-summary__tag">
        {{ tag }}
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
interface GuardrailSummaryStep {
  key: string
  title: string
  description: string
}

defineProps<{
  eyebrow: string
  title: string
  subtitle: string
  governanceLogic?: string
  steps: GuardrailSummaryStep[]
  dimensionTags: string[]
  activeStepKey?: string
  legacyLink?: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()
</script>

<style scoped>
.guardrail-summary {
  padding: 28px;
  border: 1px solid #dbe6f3;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  box-shadow: 0 10px 28px rgba(15, 76, 129, 0.08);
}

.guardrail-summary__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.guardrail-summary__eyebrow {
  margin: 0 0 8px;
  color: #1565c0;
  font-size: 13px;
  font-weight: 700;
}

.guardrail-summary h1 {
  margin: 0;
  color: #102a43;
  font-size: 30px;
  line-height: 1.25;
}

.guardrail-summary__subtitle {
  max-width: 760px;
  margin: 10px 0 0;
  color: #486581;
  font-size: 15px;
  line-height: 1.7;
}

.guardrail-summary__logic {
  max-width: 820px;
  margin: 12px 0 0;
  padding-left: 12px;
  border-left: 3px solid #1565c0;
  color: #155fa0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.7;
}

.guardrail-summary__legacy-link {
  flex: 0 0 auto;
  padding: 8px 14px;
  border: 1px solid #b7c9dd;
  border-radius: 8px;
  color: #155fa0;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  background: #fff;
}

.guardrail-summary__legacy-link:hover {
  border-color: #1565c0;
  color: #0d47a1;
}

.guardrail-summary__steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.guardrail-summary__step {
  position: relative;
  min-height: 142px;
  padding: 18px;
  border: 1px solid #d8e4f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.guardrail-summary__step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -12px;
  width: 10px;
  height: 10px;
  border-top: 2px solid #7aa7d9;
  border-right: 2px solid #7aa7d9;
  transform: translateY(-50%) rotate(45deg);
  background: #fff;
}

.guardrail-summary__step--active {
  border-color: #1565c0;
  box-shadow: inset 0 0 0 1px rgba(21, 101, 192, 0.2);
}

.guardrail-summary__step-index {
  width: 32px;
  height: 32px;
  margin-bottom: 14px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  background: #1565c0;
}

.guardrail-summary__step h2 {
  margin: 0 0 8px;
  color: #102a43;
  font-size: 17px;
  line-height: 1.35;
}

.guardrail-summary__step p {
  margin: 0;
  color: #5b7088;
  font-size: 13px;
  line-height: 1.6;
}

.guardrail-summary__dimensions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.guardrail-summary__tag {
  padding: 6px 12px;
  border: 1px solid #c9dcf0;
  border-radius: 999px;
  color: #155fa0;
  font-size: 13px;
  font-weight: 600;
  background: #eef6ff;
}

@media (max-width: 1100px) {
  .guardrail-summary__steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .guardrail-summary__step:not(:last-child)::after {
    display: none;
  }
}

@media (max-width: 720px) {
  .guardrail-summary {
    padding: 20px;
  }

  .guardrail-summary__header {
    display: block;
  }

  .guardrail-summary__legacy-link {
    display: inline-flex;
    margin-top: 16px;
  }

  .guardrail-summary h1 {
    font-size: 24px;
  }

  .guardrail-summary__steps {
    grid-template-columns: 1fr;
  }
}
</style>
