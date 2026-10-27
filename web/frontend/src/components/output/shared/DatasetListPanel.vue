<template>
  <div class="list-panel">
    <div class="col-head">
      🗂️ 数据集列表
      <span class="col-head-tag">{{ selectableCount }} 个可选</span>
    </div>

    <div class="toolbar">
      <input
        class="search-input"
        type="text"
        placeholder="🔍 搜索 dataset_id、名称或任务类型…"
        :value="store.dsSearchQuery"
        @input="onSearchInput"
      />
    </div>

    <div class="dataset-track-grid">
      <section class="dataset-track-panel dataset-track-panel--diversity">
        <div class="dataset-track-head">
          <strong>文化多样性侧内容</strong>
          <span>{{ diversityContentDatasets.length }} 个</span>
        </div>
        <div v-if="diversityContentDatasets.length === 0" class="ds-empty">
          暂无文化多样性侧内容
        </div>
        <div v-else class="ds-list">
          <button
            v-for="ds in diversityContentDatasets"
            :key="ds.id"
            type="button"
            class="ds-card"
            :class="{ selected: isSelected(ds) }"
            @click="selectDataset(ds)"
          >
            <div class="ds-card-body">
              <div class="ds-card-name-row">
                <span class="ds-card-name">{{ ds.name }}</span>
                <span class="ds-card-id mono">{{ ds.datasetId || ds.id }}</span>
              </div>
              <div class="ds-card-meta">
                <span>{{ ds.sampleCount?.toLocaleString() }} 条样本</span>
                <span v-if="ds.language" class="sep"></span>
                <span v-if="ds.language">{{ ds.language }}</span>
              </div>
            </div>
            <span v-if="isSelected(ds)" class="selected-mark">已选</span>
          </button>
        </div>
      </section>

      <section class="dataset-track-panel dataset-track-panel--risk">
        <div class="dataset-track-head">
          <strong>风险侧内容</strong>
          <span>{{ riskContentDatasets.length }} 个</span>
        </div>
        <div v-if="riskContentDatasets.length === 0" class="ds-empty">暂无风险侧内容</div>
        <div v-else class="ds-list">
          <button
            v-for="ds in riskContentDatasets"
            :key="ds.id"
            type="button"
            class="ds-card"
            :class="{ selected: isSelected(ds) }"
            @click="selectDataset(ds)"
          >
            <div class="ds-card-body">
              <div class="ds-card-name-row">
                <span class="ds-card-name">{{ ds.name }}</span>
                <span class="ds-card-id mono">{{ ds.datasetId || ds.id }}</span>
              </div>
              <div class="ds-card-meta">
                <span>{{ ds.sampleCount?.toLocaleString() }} 条样本</span>
                <span v-if="ds.language" class="sep"></span>
                <span v-if="ds.language">{{ ds.language }}</span>
              </div>
            </div>
            <span v-if="isSelected(ds)" class="selected-mark">已选</span>
          </button>
        </div>
      </section>

      <div v-if="visibleDatasets.length === 0" class="ds-empty dataset-track-empty">
        未找到匹配的数据集
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useToast } from '@/composables/common/useToast'
import { useOutputStore } from '@/stores/output'
import { OutputTrack, type DataAsset } from '@/types'

const store = useOutputStore()
const toast = useToast()
const { allAssets } = storeToRefs(store)

function onSearchInput(e: Event) {
  store.setDsSearchQuery((e.target as HTMLInputElement).value)
}

const visibleDatasets = computed(() => {
  let list = allAssets.value
  const q = store.dsSearchQuery.toLowerCase()
  if (q) {
    list = list.filter(
      (asset) =>
        asset.name.toLowerCase().includes(q) ||
        asset.id.toLowerCase().includes(q) ||
        (asset.task && asset.task.toLowerCase().includes(q)),
    )
  }
  return [...list].sort(datasetSort)
})

function datasetSort(a: DataAsset, b: DataAsset): number {
  const selectableDelta = Number(store.isAssetSelectable(b)) - Number(store.isAssetSelectable(a))
  if (selectableDelta !== 0) return selectableDelta
  const trackOrder = (asset: DataAsset) =>
    asset.scenario === '文化多样性内容' ? 0 : asset.scenario === 'AI for Science' ? 1 : 2
  const trackDelta = trackOrder(a) - trackOrder(b)
  if (trackDelta !== 0) return trackDelta
  return a.name.localeCompare(b.name, 'zh-Hans-CN')
}

const selectableCount = computed(
  () => allAssets.value.filter((asset) => store.isAssetSelectable(asset)).length,
)

const diversityContentDatasets = computed(() =>
  visibleDatasets.value.filter((asset) => asset.track === OutputTrack.DIVERSITY),
)

const riskContentDatasets = computed(() =>
  visibleDatasets.value.filter((asset) => asset.track === OutputTrack.RISK),
)

function isSelected(ds: DataAsset): boolean {
  const id = ds.datasetId || ds.id
  return store.selectedDatasets.some((item) => item.datasetId === id)
}

function selectDataset(ds: DataAsset) {
  if (!store.isAssetSelectable(ds)) {
    toast.info('当前内容暂不可选', '该内容尚未完成接入准备。')
    return
  }

  const id = ds.datasetId || ds.id
  if (isSelected(ds)) {
    toast.info('已选择该内容', ds.name)
    return
  }

  store.clearCheckedDatasets()
  if (!store.checkedDatasetIds.includes(id)) {
    store.toggleCheckedDataset(id)
  }
  store.addSelectedFromChecked()
  toast.success(
    ds.track === OutputTrack.DIVERSITY ? '已选择文化多样性侧内容' : '已选择风险侧内容',
    ds.name,
  )
}
</script>

<style src="./DatasetListPanel.css" scoped></style>
