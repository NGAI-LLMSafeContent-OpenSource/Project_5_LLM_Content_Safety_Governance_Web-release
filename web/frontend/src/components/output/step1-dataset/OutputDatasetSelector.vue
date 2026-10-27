<template>
  <div class="dataset-selector">
    <div class="top-section">
      <div class="top-title-row">
        <span class="top-icon">📥</span>
        <div>
          <h1 class="top-title">测试数据选择</h1>
          <p class="top-desc">
            按风险轨道和文化多样性轨道组织数据资产；数据集只会进入其所属轨道的后续筛选与评测流程。
          </p>
        </div>
      </div>

      <div class="status-cards">
        <div class="status-card" :class="dataServiceClass">
          <span class="sc-dot" :class="dataServiceDotClass"></span>
          <div class="sc-body">
            <span class="sc-label">测试数据服务</span>
            <span class="sc-sub">{{ dataServiceSub }}</span>
          </div>
        </div>
        <div class="status-card" :class="diversityBindingClass">
          <span class="sc-dot" :class="diversityBindingDotClass"></span>
          <div class="sc-body">
            <span class="sc-label">文化多样性内容绑定</span>
            <span class="sc-sub">{{ diversityBindingSub }}</span>
          </div>
        </div>
        <div class="status-card" :class="riskBindingClass">
          <span class="sc-dot" :class="riskBindingDotClass"></span>
          <div class="sc-body">
            <span class="sc-label">风险内容绑定</span>
            <span class="sc-sub">{{ riskBindingSub }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="store.datasetsSource === 'error'" class="datasets-error-banner">
      <span class="error-banner-icon">⚠️</span>
      <span>{{ store.datasetsErrorReason || '测试数据服务暂不可用，请检查后端数据接口' }}</span>
    </div>

    <!-- split layout -->
    <div class="split-wrap">
      <div class="split">
        <div class="col-left">
          <DatasetListPanel />
        </div>
        <div class="col-right">
          <div class="corpus-toggle-wrap">
            <button
              class="corpus-toggle-btn"
              :class="{ active: showCultureCorpusWorkbench }"
              type="button"
              @click="showCultureCorpusWorkbench = true"
            >
              <span class="corpus-toggle-main">文化语料实时生成</span>
              <span class="corpus-toggle-sub">打开生成工作台</span>
            </button>
          </div>

          <!-- selected datasets — 可滚动 -->
          <SelectedDatasetsPanel />
        </div>
      </div>
    </div>

    <!-- footer -->
    <div class="selector-footer">
      <button class="btn" @click="uploadDataset">↑ 上传自定义数据集</button>
      <div class="footer-right">
        <span v-if="selectedCount > 0" class="footer-hint">
          已选 风险 {{ riskSelectedCount }} 个 · 多样性 {{ diversitySelectedCount }} 个
        </span>
        <button class="btn" :disabled="riskSelectedCount === 0" @click="goNext(OutputTrack.RISK)">
          进入风险轨道 →
        </button>
        <button
          class="btn btn-primary"
          :disabled="diversitySelectedCount === 0"
          @click="goNext(OutputTrack.DIVERSITY)"
        >
          进入多样性轨道 →
        </button>
      </div>
      <input
        ref="fileInputRef"
        type="file"
        accept=".json,.csv,.xlsx"
        style="display: none"
        @change="onFileSelected"
      />
    </div>

    <Teleport to="body">
      <div
        v-show="showCultureCorpusWorkbench"
        class="corpus-modal-overlay"
        @click.self="showCultureCorpusWorkbench = false"
      >
        <section class="corpus-modal">
          <header class="corpus-modal-head">
            <div>
              <div class="corpus-modal-title">文化语料生成工作台</div>
              <div class="corpus-modal-desc">
                对接课题三文化语料生成工具，生成后的样本同步到文化语料批次集合。
              </div>
            </div>
            <button
              class="corpus-modal-close"
              type="button"
              @click="showCultureCorpusWorkbench = false"
            >
              关闭
            </button>
          </header>
          <div class="corpus-modal-body">
            <aside class="corpus-capability-panel">
              <div class="capability-title">原始项目能力嵌入</div>
              <div class="capability-item active">
                <span>已接入</span>
                <strong>实时生成任务</strong>
                <p>配置批次、样本数、难度分布、民族范围并启动任务。</p>
              </div>
              <div class="capability-item">
                <span>已接入</span>
                <strong>批次历史与复用</strong>
                <p>读取历史 runs 供预览，并刷新右侧已选数据中的批次筛选项。</p>
              </div>
              <div class="capability-item">
                <span>可扩展</span>
                <strong>模板、日志、样本预览</strong>
                <p>当前已展示运行日志与任务产物，后续可继续嵌入原项目生成模板。</p>
              </div>
            </aside>
            <main class="corpus-workbench-main">
              <CultureCorpusGeneratorPanel />
              <CultureCorpusRunsPanel />
            </main>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useOutputStore } from '@/stores/output'
