<template>
  <div class="strategy-report">
    <!-- Header with action buttons -->
    <div class="eval-card">
      <div class="report-header">
        <span class="report-title"><span class="title-icon">💡</span>后训练策略建议</span>
        <div class="header-btns">
          <el-button size="small" @click="showHistory">📋 历史记录</el-button>
          <el-button size="small" type="primary" @click="startTraining">🚀 开始训练</el-button>
          <el-button size="small" @click="exportReport">📥 导出报告</el-button>
          <el-button size="small" @click="scheduleReview">⏰ 复评提醒</el-button>
        </div>
      </div>

      <!-- Section 1: Training Priority -->
      <div class="stage-section">
        <h4 class="stage-title">一、基于归因分析的训练优先级建议</h4>
        <div class="priority-list">
          <div
            v-for="s in store.strategyRecommendations"
            :key="s.id"
            class="priority-card"
            :class="`priority-card--${s.priority.toLowerCase()}`"
          >
            <div class="priority-label">
              {{ s.priority }} · {{ s.trainingMethod }} {{ s.title }}
            </div>
            <div class="priority-desc">{{ s.description }}</div>
            <div class="priority-meta">
              <span>📊 预计训练数据: {{ s.trainingDataCount }}</span>
              <span>⏱ 预计训练周期: {{ s.expectedDuration }}</span>
              <span>🎯 目标指标: {{ s.targetMetric }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: Training Data Demand -->
      <div class="stage-section">
        <h4 class="stage-title">二、训练数据需求估算</h4>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-val" style="color: var(--accent-red)">847</div>
            <div class="stat-lbl">高风险Token组合</div>
          </div>
          <div class="stat-card">
            <div class="stat-val" style="color: var(--accent-orange)">1,224</div>
            <div class="stat-lbl">需修正触发样本</div>
          </div>
          <div class="stat-card">
            <div class="stat-val" style="color: var(--accent-blue)">58.3%</div>
            <div class="stat-lbl">Top-5 覆盖率</div>
          </div>
          <div class="stat-card">
            <div class="stat-val" style="color: var(--accent-green)">482</div>
            <div class="stat-lbl">DPO偏好对生成</div>
          </div>
        </div>
      </div>

      <!-- Section 3: Comparison Metrics -->
      <div class="stage-section">
        <h4 class="stage-title">三、评估指标与历史对比</h4>
        <div class="table-wrap">
          <table class="comparison-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>修正前</th>
                <th>修正后（预估）</th>
                <th>提升</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in store.comparisonMetrics" :key="m.label">
                <td class="metric-label">{{ m.label }}</td>
                <td>{{ m.before }}</td>
                <td class="after-val">{{ m.after }}</td>
                <td class="improve-val">{{ m.improvement }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useOutputStore } from '@/stores/output'
import { useToast } from '@/composables/common/useToast'

const store = useOutputStore()
const toast = useToast()

function showHistory() {
  toast.info('训练历史记录', '正在加载历史训练数据')
}
function startTraining() {
  toast.success('训练任务已启动', 'SFT/RLHF/DPO 三阶段训练已加入队列')
}
function exportReport() {
  toast.info('报告导出中...', '正在生成评估与修正报告，请稍候')
}
function scheduleReview() {
  toast.success('复评提醒已设置', '优化完成后将自动触发复评流程')
}
</script>

<style src="./OutputStrategyReport.css" scoped></style>
