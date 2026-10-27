<template>
  <div
    class="input-section"
    :class="isValueMode ? 'value-screening-panel' : 'risk-screening-panel'"
  >
    <h3>{{ isValueMode ? '价值治理标准体系' : '风险治理标准体系' }}</h3>

    <DataInputServiceStatusCard
      v-if="isValueMode && topic1Status"
      title="课题一 value_qa 治理维度资产"
      :status="topic1Status"
      :badges="topic1Badges"
      connected-label="已接入"
      disconnected-label="等待资产"
      tone="blue"
    />

    <DataInputServiceStatusCard
      v-else-if="!isValueMode && riskScreeningStatus"
      title="课题二 L1 风险治理维度"
      :status="riskScreeningStatus"
      :badges="riskScreeningBadges"
      connected-label="已对齐"
      disconnected-label="等待语料"
      tone="blue"
    />

    <div class="hint">
      {{
        isValueMode
          ? '本页展示输入数据治理默认引用的价值治理标准体系。后续评估、归因和修正将基于完整体系自动展开，无需在此步骤手动筛选。点击 ▶ 可查看轻量详情。'
          : '本页展示输入数据治理默认引用的风险治理标准体系。L1/L2 维度作为后续评估、归因和修正的默认依据，无需在此步骤手动筛选。点击 ▶ 可查看轻量详情。'
      }}
    </div>

    <div :class="isValueMode ? 'value-group-head' : 'value-group-head risk-group-head'">
      {{ isValueMode ? '价值一级维度' : '课题二 L1 风险维度' }}
    </div>
    <div class="strategy-grid checklist-grid value-checklist-grid screening-detail-grid">
      <div
        v-for="s in primaryStandards"
        :key="s.id"
        class="screening-item-wrap"
        :class="{ selected: s.enabled, open: expandedId === s.id }"
      >
        <div
          class="check-item value-check-item screening-item-row"
          :class="{ selected: s.enabled }"
        >
          <div class="screening-check-main">
            <span class="screening-status-dot" :class="{ on: s.enabled }" aria-hidden="true" />
            <span class="check-label">
              {{ s.name }}
              <small v-if="s.tag" class="check-tag">{{ s.tag }}</small>
            </span>
            <span class="screening-default-badge">{{ s.enabled ? '默认纳入' : '体系维度' }}</span>
          </div>
          <button
            type="button"
            class="screening-expand-btn"
            :aria-expanded="expandedId === s.id"
            :title="expandedId === s.id ? '收起详情' : '展开详情'"
            @click="toggleExpand(s.id)"
          >
            {{ expandedId === s.id ? '▼' : '▶' }}
          </button>
        </div>
        <div class="screening-detail-panel" :class="{ open: expandedId === s.id }">
          <div class="screening-detail-grid-inner">
            <div>
              <div class="screening-detail-label">类型</div>
              <div class="screening-detail-value">{{ s.detailKind || '治理维度' }}</div>
            </div>
            <div>
              <div class="screening-detail-label">覆盖</div>
              <div class="screening-detail-value">{{ s.coverageText || s.desc || '—' }}</div>
            </div>
            <div>
              <div class="screening-detail-label">来源</div>
              <div class="screening-detail-value">{{ s.sourceText || s.tag || '—' }}</div>
            </div>
            <div class="screening-detail-span">
              <div class="screening-detail-label">在本流程中的作用</div>
              <div class="screening-detail-value">{{ s.roleText || s.desc || '—' }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="value-group-head value-group-head--spaced">
      {{ isValueMode ? '价值二级维度（评测维度）' : '本批 L2 细类（挂在 L1 体系下）' }}
    </div>
    <template v-if="scienceStandards.length">
      <template v-if="!isValueMode && riskL2Groups.length">
        <div v-for="group in riskL2Groups" :key="group.key" class="l2-group-block">
          <div class="l2-group-head" :class="{ 'is-off': group.parentOff }">
            {{ group.label }}
            <small>
              {{ group.parentOff ? '所属 L1 暂未覆盖' : `${group.items.length} 个细类` }}
            </small>
          </div>
          <div class="strategy-grid checklist-grid science-checklist-grid screening-detail-grid">
            <div
              v-for="s in group.items"
              :key="s.id"
              class="screening-item-wrap"
              :class="{
                selected: s.enabled,
                open: expandedId === s.id,
                disabled: s.disabled,
              }"
            >
              <div
                class="check-item science-check-item screening-item-row"
                :class="{ selected: s.enabled, disabled: s.disabled }"
              >
                <div class="screening-check-main" :class="{ 'is-disabled': s.disabled }">
                  <span
                    class="screening-status-dot"
                    :class="{ on: s.enabled }"
                    aria-hidden="true"
                  />
                  <span class="check-label">
                    {{ s.name }}
                    <small v-if="s.tag" class="check-tag">{{ s.tag }}</small>
                  </span>
                  <span class="screening-default-badge">
                    {{ s.disabled ? '随 L1 归属展示' : s.enabled ? '默认纳入' : '体系维度' }}
                  </span>
                </div>
                <button
                  type="button"
                  class="screening-expand-btn"
                  :aria-expanded="expandedId === s.id"
                  :title="expandedId === s.id ? '收起详情' : '展开详情'"
                  @click="toggleExpand(s.id)"
                >
                  {{ expandedId === s.id ? '▼' : '▶' }}
                </button>
              </div>
              <div class="screening-detail-panel" :class="{ open: expandedId === s.id }">
                <div class="screening-detail-grid-inner">
                  <div>
                    <div class="screening-detail-label">类型</div>
                    <div class="screening-detail-value">{{ s.detailKind || '治理维度' }}</div>
                  </div>
                  <div>
                    <div class="screening-detail-label">覆盖</div>
                    <div class="screening-detail-value">{{ s.coverageText || s.desc || '—' }}</div>
                  </div>
                  <div>
                    <div class="screening-detail-label">来源</div>
                    <div class="screening-detail-value">{{ s.sourceText || s.tag || '—' }}</div>
                  </div>
                  <div class="screening-detail-span">
                    <div class="screening-detail-label">在本流程中的作用</div>
                    <div class="screening-detail-value">{{ s.roleText || s.desc || '—' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="strategy-grid checklist-grid science-checklist-grid screening-detail-grid">
        <div
          v-for="s in scienceStandards"
          :key="s.id"
          class="screening-item-wrap"
          :class="{ selected: s.enabled, open: expandedId === s.id }"
        >
          <div
            class="check-item science-check-item screening-item-row"
            :class="{ selected: s.enabled }"
          >
            <div class="screening-check-main">
              <span class="screening-status-dot" :class="{ on: s.enabled }" aria-hidden="true" />
              <span class="check-label">
                {{ s.name }}
                <small v-if="s.tag" class="check-tag">{{ s.tag }}</small>
              </span>
              <span class="screening-default-badge">{{ s.enabled ? '默认纳入' : '体系维度' }}</span>
            </div>
            <button
              type="button"
              class="screening-expand-btn"
              :aria-expanded="expandedId === s.id"
              :title="expandedId === s.id ? '收起详情' : '展开详情'"
              @click="toggleExpand(s.id)"
            >
              {{ expandedId === s.id ? '▼' : '▶' }}
            </button>
          </div>
          <div class="screening-detail-panel" :class="{ open: expandedId === s.id }">
            <div class="screening-detail-grid-inner">
              <div>
                <div class="screening-detail-label">类型</div>
                <div class="screening-detail-value">{{ s.detailKind || '治理维度' }}</div>
              </div>
              <div>
                <div class="screening-detail-label">覆盖</div>
                <div class="screening-detail-value">{{ s.coverageText || s.desc || '—' }}</div>
              </div>
              <div>
                <div class="screening-detail-label">来源</div>
                <div class="screening-detail-value">{{ s.sourceText || s.tag || '—' }}</div>
              </div>
              <div class="screening-detail-span">
                <div class="screening-detail-label">在本流程中的作用</div>
                <div class="screening-detail-value">{{ s.roleText || s.desc || '—' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <div v-else-if="!isValueMode" class="corpus-empty-lite">
      当前风险语料暂无 L2 标签，或尚未绑定风险侧语料。
    </div>
    <div v-else class="corpus-empty-lite">当前 value_qa 资产暂无二级评测维度。</div>

    <div class="threshold-box" :class="isValueMode ? 'value-threshold-box' : 'risk-threshold-box'">
      <div class="threshold-title">
        {{ isValueMode ? '价值达成度分档阈值' : '风险等级阈值' }}
      </div>
      <div class="threshold-subhint">
        {{
          isValueMode
            ? '将价值评估结果映射到优 / 良 / 待提升三档。'
            : '将风险评估结果映射到高 / 中 / 低风险三档。'
        }}
      </div>

      <template v-if="isValueMode">
        <div class="slider-row">
          <div class="slider-label">评分“优”区间下限</div>
          <div class="slider-control">
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              :value="valueThresholdExcellent"
              @input="emitValueThresholdExcellent"
            />
          </div>
          <div class="slider-val">≥ {{ valueThresholdExcellent }}</div>
        </div>
        <div class="slider-row">
          <div class="slider-label">评分“良”区间下限</div>
          <div class="slider-control">
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              :value="valueThresholdGood"
              @input="emitValueThresholdGood"
            />
          </div>
          <div class="slider-val warn">≥ {{ valueThresholdGood }}</div>
        </div>
        <p class="hint hint--spaced">低于“良”下限计为“待提升”，建议保持“良” &lt; “优”。</p>
      </template>
      <template v-else>
        <div class="slider-row">
          <div class="slider-label">评分“高风险”阈值</div>
          <div class="slider-control">
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              :value="riskThresholdHigh"
              @input="emitRiskThresholdHigh"
            />
          </div>
          <div class="slider-val danger">≥ {{ riskThresholdHigh }}</div>
        </div>
        <div class="slider-row">
          <div class="slider-label">评分“中风险”阈值</div>
          <div class="slider-control">
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              :value="riskThresholdMid"
              @input="emitRiskThresholdMid"
            />
          </div>
          <div class="slider-val warn">≥ {{ riskThresholdMid }}</div>
        </div>
        <div class="slider-row">
          <div class="slider-label">评分“低风险”阈值</div>
          <div class="slider-control">
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              :value="riskThresholdLow"
              @input="emitRiskThresholdLow"
            />
          </div>
          <div class="slider-val ok">≥ {{ riskThresholdLow }}</div>
        </div>
      </template>
    </div>

    <div class="custom-rule-box" :class="isValueMode ? 'value-rule-box' : 'risk-rule-box'">
      <div class="threshold-title">
        {{ isValueMode ? '补充价值治理规则（可选）' : '补充风险治理规则（可选）' }}
      </div>
      <div v-for="(r, idx) in customRules" :key="r" class="custom-rule-item">
        <span>{{ r }}</span>
        <button type="button" class="rule-del" @click="$emit('remove-rule', idx)">删除</button>
      </div>
      <div class="rule-add-row">
        <input
          :value="newRule"
          type="text"
          placeholder="输入补充规则后点击添加"
          @input="emitNewRuleDraft"
          @keydown.enter.prevent="$emit('add-rule', newRule)"
        />
        <button class="btn btn-secondary btn-sm" type="button" @click="$emit('add-rule', newRule)">
          添加规则
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import DataInputServiceStatusCard from '@/components/data-input/DataInputServiceStatusCard.vue'
import type { ScreeningStandardViewModel } from '@/utils/dataInputConfig'
import type { AttributionModuleStatus } from '@/stores/input'

const props = defineProps<{
  isValueMode: boolean
  primaryStandards: ScreeningStandardViewModel[]
  scienceStandards: ScreeningStandardViewModel[]
  customRules: string[]
  newRule: string
  valueThresholdExcellent?: string
  valueThresholdGood?: string
  riskThresholdHigh?: string
  riskThresholdMid?: string
  riskThresholdLow?: string
  topic1Status?: AttributionModuleStatus
  riskScreeningStatus?: AttributionModuleStatus
}>()

const emit = defineEmits<{
  'toggle-standard': [id: string]
  'toggle-science-standard': [id: string]
  'add-rule': [value: string]
  'remove-rule': [index: number]
  'update:new-rule': [value: string]
  'update:value-threshold-excellent': [value: string]
  'update:value-threshold-good': [value: string]
  'update:risk-threshold-high': [value: string]
  'update:risk-threshold-mid': [value: string]
  'update:risk-threshold-low': [value: string]
}>()

const expandedId = ref('')

const riskL2Groups = computed(() => {
  if (props.isValueMode) return []
  const map = new Map<
    string,
    { key: string; label: string; parentOff: boolean; items: ScreeningStandardViewModel[] }
  >()
  props.scienceStandards.forEach((item) => {
    const key = item.l1Code || 'other'
    const existing = map.get(key)
    if (existing) {
      existing.items.push(item)
      existing.parentOff = existing.parentOff && Boolean(item.disabled)
      return
    }
    map.set(key, {
      key,
      label: item.groupLabel || item.l1Code || '未标注 L1',
      parentOff: Boolean(item.disabled),
      items: [item],
    })
  })
  return Array.from(map.values()).sort((a, b) => a.key.localeCompare(b.key))
})

const topic1Badges = computed(() => {
  if (!props.topic1Status) return []
  const badges: string[] = []
  if (props.topic1Status.assetId) badges.push(props.topic1Status.assetId)
  if (props.topic1Status.total > 0) badges.push(`${props.topic1Status.total} 条`)
  return badges
})

const riskScreeningBadges = computed(() => {
  if (!props.riskScreeningStatus) return ['L1 taxonomy']
  const badges = ['L1 taxonomy']
  if (props.riskScreeningStatus.assetId) badges.push(props.riskScreeningStatus.assetId)
  if (props.riskScreeningStatus.total > 0) badges.push(`${props.riskScreeningStatus.total} 条`)
  return badges
})

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? '' : id
}

function getInputValue(event: Event) {
  return (event.target as HTMLInputElement).value
}

function emitNewRuleDraft(event: Event) {
  emit('update:new-rule', getInputValue(event))
}

function emitValueThresholdExcellent(event: Event) {
  emit('update:value-threshold-excellent', getInputValue(event))
}

function emitValueThresholdGood(event: Event) {
  emit('update:value-threshold-good', getInputValue(event))
}

function emitRiskThresholdHigh(event: Event) {
  emit('update:risk-threshold-high', getInputValue(event))
}

function emitRiskThresholdMid(event: Event) {
  emit('update:risk-threshold-mid', getInputValue(event))
}

function emitRiskThresholdLow(event: Event) {
  emit('update:risk-threshold-low', getInputValue(event))
}
</script>

<style scoped>
.screening-detail-grid {
  align-items: start;
}

.screening-item-wrap {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}

.screening-item-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
}

.screening-check-main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
  min-width: 0;
  cursor: default;
}

:global(#page-data-input .screening-item-row) {
  cursor: default;
}

.screening-status-dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 999px;
  background: #9fb2cc;
  flex: 0 0 auto;
}

