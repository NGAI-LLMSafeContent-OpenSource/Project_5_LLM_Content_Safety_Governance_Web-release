<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="86%"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @opened="loadPairs"
    @closed="handleClosed"
  >
    <div v-if="asset" class="topic2-pair-drawer">
      <section class="drawer-summary">
        <div>
          <h3>{{ asset.name }}</h3>
          <p>
            按 simple_hard_pair_id 展示配对样本；未选 Moderator 时按全体模型判断，选定 Moderator
            后按该模型判断。
          </p>
        </div>
        <dl>
          <div>
            <dt>总样本</dt>
            <dd>{{ getManifestNumber('sample_count') }}</dd>
          </div>
          <div>
            <dt>配对组</dt>
            <dd>{{ pairCount }}</dd>
          </div>
          <div>
            <dt>ASR</dt>
            <dd>{{ getManifestString('asr_definition') }}</dd>
          </div>
        </dl>
      </section>

      <section class="sample-toolbar">
        <el-select
          v-model="filters.moderator"
          clearable
          filterable
          placeholder="Moderator"
          size="small"
          @change="handleSearch"
        >
          <el-option v-for="item in moderatorOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-segmented v-model="filters.verdict" :options="verdictOptions" @change="handleSearch" />
        <el-segmented
          v-model="filters.difficulty"
          :options="difficultyOptions"
          @change="handleSearch"
        />
        <el-select
          v-model="filters.strategy"
          clearable
          filterable
          placeholder="策略"
          size="small"
          @change="handleSearch"
        >
          <el-option
            v-for="item in strategyOptions"
            :key="item.name"
            :label="`${item.name} · ${item.count}`"
            :value="item.name"
          />
        </el-select>
        <el-button size="small" type="primary" :loading="isLoading" @click="handleSearch">
          查询
        </el-button>
        <span class="filter-hint">{{ verdictHint }}</span>
      </section>

      <el-alert
        v-if="errorMessage"
        type="warning"
        :title="errorMessage"
        :closable="false"
        show-icon
      />

      <section class="sample-layout">
        <div class="sample-table-wrap">
          <el-table
            v-loading="isLoading"
            :data="pairs"
            height="520"
            size="small"
            row-key="pair_id"
            highlight-current-row
            @row-click="selectPair"
          >
            <el-table-column prop="pair_id" label="Pair" width="150" show-overflow-tooltip />
            <el-table-column prop="harm_category_l1" label="L1" width="150" show-overflow-tooltip />
            <el-table-column prop="harm_category_l2" label="L2" width="150" show-overflow-tooltip />
            <el-table-column label="simple" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.simple?.query_preview || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="hard" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.hard?.query_preview || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="hard QA" width="120">
              <template #default="{ row }">
                <el-tag :type="row.hard?.rewrite_qa?.passed ? 'success' : 'warning'" size="small">
                  {{ row.hard?.rewrite_qa?.passed ? 'passed' : 'unknown' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="sample-pagination">
            <span>共 {{ total }} 组</span>
            <el-pagination
              background
              layout="prev, pager, next, sizes"
              :page-sizes="[10, 20, 50, 100]"
              :current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              @current-change="handlePageChange"
              @size-change="handlePageSizeChange"
            />
          </div>
        </div>

        <aside class="sample-detail">
          <div v-if="!selectedPair" class="sample-detail__empty">
            <h4>配对详情</h4>
            <p>点击左侧配对组，查看 simple / hard 摘要、QA Gate 和 Moderator 判定。</p>
          </div>
          <template v-else>
            <div class="sample-detail__header">
              <div>
                <h4>{{ selectedPair.pair_id }}</h4>
                <span>{{ selectedPair.seedbank_id || selectedPair.root_seed_id || '-' }}</span>
              </div>
              <el-tag size="small">simple + hard</el-tag>
            </div>

            <dl class="detail-meta">
              <div>
                <dt>L1</dt>
                <dd>{{ selectedPair.harm_category_l1 || '-' }}</dd>
              </div>
              <div>
                <dt>L2</dt>
                <dd>{{ selectedPair.harm_category_l2 || '-' }}</dd>
              </div>
              <div>
                <dt>Source Row</dt>
                <dd>{{ selectedPair.source_row_id || '-' }}</dd>
              </div>
            </dl>

            <div class="paired-samples">
              <SampleBlock title="simple" :sample="selectedPair.simple" />
              <SampleBlock title="hard" :sample="selectedPair.hard" />
            </div>
          </template>
        </aside>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { getTopic2PrerunPairs } from '@/api/benchmark'
import type {
  BenchmarkArtifactItem,
  BenchmarkTopic2PrerunPairItem,
  BenchmarkTopic2PrerunSampleItem,
} from '@/types'

const props = defineProps<{
  modelValue: boolean
  asset: BenchmarkArtifactItem | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const pairs = ref<BenchmarkTopic2PrerunPairItem[]>([])
const selectedPair = ref<BenchmarkTopic2PrerunPairItem | null>(null)
const total = ref(0)
const pageSize = ref(20)
const currentPage = ref(1)
const isLoading = ref(false)
const errorMessage = ref('')
const apiModerators = ref<string[]>([])

const filters = reactive<{
  moderator: string
  verdict: '' | 'blocked' | 'bypassed'
  difficulty: '' | 'simple' | 'hard'
  strategy: string
}>({
  moderator: '',
  verdict: '',
  difficulty: '',
  strategy: '',
})

const verdictOptions = computed(() => {
  if (filters.moderator) {
    return [
      { label: '全部判定', value: '' },
      { label: '未拦截', value: 'bypassed' },
      { label: '已拦截', value: 'blocked' },
    ]
  }
  return [
    { label: '全部判定', value: '' },
    { label: '存在未拦截', value: 'bypassed' },
    { label: '全部拦截', value: 'blocked' },
  ]
})
const difficultyOptions = [
  { label: '全部难度', value: '' },
  { label: 'simple', value: 'simple' },
  { label: 'hard', value: 'hard' },
]

const drawerTitle = computed(() => {
  return props.asset ? `课题二配对样本 · ${props.asset.asset_id}` : '课题二配对样本'
})
const pairCount = computed(() => {
  const summary = getManifestObject('platform_summary')
  const value = summary?.pair_count
  return typeof value === 'number' ? value : total.value
})
const moderatorOptions = computed(() => {
  if (apiModerators.value.length > 0) {
    return apiModerators.value
  }
  const moderators = props.asset?.manifest.moderators
  return Array.isArray(moderators) ? moderators.map((item) => String(item)) : []
})
const strategyOptions = computed(() => {
  const summary = getManifestObject('platform_summary')
  const strategies = getNestedObject(summary, 'strategy_counts')
  return Object.entries(strategies)
    .map(([name, count]) => ({ name, count: toDisplayNumber(count) }))
    .filter((item) => item.count > 0)
})
const verdictHint = computed(() => {
  if (filters.moderator) {
    return '未拦截 = 当前难度范围内存在该 Moderator 判 safe；已拦截 = 当前难度范围内都被该 Moderator 判 unsafe'
  }
  return '存在未拦截 = 当前难度范围内存在任一 Moderator 判 safe；全部拦截 = 当前难度范围内所有 Moderator 都判 unsafe'
})

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      loadPairs()
    }
  },
)

