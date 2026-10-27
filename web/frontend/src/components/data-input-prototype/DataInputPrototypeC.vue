<template>
  <section class="dip-variant dip-workbench" aria-labelledby="dip-c-title">
    <header class="dip-page-head dip-page-head--workbench">
      <div>
        <p class="dip-eyebrow">数据工作台</p>
        <h1 id="dip-c-title">直接检视现有输入语料</h1>
        <p>人工筛选、打开样本并核对已有信息。</p>
      </div>
      <div class="dip-source-tabs" aria-label="语料类型">
        <button
          type="button"
          :aria-pressed="track === 'value'"
          :class="{ 'is-active': track === 'value' }"
          @click="track = 'value'"
        >
          价值语料
          <small>74 组 / 222 条回答</small>
        </button>
        <button
          type="button"
          :aria-pressed="track === 'risk'"
          :class="{ 'is-active': track === 'risk' }"
          @click="track = 'risk'"
        >
          风险语料
          <small>400 条样本</small>
        </button>
      </div>
    </header>

    <template v-if="track === 'value'">
      <div class="dip-workbench__toolbar">
        <div class="dip-search">
          <Search aria-hidden="true" />
          <label class="sr-only" for="dip-value-search">搜索价值问题组</label>
          <input
            id="dip-value-search"
            ref="valueSearchInput"
            v-model="valueQuery"
            type="search"
            placeholder="搜索主题、问题或价值维度"
          />
          <button
            v-if="valueQuery"
            type="button"
            title="清除搜索"
            aria-label="清除搜索"
            @click="clearValueSearch"
          >
            <Close />
          </button>
        </div>
        <span>原型展示 {{ filteredValueGroups.length }} 个代表问题组，共 74 组</span>
      </div>

      <div class="dip-value-workbench">
        <aside aria-label="价值问题组列表">
          <button
            v-for="group in filteredValueGroups"
            :key="group.id"
            type="button"
            :class="{ 'is-selected': activeValueGroup?.id === group.id }"
            @click="activeValueGroupId = group.id"
          >
            <span>{{ group.topic }} · {{ group.secondaryDimension }}</span>
            <strong>{{ group.answers.high.question }}</strong>
            <small>高 / 中 / 低三档齐全</small>
          </button>
          <div v-if="filteredValueGroups.length === 0" class="dip-empty">
            没有匹配的问题组，请清除搜索后重试。
          </div>
        </aside>
        <ValueGroupDetail v-if="activeValueGroup" :group="activeValueGroup" />
      </div>
    </template>

    <template v-else>
      <div class="dip-workbench__toolbar">
        <div class="dip-search">
          <Search aria-hidden="true" />
          <label class="sr-only" for="dip-risk-search">搜索风险样本</label>
          <input
            id="dip-risk-search"
            ref="riskSearchInput"
            v-model="riskQuery"
            type="search"
            placeholder="搜索文本、来源或风险分类"
          />
          <button
            v-if="riskQuery"
            type="button"
            title="清除搜索"
            aria-label="清除搜索"
            @click="clearRiskSearch"
          >
            <Close />
          </button>
        </div>
        <div class="dip-label-filter" aria-label="参考标注筛选">
          <button
            v-for="option in riskFilterOptions"
            :key="option.value"
            type="button"
            :class="{ 'is-active': riskLabelFilter === option.value }"
            :aria-pressed="riskLabelFilter === option.value"
            @click="riskLabelFilter = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <button type="button" class="dip-primary-button" @click="requestWorkbenchDetection">
          <VideoPlay />
          {{
            selectedRiskIds.length ? `检测已选 ${selectedRiskIds.length} 条` : '检测当前前 30 条'
          }}
        </button>
      </div>

      <div v-if="showWorkbenchConfirm" class="dip-confirmation" role="status">
        <div>
          <strong>确认运行二次校验</strong>
          <p>
            将使用风险语料，检测{{ detectionScopeText }}。参考标注不会被修改，结果仅供当前会话查看。
          </p>
        </div>
        <div>
          <button type="button" class="dip-secondary-button" @click="showWorkbenchConfirm = false">
            取消
          </button>
          <button type="button" class="dip-primary-button" @click="confirmWorkbenchDetection">
            开始检测
          </button>
        </div>
      </div>

      <section class="dip-risk-browser" aria-labelledby="dip-risk-browser-title">
        <header>
          <div>
            <span>课题二 · DynBench400</span>
            <h2 id="dip-risk-browser-title">风险样本</h2>
          </div>
          <span>原型展示 {{ filteredRiskSamples.length }} 条代表样本 / 共 400 条</span>
        </header>
        <div class="dip-table-frame">
          <table>
            <thead>
              <tr>
                <th scope="col"><span class="sr-only">选择</span></th>
                <th scope="col">样本文本</th>
                <th scope="col">参考标注</th>
                <th scope="col">风险分类</th>
                <th scope="col">来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sample in filteredRiskSamples" :key="sample.id">
                <td>
                  <input
                    v-model="selectedRiskIds"
                    type="checkbox"
                    :value="sample.id"
                    :aria-label="`选择样本 ${sample.id}`"
                  />
                </td>
                <td>
                  <strong>{{ sample.text }}</strong>
                  <small>{{ sample.id }}</small>
                </td>
                <td>
                  <span class="dip-label" :class="`is-${sample.referenceLabel}`">
                    {{ riskLabelLabels[sample.referenceLabel] }}
                  </span>
                </td>
                <td>
                  {{ sample.l1 }}
                  <small>{{ sample.l2 }}</small>
                </td>
                <td>{{ sample.source }}</td>
              </tr>
              <tr v-if="filteredRiskSamples.length === 0">
                <td colspan="5" class="dip-empty">当前筛选下没有代表样本。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <RiskResultsTable v-if="workbenchDetectionRows.length" :rows="workbenchDetectionRows" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Close, Search, VideoPlay } from '@element-plus/icons-vue'
