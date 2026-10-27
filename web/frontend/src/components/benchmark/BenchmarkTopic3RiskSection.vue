<template>
  <section class="topic3-risk-section" aria-labelledby="topic3-risk-title">
    <header class="topic3-risk-section__header">
      <div>
        <h4 id="topic3-risk-title">{{ seriesName || '课题三风险分级分类 Benchmark' }}</h4>
        <p>
          版本、样本数量、风险等级、语言分布和主评估器结果均来自服务端同一资产。
          评估器版本与评测对象版本分开展示。
        </p>
      </div>
      <span class="source-pill" :class="statusClass">
        {{ statusLabel(selected?.asset_status) }}
      </span>
    </header>

    <p v-if="loadingVersions" class="topic3-risk-section__state">
      正在读取 Benchmark 版本元数据...
    </p>
    <el-alert v-else-if="loadError" type="error" :closable="false" show-icon :title="loadError" />

    <template v-else>
      <el-empty
        v-if="versions.length === 0 && !selected"
        description="服务端尚未登记课题三风险 Benchmark 版本。"
      />

      <template v-else>
        <div class="version-toolbar">
          <label class="version-toolbar__field">
            <span>评测对象版本</span>
            <select
              :value="selectedAssetId"
              :disabled="Boolean(assetId)"
              @change="handleVersionChange"
            >
              <option v-for="item in selectOptions" :key="item.asset_id" :value="item.asset_id">
                {{ item.asset_version || '未登记' }} · {{ statusLabel(item.asset_status) }} ·
                {{ formatCount(item.sample_count) }} 条
              </option>
            </select>
          </label>
          <p v-if="assetId" class="version-toolbar__note">
            当前为单一资产地址，已固定展示该资产版本。
          </p>
          <button
            v-else-if="versions.length > 1"
            type="button"
            class="version-toolbar__history"
            @click="toggleHistory"
          >
            {{ showHistory ? '收起历史版本' : '查看历史版本' }}
          </button>
        </div>

        <dl v-if="selected" class="identity-facts">
          <div>
            <dt>资产标识</dt>
            <dd class="mono">{{ selected.asset_id }}</dd>
          </div>
          <div>
            <dt>评测对象版本</dt>
            <dd>{{ selected.asset_version || '未登记' }}</dd>
          </div>
          <div>
            <dt>内容哈希</dt>
            <dd class="mono">{{ selected.asset_sha256 }}</dd>
          </div>
          <div>
            <dt>样本数</dt>
            <dd>{{ formatCount(selected.sample_count) }} 条</dd>
          </div>
        </dl>

        <div v-if="selected" class="risk-overview">
          <div class="risk-overview__block">
            <b>安全样本与风险等级分布</b>
            <div class="level-grid">
              <div v-for="item in levelItems" :key="item.level" class="level-card">
                <span>{{ item.level }}</span>
                <strong>{{ item.count }}</strong>
              </div>
            </div>
          </div>
          <div class="risk-overview__block">
            <b>语言分布</b>
            <p v-if="languageItems.length === 0" class="risk-overview__empty">暂无语言分布</p>
            <ul v-else class="language-list">
              <li v-for="item in languageItems" :key="item.language">
                <span>{{ item.language }}</span>
                <strong>{{ item.count }}</strong>
              </li>
            </ul>
          </div>
        </div>

        <details v-if="selected" class="risk-category">
          <summary>风险类别分布（C01-C17）</summary>
          <p v-if="categoryItems.length === 0" class="risk-overview__empty">暂无类别分布</p>
          <ul v-else class="category-list">
            <li v-for="item in categoryItems" :key="item.code">
              <span>{{ item.code }}</span>
              <strong>{{ item.count }}</strong>
            </li>
          </ul>
        </details>

        <div v-if="selected" class="evaluation-panel">
          <div class="evaluation-panel__header">
            <div>
              <b>主评估器结果</b>
              <p>只展示与上方资产标识和内容哈希一致的同版本结果。</p>
            </div>
            <span class="source-pill" :class="evaluation?.available ? 'is-valid' : 'is-pending'">
              {{ evaluation?.available ? 'evaluation imported' : 'evaluation pending' }}
            </span>
          </div>

          <p v-if="loadingEvaluation" class="topic3-risk-section__state">
            正在读取同版本评测结果...
          </p>
          <el-alert
            v-else-if="evaluationError"
            type="warning"
            :closable="false"
            show-icon
            :title="evaluationError"
          />
          <template v-else>
            <template v-if="primaryResult">
              <div class="primary-result">
                <div>
                  <h5>{{ primaryModelLabel }}</h5>
                  <p>
                    评估器 {{ primaryResult.model_id }} · run {{ primaryResult.run_id }} ·
                    predictions {{ primaryResult.predictions_count }} 条
                  </p>
                </div>
                <div class="primary-metrics">
                  <div v-for="metric in primaryMetricDefs" :key="metric.key">
                    <span>{{ metric.display_name }}</span>
                    <strong>{{ formatMetric(primaryResult.primary_metrics[metric.key]) }}</strong>
                  </div>
                </div>
              </div>
              <p v-if="baselineMessage" class="baseline-message">{{ baselineMessage }}</p>
              <p v-else class="baseline-message">
                同版本基线 {{ baselineResult?.display_name || baselineResult?.model_id }}
              </p>
              <p v-if="evaluation?.asset_id" class="result-identity">
                评测结果归属 {{ evaluation.asset_id }} ·
                {{ evaluation.asset_version || '未登记' }} · {{ evaluation.asset_sha256 || '—' }}
              </p>
            </template>
            <p v-else class="baseline-message">{{ baselineMessage || '暂无主评估器结果' }}</p>
          </template>
        </div>

        <div v-if="selected" class="section-actions">
          <el-button size="small" type="primary" @click="drawerVisible = true">查看样本</el-button>
          <el-button size="small" @click="$emit('view-evaluations')">前往模型评测</el-button>
          <span class="section-actions__note">普通页面不提供 raw 或完整交付包下载。</span>
        </div>
      </template>
    </template>

    <BenchmarkRiskSampleDrawer
      v-if="selected"
      v-model="drawerVisible"
      :asset-id="selected.asset_id"
      :asset-name="selected.name"
      :asset-version="selected.asset_version"
      :asset-sha256="selected.asset_sha256"
      :sample-count="selected.sample_count"
      :risk-level-distribution="selected.risk_level_distribution || {}"
    />
  </section>
