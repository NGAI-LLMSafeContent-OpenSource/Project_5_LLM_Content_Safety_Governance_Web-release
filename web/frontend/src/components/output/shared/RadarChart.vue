<template>
  <div class="radar-chart-wrap">
    <div
      ref="chartRef"
      class="radar-chart-container"
      :style="{ width: containerWidth, height: containerHeight }"
    ></div>
    <!-- 指标选择器（仅多数据集模式显示） -->
    <div v-if="isMultiDataset && showMetricSelector" class="radar-metric-selector">
      <button
        v-for="m in availableMetrics"
        :key="m.key"
        class="metric-btn"
        :class="{ active: currentMetric === m.key }"
        @click="selectMetric(m.key)"
      >
        {{ m.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { RadarChartData, MultiDatasetRadarData } from '@/types'

echarts.use([RadarChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    data: RadarChartData | MultiDatasetRadarData | null
    size?: number
    showMetricSelector?: boolean
  }>(),
  {
    size: 320,
    showMetricSelector: false,
  },
)

const emit = defineEmits<{
  (e: 'update:selectedMetric', value: string): void
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const containerWidth = computed(() => `${props.size ?? 320}px`)
const containerHeight = computed(() => `${props.size ?? 320}px`)

const availableMetrics = [
  { key: 'f1', label: 'F1' },
  { key: 'accuracy', label: '准确率' },
  { key: 'recall', label: '召回率' },
  { key: 'riskClassAcc', label: '分层准确率' },
]

const isMultiDataset = computed(() => {
  return props.data !== null && 'selectedMetric' in props.data
})

const currentMetric = computed(() => {
  if (isMultiDataset.value) {
    return (props.data as MultiDatasetRadarData).selectedMetric
  }
  return 'f1'
})

function selectMetric(key: string) {
  emit('update:selectedMetric', key)
}

function getColorPalette(index: number): string {
  const palette = [
    '#1565c0',
    '#c62828',
    '#2e7d32',
    '#e65100',
    '#5c6bc0',
    '#ad1457',
    '#0277bd',
    '#f57c00',
  ]
  return palette[index % palette.length]
}

function buildEChartsOption(): Record<string, unknown> | null {
  if (!props.data) return null

  const data = props.data

  if (isMultiDataset.value) {
    const multiData = data as MultiDatasetRadarData
    const labels = multiData.dimensionLabels ?? {}
    const indicator = multiData.dimensions.map((code) => ({
      name: labels[code] ? `${code} ${labels[code]}` : code,
      max: 100,
    }))

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as { seriesName: string; value: number; name: string }
          return `${p.seriesName}<br/>${p.name}: <strong>${p.value.toFixed(1)}%</strong>`
        },
      },
      legend: {
        data: multiData.series.map((s) => s.datasetName),
        bottom: 0,
        textStyle: { fontSize: 10, color: '#7a96b0' },
        itemWidth: 10,
        itemHeight: 6,
        type: 'scroll',
      },
      radar: {
        center: ['50%', '45%'],
        radius: '55%',
        indicator,
        axisName: {
          color: '#4a6380',
          fontSize: 10,
          overflow: 'truncate',
          width: 60,
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(21, 101, 192, 0.02)', 'rgba(21, 101, 192, 0.02)'],
          },
        },
        splitLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.15)' } },
        axisLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.12)' } },
      },
      series: [
        {
          type: 'radar',
          data: multiData.series.map((s, i) => ({
            name: s.datasetName,
            value: s.values.map((v) => Math.min(v, 100)),
            symbol: 'circle',
            symbolSize: 4,
            lineStyle: { width: 1.8, color: s.color || getColorPalette(i) },
            areaStyle: { opacity: 0.08, color: s.color || getColorPalette(i) },
            itemStyle: { color: s.color || getColorPalette(i) },
          })),
        },
      ],
    }
  }

  // Legacy RadarChartData (diversity track)
  const legacyData = data as RadarChartData
  const maxVal = Math.max(...legacyData.series.flatMap((s) => s.values), 100)
  const indicator = legacyData.dimensions.map((name) => ({ name, max: maxVal }))

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { seriesName: string; value: number; name: string }
        return `${p.seriesName}<br/>${p.name}: <strong>${p.value.toFixed(1)}</strong>`
      },
    },
    legend: {
      data: legacyData.series.map((s) => s.name),
      bottom: 0,
      textStyle: { fontSize: 10, color: '#7a96b0' },
      itemWidth: 10,
      itemHeight: 6,
    },
    radar: {
      center: ['50%', '45%'],
      radius: '55%',
      indicator,
      axisName: {
        color: '#4a6380',
        fontSize: 10,
        overflow: 'truncate',
        width: 60,
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(21, 101, 192, 0.02)', 'rgba(21, 101, 192, 0.02)'],
        },
      },
      splitLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.15)' } },
      axisLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.12)' } },
    },
    series: [
      {
        type: 'radar',
        data: legacyData.series.map((s) => ({
          name: s.name,
          value: s.values,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { width: 1.8, color: s.stroke },
          areaStyle: { opacity: 0.1, color: s.fill },
          itemStyle: { color: s.stroke },
        })),
      },
    ],
  }
}

function hasSize(): boolean {
  if (!chartRef.value) return false
  return chartRef.value.clientWidth > 0 && chartRef.value.clientHeight > 0
}

function initChart() {
  if (!chartRef.value || !hasSize()) return
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  chartInstance = echarts.init(chartRef.value)
  const option = buildEChartsOption()
  if (option) {
    chartInstance.setOption(option)
  }
}

function updateChart() {
  if (!chartInstance) {
    initChart()
    return
  }
  const option = buildEChartsOption()
  if (option) {
    chartInstance.setOption(option, { notMerge: true })
  }
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  nextTick(() => {
    if (hasSize()) {
      initChart()
    } else {
      resizeObserver = new ResizeObserver(() => {
        if (hasSize()) {
          initChart()
          resizeObserver?.disconnect()
          resizeObserver = null
        }
      })
      if (chartRef.value) resizeObserver.observe(chartRef.value)
    }
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  resizeObserver?.disconnect()
  resizeObserver = null
  chartInstance?.dispose()
  chartInstance = null
})

watch(
  () => props.data,
  () => {
    nextTick(() => updateChart())
  },
  { deep: true },
)

watch(
  () => props.size,
  () => {
    nextTick(() => handleResize())
  },
)
</script>

<style scoped>
.radar-chart-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.radar-chart-container {
  display: block;
}

.radar-metric-selector {
  display: flex;
  gap: 4px;
  background: var(--bg-secondary, #f0f5fc);
  border-radius: 8px;
  padding: 3px;
}

.metric-btn {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: var(--text-muted, #7a96b0);
  transition: all 0.15s ease;
}

.metric-btn:hover {
  color: var(--text-primary, #1a2a44);
}

.metric-btn.active {
  background: var(--bg-primary, #ffffff);
  color: var(--accent-blue, #1565c0);
  box-shadow: 0 1px 4px rgba(21, 101, 192, 0.15);
}
</style>
