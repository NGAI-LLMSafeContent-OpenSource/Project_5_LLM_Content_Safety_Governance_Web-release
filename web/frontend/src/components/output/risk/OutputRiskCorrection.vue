<!-- eslint-disable vue/no-v-html -->
<template>
  <div class="risk-correction">
    <h2 class="track-title">修正（风险）</h2>
    <!-- Stats -->
    <div class="eval-card">
      <div class="stage-section">
        <h4 class="section-label">一、数据集统计信息</h4>
        <div class="count-grid">
          <div class="count-card count-card--total">
            <div class="count-val">{{ correctionStats.total }}</div>
            <div class="count-lbl">总量</div>
          </div>
          <div class="count-card count-card--risk">
            <div class="count-val">100.00%</div>
            <div class="count-lbl">编辑前风险</div>
          </div>
          <div class="count-card count-card--safe">
            <div class="count-val">{{ correctionStats.safePct }}</div>
            <div class="count-lbl">编辑后 Safe</div>
          </div>
          <div class="count-card count-card--review">
            <div class="count-val">{{ correctionStats.review }}</div>
            <div class="count-lbl">人工复核</div>
          </div>
          <div class="count-card count-card--edit-rate">
            <div class="count-val">92.9%</div>
            <div class="count-lbl">编辑成功率</div>
          </div>
          <div class="count-card count-card--retention">
            <div class="count-val">97.5%</div>
            <div class="count-lbl">无害内容保留率</div>
          </div>
        </div>
        <p class="section-hint">
          基于合规编辑工具 H1-H4 基准测试集统计，所有样本编辑前均判定为有害
        </p>
      </div>
    </div>
    <!-- Examples -->
    <div class="eval-card" style="margin-top: 16px">
      <div class="stage-section" style="border: none; padding-bottom: 0">
        <h4 class="section-label">二、个例展示</h4>
        <nav class="ce-tabs">
          <button
            v-for="t in tabs"
            :key="t.key"
            :class="{ active: activeTab === t.key }"
            @click="activeTab = t.key"
          >
            {{ t.label }}
          </button>
        </nav>
        <div v-if="loading" class="ce-status">加载合规编辑数据中...</div>
        <div v-else-if="error" class="ce-status ce-status--err">{{ error }}</div>
        <div v-else class="ce-workbench">
          <!-- Left Sample Pane -->
          <section class="ce-sample-pane">
            <div class="ce-pane-head">
              <div class="ce-sample-title-tools">
                <h2>样本选择</h2>
                <label v-if="activeTab === 'single'" class="ce-lang-pick">
                  <select v-model="selectedLang" @change="selectedIdx = 0">
                    <option v-for="l in languages" :key="l" :value="l">{{ l }}</option>
                  </select>
                </label>
                <label v-else-if="activeTab === 'batch'" class="ce-lang-pick">
                  <select v-model="h1h4Lang" @change="h1h4Idx = 0">
                    <option v-for="l in h1h4Langs" :key="l" :value="l">{{ l }}</option>
                  </select>
                </label>
                <label v-else-if="activeTab === 'prompt'" class="ce-lang-pick">
                  <select v-model="promptLang" @change="promptIdx = 0">
                    <option v-for="l in promptLangs" :key="l" :value="l">{{ l }}</option>
                  </select>
                </label>
              </div>
            </div>
            <div class="ce-sample-meta">
              {{ activeSampleCount }}
              条样本
            </div>
            <!-- Upstream risk samples from Step 3/4 -->
            <div v-if="activeTab === 'chain'" class="ce-sample-list">
              <button
                v-for="(s, i) in chainRiskSamples"
                :key="s.id"
                class="ce-sample-card"
                :class="{ selected: chainIdx === i }"
                @click="chainIdx = i"
              >
                <div class="ce-sample-meta-row">
                  <span class="ce-sample-idx">{{ s.id }}</span>
                  <span class="ce-sample-lvl">{{ s.level }}</span>
                  <span class="ce-sample-cat">{{ s.category || '—' }}</span>
                </div>
                <p class="ce-sample-output">{{ h1h4Preview(s.text) }}</p>
              </button>
            </div>
            <!-- Demo bundle samples (single tab) -->
            <div v-else-if="activeTab === 'single'" class="ce-sample-list">
              <button
                v-for="(s, i) in currentLangSamples"
                :key="i"
                class="ce-sample-card"
                :class="{ selected: selectedIdx === i }"
                @click="selectedIdx = i"
              >
                <div class="ce-sample-meta-row">
                  <span class="ce-sample-idx">#{{ i + 1 }}</span>
                  <span class="ce-sample-lvl">{{ s.categories[0] || '—' }}</span>
                  <span class="ce-sample-cat">{{ s.risk_category || '—' }}</span>
                </div>
                <p v-if="s.prompt" class="ce-sample-prompt">{{ s.prompt }}</p>
                <p class="ce-sample-output">{{ s.text }}</p>
              </button>
            </div>
            <!-- h1h4 samples (batch tab) -->
            <div v-else-if="activeTab === 'batch'" class="ce-sample-list">
              <button
                v-for="(s, i) in h1h4SamplesComputed"
                :key="i"
                class="ce-sample-card"
                :class="{ selected: h1h4Idx === i }"
                @click="h1h4Idx = i"
              >
                <div class="ce-sample-meta-row">
                  <span class="ce-sample-idx">{{ h1h4SampleId(s, i) }}</span>
                  <span v-if="s.difficulty_level" class="ce-sample-lvl">
                    {{ s.difficulty_level }}
                  </span>
                  <span v-if="s.risk_category" class="ce-sample-cat">{{ s.risk_category }}</span>
                </div>
                <p class="ce-sample-prompt">{{ h1h4Preview(s.text) }}</p>
                <p class="ce-sample-output">{{ h1h4Preview(s.edited_text) }}</p>
              </button>
            </div>
            <!-- Prompt samples -->
            <div v-else-if="activeTab === 'prompt'" class="ce-sample-list">
              <button
                v-for="(s, i) in promptSamplesComputed"
                :key="i"
                class="ce-sample-card"
                :class="{ selected: promptIdx === i }"
                @click="promptIdx = i"
              >
                <div class="ce-sample-meta-row">
                  <span class="ce-sample-idx">#{{ i + 1 }}</span>
                  <span class="ce-sample-lvl">
                    {{ s.difficulty_level || s.categories[0] || '—' }}
                  </span>
                </div>
                <p v-if="s.prompt" class="ce-sample-prompt">{{ s.prompt }}</p>
                <p class="ce-sample-output">{{ s.edited_text || s.text }}</p>
              </button>
            </div>
          </section>
          <!-- Right Content -->
          <section
            class="ce-content-pane"
            :class="{
              'ce-result-layout': activeTab !== 'single',
              'ce-prompt-layout': activeTab === 'prompt',
            }"
          >
            <template v-if="activeTab === 'chain'">
              <div class="ce-pane-head">
                <h2>前序风险样本修正</h2>
              </div>
              <div v-if="chainSample" class="result-grid prompt-result-grid">
                <section class="ce-block">
                  <h3>评估/归因文本</h3>
                  <pre>{{ chainSample.text }}</pre>
                </section>
                <section class="ce-block">
                  <h3>风险信息</h3>
                  <div class="result-metrics">
                    <div>
                      <span>风险等级</span>
                      <strong>{{ chainSample.level }}</strong>
                    </div>
                    <div>
                      <span>风险类别</span>
                      <strong>{{ chainSample.category || '—' }}</strong>
                    </div>
                    <div>
                      <span>来源</span>
                      <strong>{{ chainSample.source }}</strong>
                    </div>
                  </div>
                  <pre class="ce-block-pre">{{ chainSample.reason || '等待接入编辑器自动改写结果' }}</pre>
                </section>
                <section class="ce-block ce-block--safe">
                  <h3>修正建议</h3>
                  <pre>{{ chainSample.suggestion }}</pre>
                </section>
              </div>
              <div v-else class="ce-status">
                暂无前序风险样本，请先完成 Step3 评估或 Step4 归因。
              </div>
            </template>
            <template v-else-if="activeTab === 'single'">
              <div class="ce-pane-head">
                <h2>单条编辑</h2>
                <div class="ce-btn-row">
                  <button class="ce-btn" :disabled="!sample" @click="resetEdit">重置</button>
                  <button
                    class="ce-btn ce-btn--pri"
                    :disabled="!sample || editPlaying"
                    @click="playEdits"
                  >
                    {{ editPlaying ? '播放中...' : '运行编辑' }}
                  </button>
                </div>
              </div>
              <div class="ce-lifecycle">
                <div class="ce-lifecycle-flow">
                  <span>Prompt</span>
                  <strong>Qwen3.5-9B</strong>
                  <span>模型输出</span>
                  <strong>编辑工具</strong>
                  <span>编辑结果</span>
                </div>
                <div class="ce-stage-grid">
                  <article class="ce-stage">
                    <div class="ce-stage-head">
                      <span>Prompt</span>
                      <strong>#{{ selectedIdx + 1 }}</strong>
                    </div>
                    <pre>{{ sample?.prompt || '—' }}</pre>
                  </article>
                  <article class="ce-stage ce-stage--output">
                    <div class="ce-stage-head">
                      <span>模型输出</span>
                      <strong>编辑对象</strong>
                    </div>
                    <div class="ce-annotated">
                      <span v-for="(seg, j) in annoSegs" :key="j" :class="seg.type">
                        {{ seg.text }}
                      </span>
                    </div>
                  </article>
                  <article class="ce-stage ce-stage--edited">
                    <div class="ce-stage-head">
                      <span>编辑结果</span>
                      <button class="ce-btn ce-btn--small" @click="copyEdited">复制</button>
                    </div>
                    <pre>{{ editDone ? sample?.edited_text || sample?.text : '等待运行' }}</pre>
                  </article>
                </div>
              </div>
              <!-- Process + Metrics -->
              <div class="ce-analysis-grid">
                <section class="ce-block process-block">
                  <h3>编辑过程</h3>
                  <div v-if="editProcessSteps.length" class="edit-list">
                    <div class="process-live-shell">
                      <div class="process-flow">
                        <template v-for="(ps, k) in editProcessSteps" :key="k">
                          <div
                            class="process-flow-step"
                            :class="{
                              done: ps.state === 'done',
                              failed: ps.state === 'error',
                              running: ps.state === 'running',
                              active: ps.active,
                            }"
                          >
                            <span>
                              {{
                                ps.state === 'done' ? '✓' : ps.state === 'error' ? '✗' : ps.index
                              }}
                            </span>
                            <strong>{{ ps.title }}</strong>
                          </div>
                          <div
                            v-if="k < editProcessSteps.length - 1"
                            class="process-flow-line"
                          ></div>
                        </template>
                      </div>
                      <article class="process-live-panel" :class="activePanelState">
                        <div class="step-body">
                          <div class="step-head">
                            <span>{{ activeProcessStep?.agent || '' }}</span>
                            <strong>{{ activeProcessStep?.statusText || '' }}</strong>
                          </div>
                          <h4>{{ activeProcessStep?.title || '' }}</h4>
                          <div class="process-card compact live-card">
                            <div class="live-draft" :class="activeDraftTone">
                              <div class="live-draft-body" v-html="activeDraftHtml"></div>
                            </div>
                          </div>
                        </div>
                      </article>
                    </div>
                  </div>
                  <div v-else class="empty">点击"运行编辑"后展示 Agent 识别、改写和复检过程</div>
                </section>
                <section class="ce-block">
                  <div class="ce-metrics-head">
                    <h3>指标</h3>
                    <div class="ce-metric-strip">
                      <div>
                        <span>复检</span>
                        <strong :class="qlClass">{{ qualityLabel }}</strong>
                      </div>
                      <div>
                        <span>处置</span>
                        <strong>{{ sample?.disposition || '—' }}</strong>
                      </div>
                      <div>
                        <span>耗时</span>
                        <strong>
                          {{
                            sample?.elapsed_seconds ? sample.elapsed_seconds.toFixed(1) + 's' : '—'
                          }}
                        </strong>
                      </div>
                    </div>
                  </div>
                  <details class="ce-raw">
                    <summary>JSON</summary>
                    <pre>{{
                      sample
                        ? JSON.stringify({ edits: sample.edits, quality: sample.quality }, null, 2)
                        : '{}'
                    }}</pre>
                  </details>
                </section>
              </div>
            </template>
            <template v-if="activeTab === 'batch'">
              <div class="ce-pane-head"><h2>拼接数据结果</h2></div>
              <div class="ce-batch-grid">
                <section class="ce-block">
                  <h3>
                    待编辑数据（标注视图）
                    <span class="ce-legend">
                      <i class="ce-legend-d ce-legend-d--h"></i>
                      有害
                    </span>
                    <span class="ce-legend">
                      <i class="ce-legend-d ce-legend-d--s"></i>
                      无害
                    </span>
                  </h3>
                  <div class="ce-annotated">
                    <span v-for="(seg, j) in h1h4AnnoSegs" :key="j" :class="seg.type">
                      {{ seg.text }}
                    </span>
                  </div>
                </section>
                <section class="ce-block">
                  <h3>编辑结果</h3>
                  <pre class="ce-block-pre">{{ h1h4Sample?.edited_text || '—' }}</pre>
                  <button class="ce-btn ce-btn--small" @click="copyH1h4Edited">复制</button>
                </section>
              </div>
              <div class="ce-metric-strip" style="margin-top: 10px">
                <div>
                  <span>分级</span>
                  <strong>{{ h1h4Sample?.difficulty_level || '—' }}</strong>
                </div>
                <div>
                  <span>复检</span>
                  <strong
                    :class="
                      h1h4Sample?.quality?.post_safety_label?.toLowerCase() === 'safe'
                        ? 'metric-s'
                        : 'metric-u'
                    "
                  >
                    {{ h1h4Sample?.quality?.post_safety_label || '—' }}
                  </strong>
                </div>
                <div>
                  <span>保留率</span>
                  <strong>{{ h1h4Retention }}</strong>
                </div>
              </div>
            </template>
            <template v-if="activeTab === 'prompt'">
              <div class="ce-pane-head">
                <div class="result-title"><h2>真实 Prompt 结果</h2></div>
                <div v-if="promptSample" class="result-summary">
                  <div>
                    <span>总量</span>
                    <strong>{{ promptSamplesComputed.length }}</strong>
                  </div>
                  <div>
                    <span>编辑前</span>
                    <strong>有害</strong>
                  </div>
                  <div>
                    <span>编辑后Safe</span>
                    <strong>{{ promptSafeCount }}</strong>
                  </div>
                </div>
              </div>
              <div class="result-grid prompt-result-grid">
                <article class="ce-stage">
                  <div class="ce-stage-head">
                    <span>Prompt</span>
                    <strong>#{{ promptIdx + 1 }}</strong>
                  </div>
                  <pre>{{ promptSample?.prompt || '—' }}</pre>
                </article>
                <article class="ce-stage ce-stage--output">
                  <div class="ce-stage-head">
                    <span>原始模型输出</span>
                    <strong>Qwen3.5-9B</strong>
                  </div>
                  <pre>{{ promptSample?.text || '—' }}</pre>
                </article>
                <article class="ce-stage ce-stage--edited">
                  <div class="ce-stage-head">
                    <span>编辑结果</span>
                    <button class="ce-btn ce-btn--small" @click="copyPromptEdited">复制</button>
                  </div>
                  <pre>{{ promptSample?.edited_text || '—' }}</pre>
                </article>
                <section class="ce-block">
                  <div class="ce-metrics-head">
                    <h3>指标</h3>
                    <div class="ce-metric-strip">
                      <div>
                        <span>编辑前</span>
                        <strong class="metric-u">有害</strong>
                      </div>
                      <div>
                        <span>编辑后</span>
                        <strong :class="promptQlClass">
                          {{ promptSample?.quality?.post_safety_label || '—' }}
                        </strong>
                      </div>
                      <div>
                        <span>处置</span>
                        <strong>{{ promptSample?.disposition || '—' }}</strong>
                      </div>
                    </div>
                  </div>
                  <details class="ce-raw">
                    <summary>JSON</summary>
                    <pre>{{
                      promptSample
                        ? JSON.stringify(
                            { edits: promptSample.edits, quality: promptSample.quality },
                            null,
                            2,
                          )
                        : '{}'
                    }}</pre>
                  </details>
                </section>
              </div>
            </template>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useComplianceData, type ComplianceSample } from '@/composables/output/useComplianceData'
