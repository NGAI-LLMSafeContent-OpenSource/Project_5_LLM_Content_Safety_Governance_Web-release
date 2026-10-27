<template>
  <section class="governance-skill-entry" aria-label="治理技能与边界">
    <h2 class="governance-skill-entry__title">治理技能</h2>
    <p class="governance-skill-entry__hint">当前业务域技能优先；选择后填入输入框，不会直接执行。</p>

    <p v-if="loading && !skills.length" class="governance-skill-entry__status" role="status">
      正在载入技能目录…
    </p>
    <p v-else-if="!skills.length" class="governance-skill-entry__empty">暂无可用的治理技能。</p>
    <ul v-else class="governance-skill-entry__list">
      <li
        v-for="entry in orderedSkills"
        :key="`${entry.skill_key}@${entry.version}`"
        class="governance-skill-entry__item"
      >
        <button
          type="button"
          class="governance-skill-entry__button"
          :disabled="disabled"
          @click="$emit('select', entry)"
        >
          <span class="governance-skill-entry__head">
            <span class="governance-skill-entry__name">{{ entry.name || entry.skill_key }}</span>
            <span
              class="governance-skill-entry__domain"
              :class="{ 'is-active': entry.domain === activeDomain }"
            >
              {{ domainLabel(entry.domain) }}
            </span>
          </span>
          <span v-if="entry.description" class="governance-skill-entry__description">
            {{ entry.description }}
          </span>
          <span class="governance-skill-entry__facts">
            <span v-if="entry.boundary.branches.length" class="governance-skill-entry__fact">
              分支：{{ entry.boundary.branches.join('、') }}
            </span>
            <span class="governance-skill-entry__fact">
              执行器：{{ entry.boundary.executor_capability || '—' }}
            </span>
            <span class="governance-skill-entry__fact">
              成本：{{ entry.boundary.cost_units_per_sample }} 单位/样本
            </span>
            <span class="governance-skill-entry__fact">
              耗时：约 {{ entry.boundary.estimated_seconds_per_sample }} 秒/样本
            </span>
          </span>
          <span v-if="entry.boundary.steps.length" class="governance-skill-entry__steps">
            <span
              v-for="step in entry.boundary.steps"
              :key="step.step_id"
              class="governance-skill-entry__step"
              :class="stepClass(step)"
            >
              {{ step.capability }} · {{ stepTag(step) }}
            </span>
          </span>
          <span class="governance-skill-entry__meta">
            v{{ entry.version }} · 执行确认{{ entry.boundary.confirmation_required ? '必需' : '可选' }}
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type {
  GovernanceDomainKey,
  GovernanceSkillBoundaryStep,
  GovernanceSkillCatalogResult,
  GovernanceSkillEntry,
} from '@/types'
import { getGovernanceDomain } from '@/utils/governance-domains'

const props = defineProps<{
  catalog: GovernanceSkillCatalogResult | null
  activeDomain: GovernanceDomainKey
  loading: boolean
  disabled: boolean
}>()

defineEmits<{
  (event: 'select', entry: GovernanceSkillEntry): void
}>()

const skills = computed(() => props.catalog?.skills ?? [])

// 当前业务域技能排前，其它域保留目录顺序（Array.prototype.sort 稳定）。
const orderedSkills = computed(() =>
  [...skills.value].sort(
    (a, b) =>
      Number(b.domain === props.activeDomain) - Number(a.domain === props.activeDomain),
  ),
)

function domainLabel(domain: string) {
  const resolved = getGovernanceDomain(domain)
  return resolved.key === domain ? resolved.label : domain
}

function stepTag(step: GovernanceSkillBoundaryStep) {
  if (step.requires_confirmation) return '需确认执行'
  if (step.automatic) return '自动只读'
  return '步骤'
}

function stepClass(step: GovernanceSkillBoundaryStep) {
  if (step.requires_confirmation) return 'is-confirm'
  if (step.automatic) return 'is-auto'
  return ''
}
</script>
