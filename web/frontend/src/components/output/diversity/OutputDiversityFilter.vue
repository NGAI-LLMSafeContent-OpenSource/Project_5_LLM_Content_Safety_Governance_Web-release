<template>
  <div class="diversity-filter">
    <h2 class="track-page__title">治理标准体系（多样性）</h2>
    <div class="filter-card">
      <div class="filter-card-title">多样性维度 · 输出内容治理标准体系</div>
      <p class="filter-card-desc">
        本页展示输出内容治理默认引用的多样性治理维度。后续评估、归因和修正将基于完整体系自动展开，无需在此步骤手动筛选。
      </p>

      <template v-for="group in standardGroups" :key="group.key">
        <div class="dim-section-label" :class="group.className">
          <span :class="group.labelClass">{{ group.icon }} {{ group.title }}</span>
          {{ group.suffix }}
        </div>
        <div class="dim-grid">
          <div v-for="standard in group.standards" :key="standard.key" class="cat-wrap">
            <div
              class="dim-checkbox dim-checkbox--readonly"
              :class="{ selected: standard.selected }"
              @click="toggleDetail(standard.key)"
            >
              <span class="dim-status-dot" :class="{ on: standard.selected }" aria-hidden="true" />
              <span class="dim-code">{{ standard.code }}</span>
              <span class="dim-label">{{ standard.label }}</span>
              <span class="dim-default-badge">{{ standard.badge }}</span>
              <span class="dim-expand">
                {{ expandedKey === standard.key ? '▼' : '▶' }}
              </span>
            </div>

            <div class="cat-detail-panel" :class="{ open: expandedKey === standard.key }">
              <div class="cat-detail-row">
                <div class="cat-detail-def">
                  <div class="cat-detail-label">标准定义</div>
                  <div class="cat-detail-value">{{ standard.definition }}</div>
                </div>
              </div>
              <div class="cat-detail-label">判定要点（{{ standard.criteria.length }} 个）</div>
              <div class="sub-tags">
                <span v-for="criterion in standard.criteria" :key="criterion.id" class="sub-tag">
                  {{ criterion.name }}
                </span>
              </div>
              <div class="cat-detail-label">评分定义</div>
              <div class="level-defs">
                <div v-for="lv in levelList" :key="lv.key" class="level-def">
                  <div class="lv">{{ lv.label }}</div>
                  {{ standard.levels[lv.key] || '—' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <DiversityRuleBuilder />

      <div class="standard-summary">
        <span>体系维度</span>
        <strong>{{ cultureStandards.length }}</strong>
        <span>项，作为输出内容治理多样性评估的默认依据。</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DiversityRuleBuilder from './DiversityRuleBuilder.vue'
import { diversityStandards } from './diversityStandards'

const cultureStandards = diversityStandards

const standardGroups = [
  {
    key: 'ethnic',
    icon: '🧭',
    title: '民族识别',
    suffix: '相关指标',
    labelClass: 'label-green',
    className: '',
    standards: cultureStandards.filter((standard) => standard.group === 'ethnic'),
  },
  {
    key: 'cultural',
    icon: '🌍',
    title: '文化差异度',
    suffix: '相关指标',
    labelClass: 'label-blue',
    className: 'dim-section-label--culture',
    standards: cultureStandards.filter((standard) => standard.group === 'cultural'),
  },
]

const levelList = [
  { key: 'excellent', label: '优秀' },
  { key: 'good', label: '达标' },
  { key: 'weak', label: '不足' },
]

const expandedKey = ref<string | null>(null)

function toggleDetail(key: string) {
  expandedKey.value = expandedKey.value === key ? null : key
}
</script>

<style src="./OutputDiversityFilter.css" scoped></style>
