<template>
  <div class="diversity-attrib">
    <div class="track-title-row">
      <h2 class="track-title">归因（多样性）</h2>
      <span class="source-badge">
        {{ isAssessmentV1Attribution ? 'Benchmark 基准归因' : 'Cultural Gen 解释性归因' }}
      </span>
    </div>

    <div v-if="isAssessmentV1Attribution" class="eval-card benchmark-attrib-card">
      <div class="stage-section">
        <div class="stage-title-row">
          <div>
            <h4 class="stage-title">一、数据集统计信息</h4>
          </div>
        </div>

        <div v-if="assessmentReferenceSummary" class="attrib-overview">
          <div class="cds-grid benchmark-cds-grid">
            <div class="cds-card primary">
              <div class="cds-val">{{ attributionStaticStats.explainable }}</div>
              <div class="cds-lbl">Judge 可解释样本</div>
            </div>
            <div class="cds-card">
              <div class="cds-val">{{ attributionStaticStats.ethnicMiss }}</div>
              <div class="cds-lbl">民族识别失误归因</div>
            </div>
            <div class="cds-card">
              <div class="cds-val">{{ attributionStaticStats.culturalMiss }}</div>
              <div class="cds-lbl">文化响应失误归因</div>
            </div>
            <div class="cds-card">
              <div class="cds-val">{{ attributionStaticStats.doubleMiss }}</div>
              <div class="cds-lbl">双维失误归因</div>
            </div>
          </div>

          <div class="benchmark-breakdown-compact">
            <section>
              <div class="breakdown-title">按民族失误归因分布</div>
              <div class="breakdown-rows">
                <div v-for="row in assessmentEthnicStats" :key="row.label" class="breakdown-row">
                  <span class="breakdown-name">{{ row.label }}</span>
                  <span class="breakdown-bar"><i :style="{ width: row.missRate }"></i></span>
                  <strong>{{ row.miss }} / {{ row.count }}</strong>
                  <em>覆盖 {{ row.count }} 条</em>
                </div>
              </div>
            </section>

            <section>
              <div class="breakdown-title">按难度失误归因分布</div>
              <div class="breakdown-rows">
                <div
                  v-for="row in assessmentDifficultyStats"
                  :key="row.label"
                  class="breakdown-row"
                >
                  <span class="breakdown-name">{{ row.label }}</span>
                  <span class="breakdown-bar"><i :style="{ width: row.missRate }"></i></span>
                  <strong>{{ row.miss }} / {{ row.count }}</strong>
                  <em>覆盖 {{ row.count }} 条</em>
                </div>
              </div>
            </section>
          </div>
        </div>
        <div v-else class="attrib-empty">
          {{
            store.cultureAssessmentStaticError ||
            '尚未加载 Cultural Diversity Evaluation Dataset V1 的基准验证归因数据。'
          }}
        </div>
      </div>

      <div class="stage-section">
        <h4 class="stage-title">二、个例展示</h4>
        <div v-if="assessmentAttributionRows.length > 0" class="benchmark-attrib-list">
          <article
            v-for="row in assessmentAttributionRows"
            :key="row.sample_id"
            class="benchmark-attrib-card-item"
            :class="{ 'is-pass': row.composite_score === 1, 'is-fail': row.composite_score !== 1 }"
          >
            <div class="attrib-head">
              <code>{{ row.sample_id }}</code>
              <span class="tag">{{ row.difficulty_level || 'unknown' }}</span>
              <span class="tag">{{ row.composite_score === 1 ? '准确' : '不准确' }}</span>
            </div>
            <div class="question-box">
              <b>原始问题</b>
              <br />
              {{ row.original_question || '' }}
            </div>
            <div class="answer-box">
              <b>标准回答</b>
              <br />
              {{ row.answer_a || '' }}
            </div>
            <div class="benchmark-attrib-grid">
              <div>
                <b>民族识别 {{ row.ethnic_group_judge?.score ?? 0 }}</b>
                <p>
                  <mark>
                    {{
                      row.ethnic_group_judge?.mentioned_ethnic_group ||
                      row.expected_ethnic_group ||
                      '未识别'
                    }}
                  </mark>
                </p>
                <p>{{ row.ethnic_group_judge?.reason || '未提供 Judge 理由' }}</p>
              </div>
              <div>
                <b>文化差异 {{ row.cultural_difference_judge?.score ?? 0 }}</b>
                <p>{{ row.cultural_difference_judge?.reason || '未提供 Judge 理由' }}</p>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="attrib-empty">暂无可展示的基准验证归因个例。</div>
      </div>
    </div>

    <div v-else class="eval-card">
      <div class="stage-section">
        <div class="stage-title-row">
          <div>
            <h4 class="stage-title">一、归因资产概览</h4>
            <div class="stage-subtitle">
              基于 Cultural Gen
              样本字段组织文化线索、知识依据、三维评分缺口和修正建议；当前不是课题三正式 attribution
              接口结果。
            </div>
          </div>
          <div class="preview-tools">
            <span>缺口筛选</span>
            <select v-model="previewFilter">
              <option value="all">全部样例</option>
              <option value="culture">文化适配</option>
              <option value="semantic">语义质量</option>
              <option value="integrity">完整度</option>
            </select>
          </div>
        </div>

        <div v-if="hasAttributionRows" class="attrib-overview">
          <div class="cds-grid">
            <div class="cds-card">
              <div class="cds-val">{{ attributionStats.total }}</div>
              <div class="cds-lbl">可解释样本</div>
            </div>
            <div class="cds-card">
              <div class="cds-val">{{ attributionStats.withCues }}</div>
              <div class="cds-lbl">含文化线索</div>
            </div>
            <div class="cds-card">
              <div class="cds-val">{{ attributionStats.withKnowledge }}</div>
              <div class="cds-lbl">含知识依据</div>
            </div>
            <div class="cds-card cds--need">
              <div class="cds-val">{{ attributionStats.needFix }}</div>
              <div class="cds-lbl">需优先修正</div>
            </div>
          </div>

          <div class="feature-strip">
            <span>民族识别</span>
            <span>文化线索</span>
            <span>知识依据</span>
            <span>三维缺口</span>
            <span>错误示例</span>
            <span>修正建议</span>
          </div>

          <div class="table-wrap">
            <table class="preview-table">
              <thead>
                <tr>
                  <th>样本 ID</th>
                  <th>民族/类别</th>
                  <th>文化线索与知识依据</th>
                  <th>主要缺口</th>
                  <th>修正建议</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in filteredRows" :key="row.id">
                  <td>
                    <code>{{ row.id }}</code>
                  </td>
                  <td>
                    <div>{{ row.ethnic || '未识别民族' }}</div>
                    <div class="muted">{{ row.category || '未分类' }}</div>
                  </td>
                  <td class="evidence-cell">
                    <div>
                      <span class="muted">线索：</span>
                      {{ compactList(row.cues) }}
                    </div>
                    <div>
                      <span class="muted">依据：</span>
                      {{ row.knowledge || '未提供知识依据' }}
                    </div>
                  </td>
                  <td>
                    <span class="eval-tag" :class="levelTagColor(row.weakestLevel)">
                      {{ row.weakestLabel }} {{ row.weakestScore }}
                    </span>
                  </td>
                  <td class="summary-cell">
                    {{ row.fixSuggestion || row.wrongExample || '暂无修正建议' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else class="attrib-empty">
          当前选择的数据不包含 Cultural Gen
          三维评分、错误示例和修正建议字段。文化语料批次集合更适合在评估页展示参考答案与评分规则，不建议作为归因主资产。
        </div>
      </div>

      <div class="stage-section">
        <h4 class="stage-title">二、解释性归因个例</h4>
        <div v-if="hasAttributionRows" class="attrib-list">
          <div v-for="row in filteredRows" :key="row.id" class="attrib-card">
            <div class="attrib-head">
              <code>{{ row.id }}</code>
              <span>{{ row.ethnic || '未识别民族' }} · {{ row.category || '未分类' }}</span>
              <strong :style="{ color: weightColor(row.weight) }">
                {{ row.weight.toFixed(2) }}
              </strong>
            </div>
            <div class="path-row">
              <span>文化线索</span>
              <i></i>
              <span>知识依据</span>
              <i></i>
              <span>民族/类别识别</span>
              <i></i>
              <span>三维评分缺口</span>
              <i></i>
              <span>修正建议</span>
            </div>
            <div class="attrib-grid">
              <div>
                <span class="muted">样例原文</span>
                <p>{{ row.text }}</p>
              </div>
              <div>
                <span class="muted">错误示例</span>
                <p>{{ row.wrongExample || '未提供错误示例' }}</p>
              </div>
              <div>
                <span class="muted">改进项</span>
                <p>{{ compactList(row.improveItems) }}</p>
              </div>
              <div>
                <span class="muted">归因链（示意）</span>
                <p>{{ row.chain }}</p>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="attrib-empty">
          暂无可展示的解释性归因个例。请在测试数据选择页选择 Cultural Gen
          动态文化样本集并进入多样性评估后查看。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch, ref } from 'vue'
import { useOutputStore } from '@/stores/output'
import { DiversityLevel, type EvalSample } from '@/types'
import { levelTagColor } from '@/utils/outputHelpers'

type GapFilter = 'all' | 'culture' | 'semantic' | 'integrity'

interface AttributionRow extends EvalSample {
  weakestKey: Exclude<GapFilter, 'all'>
  weakestLabel: string
  weakestScore: number
  weakestLevel: DiversityLevel
  weight: number
  chain: string
}

const store = useOutputStore()
const previewFilter = ref<GapFilter>('all')
const ASSESSMENT_V1_VIEW_ID = 'cultural_diversity_evaluation_dataset_v1'

const isAssessmentV1Attribution = computed(() => true)

const assessmentReferenceSummary = computed(
  () => store.cultureAssessmentStaticView?.reference?.summary || null,
)

const assessmentAttributionRows = computed(
  () => store.cultureAssessmentStaticView?.reference_samples || [],
)

const attributionStaticStats = computed(() => {
  const rows = assessmentAttributionRows.value
  const explainable = rows.filter(
    (row) =>
      Boolean(row.ethnic_group_judge?.reason) || Boolean(row.cultural_difference_judge?.reason),
  ).length
  const ethnicMiss = rows.filter((row) => Number(row.ethnic_group_judge?.score ?? 0) === 0).length
  const culturalMiss = rows.filter(
    (row) => Number(row.cultural_difference_judge?.score ?? 0) === 0,
  ).length
  const doubleMiss = rows.filter(
    (row) =>
      Number(row.ethnic_group_judge?.score ?? 0) === 0 &&
      Number(row.cultural_difference_judge?.score ?? 0) === 0,
  ).length
  return { explainable, ethnicMiss, culturalMiss, doubleMiss }
})

const assessmentEthnicStats = computed(() =>
  buildAttributionStats(
    assessmentAttributionRows.value,
    (row) => row.expected_ethnic_group || '未标注民族',
  ),
)

const assessmentDifficultyStats = computed(() =>
  buildAttributionStats(
    assessmentAttributionRows.value,
    (row) => row.difficulty_level || '未标注难度',
  ),
)

onMounted(() => {
  void loadAssessmentAttributionView()
})

watch(isAssessmentV1Attribution, (active) => {
  if (active) {
    void loadAssessmentAttributionView()
  }
})

async function loadAssessmentAttributionView() {
  if (store.cultureAssessmentStaticView?.view_id === ASSESSMENT_V1_VIEW_ID) return
  await store.loadCultureAssessmentStaticView(ASSESSMENT_V1_VIEW_ID)
}

const nodeMap = computed(
  () => new Map(store.diversityAttributionNodes.map((node) => [node.id, node])),
)

const attributionRows = computed<AttributionRow[]>(() =>
  store.evalDiversitySamples
    .filter((sample) => sample.evaluationKind !== 'reference_review')
    .filter(
      (sample) =>
        typeof sample.cultureScore === 'number' &&
        typeof sample.semanticScore === 'number' &&
        typeof sample.integrityScore === 'number',
    )
    .map((sample) => {
      const gaps = [
        { key: 'culture' as const, label: '文化适配', score: sample.cultureScore ?? 0 },
        { key: 'semantic' as const, label: '语义质量', score: sample.semanticScore ?? 0 },
        { key: 'integrity' as const, label: '完整度', score: sample.integrityScore ?? 0 },
      ].sort((a, b) => a.score - b.score)
      const weakest = gaps[0]
      const avg = Math.round(
        ((sample.cultureScore ?? 0) + (sample.semanticScore ?? 0) + (sample.integrityScore ?? 0)) /
          3,
      )
      const node = nodeMap.value.get(sample.id)
      return {
        ...sample,
        weakestKey: weakest.key,
        weakestLabel: weakest.label,
        weakestScore: weakest.score,
        weakestLevel: scoreToLevel(weakest.score),
        weight: avg / 100,
        chain:
          node?.chain ||
          `${compactList(sample.cues)} → ${sample.ethnic || '民族识别'} / ${sample.category || '文化类别'} → ${weakest.label}缺口 → ${sample.fixSuggestion || '修正建议'}`,
      }
    }),
)

const hasAttributionRows = computed(() => attributionRows.value.length > 0)

const filteredRows = computed(() => {
  if (previewFilter.value === 'all') return attributionRows.value
  return attributionRows.value.filter((row) => row.weakestKey === previewFilter.value)
})

const attributionStats = computed(() => {
  const rows = attributionRows.value
  return {
    total: rows.length,
    withCues: rows.filter((row) => (row.cues || []).length > 0).length,
    withKnowledge: rows.filter((row) => Boolean(row.knowledge)).length,
    needFix: rows.filter((row) => row.weakestScore < 70).length,
  }
})

function scoreToLevel(score: number) {
  if (score >= 85) return DiversityLevel.EXCELLENT
  if (score >= 70) return DiversityLevel.GOOD
  return DiversityLevel.NEEDS_IMPROVEMENT
}

function compactList(values?: string[]) {
  if (!values || values.length === 0) return '未提供'
  return values.slice(0, 3).join('；')
}

function weightColor(w: number): string {
  if (w < 0.7) return 'var(--accent-red)'
  if (w < 0.85) return 'var(--accent-orange)'
  return 'var(--accent-green)'
}

function buildAttributionStats<T extends { composite_score?: number }>(
  rows: T[],
  keyOf: (row: T) => string,
) {
  const map = new Map<string, { count: number; miss: number }>()
  for (const row of rows) {
    const key = keyOf(row)
    const item = map.get(key) || { count: 0, miss: 0 }
    item.count += 1
    if (Number(row.composite_score ?? 0) !== 1) item.miss += 1
    map.set(key, item)
  }
  return Array.from(map.entries()).map(([label, item]) => ({
    label,
    count: item.count,
    miss: item.miss,
    missRate: item.count > 0 ? `${Math.round((item.miss / item.count) * 100)}%` : '0%',
  }))
}
</script>

<style src="./OutputDiversityAttribution.css" scoped></style>