import { useToast } from '@/composables/common/useToast'
import { useOutputStore } from '@/stores/output'

const {
  loading,
  error,
  languages,
  langSamples,
  load,
  promptLangSamples,
  loadPrompt,
  h1h4LangSamples,
  h1h4Summary,
  loadH1h4,
} = useComplianceData()
const toast = useToast()
const store = useOutputStore()

const tabs = [
  { key: 'chain' as const, label: '前序风险样本' },
  { key: 'single' as const, label: '单条编辑演示' },
  { key: 'batch' as const, label: '拼接数据结果' },
  { key: 'prompt' as const, label: '真实 Prompt 结果' },
]
const activeTab = ref<'chain' | 'single' | 'batch' | 'prompt'>('chain')
const selectedLang = ref('zh')
const selectedIdx = ref(0)
const chainIdx = ref(0)
const editPlaying = ref(false)
const editDone = ref(false)

interface ChainRiskSample {
  id: string
  text: string
  level: string
  category: string
  reason: string
  source: string
  suggestion: string
}

const chainRiskSamples = computed<ChainRiskSample[]>(() => {
  const attributionSamples = store.riskAttributionNodes
    .filter((node) => !!node.text)
    .map((node) => ({
      id: node.id,
      text: node.text || '',
      level: node.overall || 'LOW',
      category: node.predCategories?.join('、') || Object.keys(node.signals || {}).join('、'),
      reason: node.reasonPath || node.chain,
      source: store.riskAttributionSource === 'live' ? 'Step4 Benchmark 归因' : 'Step4 本地样例',
      suggestion: '请基于风险证据删除、弱化或替换有害表达，并保留无害上下文信息。',
    }))
  if (attributionSamples.length > 0) return attributionSamples
  return store.evalRiskSamples.map((sample) => ({
    id: sample.id,
    text: sample.text,
    level: String(sample.predLevel || sample.overallLevel || 'LOW'),
    category: sample.predCategoryCode || sample.predCategory || sample.goldCategoryCode || '',
    reason: sample.summary,
    source: 'Step3 评估结果',
    suggestion: '请根据评估出的风险等级与类别生成安全改写，并保留原始任务语义。',
  }))
})