import { useToast } from '@/composables/common/useToast'
import DatasetListPanel from '../shared/DatasetListPanel.vue'
import CultureCorpusGeneratorPanel from './CultureCorpusGeneratorPanel.vue'
import CultureCorpusRunsPanel from './CultureCorpusRunsPanel.vue'
import SelectedDatasetsPanel from './SelectedDatasetsPanel.vue'
import { OutputTrack } from '@/types'

const store = useOutputStore()
const toast = useToast()
const fileInputRef = ref<HTMLInputElement | null>(null)
const showCultureCorpusWorkbench = ref(false)
const selectedCount = computed(() => store.selectedDatasets.length)
const riskSelectedCount = computed(() => store.selectedRiskDatasets.length)
const diversitySelectedCount = computed(() => store.selectedDiversityDatasets.length)

const dataServiceClass = computed(() =>
  store.datasetsSource === 'error' ? 'status-card--neutral' : 'status-card--ok',
)
const dataServiceDotClass = computed(() =>
  store.datasetsSource === 'error' ? 'sc-dot--neutral' : 'sc-dot--on',
)
const dataServiceSub = computed(() =>
  store.datasetsSource === 'error'
    ? store.datasetsErrorReason || '测试数据服务暂不可用'
    : '已连接治理标准与评测快照',
)
const diversityBindingClass = computed(() =>
  diversitySelectedCount.value > 0 ? 'status-card--ok' : 'status-card--warn',
)
const diversityBindingDotClass = computed(() =>
  diversitySelectedCount.value > 0 ? 'sc-dot--on' : 'sc-dot--warn',
)
const diversityBindingSub = computed(() =>
  diversitySelectedCount.value > 0
    ? `已选择 ${diversitySelectedCount.value} 个文化多样性内容`
    : '尚未选择文化多样性内容',
)
const riskBindingClass = computed(() =>
  riskSelectedCount.value > 0 ? 'status-card--ok' : 'status-card--warn',
)
const riskBindingDotClass = computed(() =>
  riskSelectedCount.value > 0 ? 'sc-dot--on' : 'sc-dot--warn',
)
const riskBindingSub = computed(() =>
  riskSelectedCount.value > 0 ? `已选择 ${riskSelectedCount.value} 个风险内容` : '尚未选择风险内容',
)

function uploadDataset() {
  fileInputRef.value?.click()
}

function goNext(track: OutputTrack.RISK | OutputTrack.DIVERSITY) {
  const selectedCountForTrack =
    track === OutputTrack.RISK ? riskSelectedCount.value : diversitySelectedCount.value
  if (selectedCountForTrack === 0) {
    toast.info(
      `请先选择${track === OutputTrack.RISK ? '风险' : '多样性'}轨道数据集`,
      '数据集只能进入与其所属场景一致的后续流程。',
    )
    return
  }
  store.goToStep(2, track)
  if (track === OutputTrack.DIVERSITY) {
    void store.loadDiversityData()
  }
  window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
}

function onFileSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    toast.info('功能暂未接入', `已选择文件：${file.name}。自定义数据集导入功能开发中。`)
  }
  input.value = ''
}

onMounted(() => {
  void store.loadCultureCorpusRunHistory()
  void store.loadCultureAssessmentDatasets(true)
})
</script>

<style src="./OutputDatasetSelector.css" scoped></style>
