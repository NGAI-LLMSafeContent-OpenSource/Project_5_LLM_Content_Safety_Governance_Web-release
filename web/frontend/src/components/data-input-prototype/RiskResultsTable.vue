<template>
  <section class="dip-risk-results" aria-labelledby="dip-risk-result-title">
    <header class="dip-risk-results__summary">
      <div>
        <span>检测演示结果 · 仅当前会话</span>
        <h2 id="dip-risk-result-title">{{ rows.length }} 条样本完成二次校验</h2>
      </div>
      <dl>
        <div>
          <dt>一致</dt>
          <dd>{{ counts.match }}</dd>
        </div>
        <div>
          <dt>不一致</dt>
          <dd>{{ counts.mismatch }}</dd>
        </div>
        <div>
          <dt>失败</dt>
          <dd>{{ counts.failed }}</dd>
        </div>
      </dl>
    </header>

    <div class="dip-result-filters" aria-label="检测结果筛选">
      <button
        v-for="option in filterOptions"
        :key="option.value"
        type="button"
        :class="{ 'is-active': filter === option.value }"
        :aria-pressed="filter === option.value"
        @click="filter = option.value"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="dip-table-frame">
      <table>
        <thead>
          <tr>
            <th scope="col">样本摘要</th>
            <th scope="col">参考标注</th>
            <th scope="col">本次检测</th>
            <th scope="col">对比结果</th>
            <th scope="col"><span class="sr-only">查看详情</span></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in filteredRows" :key="row.id">
            <tr>
              <td>
                <strong>{{ row.text }}</strong>
                <small>{{ row.source }} · {{ row.id }}</small>
              </td>
              <td>
                <span class="dip-label" :class="`is-${row.referenceLabel}`">
                  {{ riskLabelLabels[row.referenceLabel] }}
                </span>
                <small>{{ row.l1 }}</small>
              </td>
              <td>
                <span v-if="row.detectedLabel" class="dip-label" :class="`is-${row.detectedLabel}`">
                  {{ riskLabelLabels[row.detectedLabel] }}
                </span>
                <span v-else class="dip-label is-failed">未返回</span>
                <small>{{ row.detectedCategory }}</small>
              </td>
              <td>
                <span class="dip-comparison" :class="`is-${row.detectionState}`">
                  {{ detectionStateLabels[row.detectionState] }}
                </span>
              </td>
              <td>
                <button
                  type="button"
                  class="dip-icon-button"
                  :title="expandedId === row.id ? '收起来源信息' : '查看来源信息'"
                  :aria-label="expandedId === row.id ? '收起来源信息' : '查看来源信息'"
                  :aria-expanded="expandedId === row.id"
                  @click="expandedId = expandedId === row.id ? '' : row.id"
                >
                  <ArrowDown :class="{ 'is-open': expandedId === row.id }" />
                </button>
              </td>
            </tr>
            <tr v-if="expandedId === row.id" class="dip-result-detail-row">
              <td colspan="5">
                <dl>
                  <div>
                    <dt>来源 Benchmark</dt>
                    <dd>{{ row.source }}</dd>
                  </div>
                  <div>
                    <dt>风险分类</dt>
                    <dd>{{ row.l1 }} / {{ row.l2 }}</dd>
                  </div>
                  <div>
                    <dt>攻击方式</dt>
                    <dd>{{ row.attackVector }}</dd>
                  </div>
                  <div>
                    <dt>资产标记</dt>
                    <dd>{{ assetFlags(row) }}</dd>
                  </div>
                </dl>
              </td>
            </tr>
          </template>
          <tr v-if="filteredRows.length === 0">
            <td colspan="5" class="dip-empty">当前筛选下没有检测结果。</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import type { DetectionState, RiskDetectionRow } from './prototypeData'
import { detectionStateLabels, riskLabelLabels } from './prototypeData'

const props = defineProps<{ rows: RiskDetectionRow[]; initialFilter?: DetectionState | 'all' }>()
const filter = ref<DetectionState | 'all'>(props.initialFilter ?? 'all')
const expandedId = ref('')
const filterOptions: Array<{ value: DetectionState | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'match', label: '一致' },
  { value: 'mismatch', label: '不一致' },
  { value: 'failed', label: '检测失败' },
]

const counts = computed(() => ({
  match: props.rows.filter((row) => row.detectionState === 'match').length,
  mismatch: props.rows.filter((row) => row.detectionState === 'mismatch').length,
  failed: props.rows.filter((row) => row.detectionState === 'failed').length,
}))
const filteredRows = computed(() =>
  filter.value === 'all'
    ? props.rows
    : props.rows.filter((row) => row.detectionState === filter.value),
)

function assetFlags(row: RiskDetectionRow) {
  const flags = [row.polluted ? '污染样本' : '', row.poisoned ? '投毒样本' : ''].filter(Boolean)
  return flags.length ? flags.join('、') : '无污染或投毒标记'
}
</script>