async function loadPairs() {
  if (!props.asset) {
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await getTopic2PrerunPairs(props.asset.asset_id, {
      moderator: filters.moderator || undefined,
      verdict: filters.verdict || undefined,
      difficulty: filters.difficulty || undefined,
      strategy: filters.strategy || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })
    pairs.value = response.pairs
    total.value = response.total
    apiModerators.value = response.moderators
    selectedPair.value = response.pairs[0] || null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '样本读取失败'
  } finally {
    isLoading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadPairs()
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadPairs()
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadPairs()
}

function selectPair(pair: BenchmarkTopic2PrerunPairItem) {
  selectedPair.value = pair
}

function handleClosed() {
  pairs.value = []
  selectedPair.value = null
  errorMessage.value = ''
}

function getManifestString(key: string) {
  const value = props.asset?.manifest[key]
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '-'
}

function getManifestNumber(key: string) {
  return toDisplayNumber(props.asset?.manifest[key])
}

function getManifestObject(key: string) {
  const value = props.asset?.manifest[key]
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function getNestedObject(value: Record<string, unknown> | null, key: string) {
  const item = value?.[key]
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    return {}
  }
  return item as Record<string, unknown>
}

function toDisplayNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function verdictType(label?: string | null) {
  if (label === 'unsafe') {
    return 'success'
  }
  if (label === 'safe') {
    return 'danger'
  }
  return 'info'
}

const SampleBlock = defineComponent({
  name: 'SampleBlock',
  props: {
    title: { type: String, required: true },
    sample: {
      type: Object as () => BenchmarkTopic2PrerunSampleItem | null | undefined,
      default: null,
    },
  },
  setup(blockProps) {
    const expanded = ref(false)
    return () => {
      const sample = blockProps.sample
      if (!sample) {
        return h('article', { class: 'sample-block' }, [
          h('h5', blockProps.title),
          h('p', { class: 'sample-block__empty' }, '暂无样本'),
        ])
      }
      return h('article', { class: 'sample-block' }, [
        h('div', { class: 'sample-block__header' }, [
          h('h5', blockProps.title),
          h('span', `rewrite ${sample.rewrite_rounds ?? '-'}`),
        ]),
        h('p', { class: 'sample-preview' }, expanded.value ? sample.query : sample.query_preview),
        h(
          'button',
          {
            class: 'link-button',
            type: 'button',
            onClick: () => {
              expanded.value = !expanded.value
            },
          },
          expanded.value ? '收起完整样本' : '显示完整样本',
        ),
        h('div', { class: 'strategy-list' }, [
          ...sample.strategy_chain.map((strategy) => h('span', strategy)),
        ]),
        h('dl', { class: 'qa-list' }, [
          h('div', [h('dt', 'QA Gate'), h('dd', sample.rewrite_qa.passed ? 'passed' : '-')]),
          h('div', [h('dt', 'semantic_ok'), h('dd', sample.rewrite_qa.semantic_ok ? 'true' : '-')]),
          h('div', [h('dt', 'format_ok'), h('dd', sample.rewrite_qa.format_ok ? 'true' : '-')]),
        ]),
        sample.rewrite_qa.reason ? h('p', { class: 'qa-reason' }, sample.rewrite_qa.reason) : null,
        h(
          'div',
          { class: 'moderator-list' },
          Object.entries(sample.moderator_results).map(([name, result]) =>
            h('span', { class: `moderator-pill is-${verdictType(result.label)}` }, [
              h('b', name),
              h('em', result.label || '-'),
            ]),
          ),
        ),
      ])
    }
  },
})
</script>

<style scoped>
.topic2-pair-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.drawer-summary h3 {
  margin: 0;
  color: var(--text-primary);
}

.drawer-summary p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.drawer-summary dl,
.detail-meta,
.qa-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.drawer-summary dt,
.detail-meta dt,
.qa-list dt {
  color: var(--text-muted);
  font-size: 12px;
}

.drawer-summary dd,
.detail-meta dd,
.qa-list dd {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.sample-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.sample-toolbar .el-select,
.sample-toolbar .el-input {
  width: 180px;
}

.filter-hint {
  color: var(--text-muted);
  font-size: 12px;
}

.sample-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.9fr);
  gap: 14px;
}