.screening-status-dot.on {
  background: #1565c0;
  box-shadow: 0 0 0 4px rgba(21, 101, 192, 0.12);
}

.screening-default-badge {
  flex: 0 0 auto;
  align-self: flex-start;
  margin-left: auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef6ff;
  color: #155fa0;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.screening-expand-btn {
  flex-shrink: 0;
  margin-top: 2px;
  border: none;
  background: transparent;
  color: #5b7a9a;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 4px 6px;
  border-radius: 6px;
}

.screening-expand-btn:hover {
  background: rgba(21, 101, 192, 0.08);
  color: #1565c0;
}

.screening-detail-panel {
  display: none;
  margin: 0 2px 2px;
  padding: 10px 12px;
  border: 1px solid #d7e3f0;
  border-top: none;
  border-radius: 0 0 10px 10px;
  background: #f7fafc;
}

.screening-detail-panel.open {
  display: block;
}

.screening-item-wrap.open .screening-item-row {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

.screening-detail-grid-inner {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 12px;
}

.screening-detail-span {
  grid-column: 1 / -1;
}

.screening-detail-label {
  font-size: 11px;
  color: #6b86a5;
  margin-bottom: 2px;
  font-weight: 600;
}

.screening-detail-value {
  font-size: 12px;
  color: #334e68;
  line-height: 1.45;
  word-break: break-word;
}

.screening-item-wrap.disabled {
  opacity: 0.55;
}

.screening-check-main.is-disabled {
  cursor: default;
}

.check-item.disabled {
  background: #f4f7fa;
}

.l2-group-block {
  margin-bottom: 12px;
}

.l2-group-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #334e68;
}

.l2-group-head small {
  font-weight: 500;
  color: #6b86a5;
}

.l2-group-head.is-off {
  color: #8a9bb0;
}

.corpus-empty-lite {
  margin: 0 0 12px;
  padding: 12px 14px;
  border: 1px dashed #cbd8e7;
  border-radius: 10px;
  color: #6b86a5;
  font-size: 13px;
}

@media (max-width: 720px) {
  .screening-detail-grid-inner {
    grid-template-columns: 1fr;
  }
}
</style>
