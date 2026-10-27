<template>
  <div class="content">
    <div class="section-title">
      真实任务验证
      <small>当前 seed-v4 多标签快照可展示，现场重跑需先通过运行条件检查</small>
    </div>
    <div class="verify-grid">
      <div class="section-card">
        <div class="source-title">运行前检查</div>
        <div class="check-list">
          <div class="check ok">
            <span>Benchmark 服务</span>
            <b>在线</b>
          </div>
          <div class="check ok">
            <span>静态结果快照</span>
            <b>可读</b>
          </div>
          <div class="check warn">
            <span>Audit Tool</span>
            <b>待确认</b>
          </div>
          <div class="check warn">
            <span>Qwen3.5-9B 模型路径</span>
            <b>待确认</b>
          </div>
          <div class="check warn">
            <span>GPU / 显存</span>
            <b>待确认</b>
          </div>
          <div class="check ok">
            <span>数据路径</span>
            <b>已在快照中记录</b>
          </div>
        </div>
      </div>
      <div class="section-card">
        <div class="source-title">任务能力边界</div>
        <p class="panel-desc">
          课题三当前静态展示已稳定承接
          <span class="mono">multilabel_then_severity</span>
          ，但批量真实任务是否可现场重跑，还依赖 Audit Tool、多标签脚本、模型路径和 GPU 环境。
        </p>
        <div class="notice">
          建议：先检查运行条件，通过后再开放"发起真实评测"。失败时明确原因，并引导返回静态快照。
        </div>
        <div class="run-scope">
          <span>本次任务会传入 Step 2 治理标准体系风险类别：</span>
          <b>{{ selectedRiskScopeText }}</b>
        </div>
        <p style="margin-top: 14px">
          <button class="btn" @click="checkConditions">检查运行条件</button>
          <button class="btn primary" :disabled="!canStartRealEval" @click="startRealEval">
            发起真实评测
          </button>
          <button class="btn" @click="$emit('switchToStatic')">查看静态结果摘要</button>
        </p>
        <div v-if="store.evalJobLogs.length" class="task-log">
          <div v-for="(log, index) in store.evalJobLogs.slice(-4)" :key="index">{{ log }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useOutputStore } from '@/stores/output'

defineEmits<{ switchToStatic: [] }>()

const store = useOutputStore()
const conditionsChecked = ref(false)
const selectedRiskCodes = computed(() =>
  store.riskDimensions
    .filter((dim) => dim.selected && /^C\d{2}$/.test(dim.key))
    .map((dim) => dim.key),
)
const selectedRiskScopeText = computed(() =>
  selectedRiskCodes.value.length ? selectedRiskCodes.value.join('、') : '暂无风险类别覆盖',
)
const canStartRealEval = computed(
  () =>
    conditionsChecked.value &&
    selectedRiskCodes.value.length > 0 &&
    store.selectedRiskDatasets.length > 0 &&
    !['pending', 'running'].includes(store.evalJobStatus),
)
function checkConditions() {
  conditionsChecked.value = true
}
function startRealEval() {
  store.startEvalJob()
}
</script>

<style scoped>
.content {
  padding: 16px 18px 20px;
}
.section-title {
  font-size: 15px;
  font-weight: 800;
  margin: 18px 0 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-primary);
}
.section-title small {
  font-weight: 500;
  color: var(--text-muted);
  font-size: 12px;
}
.verify-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.section-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary, #fff);
  padding: 14px;
}
.source-title {
  font-size: 15px;
  font-weight: 800;
  margin-bottom: 10px;
}
.panel-desc {
  margin: 0;
  color: var(--text-muted, #8899aa);
  font-size: 12px;
}
.mono {
  font-family: Consolas, Menlo, monospace;
  font-size: 11px;
}
.check-list {
  display: grid;
  gap: 8px;
}
.check {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: #fff;
  padding: 10px;
  font-size: 12px;
}
.check.ok b {
  color: var(--accent-green);
}
.check.warn b {
  color: #a45d00;
}
.check.err b {
  color: var(--accent-red);
}
.notice {
  border: 1px solid #ffd89a;
  background: #fff8e8;
  color: #7a4b00;
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 10px;
  font-size: 12px;
}
.run-scope {
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid #d8e8f8;
  border-radius: 7px;
  background: #f5faff;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.run-scope b {
  color: var(--text-primary);
}
.task-log {
  display: grid;
  gap: 5px;
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: #fbfdff;
  color: var(--text-secondary);
  font-family: Consolas, Menlo, monospace;
  font-size: 11px;
  line-height: 1.5;
}
.btn {
  border: 1px solid var(--border-color);
  background: #fff;
  border-radius: 6px;
  padding: 7px 12px;
  font-weight: 700;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-primary);
  margin-right: 8px;
}
.btn.primary {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: #fff;
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 960px) {
  .verify-grid {
    grid-template-columns: 1fr;
  }
}
</style>