.sample-table-wrap,
.sample-detail {
  min-width: 0;
}

.sample-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.sample-detail {
  display: flex;
  min-height: 520px;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.sample-detail__empty {
  color: var(--text-secondary);
}

.sample-detail__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.sample-detail__header h4 {
  margin: 0;
  color: var(--text-primary);
}

.sample-detail__header span {
  color: var(--text-muted);
  font-size: 12px;
}

.paired-samples {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

:deep(.sample-block) {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

:deep(.sample-block__header) {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

:deep(.sample-block h5) {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
}

:deep(.sample-block__header span),
:deep(.sample-block__empty) {
  color: var(--text-muted);
  font-size: 12px;
}

:deep(.sample-preview),
:deep(.qa-reason) {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

:deep(.link-button) {
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent-blue);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

:deep(.strategy-list),
:deep(.moderator-list) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.strategy-list span),
:deep(.moderator-pill) {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 11px;
  font-weight: 700;
}

:deep(.moderator-pill em) {
  font-style: normal;
}

:deep(.moderator-pill.is-success) {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

:deep(.moderator-pill.is-danger) {
  background: rgba(198, 40, 40, 0.12);
  color: #c62828;
}

:deep(.moderator-pill.is-info) {
  background: rgba(91, 107, 125, 0.12);
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .sample-layout {
    grid-template-columns: 1fr;
  }
}
</style>
