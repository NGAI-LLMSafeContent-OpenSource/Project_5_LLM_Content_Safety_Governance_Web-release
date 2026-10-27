<template>
  <div v-if="view || loading || error" class="topic3-version">
    <p v-if="loading" class="version-state">正在读取当前评测对象及其同版本结果。</p>
    <p v-else-if="error" class="version-state version-state--error">{{ error }}</p>
    <template v-else-if="view">
      <div class="version-head">
        <div class="version-identity">
          <span class="version-eyebrow">评测对象</span>
          <b class="version-name">{{ view.name }}</b>
          <span class="snapshot-badge" title="来自课题三静态评测结果快照，不代表本次现场运行">
            静态快照
          </span>
        </div>
        <label class="version-picker">
          <span>版本</span>
          <select :value="view.asset_version ?? ''" @change="onVersionChange">
            <option
              v-for="item in view.versions"
              :key="item.asset_id"
              :value="item.asset_version ?? ''"
            >
              {{ item.asset_version }} · {{ item.asset_status === 'current' ? '当前' : '历史' }}
            </option>
          </select>
        </label>
      </div>

      <dl class="version-meta">
        <div class="meta-item">
          <dt>数据集 ID</dt>
          <dd class="mono" :title="view.asset_id">{{ shorten(view.asset_id) }}</dd>
        </div>
        <div class="meta-item">
          <dt>内容哈希</dt>
          <dd class="mono" :title="view.asset_sha256">{{ shorten(view.asset_sha256) }}</dd>
        </div>
        <div class="meta-item">
          <dt>样本数</dt>
          <dd>
            {{ view.sample_count ?? '—' }}
            <template v-if="view.sample_count != null">条</template>
          </dd>
        </div>
        <div v-if="view.result_display.task" class="meta-item">
          <dt>任务口径</dt>
          <dd class="mono">{{ view.result_display.task }}</dd>
        </div>
        <div class="meta-item">
          <dt>主评估器</dt>
          <dd class="mono">{{ evaluatorText }}</dd>
        </div>
        <div class="meta-item">
          <dt>同版本基线</dt>
          <dd>{{ baselineText }}</dd>
        </div>
      </dl>

      <details v-if="integritySamples.length" class="version-fold">
        <summary>
          完整性告警
          <b class="fold-count">{{ integritySamples.length }}</b>
        </summary>
        <ul class="fold-list">
          <li v-for="sample in integritySamples" :key="sample.sample_id">
            <span class="fold-id">{{ sample.sample_id }}</span>
            <span class="fold-text">
              {{ sample.label_reason_status }}
              <template v-if="sample.integrity_warnings[0]">
                · {{ sample.integrity_warnings[0].message }}
              </template>
            </span>
          </li>
        </ul>
      </details>

      <details v-if="view.automatic_explanations.length" class="version-fold">
        <summary>
          自动解释
          <b class="fold-count">{{ view.automatic_explanations.length }}</b>
          <small>仅收录可用于自动治理解释的标注理由</small>
        </summary>
        <ul class="fold-list">
          <li v-for="item in view.automatic_explanations" :key="item.sample_id">
            <span class="fold-id">{{ item.sample_id }}</span>
            <span class="fold-text explain-text" :title="item.text">{{ item.text }}</span>
          </li>
        </ul>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Topic3RiskSameVersion } from '@/api/output'

const props = defineProps<{
  view: Topic3RiskSameVersion | null
  loading: boolean
  error: string
}>()

const emit = defineEmits<{
  (e: 'selectVersion', assetVersion: string): void
}>()

const integritySamples = computed(() =>
  (props.view?.sample_details ?? []).filter(
    (sample) => !sample.label_reason_usable_for_automatic_explanation,
  ),
)

const evaluatorText = computed(() => {
  const evaluator = props.view?.primary_evaluator
  if (!evaluator?.available) return '未提供'
  return evaluator.model_id || '—'
})

const baselineText = computed(() => {
  const baseline = props.view?.baseline
  if (!baseline) return '—'
  if (baseline.available) return baseline.model_id || '已提供'
  return baseline.message || '暂无同版本基线'
})

/** 长哈希只展示前缀，完整值通过 title 提示，避免撑坏网格列宽。 */
function shorten(value: string | null | undefined, max = 14): string {
  if (!value) return '—'
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function onVersionChange(event: Event) {
  emit('selectVersion', (event.target as HTMLSelectElement).value)
}
</script>

<style scoped>
.topic3-version {
  margin: 0 0 14px;
  padding: 12px 14px;
  border: 1px solid var(--border-color, #e0e4e8);
  border-radius: 8px;
  background: #fff;
  color: var(--text-secondary, #52677f);
  font-size: 12px;
  line-height: 1.5;
}
.version-state {
  margin: 0;
  color: var(--text-muted, #8899aa);
  font-size: 12px;
}
.version-state--error {
  color: var(--accent-red, #d33);
}
.version-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}
.version-identity {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.version-eyebrow {
  color: var(--text-muted, #8899aa);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.version-name {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.snapshot-badge {
  padding: 1px 7px;
  border: 1px solid rgba(21, 101, 192, 0.28);
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.08);
  color: var(--accent-blue, #1565c0);
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}
.version-picker {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  color: var(--text-muted, #8899aa);
  font-size: 12px;
  white-space: nowrap;
}
.version-picker select {
  padding: 4px 6px;
  border: 1px solid var(--border-color, #e0e4e8);
  border-radius: 6px;
  background: #fff;
  color: var(--text-primary);
  font-size: 12px;
}
.version-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 22px;
  margin: 10px 0 0;
  padding: 10px 0 0;
  border-top: 1px dashed #e4ebf4;
}
.meta-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.meta-item dt {
  color: var(--text-muted, #8899aa);
  font-size: 11px;
  white-space: nowrap;
}
.meta-item dd {
  margin: 0;
  color: var(--text-primary);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.meta-item dd.mono {
  font-family: Consolas, Menlo, monospace;
  font-size: 11px;
}
.version-fold {
  margin-top: 10px;
  border: 1px solid var(--border-color, #e0e4e8);
  border-radius: 7px;
  background: #fbfdff;
}
.version-fold > summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  color: #38516b;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  list-style: none;
}
.version-fold > summary::-webkit-details-marker {
  display: none;
}
.version-fold > summary::before {
  content: '▸';
  color: #8fa1b5;
  font-size: 11px;
  transition: transform 0.15s;
}
.version-fold[open] > summary::before {
  transform: rotate(90deg);
}
.version-fold > summary small {
  margin-left: auto;
  color: var(--text-muted, #8899aa);
  font-size: 11px;
  font-weight: 500;
}
.fold-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue, #1565c0);
  font-size: 11px;
}
.fold-list {
  max-height: 260px;
  margin: 0;
  padding: 4px 10px 10px 26px;
  overflow: auto;
}
.fold-list li {
  color: var(--text-secondary, #52677f);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.fold-id {
  margin-right: 6px;
  color: #38516b;
  font-weight: 700;
}
.fold-text {
  display: block;
}
.explain-text {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
</style>
