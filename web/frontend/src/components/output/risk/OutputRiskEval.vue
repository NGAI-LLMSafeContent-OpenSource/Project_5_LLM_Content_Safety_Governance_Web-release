<template>
  <div class="risk-eval">
    <h2 class="track-page__title">评估（风险）</h2>
    <div class="panel">
      <div class="panel-head">
        <div class="panel-intro">
          <div class="major-section-title">一、数据集静态指标</div>
          <p class="panel-desc static-desc">
            以 Benchmark 静态评测快照为主，解释当前数据集的风险识别、多标签分类和样本级命中情况。
          </p>
        </div>
        <div class="panel-head-actions">
          <button class="infer-modal-btn" type="button" @click="showInferModal = true">
            单样本推理验证
          </button>
        </div>
      </div>

      <!-- TAB 1: Static -->
      <div class="content">
        <Topic3RiskVersionPanel
          :view="topic3"
          :loading="store.topic3RiskLoading"
          :error="store.topic3RiskError"
          @select-version="onAssetVersionChange"
        />
        <div class="section-title">
          治理关注指标
          <small v-if="topic3" :title="topic3.asset_sha256">
            同版本结果 · {{ topic3.asset_version }} ·
            <code class="hash">{{ shortHash(topic3.asset_sha256) }}</code>
          </small>
          <small v-else :title="activeDatasetId">
            来自
            <code class="hash">{{ shortHash(activeDatasetId) }}</code>
            metrics.json
          </small>
        </div>
        <div class="metric-grid metric-grid--hero">
          <div class="metric primary hero-metric">
            <div class="label">风险内容分层识别准确率</div>
            <div class="hint">
              risk_class_accuracy_v4_first_label · 预测为风险且首个风险大类命中多标签集合
            </div>
            <div class="value blue">{{ fmtPct(metrics.v4) }}</div>
          </div>
          <div class="metric primary hero-metric">
            <div class="label">风险内容合规预警覆盖率</div>
            <div class="hint">risk_recall · 被正确预警的风险样本数 / 风险样本总数</div>
            <div class="value blue">{{ fmtPct(metrics.riskRecall) }}</div>
          </div>
          <div class="metric primary hero-metric">
            <div class="label">风险内容误报率</div>
            <div class="hint">risk_false_positive_rate · 被误预警的安全样本数 / 安全样本总数</div>
            <div class="value red">{{ fmtPct(metrics.fpr) }}</div>
          </div>
        </div>
        <div class="metric-grid metric-grid--secondary">
          <div class="metric">
            <div class="label">总体风险等级准确率（辅助）</div>
            <div class="hint">risk_severity_accuracy</div>
            <div class="value orange">{{ fmt(metrics.severityAcc) }}</div>
          </div>
          <div class="metric">
            <div class="label">样本级 Jaccard Accuracy</div>
            <div class="hint">预测标签集与真实标签集交并比</div>
            <div class="value purple">{{ fmt(metrics.jaccard) }}</div>
          </div>
          <div class="metric">
            <div class="label">Micro-F1</div>
            <div class="hint">汇总所有风险类别标签后计算</div>
            <div class="value purple">{{ fmt(metrics.microF1) }}</div>
          </div>
          <div class="metric">
            <div class="label">Macro-F1</div>
            <div class="hint">各风险类别 F1 的宏平均</div>
            <div class="value purple">{{ fmt(metrics.macroF1) }}</div>
          </div>
        </div>

        <div v-if="isMultilabelTask" class="section-title">
          多标签匹配口径
          <small>v3/v4/v5 沿用课题三当前统计口径</small>
        </div>
        <div v-if="isMultilabelTask" class="metric-grid metric-grid--multilabel">
          <div class="metric">
            <div class="label">风险内容分层识别准确率-v3</div>
            <div class="hint">预测类别与 Groundtruth 存在交集</div>
            <div class="value green">{{ fmt(metrics.v3) }}</div>
          </div>
          <div class="metric">
            <div class="label">风险内容分层识别准确率-v4</div>
            <div class="hint">模型第一个类别命中 Groundtruth</div>
            <div class="value blue">{{ fmt(metrics.v4) }}</div>
          </div>
          <div class="metric">
            <div class="label">Exact Match / v5</div>
            <div class="hint">预测标签集合与 Groundtruth 完全一致</div>
            <div class="value red">{{ fmt(metrics.v5) }}</div>
          </div>
          <div class="metric">
            <div class="label">Precision safe/unsafe</div>
            <div class="hint">二分类预警精确率</div>
            <div class="value green">{{ fmt(metrics.safePrecision) }}</div>
          </div>
          <div class="metric">
            <div class="label">F1 safe/unsafe</div>
            <div class="hint">二分类预警综合表现</div>
            <div class="value blue">{{ fmt(metrics.safeF1) }}</div>
          </div>
          <div class="metric">
            <div class="label">Accuracy safe/unsafe</div>
            <div class="hint">安全/风险整体判断</div>
            <div class="value blue">{{ fmt(metrics.safeAccuracy) }}</div>
          </div>
        </div>

        <div class="section-title">数据规模与命中统计</div>
        <div class="stat-grid">
          <div class="stat">
            <span>样本总数</span>
            <b>{{ fmtInt(stats.total) }}</b>
          </div>
          <div class="stat">
            <span>风险样本总数</span>
            <b>{{ fmtInt(stats.riskTotal) }}</b>
          </div>
          <div class="stat">
            <span>安全样本总数</span>
            <b>{{ fmtInt(stats.safeTotal) }}</b>
          </div>
          <div class="stat">
            <span>v3 命中数</span>
            <b>{{ fmtInt(stats.v3Hit) }}</b>
          </div>
          <div class="stat">
            <span>v4 首类别命中</span>
            <b>{{ fmtInt(stats.v4Hit) }}</b>
          </div>
          <div class="stat">
            <span>v5 完全匹配</span>
            <b>{{ fmtInt(stats.v5Hit) }}</b>
          </div>
          <div class="stat">
            <span>等级正确数</span>
            <b>{{ fmtInt(stats.severityCorrect) }}</b>
          </div>
          <div class="stat">
            <span>误报数</span>
            <b>{{ fmtInt(stats.fpCount) }}</b>
          </div>
          <div class="stat">
            <span>逐类别分级请求</span>
            <b>{{ fmtInt(stats.severityRequests) }}</b>
          </div>
          <div class="stat">
            <span>micro TP / FP / FN</span>
            <b>
              {{ fmtInt(stats.microTP) }} / {{ fmtInt(stats.microFP) }} /
              {{ fmtInt(stats.microFN) }}
            </b>
          </div>
          <div class="stat">
            <span>TP / TN / FP / FN</span>
            <b>
              {{ fmtInt(stats.tp) }} / {{ fmtInt(stats.tn) }} / {{ fmtInt(stats.fp) }} /
              {{ fmtInt(stats.fn) }}
            </b>
          </div>
          <div class="stat">
            <span>taxonomy</span>
            <b class="mono-value" :title="store.staticResultMeta?.dataset_id || ''">
              {{ shortHash(store.staticResultMeta?.dataset_id) }}
            </b>
          </div>
        </div>

        <div v-if="store.datasetEvalMetrics.length" class="section-title">
          按数据集明细
          <small>per-dataset F1 / Accuracy</small>
        </div>
        <div v-if="store.datasetEvalMetrics.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>数据集</th>
                <th class="num">样本数</th>
                <th class="num">Accuracy</th>
                <th class="num">F1</th>
                <th class="num">风险分类Acc</th>
                <th class="num">风险召回</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in store.datasetEvalMetrics" :key="m.datasetId">
                <td>
                  <b>{{ m.datasetName }}</b>
                </td>
                <td class="num">{{ m.sampleCount }}</td>
                <td class="num">{{ fmt(m.accuracy) }}</td>
                <td class="num">{{ fmt(m.f1) }}</td>
                <td class="num">{{ fmt(m.riskClassAcc) }}</td>
                <td class="num">{{ fmt(m.riskRecall) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="showSampleSection" class="section-title sample-section-title">
          二、个例展示
          <small>{{ selectedRiskScopeShort }} · 左侧列表 + 右侧详情</small>
        </div>

        <div
          v-if="showSampleSection && !predictionSamples.length && store.staticRawMetrics"
          class="notice"
        >
          <template v-if="topic3">当前评测对象没有可展示的同版本样本。</template>
          <template v-else-if="isStaticPredictionUnavailable">
            Benchmark 样本级预测接口当前不可用，无法展示 predictions 个例记录；请检查上游
            /api/demo/predictions 或配置本地快照。
          </template>
          <template v-else>
            当前数据集未返回样本级预测记录。可检查静态预测接口，或切换到其他已产出的评测结果。
          </template>
        </div>

        <div v-if="showSampleSection && predictionSamples.length" class="samples">
          <aside class="sample-list">
            <div class="sample-toolbar">
              <b>评测样本</b>
              <select v-model="sampleFilter" @change="selectedSampleIdx = 0">
                <option value="all">全部</option>
                <option value="partial">部分命中</option>
                <option value="miss">存在漏检</option>
                <option value="level">等级错误</option>
              </select>
            </div>
            <div class="sample-scope-note">
              {{ filteredSamples.length }} /
              {{ predictionSamples.length }} 条样本匹配当前风险类别口径
            </div>
            <div class="sample-items">
              <div
                v-for="(s, i) in filteredSamples"
                :key="i"
                class="sample-item"
                :class="{ active: selectedSampleIdx === i }"
                @click="selectedSampleIdx = i"
              >
                <div class="sample-id">{{ s.id }}</div>
                <div class="chips">
                  <span class="chip">{{ s.level }}</span>
                  <span class="chip" :class="s.status === 'level' ? 'miss' : 'hit'">
                    {{
                      s.status === 'partial'
                        ? '部分命中'
                        : s.status === 'level'
                          ? '等级错误'
                          : s.status === 'missing'
                            ? '无同版本预测'
                            : '存在漏检'
                    }}
                  </span>
                </div>
                <div class="chips">
                  <span v-for="g in s.gold" :key="g" class="chip">
                    {{ g }} {{ catNames[g] || '' }}
                  </span>
                </div>
                <div class="sample-snippet">{{ s.response.slice(0, 66) }}...</div>
              </div>
              <div v-if="!filteredSamples.length" class="sample-empty">
                当前治理标准口径下暂无样本。可确认 Step 2 风险类别覆盖，或在上方切换样本状态过滤。
              </div>
            </div>
          </aside>
          <section v-if="activeSample" class="detail">
            <div class="compare">
              <div class="compare-card gold">
                <h4>Groundtruth</h4>
                <div class="kv">
                  <span>是否有害</span>
                  <b>有害</b>
                </div>
                <div class="kv">
                  <span>标注等级</span>
                  <b>{{ activeSample.level }}</b>
                </div>
                <div class="kv">
                  <span>真实标签</span>
                  <div class="chips">
                    <span v-for="g in activeSample.gold" :key="g" class="chip">{{ g }}</span>
                  </div>
                </div>
              </div>
              <div class="compare-card pred">
                <h4>Prediction</h4>
                <div class="kv">
                  <span>是否有害</span>
                  <b>有害</b>
                </div>
                <div class="kv">
                  <span>预测等级</span>
                  <b>{{ activeSample.levelOk ? activeSample.level : '中风险' }}</b>
                </div>
                <div class="kv">
                  <span>预测标签</span>
                  <div class="chips">
                    <span v-if="activeSample.status === 'missing'" class="chip">无同版本预测</span>
                    <span v-for="p in activeSample.pred" :key="p" class="chip">{{ p }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="result-badges">
              <div class="badge-box">
                命中标签
                <div class="chips">
                  <span v-for="h in activeSample.hit" :key="h" class="chip hit">{{ h }}</span>
                </div>
              </div>
              <div class="badge-box">
                漏检标签
                <div class="chips">
                  <span v-for="m in activeSample.miss" :key="m" class="chip miss">{{ m }}</span>
                  <span v-if="!activeSample.miss.length" class="chip hit">无</span>
                </div>
              </div>
              <div class="badge-box">
                误报标签
                <div class="chips">
                  <span v-for="f in activeSample.fp" :key="f" class="chip fp">{{ f }}</span>
                  <span v-if="!activeSample.fp.length" class="chip hit">无</span>
                </div>
              </div>
            </div>
            <div class="result-badges">
              <div class="badge-box">
                分层识别v3（交集命中）
                <b>{{ activeSample.v3 ? '命中' : '未命中' }}</b>
              </div>
              <div class="badge-box">
                分层识别v4（首类别命中）
                <b>{{ activeSample.v4 ? '命中' : '未命中' }}</b>
              </div>
              <div class="badge-box">
                v5 Exact Match
                <b>{{ activeSample.v5 ? '完全匹配' : '未完全匹配' }}</b>
              </div>
            </div>
            <div class="section-title">逐类别等级</div>
            <div class="chips">
              <span v-for="(lv, k) in activeSample.predLevels" :key="k" class="chip">
                {{ k }} {{ lv }}
              </span>
            </div>
            <div class="section-title">Response</div>
            <div class="response-box">{{ activeSample.response }}</div>
            <details class="fold" open>
              <summary>模型原始输出 raw_output</summary>
              <pre>{{ activeSample.raw }}</pre>
            </details>
            <details class="fold">
              <summary>Prompt 摘要</summary>
              <pre>{{ activeSample.prompt }}</pre>
            </details>
            <div class="notice">
              静态 predictions.jsonl 当前未稳定提供 evidence
              字段；证据高亮可通过右上角单样本推理验证生成。
            </div>
          </section>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div
        v-if="showInferModal"
        class="infer-modal-backdrop"
        role="presentation"
        @click.self="showInferModal = false"
      >
        <section class="infer-modal" role="dialog" aria-modal="true" aria-label="单样本推理验证">
          <div class="infer-modal-head">
            <div>
              <h3>单样本推理验证</h3>
              <p>用于模型链路验证，不回写上方静态指标。</p>
            </div>
            <button
              class="infer-modal-close"
              type="button"
              aria-label="关闭"
              @click="showInferModal = false"
            >
              ×
            </button>
          </div>
          <RiskEvalInferTab :datasets="inferDatasets" />
        </section>
      </div>
    </Teleport>
    <div class="footer-note">
      指标来自当前选中的课题三风险评测对象，样本和结果使用同一资产版本与内容哈希。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useOutputStore } from '@/stores/output'
import RiskEvalInferTab from './RiskEvalInferTab.vue'
import Topic3RiskVersionPanel from './Topic3RiskVersionPanel.vue'
import { normalizeCategoryList } from './normalizeCategoryList'
import type { SampleItem } from './samplesData'

const store = useOutputStore()

const showInferModal = ref(false)

const step1Datasets = computed(() => store.selectedRiskDatasets)
const topic3 = computed(() => store.topic3RiskView)
const inferDatasets = computed(() => {
  const view = topic3.value
  const selected = step1Datasets.value
  if (!view) return selected
  if (selected.some((item) => item.datasetId === view.asset_id)) return selected
  return [
    {
      datasetId: view.asset_id,
      name: `${view.name} · ${view.asset_version ?? ''}`,
      recordCount: view.sample_count ?? 0,
    },
    ...selected,
  ]
})
const activeDatasetId = computed(() => topic3.value?.asset_id || '—')
const activeDsTask = computed(() => store.staticResultMeta?.task || '—')
const isMultilabelTask = computed(() =>
  ['multilabel_then_severity', 'joint_level_then_multilabel'].includes(activeDsTask.value),
)
const showSampleSection = computed(
  () => isMultilabelTask.value || (topic3.value?.sample_details.length ?? 0) > 0,
)
const isStaticPredictionUnavailable = computed(
  () => store.staticPredictionsSource === 'unavailable',
)

function onAssetVersionChange(assetVersion: string) {
  void store.loadTopic3RiskSameVersion(assetVersion)
}

onMounted(() => {
  void store.loadTopic3RiskSameVersion()
})

// 从 store 透传的全部 API 字段中按名取值，缺失返回 null → fmt() 显示"数据缺失"
function apiVal(...keys: string[]): number | null {
  const m = store.staticRawMetrics
  if (!m) return null
  for (const k of keys) {
    const v = m[k]
    if (v != null) return v
  }
  return null
}

const metrics = computed(() => ({
  riskRecall: apiVal('risk_recall'),
  fpr: apiVal('risk_false_positive_rate', 'fpr'),
  severityAcc: apiVal('risk_severity_accuracy'),
  jaccard: apiVal('jaccard_accuracy'),
  microF1: apiVal('micro_f1'),
  macroF1: apiVal('macro_f1'),
  v3: apiVal('risk_class_accuracy_v3', 'risk_class_acc'),
  v4: apiVal('risk_class_accuracy_v4_first_label'),
  v5: apiVal('risk_class_accuracy_v5_exact_match'),
  safePrecision: apiVal('precision_safe_unsafe', 'precision'),
  safeF1: apiVal('f1_safe_unsafe', 'f1'),
  safeAccuracy: apiVal('accuracy_safe_unsafe', 'accuracy'),
}))

function fmt(v: unknown): string {
  if (v == null) {
    return store.staticRawMetrics === null ? '后端不可达' : '评测无该字段'
  }
  if (typeof v === 'number') {
    const s = v.toFixed(4)
    return s.replace(/0+$/, '').replace(/\.$/, '')
  }
  return String(v)
}
function fmtPct(v: unknown): string {
  if (v == null) {
    return store.staticRawMetrics === null ? '后端不可达' : '评测无该字段'
  }
  if (typeof v === 'number') return `${(v * 100).toFixed(2)}%`
  return String(v)
}
function fmtInt(v: unknown): string {
  if (v == null) {
    return store.staticRawMetrics === null ? '后端不可达' : '评测无该字段'
  }
  if (typeof v === 'number') return v.toLocaleString()
  return String(v)
}

/** 长哈希/ID 只展示前缀，完整值放在 title 里，避免撑开网格列宽。 */
function shortHash(v: string | null | undefined, max = 12): string {
  if (!v) return '—'
  return v.length > max ? `${v.slice(0, max)}…` : v
}

// 数据规模与命中统计 — 从 staticRawMetrics 动态计算
const stats = computed(() => {
  const m = store.staticRawMetrics
  return {
    total: m?.num_examples ?? null,
    riskTotal: m?.risk_total ?? null,
    safeTotal: m?.safe_total ?? null,
    v3Hit: m?.risk_class_correct_v3 ?? null,
    v4Hit: m?.risk_class_correct_v4_first_label ?? null,
    v5Hit: m?.risk_class_correct_v5_exact_match ?? null,
    severityCorrect: m?.risk_severity_correct ?? null,
    fpCount: m?.risk_false_positive_count ?? null,
    severityRequests: m?.num_severity_requests ?? null,
    microTP: m?.micro_tp ?? null,
    microFP: m?.micro_fp ?? null,
    microFN: m?.micro_fn ?? null,
    tp: m?.tp ?? null,
    tn: m?.tn ?? null,
    fp: m?.fp ?? null,
    fn: m?.fn ?? null,
  }
})

const catNames: Record<string, string> = {
  C01: '煽动颠覆国家政权',
  C02: '危害国家安全和利益',
  C03: '煽动分裂国家',
  C04: '宣扬恐怖主义',
  C05: '宣扬民族仇恨',
  C06: '宣扬暴力淫秽',
  C07: '传播虚假有害信息',
  C08: '歧视性内容',
  C09: '商业违法违规',
  C10: '侵犯他人权益',
  C11: '无法满足安全需求',
  C12: '经济损失高风险',
  C13: '未成年人安全',
  C14: '欺诈虐待掠夺',
  C15: '不正确民族叙事',
  C16: '民族情感商业化',
  C17: '价值导向偏差',
}
const selectedRiskCodes = computed(() =>
  store.riskDimensions
    .filter((dim) => dim.selected && /^C\d{2}$/.test(dim.key))
    .map((dim) => dim.key),
)
const displayRiskCodes = computed(() => {
  if (selectedRiskCodes.value.length) return selectedRiskCodes.value
  return Object.keys(store.staticPerCategory || {})
    .filter((code) => /^C\d{2}$/.test(code))
    .sort()
})
const selectedRiskCodeSet = computed(() => new Set(displayRiskCodes.value))
const selectedRiskScopeShort = computed(() =>
  selectedRiskCodes.value.length
    ? `治理标准体系 ${selectedRiskCodes.value.length} 类`
    : '全量风险类别',
)
const sampleFilter = ref('all')
const selectedSampleIdx = ref(0)
const LEVEL_MAP: Record<number, string> = { 1: '低风险', 2: '中风险', 3: '高风险' }

function mapPredictionRow(row: Record<string, unknown>): SampleItem {
  const gold = normalizeCategoryList(row.gold_categories ?? row.gold_category ?? row.risk_category)
  const predictionMissing = row.prediction_missing === true
  const predKnown =
    !predictionMissing && (Array.isArray(row.pred_categories) || row.pred_category != null)
  const pred = predKnown ? normalizeCategoryList(row.pred_categories ?? row.pred_category) : []
  const listedOverlap = Array.isArray(row.category_overlap)
    ? (row.category_overlap as string[])
    : []
  const overlap = listedOverlap.length ? listedOverlap : gold.filter((code) => pred.includes(code))
  const miss = predKnown ? gold.filter((g: string) => !pred.includes(g)) : []
  const fp = predKnown ? pred.filter((p: string) => !gold.includes(p)) : []
  const predLevels = (row.pred_category_levels || {}) as Record<string, number>
  const example = (row.example || {}) as Record<string, string>
  const hasOverlap = overlap.length > 0
  const levelOk = !!row.risk_severity_correct
  let status: string
  if (predictionMissing || !predKnown) status = 'missing'
  else if (!hasOverlap) status = 'miss'
  else if (!levelOk) status = 'level'
  else if (gold.length !== pred.length || miss.length > 0) status = 'partial'
  else status = 'hit'
  return {
    id: `#${row.index}`,
    status,
    level: LEVEL_MAP[(row.gold_level as number) || 1] || '中风险',
    gold,
    pred,
    hit: overlap,
    miss,
    fp,
    v3: !!row.risk_class_correct_v3,
    v4: !!row.risk_class_correct_v4_first_label,
    v5: !!row.risk_class_correct_v5_exact_match,
    levelOk,
    predLevels: Object.fromEntries(
      Object.entries(predLevels).map(([k, v]) => [k, LEVEL_MAP[v] || `${v}`]),
    ),
    raw:
      (row.raw_output as string) ||
      (row.raw_classification as string) ||
      (row.model_output as string) ||
      '',
    prompt: example.prompt || '',
    response: example.response || (example.text as string) || '',
  }
}

const predictionSamples = computed<SampleItem[]>(() =>
  store.staticPredictions.map(mapPredictionRow),
)
const filteredSamples = computed<SampleItem[]>(() => {
  const selectedCodes = selectedRiskCodeSet.value
  const scopedList =
    selectedCodes.size && selectedRiskCodes.value.length
      ? predictionSamples.value.filter((sample) =>
          [...sample.gold, ...sample.pred, ...sample.hit, ...sample.miss, ...sample.fp].some(
            (code) => selectedCodes.has(code),
          ),
        )
      : predictionSamples.value
  const list = scopedList
  if (!list.length) return []
  if (sampleFilter.value === 'all') return list
  return list.filter((s) => s.status === sampleFilter.value)
})
const activeSample = computed<SampleItem | null>(
  () => filteredSamples.value[selectedSampleIdx.value] || null,
)
</script>

<style src="./OutputRiskEval.css" scoped></style>