import RiskResultsTable from './RiskResultsTable.vue'
import ValueGroupDetail from './ValueGroupDetail.vue'
import type { RiskDetectionRow, RiskLabel } from './prototypeData'
import { buildDemoDetectionRows, riskLabelLabels, riskSamples, valueGroups } from './prototypeData'

type Track = 'value' | 'risk'

const track = ref<Track>('value')
const valueQuery = ref('')
const riskQuery = ref('')
const riskLabelFilter = ref<RiskLabel | 'all'>('all')
const activeValueGroupId = ref(valueGroups[0].id)
const selectedRiskIds = ref<string[]>([])
const showWorkbenchConfirm = ref(false)
const workbenchDetectionRows = ref<RiskDetectionRow[]>([])
const valueSearchInput = ref<HTMLInputElement | null>(null)
const riskSearchInput = ref<HTMLInputElement | null>(null)

const riskFilterOptions: Array<{ value: RiskLabel | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'unsafe', label: '不安全' },
  { value: 'safe', label: '安全' },
]

const filteredValueGroups = computed(() => {
  const keyword = valueQuery.value.trim().toLocaleLowerCase('zh-CN')
  if (!keyword) return valueGroups
  return valueGroups.filter((group) =>
    `${group.topic} ${group.primaryDimension} ${group.secondaryDimension} ${group.answers.high.question}`
      .toLocaleLowerCase('zh-CN')
      .includes(keyword),
  )
})
const activeValueGroup = computed(() =>
  filteredValueGroups.value.find((group) => group.id === activeValueGroupId.value),
)
const filteredRiskSamples = computed(() => {
  const keyword = riskQuery.value.trim().toLocaleLowerCase('zh-CN')
  return riskSamples.filter((sample) => {
    const matchesLabel =
      riskLabelFilter.value === 'all' || sample.referenceLabel === riskLabelFilter.value
    const matchesKeyword =
      !keyword ||
      `${sample.text} ${sample.source} ${sample.l1} ${sample.l2}`
        .toLocaleLowerCase('zh-CN')
        .includes(keyword)
    return matchesLabel && matchesKeyword
  })
})
const detectionTargets = computed(() => {
  const selected = filteredRiskSamples.value.filter((sample) =>
    selectedRiskIds.value.includes(sample.id),
  )
  return (selected.length ? selected : filteredRiskSamples.value).slice(0, 30)
})
const detectionScopeText = computed(() =>
  selectedRiskIds.value.length
    ? `已选中的 ${detectionTargets.value.length} 条样本`
    : `当前筛选结果前 ${detectionTargets.value.length} 条`,
)

function requestWorkbenchDetection() {
  showWorkbenchConfirm.value = true
}

function confirmWorkbenchDetection() {
  workbenchDetectionRows.value = buildDemoDetectionRows(detectionTargets.value)
  showWorkbenchConfirm.value = false
}

function clearValueSearch() {
  valueQuery.value = ''
  valueSearchInput.value?.focus()
}

function clearRiskSearch() {
  riskQuery.value = ''
  riskSearchInput.value?.focus()
}

watch(filteredValueGroups, (groups) => {
  if (!groups.some((group) => group.id === activeValueGroupId.value)) {
    activeValueGroupId.value = groups[0]?.id ?? ''
  }
})
</script>