const chainSample = computed(() => chainRiskSamples.value[chainIdx.value] || null)
const activeSampleCount = computed(() => {
  if (activeTab.value === 'chain') return chainRiskSamples.value.length
  if (activeTab.value === 'prompt') return promptSamplesComputed.value.length
  if (activeTab.value === 'batch') return h1h4SamplesComputed.value.length
  return currentLangSamples.value.length
})

interface ProcessStep {
  index: number
  key: string
  title: string
  agent: string
  statusText: string
  state: string
  active: boolean
  draftHtml: string
  draftTone: string
}
const editProcessSteps = ref<ProcessStep[]>([])
const activeStepIdx = ref(-1)
const activeProcessStep = computed(() => editProcessSteps.value[activeStepIdx.value] || null)
const activeDraftHtml = computed(() => activeProcessStep.value?.draftHtml || '')
const activeDraftTone = computed(() => activeProcessStep.value?.draftTone || '')
const activePanelState = computed(() => activeProcessStep.value?.state || '')

const currentLangSamples = computed(() => langSamples.value[selectedLang.value] || [])
const sample = computed(() => currentLangSamples.value[selectedIdx.value] || null)

const annoSegs = computed(() => {
  const s = sample.value
  if (!s?.text) return []
  const text = s.text
  const spans: Array<{ start: number; end: number; type: string }> = []
  for (const h of s.harmful_spans) spans.push({ ...h, type: 'harmful' })
  for (const h of s.harmless_spans) spans.push({ ...h, type: 'harmless' })
  spans.sort((a, b) => a.start - b.start)
  if (!spans.length) return [{ text, type: '' }]
  const segs: Array<{ text: string; type: string }> = []
  let pos = 0
  for (const sp of spans) {
    if (sp.start > pos) segs.push({ text: text.substring(pos, sp.start), type: '' })
    segs.push({ text: text.substring(sp.start, sp.end), type: sp.type })
    pos = sp.end
  }
  if (pos < text.length) segs.push({ text: text.substring(pos), type: '' })
  return segs
})
// Batch (h1h4) tab state
const h1h4Lang = ref('zh-Hans')
const h1h4Idx = ref(0)
const h1h4Langs = computed(() => Object.keys(h1h4LangSamples.value).sort())
const h1h4SamplesComputed = computed(() => h1h4LangSamples.value[h1h4Lang.value] || [])
const h1h4Sample = computed(() => h1h4SamplesComputed.value[h1h4Idx.value] || null)
const h1h4AnnoSegs = computed(() => {
  const s = h1h4Sample.value
  if (!s?.text) return []
  const text = s.text
  const spans: Array<{ start: number; end: number; type: string }> = []
  for (const h of s.harmful_spans) spans.push({ ...h, type: 'harmful' })
  for (const h of s.harmless_spans) spans.push({ ...h, type: 'harmless' })
  spans.sort((a, b) => a.start - b.start)
  if (!spans.length) return [{ text, type: '' }]
  const segs: Array<{ text: string; type: string }> = []
  let pos = 0
  for (const sp of spans) {
    if (sp.start > pos) segs.push({ text: text.substring(pos, sp.start), type: '' })
    segs.push({ text: text.substring(sp.start, sp.end), type: sp.type })
    pos = sp.end
  }
  if (pos < text.length) segs.push({ text: text.substring(pos), type: '' })
  return segs
})
const correctionStats = computed(() => {
  if (h1h4Summary.value) {
    const s = h1h4Summary.value
    const safePct = s.total > 0 ? ((s.safeCount / s.total) * 100).toFixed(1) + '%' : '—'
    return { total: s.total, safePct, review: s.reviewCount }
  }
  return { total: '7,446', safePct: '38.71%', review: '4,564' }
})
const h1h4Retention = computed(() => {
  const r = h1h4Sample.value?.quality?.unchanged_non_risk_ratio
  return r != null ? (r * 100).toFixed(1) + '%' : '—'
})
function h1h4SampleId(s: ComplianceSample, pos: number): string {
  const sid = String(s.source_id || s.risk_category_id || '')
  const m = sid.match(/(\d{4,})(?!.*\d)/)
  if (m) return m[1]
  const idx = Number(s.index)
  return Number.isInteger(idx) ? String(idx + 1).padStart(6, '0') : String(pos + 1).padStart(6, '0')
}
function h1h4Preview(v: string): string {
  const compact = String(v || '')
    .replace(/\s+/g, ' ')
    .trim()
  return compact.length > 140 ? compact.slice(0, 140) + '...' : compact
}
function copyH1h4Edited() {
  if (h1h4Sample.value?.edited_text)
    navigator.clipboard.writeText(h1h4Sample.value.edited_text).then(
      () => toast.success('已复制', ''),
      () => toast.error('复制失败', ''),
    )
}

