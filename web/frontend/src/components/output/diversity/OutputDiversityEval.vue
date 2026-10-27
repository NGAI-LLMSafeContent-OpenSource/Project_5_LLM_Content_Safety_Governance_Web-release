<template>
  <div class="diversity-eval">
    <div class="track-title-row">
      <h2 class="track-title">评估（多样性）</h2>
      <span
        v-if="store.diversityEvalSource"
        class="source-badge"
        :class="{
          real: store.diversityEvalSource === 'real',
          static:
            store.diversityEvalSource === 'corpus_static' ||
            store.diversityEvalSource === 'culture_assessment_static',
          mock: store.diversityEvalSource === 'demo_fixture',
        }"
      >
        {{ dataSourceLabel(store.diversityEvalSource) }}
      </span>
    </div>

    <!-- Stats + Radar -->
    <div v-if="isAssessmentStatic" class="eval-card assessment-view">
      <div class="stage-section">
        <div class="stage-title-row">
          <div>
            <h4 class="stage-title">{{ assessmentStageTitle }}</h4>
            <div class="stage-subtitle">
              {{ assessmentStageSubtitle }}
            </div>
          </div>
          <button
            class="analyze-btn"
            :disabled="store.cultureAssessmentStaticLoading"
            type="button"
            @click="refreshAssessmentStaticView"
          >
            {{ store.cultureAssessmentStaticLoading ? '加载中...' : assessmentRefreshLabel }}
          </button>
        </div>

        <div v-if="assessmentView" class="assessment-compare">
          <div v-if="!isAssessmentReferenceMode" class="assessment-summary">
            <div class="summary-copy">
              <div class="assess-label">{{ assessmentView.title }}</div>
              <p>{{ assessmentView.advantage_summary }}</p>
            </div>
            <div class="compare-cards">
              <div class="compare-card direct">
                <span>{{ assessmentView.direct.label }}</span>
                <strong>{{ pct(assessmentView.direct.summary.composite_pass_rate) }}</strong>
                <em>综合通过率</em>
              </div>
              <div class="compare-card agent">
                <span>{{ assessmentView.agent.label }}</span>
                <strong>{{ pct(assessmentView.agent.summary.composite_pass_rate) }}</strong>
                <em>综合通过率</em>
              </div>
              <div class="compare-card gain">
                <span>提升</span>
                <strong>{{ assessmentGain }}</strong>
                <em>percentage points</em>
              </div>
            </div>
          </div>
          <div v-else class="assessment-summary reference-summary">
            <div class="summary-copy">
              <div class="assess-label">Cultural Diversity Evaluation Dataset V1</div>
              <p>
                使用 DeepSeek 对 500
                条文化多样性基准样本进行验证，指标聚焦民族背景识别、文化实质响应与综合文化感知准确率。
              </p>
            </div>
          </div>

          <div class="assessment-console-grid" :class="{ compact: isAssessmentReferenceMode }">
            <div class="metric-console">
              <div class="console-head">
                <strong>指标结果</strong>
                <span>{{ assessmentMetricHint }}</span>
              </div>
              <div class="assessment-metric-grid">
                <div v-for="metric in assessmentMetricCards" :key="metric.label">
                  <span>{{ metric.label }}</span>
                  <b v-if="isAssessmentReferenceMode">{{ metric.value }}</b>
                  <b v-else>{{ metric.direct }} → {{ metric.agent }}</b>
                  <em v-if="metric.note">{{ metric.note }}</em>
                </div>
              </div>
            </div>

            <div v-if="!isAssessmentReferenceMode" class="assessment-radar-box">
              <div class="console-head">
                <strong>指标雷达图</strong>
                <span>Direct vs 3-Agent</span>
              </div>
              <RadarChart :data="assessmentRadarData" :size="300" />
            </div>
          </div>

          <div v-if="!isAssessmentReferenceMode" class="assessment-breakdowns">
            <div>
              <div class="breakdown-title">按民族综合通过率</div>
              <div class="breakdown-list">
                <span v-for="row in assessmentEthnicBreakdown" :key="row.label">
                  {{ row.label }} {{ row.direct }} → {{ row.agent }}
                </span>
              </div>
            </div>
            <div>
              <div class="breakdown-title">按难度综合通过率</div>
              <div class="breakdown-list">
                <span v-for="row in assessmentDifficultyBreakdown" :key="row.label">
                  {{ row.label }} {{ row.direct }} → {{ row.agent }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="!isAssessmentReferenceMode" class="assessment-highlights">
            <span v-for="item in assessmentView.highlights" :key="item">{{ item }}</span>
          </div>
        </div>
        <div v-else class="analyze-empty">
          {{ store.cultureAssessmentStaticError || '尚未加载文化评测 Benchmark 静态对比结果。' }}
        </div>
      </div>

      <div class="stage-section">
        <div class="stage-title-row">
          <div>
            <h4 class="stage-title">{{ assessmentSampleStageTitle }}</h4>
            <div class="stage-subtitle">
              {{ assessmentSampleStageSubtitle }}
            </div>
          </div>
          <div class="sample-actions">
            <span v-if="assessmentView" class="sample-count-pill">
              共 {{ assessmentDisplaySamples.length }} 条
            </span>
            <button
              class="analyze-btn"
              :disabled="selectedAssessmentDatasetIds.length === 0"
              type="button"
              @click="openAssessmentJobModal"
            >
              数据实时评测
            </button>
          </div>
        </div>
        <div class="assessment-sample-browser">
          <div class="assessment-sample-list" role="listbox" aria-label="文化评测样本列表">
            <button
              v-for="sample in assessmentDisplaySamples"
              :key="sample.sample_id"
              class="assessment-sample-item"
              :class="{ active: selectedAssessmentSample?.sample_id === sample.sample_id }"
              type="button"
              @click="selectedAssessmentSampleId = sample.sample_id"
            >
              <span class="sample-item-head">
                <code>{{ sample.sample_id }}</code>
                <strong :class="assessmentSampleClass(sample)">
                  {{ assessmentSampleLabel(sample) }}
                </strong>
              </span>
              <span class="sample-tags-line">
                <span>{{ sample.expected_ethnic_group || '—' }}</span>
                <span>{{ sample.difficulty_level || '—' }}</span>
                <template v-if="isAssessmentReferenceMode">
                  <span>综合 {{ sample.reference?.composite_score ?? 0 }}</span>
                  <span>民族 {{ sample.reference?.ethnic_group_judge?.score ?? 0 }}</span>
                </template>
                <template v-else>
                  <span>Direct {{ sample.direct?.composite_score ?? 0 }}</span>
                  <span>3-Agent {{ sample.agent?.composite_score ?? 0 }}</span>
                </template>
              </span>
              <span class="sample-item-note">{{ assessmentSampleNote(sample) }}</span>
            </button>
          </div>

          <article v-if="selectedAssessmentSample" class="assessment-sample-detail">
            <div class="detail-head">
              <div>
                <code>{{ selectedAssessmentSample.sample_id }}</code>
                <div class="sample-tags-line">
                  <span>{{ selectedAssessmentSample.expected_ethnic_group || '—' }}</span>
                  <span>{{ selectedAssessmentSample.difficulty_level || '—' }}</span>
                </div>
              </div>
              <strong :class="assessmentSampleClass(selectedAssessmentSample)">
                {{ assessmentSampleLabel(selectedAssessmentSample) }}
              </strong>
            </div>

            <div class="detail-section">
              <div class="detail-title">问题对照</div>
              <div class="question-grid">
                <div>
                  <span class="muted">原问题</span>
                  <p>{{ selectedAssessmentSample.original_question || '—' }}</p>
                </div>
                <div>
                  <span class="muted">去民族化问题</span>
                  <p>{{ selectedAssessmentSample.neutralized_question || '—' }}</p>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-title">回答与判定</div>
              <div
                v-if="isAssessmentReferenceMode"
                class="answer-compare-grid reference-answer-grid"
              >
                <div class="answer-panel reference-panel">
                  <div class="judge-row">
                    <strong>DeepSeek 评估结果</strong>
                    <span
                      class="judge-chip"
                      :class="{ pass: selectedAssessmentSample.reference?.composite_score === 1 }"
                    >
                      综合 {{ selectedAssessmentSample.reference?.composite_score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      民族 {{ selectedAssessmentSample.reference?.ethnic_group_judge?.score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      差异
                      {{
                        selectedAssessmentSample.reference?.cultural_difference_judge?.score ?? 0
                      }}
                    </span>
                  </div>
                  <p>{{ selectedAssessmentSample.reference?.answer_a }}</p>
                  <div class="judge-reason">
                    {{
                      selectedAssessmentSample.reference?.cultural_difference_judge?.reason ||
                      selectedAssessmentSample.reference?.ethnic_group_judge?.reason ||
                      '未提供评测理由'
                    }}
                  </div>
                </div>
              </div>
              <div v-else class="answer-compare-grid">
                <div class="answer-panel direct-panel">
                  <div class="judge-row">
                    <strong>普通 DeepSeek API</strong>
                    <span
                      class="judge-chip"
                      :class="{ pass: selectedAssessmentSample.direct?.composite_score === 1 }"
                    >
                      综合 {{ selectedAssessmentSample.direct?.composite_score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      民族 {{ selectedAssessmentSample.direct?.ethnic_group_judge?.score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      差异
                      {{ selectedAssessmentSample.direct?.cultural_difference_judge?.score ?? 0 }}
                    </span>
                  </div>
                  <p>{{ selectedAssessmentSample.direct?.answer_a }}</p>
                  <div class="judge-reason">
                    {{
                      selectedAssessmentSample.direct?.cultural_difference_judge?.reason ||
                      selectedAssessmentSample.direct?.ethnic_group_judge?.reason ||
                      '未提供评测理由'
                    }}
                  </div>
                </div>
                <div class="answer-panel agent-panel">
                  <div class="judge-row">
                    <strong>3-Agent</strong>
                    <span
                      class="judge-chip"
                      :class="{ pass: selectedAssessmentSample.agent?.composite_score === 1 }"
                    >
                      综合 {{ selectedAssessmentSample.agent?.composite_score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      民族 {{ selectedAssessmentSample.agent?.ethnic_group_judge?.score ?? 0 }}
                    </span>
                    <span class="judge-mini">
                      差异
                      {{ selectedAssessmentSample.agent?.cultural_difference_judge?.score ?? 0 }}
                    </span>
                  </div>
                  <p>{{ selectedAssessmentSample.agent?.answer_a }}</p>
                  <div class="judge-reason">
                    {{
                      selectedAssessmentSample.agent?.cultural_difference_judge?.reason ||
                      selectedAssessmentSample.agent?.ethnic_group_judge?.reason ||
                      '未提供评测理由'
                    }}
                  </div>
                </div>
              </div>
            </div>

            <div v-if="!isAssessmentReferenceMode" class="detail-section advantage-detail">
              <div class="detail-title">优势说明</div>
              <p>{{ selectedAssessmentSample.advantage_note || '未提供优势说明' }}</p>
            </div>
          </article>
          <div v-else class="analyze-empty">尚未加载样本级回答对比结果。</div>
        </div>
      </div>
    </div>

    <div v-else class="eval-card">
      <div class="stage-section">
        <h4 class="stage-title">一、文化评估资产概览</h4>
        <div class="assess-split">
          <!-- Left: Stats -->
          <div class="assess-left">
            <div class="assess-label">{{ overviewTitle }}</div>
            <div class="assess-domain">
              <strong>当前场景：</strong>
              多民族语言文化多样性 ·
              <strong>展示口径：</strong>
              {{ overviewScope }}
            </div>
            <div v-if="isCorpusStatic" class="source-context">
              <span>{{ selectedCorpusDataset?.name || '文化语料生成批次集合' }}</span>
              <span>{{ activeCorpusFilters.runIds }}</span>
              <span>{{ activeCorpusFilters.ethnicGroups }}</span>
              <span>{{ activeCorpusFilters.difficultyLevels }}</span>
            </div>
            <div class="stats-grid">
              <div class="stat-card">
                <div class="stat-val" style="color: var(--accent-blue)">
                  {{ diversityStats.total.toLocaleString() }}
                </div>
                <div class="stat-lbl">样本总量</div>
              </div>
              <div class="stat-card">
                <div class="stat-val" style="color: var(--accent-green)">
                  {{ isCorpusStatic ? coverageStats.ethnicCount : scoreStats.avgCulture }}
                </div>
                <div class="stat-lbl">
                  {{ isCorpusStatic ? '覆盖民族数' : '平均文化适配' }}
                  <span v-if="store.diversityEvalSource === 'demo_fixture'" class="mock-tag">
                    Demo
                  </span>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-val" style="color: var(--accent-orange)">
                  {{ isCorpusStatic ? coverageStats.difficultyCount : scoreStats.avgSemantic }}
                </div>
                <div class="stat-lbl">
                  {{ isCorpusStatic ? '覆盖难度数' : '平均语义质量' }}
                  <span v-if="store.diversityEvalSource === 'demo_fixture'" class="mock-tag">
                    Demo
                  </span>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-val" style="color: var(--accent-red)">
                  {{ isCorpusStatic ? coverageStats.reviewedCount : scoreStats.avgIntegrity }}
                </div>
                <div class="stat-lbl">
                  {{ isCorpusStatic ? '已审核样本' : '平均完整度' }}
                  <span v-if="store.diversityEvalSource === 'demo_fixture'" class="mock-tag">
                    Demo
                  </span>
                </div>
              </div>
            </div>
            <div class="assess-meta">
              <template v-if="isCorpusStatic">
                样本来自课题三文化语料批次集合（{{ diversityStats.total }}
                条），当前展示题目、文化知识点、参考答案、评分规则与审核结论，不等同于待测模型输出评分。
              </template>
              <template v-else>
                样本来自 Cultural Gen
                动态文化样本集，展示民族识别、文化类别、生成回答、参考答案、三维质量评分和改进建议。
              </template>
              <template v-if="store.diversityEvalSource === 'demo_fixture'">
                分档分布为 Demo 示例数据，阈值变更暂未接入实时计算。
              </template>
              <template v-else-if="store.diversityEvalSource === 'unavailable'">
                Cultural Gen 服务不可用，未生成静默 Mock 结果。
              </template>
              <template v-else-if="!isCorpusStatic">
                分档基于文化/语义/完整三维评分按阈值计算。
              </template>
            </div>
          </div>

          <!-- Right: Radar -->
          <div v-if="!isCorpusStatic" class="assess-right">
            <div class="assess-label">按民族聚合 · 三维评分雷达</div>
            <div class="assess-hint">
              文化适配 / 语义质量 / 完整度按民族平均分（绿 · 蓝 · 橙）。
            </div>
            <RadarChart :data="store.radarDiversityData" />
            <div class="project-feature-list">
              <span>民族识别</span>
              <span>生成回答</span>
              <span>参考答案</span>
              <span>错误示例</span>
              <span>修正建议</span>
            </div>
            <div class="assess-meta">
              <template v-if="store.diversityEvalSource === 'real'">
                雷达数据来自 Cultural Gen 38 条样本按民族聚合。
              </template>
              <template v-else-if="store.diversityEvalSource === 'demo_fixture'">
                雷达图为 Demo 示例数据。
              </template>
              <template v-else>Cultural Gen 服务不可用，雷达图暂无数据。</template>
            </div>
          </div>
          <div v-else class="assess-right">
            <div class="assess-label">语料构造与规则审核覆盖</div>
            <div class="assess-hint">
              该资产突出评测题目构造、参考答案和评分规则，不生成 Cultural Gen 三维评分雷达。
            </div>
            <div class="coverage-panel">
              <div>
                <span class="muted">民族分布</span>
                <strong>{{ coverageStats.ethnicSummary }}</strong>
              </div>
              <div>
                <span class="muted">难度分布</span>
                <strong>{{ coverageStats.difficultySummary }}</strong>
              </div>
              <div>
                <span class="muted">背景类型</span>
                <strong>{{ coverageStats.bgSummary }}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sample Review -->
      <div class="stage-section">
        <div class="stage-title-row">
          <div>
            <h4 class="stage-title">二、文化样本验证与个例展示</h4>
            <div class="stage-subtitle">
              批量样本是主评估展示；单条分析仅用于文化侧服务连通和推理验证。
            </div>
          </div>
          <div class="section-tabs" role="tablist" aria-label="文化样本展示模式">
            <button
              class="section-tab"
              :class="{ active: cultureSampleView === 'samples' }"
              type="button"
              @click="cultureSampleView = 'samples'"
            >
              样本个例
            </button>
            <button
              class="section-tab"
              :class="{ active: cultureSampleView === 'single' }"
              type="button"
              @click="cultureSampleView = 'single'"
            >
              单条分析
            </button>
          </div>
        </div>

        <div v-if="cultureSampleView === 'single'" class="analyze-panel">
          <div class="analyze-editor">
            <div class="analyze-head">
              <div>
                <div class="assess-label">Cultural Gen 实时推理接口</div>
                <div class="assess-hint">
                  用于验证课题三文化生成/推理服务是否可用；结果不写入正式评估样本。
                </div>
              </div>
              <button
                class="analyze-btn"
                :disabled="cultureAnalyzeLoading"
                @click="runCultureAnalyze"
              >
                {{ cultureAnalyzeLoading ? '分析中...' : '分析文本' }}
              </button>
            </div>
            <textarea
              v-model="cultureAnalyzeText"
              class="analyze-input"
              rows="3"
              placeholder="输入一条待分析文本，例如：我想在团队活动中加入蒙古族双手端奶茶的待客礼仪，怎样表达更尊重？"
            />
            <div v-if="cultureAnalyzeError" class="analyze-error">
              {{ cultureAnalyzeError }}
            </div>
          </div>
          <div class="analyze-result">
            <template v-if="cultureAnalyzeResult">
              <div class="result-grid">
                <div>
                  <span class="muted">识别民族</span>
                  <strong>{{ cultureAnalyzeResult.ethnic || '未识别' }}</strong>
                </div>
                <div>
                  <span class="muted">置信度</span>
                  <strong>{{ cultureAnalyzeResult.confidence ?? 0 }}</strong>
                </div>
                <div>
                  <span class="muted">文化类别</span>
                  <strong>{{ cultureAnalyzeResult.category || '未分类' }}</strong>
                </div>
                <div>
                  <span class="muted">综合分</span>
                  <strong>{{ cultureAnalyzeResult.scores?.total ?? 0 }}</strong>
                </div>
              </div>
              <div class="result-block">
                <span class="muted">文化线索</span>
                <p>{{ cultureAnalyzeResult.cues?.join('、') || '未返回线索' }}</p>
              </div>
              <div class="result-block">
                <span class="muted">知识依据</span>
                <p>{{ cultureAnalyzeResult.knowledge || '未返回知识依据' }}</p>
              </div>
              <div class="score-strip">
                <span>文化 {{ cultureAnalyzeResult.scores?.culture ?? 0 }}</span>
                <span>语义 {{ cultureAnalyzeResult.scores?.semantic ?? 0 }}</span>
                <span>完整 {{ cultureAnalyzeResult.scores?.integrity ?? 0 }}</span>
              </div>
            </template>
            <div v-else class="analyze-empty">
              点击“分析文本”后展示民族识别、文化线索、知识依据和三维评分。
            </div>
          </div>
        </div>

        <div v-else class="sample-tab-pane">
          <div class="table-label">{{ sampleTableTitle }}</div>
          <div class="table-wrap">
            <table class="sample-table">
              <thead>
                <tr v-if="isCorpusStatic">
                  <th>数据点 ID</th>
                  <th>民族/难度/背景</th>
                  <th>评测问题</th>
                  <th>文化知识点</th>
                  <th>参考答案</th>
                  <th>评分规则</th>
                  <th>审核结论</th>
                </tr>
                <tr v-else>
                  <th>数据点 ID</th>
                  <th>民族/类别</th>
                  <th>用户问题</th>
                  <th>生成回答 / 参考答案</th>
                  <th>三维评分</th>
                  <th>改进建议</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in store.evalDiversitySamples" :key="s.id">
                  <template v-if="isCorpusStatic">
                    <td>
                      <code>{{ s.id }}</code>
                      <button class="inline-action" type="button" @click="reviewSample(s.text)">
                        复核
                      </button>
                    </td>
                    <td>
                      <div>{{ s.ethnic || '未标注民族' }}</div>
                      <div class="muted">{{ s.difficultyLevel || '未标注难度' }}</div>
                      <div class="muted">{{ bgTypeLabel(s.bgType) }}</div>
                    </td>
                    <td class="snippet">{{ s.text }}</td>
                    <td class="summary-cell">
                      {{ (s.cues || []).slice(0, 2).join('；') || s.knowledge || '未提供' }}
                    </td>
                    <td class="summary-cell">{{ s.expectedAnswer || '未提供参考答案' }}</td>
                    <td class="rubric-cell">
                      <div>
                        <span class="muted">must_have：</span>
                        {{ (s.mustHave || []).slice(0, 2).join('；') || '未提供' }}
                      </div>
                      <div>
                        <span class="muted">penalty：</span>
                        {{ (s.penalty || []).slice(0, 2).join('；') || '未提供' }}
                      </div>
                    </td>
                    <td>
                      <span class="eval-tag" :class="levelTagColor(s.overallLevel)">
                        {{ s.overallLevel === 'excellent' ? '通过' : '未通过' }}
                      </span>
                      <div class="muted">{{ s.reviewAccuracy ?? '未提供' }}/5</div>
                    </td>
                  </template>
                  <template v-else>
                    <td>
                      <code>{{ s.id }}</code>
                      <button class="inline-action" type="button" @click="reviewSample(s.text)">
                        复核
                      </button>
                    </td>
                    <td>
                      <div>{{ s.ethnic || '未识别民族' }}</div>
                      <div class="muted">{{ s.category || '未分类' }}</div>
                    </td>
                    <td class="snippet">{{ s.text }}</td>
                    <td class="answer-cell">
                      <div>
                        <span class="muted">生成：</span>
                        {{ s.generatedAnswer || '未提供生成回答' }}
                      </div>
                      <div>
                        <span class="muted">参考：</span>
                        {{ s.expectedAnswer || '未提供参考答案' }}
                      </div>
                    </td>
                    <td class="score-cell">
                      <span>文化 {{ s.cultureScore ?? '—' }}</span>
                      <span>语义 {{ s.semanticScore ?? '—' }}</span>
                      <span>完整 {{ s.integrityScore ?? '—' }}</span>
                    </td>
                    <td class="summary-cell">
                      {{ s.fixSuggestion || s.wrongExample || s.summary }}
                    </td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <div v-if="assessmentJobModalOpen" class="modal-backdrop" @click.self="closeAssessmentJobModal">
      <section class="assessment-job-modal" role="dialog" aria-modal="true">
        <div class="modal-head">
          <div>
            <h3>文化评测 Benchmark 实时任务</h3>
            <p>对齐 8877 控制台“开始评测（按当前配置）”流程，任务由课题三文化评测控制台执行。</p>
          </div>
          <button
            class="icon-close"
            type="button"
            aria-label="关闭"
            @click="closeAssessmentJobModal"
          >
            ×
          </button>
        </div>

        <div class="assessment-job-grid">
          <div class="job-control-panel">
            <div class="console-head">
              <strong>评测控制</strong>
              <span>{{ assessmentConsoleStatus }}</span>
            </div>
            <div v-if="assessmentJobError" class="analyze-error">{{ assessmentJobError }}</div>
            <div class="job-field-grid">
              <label class="job-field">
                <span>数据集</span>
                <select v-model="assessmentJobForm.datasetId">
                  <option
                    v-for="dataset in selectableAssessmentConsoleDatasets"
                    :key="dataset.id"
                    :value="dataset.id"
                  >
                    {{ dataset.label }} · {{ dataset.sample_count }} 条
                  </option>
                </select>
              </label>
              <label class="job-field">
                <span>目标类型</span>
                <div class="readonly-field">DeepSeek 评测</div>
              </label>
              <label class="job-field">
                <span>运行后缀</span>
                <input v-model.trim="assessmentJobForm.runSuffix" placeholder="可选" />
              </label>
              <label class="job-field">
                <span>limit</span>
                <input
                  v-model.trim="assessmentJobForm.limit"
                  min="1"
                  placeholder="留空表示全量"
                  type="number"
                />
              </label>
              <label class="job-field">
                <span>offset</span>
                <input v-model.trim="assessmentJobForm.offset" min="0" type="number" />
              </label>
            </div>
            <div class="dataset-note-box">{{ selectedAssessmentConsoleDatasetDescription }}</div>
            <div class="job-button-row">
              <button
                class="analyze-btn"
                :disabled="assessmentJobLoading || !assessmentJobForm.datasetId"
                type="button"
                @click="startAssessmentJob"
              >
                {{ assessmentJobLoading ? '启动中...' : '开始评测（按当前配置）' }}
              </button>
              <button
                class="secondary-btn"
                :disabled="!assessmentJob?.running"
                type="button"
                @click="stopAssessmentJob"
              >
                停止当前任务
              </button>
              <button class="secondary-btn" type="button" @click="loadAssessmentConsoleMeta">
                刷新
              </button>
            </div>
          </div>

          <div class="job-status-panel">
            <div class="console-head">
              <strong>任务状态</strong>
              <span>{{ assessmentJob?.status || '未运行' }}</span>
            </div>
            <div class="job-progress">
              <div :style="{ width: `${assessmentJobProgress}%` }"></div>
            </div>
            <div class="job-progress-text">
              {{ assessmentJob?.completed ?? 0 }} / {{ assessmentJob?.total ?? 0 }} ·
              {{ assessmentJobProgress }}%
            </div>
            <div class="job-meta-grid">
              <div>
                <span>job_id</span>
                <strong>{{ assessmentJob?.job_id || '—' }}</strong>
              </div>
              <div>
                <span>目标类型</span>
                <strong>{{ assessmentJobTargetLabel }}</strong>
              </div>
              <div>
                <span>数据集</span>
                <strong>{{ assessmentJob?.dataset_label || '—' }}</strong>
              </div>
              <div>
                <span>结果目录</span>
                <strong>{{ assessmentJob?.output_dir || '—' }}</strong>
              </div>
            </div>
            <pre class="job-log-box">{{ assessmentJobLogText }}</pre>
          </div>
        </div>

        <div v-if="assessmentJobResult?.summary" class="job-result-panel">
          <div class="console-head">
            <strong>实时评测结果摘要</strong>
            <span>
              {{ assessmentJobResult.dataset_label || '—' }}
              {{ assessmentJobResult.cached ? ' · 命中缓存' : '' }}
            </span>
          </div>
          <div class="assessment-metric-grid job-summary-metric-grid">
            <div v-for="metric in assessmentJobMetricCards" :key="metric.label">
              <span>{{ metric.label }}</span>
              <b>{{ metric.value }}</b>
              <em v-if="metric.note">{{ metric.note }}</em>
            </div>
          </div>
          <div v-if="assessmentJobSamples.length" class="job-sample-results">
            <div class="job-sample-results-head">
              <strong>评估样本信息</strong>
              <span>展示 {{ assessmentJobSamples.length }} 条</span>
            </div>
            <article
              v-for="sample in assessmentJobSamples"
              :key="sample.sample_id"
              class="job-sample-card"
            >
              <div class="job-sample-head">
                <code>{{ sample.sample_id }}</code>
                <span>{{ sample.difficulty_level || '—' }}</span>
                <b :class="{ pass: sample.passed }">{{ sample.passed ? '准确' : '不准确' }}</b>
              </div>
              <div class="job-sample-question">
                <span>原始问题</span>
                <p>{{ sample.original_question || '—' }}</p>
              </div>
              <div class="job-sample-answer-box">
                <span>标准回答</span>
                <p>{{ sample.reference_answer || sample.answer_a || '—' }}</p>
              </div>
              <div class="job-sample-answer-grid">
                <div>
                  <span>民族识别 {{ assessmentJobHighlightScore(sample, 'ethnic') }}</span>
                  <p v-if="assessmentJobEthnicMention(sample)" class="job-sample-mark">
                    {{ assessmentJobEthnicMention(sample) }}
                  </p>
                  <p>{{ assessmentJobHighlightReason(sample, 'ethnic') }}</p>
                </div>
                <div>
                  <span>文化差异 {{ assessmentJobHighlightScore(sample, 'cultural') }}</span>
                  <p>{{ assessmentJobHighlightReason(sample, 'cultural') }}</p>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useOutputStore } from '@/stores/output'
import {
  analyzeCultureText,
  fetchCultureAssessmentConsoleDatasets,
  fetchCultureAssessmentConsoleHealth,
  fetchCultureAssessmentConsoleJob,
  fetchCultureAssessmentConsoleJobResults,
  fetchCultureAssessmentConsoleJobs,
  startCultureAssessmentConsoleJob,
  stopCultureAssessmentConsoleJob,
  type CultureAnalyzeResultDTO,
  type CultureAssessmentConsoleDataset,
  type CultureAssessmentConsoleJob,
  type CultureAssessmentConsoleJobResult,
  type CultureAssessmentReferenceSample,
  type CultureAssessmentSamplePair,
} from '@/api/output'
import RadarChart from '../shared/RadarChart.vue'
import { dataSourceLabel, levelTagColor } from '@/utils/outputHelpers'
import type { RadarChartData } from '@/types'

const store = useOutputStore()
const cultureSampleView = ref<'samples' | 'single'>('samples')
const cultureAnalyzeText = ref('我想在团队活动中加入蒙古族双手端奶茶的待客礼仪，怎样表达更尊重？')
const cultureAnalyzeLoading = ref(false)
const cultureAnalyzeError = ref('')
const cultureAnalyzeResult = ref<CultureAnalyzeResultDTO | null>(null)
const selectedAssessmentSampleId = ref('')
const assessmentJobModalOpen = ref(false)
const assessmentConsoleDatasets = ref<CultureAssessmentConsoleDataset[]>([])
const assessmentConsoleStatus = ref('尚未连接')
const assessmentJob = ref<CultureAssessmentConsoleJob | null>(null)
const assessmentJobResult = ref<CultureAssessmentConsoleJobResult | null>(null)
const assessmentJobLoading = ref(false)
const assessmentJobError = ref('')
const ASSESSMENT_V1_DATASET_ID = 'framework_cultural_diversity_evaluation_dataset_v1'
const ASSESSMENT_V1_VIEW_ID = 'cultural_diversity_evaluation_dataset_v1'
const assessmentJobForm = reactive({
  datasetId: ASSESSMENT_V1_DATASET_ID,
  runSuffix: '',
  limit: '1',
  offset: '0',
})
let assessmentJobPollTimer: ReturnType<typeof setInterval> | null = null

type AssessmentMetricCard = {
  label: string
  value?: string
  direct?: string
  agent?: string
  note?: string
}

type AssessmentDisplaySample = {
  sample_id: string
  difficulty_level?: string
  expected_ethnic_group?: string
  original_question?: string
  neutralized_question?: string
  reference?: CultureAssessmentReferenceSample
  direct?: CultureAssessmentSamplePair['direct']
  agent?: CultureAssessmentSamplePair['agent']
  advantage_note?: string
}

type AssessmentJobSample = Record<string, unknown> & {
  sample_id: string
  difficulty_level?: string
  original_question?: string
  reference_answer?: string
  answer_a?: string
  passed?: boolean
  highlights?: {
    ethnic_score?: number | string
    ethnic_mention?: string
    ethnic_judge_reason?: string
    cultural_score?: number | string
    cultural_judge_reason?: string
  }
  ethnic_group_judge?: { score?: number | string; reason?: string }
  cultural_difference_judge?: { score?: number | string; reason?: string }
}

const emptyAssessmentEval = {
  answer_a: '',
  answer_b: '',
  ethnic_group_judge: {},
  cultural_difference_judge: {},
  composite_score: 0,
}

onMounted(() => {
  void store.loadCultureAssessmentStaticView(ASSESSMENT_V1_VIEW_ID)
})

onUnmounted(() => {
  clearAssessmentJobPoll()
})

const diversityStats = computed(() => {
  const samples = store.evalDiversitySamples
  const total = samples.length
  const excellent = samples.filter((s) => s.overallScore * 100 >= 85).length
  const good = samples.filter((s) => s.overallScore * 100 >= 70 && s.overallScore * 100 < 85).length
  const needsImprovement = samples.filter((s) => s.overallScore * 100 < 70).length
  const passed = samples.filter((s) => s.overallLevel === 'excellent').length
  const failed = samples.filter((s) => s.overallLevel === 'needsImprovement').length
  const withAccuracy = samples.filter((s) => s.overallScore > 0).length
  return { total, excellent, good, needsImprovement, passed, failed, withAccuracy }
})

const isCorpusStatic = computed(() => store.diversityEvalSource === 'corpus_static')
const isAssessmentStatic = computed(() => true)
const assessmentView = computed(() => store.cultureAssessmentStaticView)
const isAssessmentReferenceMode = computed(
  () => assessmentView.value?.view_id === 'cultural_diversity_evaluation_dataset_v1',
)
const referenceSummary = computed(() => assessmentView.value?.reference?.summary || null)
const assessmentPairs = computed(() => assessmentView.value?.sample_pairs || [])
const referenceSamples = computed(() => assessmentView.value?.reference_samples || [])
const assessmentDisplaySamples = computed<AssessmentDisplaySample[]>(() =>
  isAssessmentReferenceMode.value
    ? referenceSamples.value.map((sample) => ({
        sample_id: sample.sample_id,
        difficulty_level: sample.difficulty_level,
        expected_ethnic_group: sample.expected_ethnic_group,
        original_question: sample.original_question,
        neutralized_question: sample.neutralized_question,
        reference: sample,
      }))
    : assessmentPairs.value.map((pair) => ({
        sample_id: pair.sample_id,
        difficulty_level: pair.difficulty_level,
        expected_ethnic_group: pair.expected_ethnic_group,
        original_question: pair.original_question,
        neutralized_question: pair.neutralized_question,
        direct: pair.direct,
        agent: pair.agent,
        advantage_note: pair.advantage_note,
      })),
)
const selectedAssessmentSample = computed(
  () =>
    assessmentDisplaySamples.value.find(
      (sample) => sample.sample_id === selectedAssessmentSampleId.value,
    ) ||
    assessmentDisplaySamples.value[0] ||
    null,
)
const assessmentGain = computed(() => {
  const view = assessmentView.value
  if (!view) return '—'
  const gain =
    (view.agent.summary.composite_pass_rate - view.direct.summary.composite_pass_rate) * 100
  return `${gain >= 0 ? '+' : ''}${gain.toFixed(2)}`
})

const assessmentMetricCards = computed<AssessmentMetricCard[]>(() => {
  const view = assessmentView.value
  if (!view) return []
  if (isAssessmentReferenceMode.value) {
    const summary = referenceSummary.value
    return [
      {
        label: '文化感知准确率',
        value: pct(summary?.composite_pass_rate),
      },
      {
        label: '民族背景识别准确率',
        value: pct(summary?.ethnic_group_metric_rate),
      },
      {
        label: '文化实质响应率',
        value: pct(summary?.cultural_difference_rate),
      },
      {
        label: '文化感知准确样本',
        value: `${summary?.composite_pass_count ?? 0} / ${summary?.total_samples ?? 0}`,
        note: '准确识别民族背景并具有文化实质响应的样本',
      },
      {
        label: 'L1 文化感知准确率',
        value: pct(summary?.by_difficulty?.L1?.pass_rate),
        note: `${summary?.by_difficulty?.L1?.count ?? 0} 条样本`,
      },
      {
        label: 'L2 文化感知准确率',
        value: pct(summary?.by_difficulty?.L2?.pass_rate),
        note: `${summary?.by_difficulty?.L2?.count ?? 0} 条样本`,
      },
      {
        label: 'L3 文化感知准确率',
        value: pct(summary?.by_difficulty?.L3?.pass_rate),
        note: `${summary?.by_difficulty?.L3?.count ?? 0} 条样本`,
      },
    ]
  }
  return [
    {
      label: '综合通过率',
      direct: pct(view.direct.summary.composite_pass_rate),
      agent: pct(view.agent.summary.composite_pass_rate),
    },
    {
      label: '民族识别',
      direct: pct(view.direct.summary.ethnic_group_metric_rate),
      agent: pct(view.agent.summary.ethnic_group_metric_rate),
    },
    {
      label: '文化差异度',
      direct: pct(view.direct.summary.cultural_difference_rate),
      agent: pct(view.agent.summary.cultural_difference_rate),
    },
    {
      label: '通过样本',
      direct: `${view.direct.summary.composite_pass_count} / ${view.direct.summary.total_samples}`,
      agent: `${view.agent.summary.composite_pass_count} / ${view.agent.summary.total_samples}`,
    },
    {
      label: 'L1',
      direct: pct(view.direct.summary.by_difficulty.L1?.pass_rate),
      agent: pct(view.agent.summary.by_difficulty.L1?.pass_rate),
    },
    {
      label: 'L2',
      direct: pct(view.direct.summary.by_difficulty.L2?.pass_rate),
      agent: pct(view.agent.summary.by_difficulty.L2?.pass_rate),
    },
    {
      label: 'L3',
      direct: pct(view.direct.summary.by_difficulty.L3?.pass_rate),
      agent: pct(view.agent.summary.by_difficulty.L3?.pass_rate),
    },
    {
      label: '样本对',
      direct: `${view.sample_pairs.length} 条`,
      agent: `${view.sample_pairs.length} 条`,
    },
  ]
})

const assessmentRadarData = computed<RadarChartData | null>(() => {
  const radar = assessmentView.value?.radar
  if (!radar) return null
  return {
    dimensions: radar.labels,
    series: radar.series.map((item) => ({
      name: item.name,
      values: item.values.map((value) => Math.round(value * 10000) / 100),
      stroke: item.color,
      fill: `${item.color}22`,
    })),
  }
})

const assessmentEthnicBreakdown = computed(() =>
  buildAssessmentBreakdown(
    assessmentView.value?.direct.summary.by_ethnic_group,
    assessmentView.value?.agent.summary.by_ethnic_group,
  ),
)

const assessmentDifficultyBreakdown = computed(() =>
  buildAssessmentBreakdown(
    assessmentView.value?.direct.summary.by_difficulty,
    assessmentView.value?.agent.summary.by_difficulty,
  ),
)

const selectedAssessmentDatasetIds = computed(() => {
  const ids = store.selectedDiversityDatasets
    .filter((dataset) => dataset.dataSource === 'culture_assessment_static' && dataset.datasetId)
    .map((dataset) => dataset.datasetId as string)
  return ids.length > 0 ? ids : [ASSESSMENT_V1_DATASET_ID]
})

const ASSESSMENT_V2_DATASET_OPTIONS = [
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_single_sample',
    label: 'Cultural Diversity Evaluation Dataset V1(1)',
    sample_count: 1,
  },
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_random_10_samples',
    label: 'Cultural Diversity Evaluation Dataset V1(10)',
    sample_count: 10,
  },
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1_random_100_samples',
    label: 'Cultural Diversity Evaluation Dataset V1(100)',
    sample_count: 100,
  },
  {
    id: 'framework_cultural_diversity_evaluation_dataset_v1',
    label: 'Cultural Diversity Evaluation Dataset V1(500)',
    sample_count: 500,
  },
] satisfies CultureAssessmentConsoleDataset[]

const ASSESSMENT_V2_DATASET_IDS = new Set(
  ASSESSMENT_V2_DATASET_OPTIONS.map((dataset) => dataset.id),
)

const selectableAssessmentConsoleDatasets = computed(() => {
  const byId = new Map(assessmentConsoleDatasets.value.map((dataset) => [dataset.id, dataset]))
  return ASSESSMENT_V2_DATASET_OPTIONS.map((option) => ({
    ...option,
    ...(byId.get(option.id) || {}),
    label: option.label,
    sample_count: option.sample_count,
  }))
})

const selectedAssessmentConsoleDatasetDescription = computed(() => {
  const dataset = selectableAssessmentConsoleDatasets.value.find(
    (item) => item.id === assessmentJobForm.datasetId,
  )
  if (!dataset) return '当前已选数据集未在 8877 控制台数据集中匹配，请刷新或检查课题三服务。'
  return `${dataset.description || '暂无数据集说明'} 当前样本数 ${dataset.sample_count}；预览样本：${dataset.preview_sample_id || '-'} / ${dataset.preview_ethnic_group || '-'} / ${dataset.preview_difficulty_level || '-'}`
})

const assessmentJobTargetMode = computed<'reference' | 'direct'>(() =>
  ASSESSMENT_V2_DATASET_IDS.has(assessmentJobForm.datasetId) ? 'reference' : 'direct',
)

const assessmentJobProgress = computed(() =>
  Math.max(0, Math.min(100, Math.round(Number(assessmentJob.value?.progress || 0)))),
)

const assessmentJobTargetLabel = computed(() => {
  const mode = assessmentJob.value?.target_mode || assessmentJobTargetMode.value
  if (mode === 'reference') return 'DeepSeek 基准验证'
  if (mode === 'direct') return 'DeepSeek 评测'
  return mode || '—'
})

const assessmentJobLogText = computed(() => {
  const logs = assessmentJob.value?.log_tail || []
  return logs.length > 0 ? logs.join('\n') : '等待日志输出'
})

const assessmentJobMetricCards = computed<AssessmentMetricCard[]>(() => {
  const summary = assessmentJobResult.value?.summary
  if (!summary) return []
  const difficultyCards = Object.entries(summary.by_difficulty || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([level, item]) => ({
      label: `${level} 文化感知准确率`,
      value: pct(item.pass_rate),
      note: `${item.count ?? 0} 条样本`,
    }))
  return [
    {
      label: '文化感知准确率',
      value: pct(summary.composite_pass_rate),
    },
    {
      label: '民族背景识别准确率',
      value: pct(summary.ethnic_group_metric_rate),
    },
    {
      label: '文化实质响应率',
      value: pct(summary.cultural_difference_rate),
    },
    {
      label: '文化感知准确样本',
      value: `${summary.composite_pass_count ?? 0} / ${summary.total_samples ?? 0}`,
      note: '准确识别民族背景并具有文化实质响应的样本',
    },
    ...difficultyCards,
  ]
})

const assessmentJobSamples = computed<AssessmentJobSample[]>(() => {
  const rows =
    assessmentJobResult.value?.attribution || assessmentJobResult.value?.sample_results || []
  return rows
    .slice(0, 6)
    .map((row, index) => ({ ...row, sample_id: String(row.sample_id || `sample-${index + 1}`) }))
})

watch(
  assessmentDisplaySamples,
  (samples) => {
    if (samples.length === 0) {
      selectedAssessmentSampleId.value = ''
      return
    }
    if (!samples.some((sample) => sample.sample_id === selectedAssessmentSampleId.value)) {
      selectedAssessmentSampleId.value = samples[0].sample_id
    }
  },
  { immediate: true },
)

function pct(value?: number) {
  if (typeof value !== 'number') return '—'
  return `${(value * 100).toFixed(2)}%`
}

function assessmentOutcomeLabel(pair: CultureAssessmentSamplePair) {
  const direct = Number(pair.direct.composite_score || 0)
  const agent = Number(pair.agent.composite_score || 0)
  if (direct === agent && agent === 1) return '均通过'
  if (direct === agent) return '均未通过'
  if (agent > direct) return '3-Agent 更优'
  return 'Direct 更优'
}

function assessmentOutcomeClass(pair: CultureAssessmentSamplePair) {
  const direct = Number(pair.direct.composite_score || 0)
  const agent = Number(pair.agent.composite_score || 0)
  if (agent > direct) return 'agent-win'
  if (direct > agent) return 'direct-win'
  if (agent === 1) return 'balanced-pass'
  return 'balanced-fail'
}

const assessmentStageTitle = computed(() => '一、数据集统计信息')

const assessmentStageSubtitle = computed(() =>
  isAssessmentReferenceMode.value
    ? '静态展示 Cultural Diversity Evaluation Dataset V1 的 500 条 DeepSeek 文化多样性评估结果。'
    : '静态展示 Project_3_Cultural_Diversity_Assessment_Tool 已完成的 30 条对比评测结果。',
)

const assessmentRefreshLabel = computed(() =>
  isAssessmentReferenceMode.value ? '刷新评估结果' : '刷新静态对比',
)

const assessmentMetricHint = computed(() =>
  isAssessmentReferenceMode.value
    ? '对齐 8878 文化评测工作台验证结果'
    : '对齐 8877 文化评测控制台口径',
)

const assessmentSampleStageTitle = computed(() => '二、个例展示')

const assessmentSampleStageSubtitle = computed(() =>
  isAssessmentReferenceMode.value
    ? '展示原问题、去民族化问题、DeepSeek 评估判定和 Judge 理由，样本按通过优先并夹少量未通过样本呈现。'
    : '展示原问题、去民族化问题、Direct 与 3-Agent 的综合判定和评测理由。',
)

function assessmentSampleLabel(sample: AssessmentDisplaySample) {
  if (sample.reference)
    return Number(sample.reference.composite_score || 0) === 1 ? '评估通过' : '待改进'
  return assessmentOutcomeLabel({
    sample_id: sample.sample_id,
    direct: sample.direct || emptyAssessmentEval,
    agent: sample.agent || emptyAssessmentEval,
    advantage_note: sample.advantage_note || '',
  })
}

function assessmentSampleClass(sample: AssessmentDisplaySample) {
  if (sample.reference)
    return Number(sample.reference.composite_score || 0) === 1 ? 'balanced-pass' : 'balanced-fail'
  return assessmentOutcomeClass({
    sample_id: sample.sample_id,
    direct: sample.direct || emptyAssessmentEval,
    agent: sample.agent || emptyAssessmentEval,
    advantage_note: sample.advantage_note || '',
  })
}

function assessmentSampleNote(sample: AssessmentDisplaySample) {
  if (!sample.reference) return sample.advantage_note || ''
  return (
    sample.reference.cultural_difference_judge?.reason ||
    sample.reference.ethnic_group_judge?.reason ||
    '未提供评测理由'
  )
}

function assessmentJobHighlightScore(sample: AssessmentJobSample, type: 'ethnic' | 'cultural') {
  if (type === 'ethnic') {
    return sample.highlights?.ethnic_score ?? sample.ethnic_group_judge?.score ?? '—'
  }
  return sample.highlights?.cultural_score ?? sample.cultural_difference_judge?.score ?? '—'
}

function assessmentJobEthnicMention(sample: AssessmentJobSample) {
  return sample.highlights?.ethnic_mention || ''
}

function assessmentJobHighlightReason(sample: AssessmentJobSample, type: 'ethnic' | 'cultural') {
  if (type === 'ethnic') {
    return sample.highlights?.ethnic_judge_reason || sample.ethnic_group_judge?.reason || '无理由'
  }
  return (
    sample.highlights?.cultural_judge_reason || sample.cultural_difference_judge?.reason || '无理由'
  )
}

async function refreshAssessmentStaticView() {
  await store.loadCultureAssessmentStaticView(assessmentView.value?.view_id || ASSESSMENT_V1_VIEW_ID)
}

async function openAssessmentJobModal() {
  assessmentJobModalOpen.value = true
  await store.loadCultureAssessmentDatasets()
  await loadAssessmentConsoleMeta()
}

function closeAssessmentJobModal() {
  assessmentJobModalOpen.value = false
}

async function loadAssessmentConsoleMeta() {
  assessmentJobError.value = ''
  try {
    const [health, datasets, jobs] = await Promise.all([
      fetchCultureAssessmentConsoleHealth(),
      fetchCultureAssessmentConsoleDatasets(),
      fetchCultureAssessmentConsoleJobs(),
    ])
    assessmentConsoleStatus.value = `已连接 · 活跃任务 ${health.active_jobs ?? 0} · 数据集 ${health.dataset_count ?? datasets.datasets.length}`
    assessmentConsoleDatasets.value = datasets.datasets || []
    if (
      !assessmentJobForm.datasetId ||
      !selectableAssessmentConsoleDatasets.value.some(
        (dataset) => dataset.id === assessmentJobForm.datasetId,
      )
    ) {
      assessmentJobForm.datasetId = selectableAssessmentConsoleDatasets.value[0]?.id || ''
    }
    const latest = (jobs.jobs || []).find((job) => job.running) || (jobs.jobs || []).at(-1)
    if (latest) {
      assessmentJob.value = latest
      if (latest.running) startAssessmentJobPoll(latest.job_id)
    }
  } catch (error: unknown) {
    assessmentConsoleStatus.value = '控制台不可用'
    assessmentJobError.value =
      error instanceof Error ? error.message : '文化评测控制台连接失败，请确认 8877 服务已启动。'
  }
}

async function startAssessmentJob() {
  if (!assessmentJobForm.datasetId) {
    assessmentJobError.value = '请选择文化评测 Benchmark 数据集。'
    return
  }
  if (
    !selectableAssessmentConsoleDatasets.value.some(
      (dataset) => dataset.id === assessmentJobForm.datasetId,
    )
  ) {
    assessmentJobError.value = '当前数据集不在测试数据选择页已选范围内，不能发起实时评测。'
    return
  }
  assessmentJobLoading.value = true
  assessmentJobError.value = ''
  assessmentJobResult.value = null
  try {
    const job = await startCultureAssessmentConsoleJob({
      dataset_id: assessmentJobForm.datasetId,
      target_mode: assessmentJobTargetMode.value,
      run_suffix: assessmentJobForm.runSuffix,
      limit: assessmentJobForm.limit,
      offset: assessmentJobForm.offset || '0',
    })
    assessmentJob.value = job
    startAssessmentJobPoll(job.job_id)
  } catch (error: unknown) {
    assessmentJobError.value = error instanceof Error ? error.message : '启动文化实时评测任务失败。'
  } finally {
    assessmentJobLoading.value = false
  }
}

function startAssessmentJobPoll(jobId: string) {
  clearAssessmentJobPoll()
  assessmentJobPollTimer = setInterval(() => {
    void pollAssessmentJob(jobId)
  }, 2000)
  void pollAssessmentJob(jobId)
}

function clearAssessmentJobPoll() {
  if (assessmentJobPollTimer) {
    clearInterval(assessmentJobPollTimer)
    assessmentJobPollTimer = null
  }
}

async function pollAssessmentJob(jobId: string) {
  try {
    const job = await fetchCultureAssessmentConsoleJob(jobId)
    assessmentJob.value = job
    if (!job.running && ['completed', 'failed', 'idle'].includes(job.status)) {
      clearAssessmentJobPoll()
      if (job.status === 'completed') {
        assessmentJobResult.value = await fetchCultureAssessmentConsoleJobResults(jobId)
      }
    }
  } catch (error: unknown) {
    clearAssessmentJobPoll()
    assessmentJobError.value =
      error instanceof Error ? error.message : '读取文化实时评测任务状态失败。'
  }
}

async function stopAssessmentJob() {
  if (!assessmentJob.value?.job_id) return
  try {
    assessmentJob.value = await stopCultureAssessmentConsoleJob(assessmentJob.value.job_id)
    clearAssessmentJobPoll()
  } catch (error: unknown) {
    assessmentJobError.value = error instanceof Error ? error.message : '停止任务失败。'
  }
}

function buildAssessmentBreakdown(
  direct?: Record<string, { count: number; pass_rate: number }>,
  agent?: Record<string, { count: number; pass_rate: number }>,
) {
  const labels = Array.from(new Set([...Object.keys(direct || {}), ...Object.keys(agent || {})]))
  return labels.map((label) => ({
    label,
    direct: pct(direct?.[label]?.pass_rate),
    agent: pct(agent?.[label]?.pass_rate),
  }))
}

const overviewTitle = computed(() =>
  isCorpusStatic.value
    ? '文化语料批次集合 · 规则审核口径'
    : 'Cultural Gen 动态文化样本 · 三维评分口径',
)

const overviewScope = computed(() =>
  isCorpusStatic.value
    ? '题目构造、参考答案、评分规则、审核结果'
    : '民族识别、生成回答、参考答案、三维质量评分',
)

const sampleTableTitle = computed(() =>
  isCorpusStatic.value ? '评测语料个例 · 参考答案与规则审核' : '生成样本个例 · 三维评分与改进建议',
)

const selectedCorpusDataset = computed(() =>
  store.selectedDiversityDatasets.find((dataset) => dataset.dataSource === 'corpus_static'),
)

const activeCorpusFilters = computed(() => {
  const filters = selectedCorpusDataset.value?.cultureCorpusFilters
  const label = (values?: string[], fallback = '全部') =>
    values && values.length > 0 ? values.join('、') : fallback
  return {
    runIds: `批次：${label(filters?.runIds)}`,
    ethnicGroups: `民族：${label(filters?.ethnicGroups)}`,
    difficultyLevels: `难度：${label(filters?.difficultyLevels)}`,
  }
})

const scoreStats = computed(() => {
  const samples = store.evalDiversitySamples.filter((s) => s.evaluationKind !== 'reference_review')
  const avg = (values: Array<number | undefined>) => {
    const nums = values.filter((value): value is number => typeof value === 'number')
    if (nums.length === 0) return '—'
    return Math.round(nums.reduce((sum, value) => sum + value, 0) / nums.length)
  }
  return {
    avgCulture: avg(samples.map((s) => s.cultureScore)),
    avgSemantic: avg(samples.map((s) => s.semanticScore)),
    avgIntegrity: avg(samples.map((s) => s.integrityScore)),
  }
})

const coverageStats = computed(() => {
  const samples = store.evalDiversitySamples
  const countBy = (values: Array<string | undefined>) => {
    const map = new Map<string, number>()
    for (const value of values) {
      if (!value) continue
      map.set(value, (map.get(value) || 0) + 1)
    }
    return map
  }
  const summarize = (map: Map<string, number>) => {
    const entries = Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([key, value]) => `${key} ${value}`)
    return entries.length > 0 ? entries.join(' · ') : '暂无'
  }
  const ethnic = countBy(samples.map((s) => s.ethnic))
  const difficulty = countBy(samples.map((s) => s.difficultyLevel))
  const bg = countBy(samples.map((s) => bgTypeLabel(s.bgType)))
  return {
    ethnicCount: ethnic.size,
    difficultyCount: difficulty.size,
    reviewedCount: samples.filter((s) => s.reviewAccuracy != null).length,
    ethnicSummary: summarize(ethnic),
    difficultySummary: summarize(difficulty),
    bgSummary: summarize(bg),
  }
})

function bgTypeLabel(type?: 'explicit' | 'implicit') {
  if (type === 'explicit') return '显式背景'
  if (type === 'implicit') return '隐式背景'
  return '未标注背景'
}

async function reviewSample(text: string) {
  cultureAnalyzeText.value = text
  cultureSampleView.value = 'single'
  await runCultureAnalyze()
}

async function runCultureAnalyze() {
  const text = cultureAnalyzeText.value.trim()
  cultureAnalyzeError.value = ''
  if (!text) {
    cultureAnalyzeError.value = '请输入需要分析的文本。'
    return
  }
  cultureAnalyzeLoading.value = true
  try {
    cultureAnalyzeResult.value = await analyzeCultureText(text)
  } catch (error: unknown) {
    cultureAnalyzeResult.value = null
    cultureAnalyzeError.value =
      error instanceof Error
        ? error.message
        : '文化分析接口调用失败，请确认 Cultural Gen 服务是否已启动。'
  } finally {
    cultureAnalyzeLoading.value = false
  }
}
</script>

<style src="./OutputDiversityEval.css" scoped></style>
