<template>
  <div v-if="payload" class="governance-skill-plan" aria-label="治理技能执行计划">
    <div class="governance-skill-plan__head">
      <span class="governance-skill-plan__title">{{ payload.title || payload.skill_key }}</span>
      <span
        class="governance-skill-plan__badge"
        :class="payload.confirmation_required ? 'is-confirm' : 'is-auto'"
      >
        {{ payload.confirmation_required ? '需确认执行' : '自动只读' }}
      </span>
    </div>
    <p class="governance-skill-plan__meta">
      技能：{{ payload.skill_key }}@{{ payload.skill_version }} · 分支：{{ payload.branch }} ·
      状态：{{ payload.status }}
    </p>
    <p v-for="note in payload.notes" :key="note" class="governance-skill-plan__note">{{ note }}</p>

    <details class="governance-skill-plan__section" open>
      <summary>执行步骤（{{ payload.steps.length }}）</summary>
      <ol class="governance-skill-plan__steps">
        <li v-for="step in payload.steps" :key="step.step_id" class="governance-skill-plan__step">
          <span class="governance-skill-plan__step-capability">{{ step.capability }}</span>
          <span
            class="governance-skill-plan__badge"
            :class="step.requires_confirmation ? 'is-confirm' : 'is-auto'"
          >
            {{ stepTag(step) }}
          </span>
          <span class="governance-skill-plan__step-status">状态：{{ step.status }}</span>
          <span v-if="step.completion_condition" class="governance-skill-plan__step-condition">
            完成条件：{{ step.completion_condition }}
          </span>
        </li>
      </ol>
    </details>

    <details class="governance-skill-plan__section">
      <summary>冻结范围</summary>
      <dl class="governance-skill-plan__grid">
        <div class="governance-skill-plan__field">
          <dt>数据资产</dt>
          <dd>{{ payload.scope.asset_name || payload.scope.asset_id || '—' }}</dd>
        </div>
        <div class="governance-skill-plan__field">
          <dt>样本数量</dt>
          <dd>{{ payload.scope.sample_count }}</dd>
        </div>
        <div class="governance-skill-plan__field">
          <dt>范围指纹</dt>
          <dd>{{ payload.scope_fingerprint || '—' }}</dd>
        </div>
      </dl>
      <ul v-if="scopeFilterEntries.length" class="governance-skill-plan__tags">
        <li v-for="entry in scopeFilterEntries" :key="entry.key">
          {{ entry.key }}：{{ entry.value }}
        </li>
      </ul>
    </details>

    <details class="governance-skill-plan__section">
      <summary>执行器与估算</summary>
      <dl class="governance-skill-plan__grid">
        <div class="governance-skill-plan__field">
          <dt>执行器能力</dt>
          <dd>{{ payload.executor?.capability || '—' }}</dd>
        </div>
        <div class="governance-skill-plan__field">
          <dt>执行器版本</dt>
          <dd>{{ payload.executor?.capability_version || '—' }}</dd>
        </div>
        <div class="governance-skill-plan__field">
          <dt>成本估算</dt>
          <dd>{{ payload.scope.estimated_cost_units }} 单位</dd>
        </div>
        <div class="governance-skill-plan__field">
          <dt>耗时估算</dt>
          <dd>约 {{ payload.scope.estimated_seconds }} 秒</dd>
        </div>
      </dl>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { GovernanceSessionMessage, GovernanceSkillPlanPayload } from '@/types'
import { toFilterEntries } from '@/utils/governance-format'

const props = defineProps<{
  message: GovernanceSessionMessage
}>()

const payload = computed<GovernanceSkillPlanPayload | null>(() => {
  const raw = props.message.payload
  if (props.message.kind !== 'governance_skill_plan' || !raw) return null
  return raw as unknown as GovernanceSkillPlanPayload
})

function stepTag(step: GovernanceSkillPlanPayload['steps'][number]) {
  if (step.requires_confirmation) return '需确认执行'
  if (step.automatic) return '自动只读'
  return '步骤'
}

const scopeFilterEntries = computed(() => toFilterEntries(payload.value?.scope.filters))
</script>