// Prompt tab state
const promptLang = ref('zh-Hans')
const promptIdx = ref(0)
const promptLangs = computed(() => Object.keys(promptLangSamples.value).sort())
const promptSamplesComputed = computed(() => promptLangSamples.value[promptLang.value] || [])
const promptSample = computed(() => promptSamplesComputed.value[promptIdx.value] || null)
const promptQlClass = computed(() => {
  const l = (promptSample.value?.quality?.post_safety_label || '').toLowerCase()
  return l === 'safe' ? 'metric-s' : l === 'unsafe' ? 'metric-u' : ''
})
const promptSafeCount = computed(
  () =>
    promptSamplesComputed.value.filter(
      (s: ComplianceSample) => (s.quality?.post_safety_label || '').toLowerCase() === 'safe',
    ).length,
)
function copyPromptEdited() {
  if (promptSample.value?.edited_text)
    navigator.clipboard.writeText(promptSample.value.edited_text).then(
      () => toast.success('已复制', ''),
      () => toast.error('复制失败', ''),
    )
}

const qualityLabel = computed(() => sample.value?.quality?.post_safety_label || '—')
const qlClass = computed(() => {
  const l = qualityLabel.value.toLowerCase()
  return l === 'safe' ? 'metric-s' : l === 'unsafe' ? 'metric-u' : ''
})

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildMarkedDraft(
  mode: 'risk' | 'preview' | 'replace',
  items: Array<Record<string, unknown>>,
  fullText: string,
): string {
  if (mode === 'risk') {
    const spans = items
      .filter((it) => it.start !== undefined && it.end !== undefined)
      .map((it) => ({
        start: it.start as number,
        end: it.end as number,
        text: (it.text as string) || fullText.substring(it.start as number, it.end as number),
      }))
      .sort((a, b) => a.start - b.start)
    if (!spans.length) return esc(fullText)
    let out = ''
    let pos = 0
    for (const sp of spans) {
      if (sp.start > pos) out += esc(fullText.substring(pos, sp.start))
      out += `<mark class="draft-risk">${esc(sp.text)}</mark>`
      pos = sp.end
    }
    if (pos < fullText.length) out += esc(fullText.substring(pos))
    return out
  }
  if (mode === 'preview') {
    return items
      .map((ed) => {
        const o =
          esc(String(ed.original || '').substring(0, 150)) +
          (String(ed.original || '').length > 150 ? '...' : '')
        const r =
          esc(String(ed.replacement || '').substring(0, 150)) +
          (String(ed.replacement || '').length > 150 ? '...' : '')
        return `<div class="rewrite-row"><mark class="draft-risk">${o}</mark><span class="draft-suggestion">${r}</span></div>`
      })
      .join('')
  }
  const edits = items
    .filter((it) => it.start !== undefined && it.end !== undefined)
    .sort((a, b) => (a.start as number) - (b.start as number))
  if (!edits.length) return esc(fullText)
  let out = ''
  let pos = 0
  for (const ed of edits) {
    const st = ed.start as number
    const en = ed.end as number
    if (st > pos) out += esc(fullText.substring(pos, st))
    out += `<span class="draft-delete">${esc(fullText.substring(st, en))}</span><span class="draft-insert">${esc(String(ed.replacement || '').substring(0, 150))}${String(ed.replacement || '').length > 150 ? '...' : ''}</span>`
    pos = en
  }
  if (pos < fullText.length) out += esc(fullText.substring(pos))
  return out
}