</template>
<script setup lang="ts">
import { toRef } from 'vue'
import type { BenchmarkArtifactItem } from '@/types'
import { useTopic3RiskAssetVersions } from '@/composables/benchmark/useTopic3RiskAssetVersions'
import BenchmarkRiskSampleDrawer from './BenchmarkRiskSampleDrawer.vue'

const props = defineProps<{
  assetId?: string
  fallbackAsset?: BenchmarkArtifactItem | null
}>()

defineEmits<{
  (event: 'view-evaluations'): void
}>()

const {
  loadingVersions,
  loadError,
  versions,
  seriesName,
  selectedAssetId,
  selected,
  selectOptions,
  statusClass,
  loadingEvaluation,
  evaluationError,
  evaluation,
  drawerVisible,
  showHistory,
  levelItems,
  languageItems,
  categoryItems,
  primaryResult,
  baselineResult,
  primaryModelLabel,
  primaryMetricDefs,
  baselineMessage,
  handleVersionChange,
  toggleHistory,
  statusLabel,
  formatCount,
  formatMetric,
} = useTopic3RiskAssetVersions({
  assetId: toRef(props, 'assetId'),
  fallbackAsset: toRef(props, 'fallbackAsset'),
})
</script>

<style scoped src="./BenchmarkTopic3RiskSection.css"></style>
