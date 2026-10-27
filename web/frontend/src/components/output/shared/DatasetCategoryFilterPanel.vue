<template>
  <div class="cat-panel">
    <div class="col-head">
      🏷️ 数据场景分类
      <span class="col-head-sub">勾选标签筛选左侧数据集</span>
    </div>
    <div class="cat-filter-panel">
      <div class="cat-filter-group-label cat-filter-group-label--science">🔬 AI4Sci 数据场景</div>
      <div class="cat-filter-grid">
        <label
          v-for="cat in ai4sciCategories"
          :key="cat.key"
          class="cat-filter-item"
          :class="{ 'cat-filter-item--off': !cat.visible }"
        >
          <input
            type="checkbox"
            :checked="cat.visible"
            @change="store.toggleDsCategoryFilter(cat.key)"
          />
          <span class="cat-label">{{ cat.label }}</span>
          <span class="cat-count">{{ cat.count }}条</span>
        </label>
      </div>

      <div class="cat-filter-group-label cat-filter-group-label--culture">🌍 文化多样性内容</div>
      <div class="cat-filter-grid">
        <label
          v-for="cat in cultureCategories"
          :key="cat.key"
          class="cat-filter-item"
          :class="{ 'cat-filter-item--off': !cat.visible }"
        >
          <input
            type="checkbox"
            :checked="cat.visible"
            @change="store.toggleDsCategoryFilter(cat.key)"
          />
          <span class="cat-label">{{ cat.label }}</span>
          <span class="cat-count">{{ cat.count }}条</span>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useOutputStore } from '@/stores/output'

const store = useOutputStore()
const { availableDatasets, dsCategoryFilters } = storeToRefs(store)

const SUBTYPE_LABELS: Record<string, string> = {
  'benchmark-risk_classification': '风险分类',
  'benchmark-multilabel_then_severity': '多标签分级',
  'benchmark-binary_then_severity': '二分类+分级',
  'benchmark-binary': '二分类',
  'benchmark-severity': '严重性分级',
}

function subTypeLabel(key: string): string {
  if (SUBTYPE_LABELS[key]) return SUBTYPE_LABELS[key]
  return key.startsWith('benchmark-') ? key.slice('benchmark-'.length).replace(/_/g, ' ') : key
}

interface CategoryItem {
  key: string
  label: string
  count: number
  visible: boolean
}

const ai4sciCategories = computed<CategoryItem[]>(() => buildCategories('science'))
const cultureCategories = computed<CategoryItem[]>(() => buildCategories('culture'))

function buildCategories(type: string): CategoryItem[] {
  const seen = new Set<string>()
  for (const ds of availableDatasets.value) {
    if (ds.type !== type) continue
    if (!ds.subType) continue
    if (seen.has(ds.subType)) continue
    seen.add(ds.subType)
  }
  return [...seen].map((key) => ({
    key,
    label: subTypeLabel(key),
    count: availableDatasets.value.filter((ds) => ds.subType === key).length,
    visible: dsCategoryFilters.value[key] ?? true,
  }))
}
</script>

<style scoped>
.cat-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.col-head {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #334455);
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-secondary, #f0f2f5);
  border-bottom: 1px solid var(--border-color, #e0e4e8);
}

.col-head-sub {
  margin-left: auto;
  font-size: 10px;
  font-weight: 400;
  color: var(--text-muted, #8899aa);
}
.cat-filter-panel {
  flex: 1;
  padding: 10px 14px;
}
.cat-filter-group-label {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
}
.cat-filter-group-label--science {
  color: var(--accent-green, #3fb981);
}
.cat-filter-group-label--culture {
  color: var(--accent-blue, #1565c0);
}
.cat-filter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 12px;
}

.cat-filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-primary, #fff);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid transparent;
  font-size: 11px;
}

.cat-filter-item:hover {
  border-color: var(--accent-blue, #1565c0);
}
.cat-filter-item--off {
  opacity: 0.4;
}
.cat-filter-item input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent-blue, #1565c0);
  flex-shrink: 0;
}
.cat-label {
  flex: 1;
}
.cat-count {
  font-size: 10px;
  color: var(--text-muted, #8899aa);
  flex-shrink: 0;
}
</style>