function buildProcessSteps(): ProcessStep[] {
  if (!sample.value) return []
  const s = sample.value
  const edList = s.edits
  const text = s.text
  const isZh = selectedLang.value === 'zh'
  // For non-Chinese: editing happens on the Chinese translation, then translated back
  const zhText = s.translated_input_zh || text
  const zhEdited = s.edited_text_zh || s.edited_text || text
  const steps: ProcessStep[] = []

  if (!isZh) {
    // Show original + Chinese translation side by side
    const transHtml = `<div class="translation-pair"><div class="translation-side"><span class="trans-label">原文 (${selectedLang.value})</span>${esc(text)}</div><div class="translation-side"><span class="trans-label">中文翻译</span>${esc(zhText)}</div></div>`
    steps.push({
      index: 1,
      key: 'translate_to_zh',
      title: '翻译为中文',
      agent: 'Hy-MT2 翻译 Agent',
      statusText: '完成',
      state: 'done',
      active: false,
      draftHtml: transHtml,
      draftTone: '',
    })
  }

  const baseIdx = steps.length
  // Editing happens on the Chinese text (if available), otherwise on original
  const editText = isZh ? text : zhText || text
  const finalText = isZh ? zhEdited || text : text
  steps.push(
    {
      index: baseIdx + 1,
      key: 'identify',
      title: '识别 Unsafe 片段',
      agent: '编辑 Agent',
      statusText: '完成',
      state: 'done',
      active: false,
      draftHtml: buildMarkedDraft(
        'risk',
        s.harmful_spans.length > 0
          ? s.harmful_spans.map((sp) => ({
              start: sp.start,
              end: sp.end,
              text: editText.substring(sp.start, sp.end),
            }))
          : [],
        editText,
      ),
      draftTone: '',
    },
    {
      index: baseIdx + 2,
      key: 'rewrite',
      title: '生成局部改写',
      agent: '编辑 Agent',
      statusText: `完成 (${edList.length} 处)`,
      state: 'done',
      active: false,
      draftHtml: buildMarkedDraft(
        'preview',
        edList.map((ed) => ({ original: ed.original, replacement: ed.replacement })),
        '',
      ),
      draftTone: '',
    },
    {
      index: baseIdx + 3,
      key: 'align',
      title: '对齐并拼接',
      agent: 'Span 对齐器',
      statusText: '完成',
      state: 'done',
      active: false,
      draftHtml: buildMarkedDraft(
        'replace',
        edList.map((ed) => ({ start: ed.start, end: ed.end, replacement: ed.replacement })),
        editText,
      ),
      draftTone: '',
    },
    {
      index: baseIdx + 4,
      key: 'guard',
      title: '验收编辑结果',
      agent: 'Qwen3Guard 复检 Agent',
      statusText: qualityLabel.value.toLowerCase() === 'safe' ? '通过' : qualityLabel.value,
      state: qualityLabel.value.toLowerCase() === 'safe' ? 'done' : 'error',
      active: false,
      draftHtml: esc(zhEdited || finalText),
      draftTone: qualityLabel.value.toLowerCase() === 'safe' ? 'final-safe' : 'final-unsafe',
    },
  )

  if (!isZh) {
    const backHtml = `<div class="translation-pair"><div class="translation-side"><span class="trans-label">编辑后中文</span>${esc(zhEdited)}</div><div class="translation-side"><span class="trans-label">回译 ${selectedLang.value}</span>${esc(s.edited_text || text)}</div></div>`
    steps.push({
      index: baseIdx + 5,
      key: 'translate_to_source',
      title: '回译原语言',
      agent: 'Hy-MT2 翻译 Agent',
      statusText: '完成',
      state: 'done',
      active: false,
      draftHtml: backHtml,
      draftTone: qualityLabel.value.toLowerCase() === 'safe' ? 'final-safe' : 'final-unsafe',
    })
  }

  return steps
}

const STAGE_MIN_MS = 2000

function resetEdit() {
  editProcessSteps.value = []
  activeStepIdx.value = -1
  editDone.value = false
  editPlaying.value = false
}

async function playEdits() {
  if (!sample.value || editPlaying.value) return
  editPlaying.value = true
  editDone.value = false
  activeStepIdx.value = -1
  const steps = buildProcessSteps()
  // All pending except first running
  const initial = steps.map((s, i) => ({
    ...s,
    state: i === 0 ? 'running' : 'pending',
    active: i === 0,
    statusText: i === 0 ? '进行中' : '等待',
  }))
  editProcessSteps.value = initial
  activeStepIdx.value = 0
  await new Promise((r) => setTimeout(r, STAGE_MIN_MS))
  const guardIdx = steps.findIndex((s) => s.key === 'guard')
  for (let i = 0; i < steps.length; i++) {
    const upd = [...editProcessSteps.value]
    const isGuard = i === guardIdx
    const finalState = isGuard
      ? qualityLabel.value.toLowerCase() === 'safe'
        ? 'done'
        : 'error'
      : 'done'
    upd[i] = {
      ...upd[i],
      state: finalState,
      statusText: isGuard ? (finalState === 'done' ? '通过' : qualityLabel.value) : '完成',
      active: false,
    }
    if (i + 1 < steps.length) {
      upd[i + 1] = {
        ...upd[i + 1],
        state: 'running',
        active: true,
        statusText: '进行中',
        draftTone: 'reviewing',
      }
      activeStepIdx.value = i + 1
    }
    editProcessSteps.value = upd
    if (i + 1 < steps.length) await new Promise((r) => setTimeout(r, STAGE_MIN_MS))
  }
  editDone.value = true
  editPlaying.value = false
}

function copyEdited() {
  if (sample.value?.edited_text)
    navigator.clipboard.writeText(sample.value.edited_text).then(
      () => toast.success('已复制', ''),
      () => toast.error('复制失败', ''),
    )
}

watch(selectedIdx, resetEdit)
watch(selectedLang, () => {
  selectedIdx.value = 0
  resetEdit()
})
watch(activeTab, () => {
  resetEdit()
})
load()
loadPrompt()
loadH1h4()
</script>

<style src="./OutputRiskCorrection.css" scoped></style>
