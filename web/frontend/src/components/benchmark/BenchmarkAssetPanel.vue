<template>
  <div class="asset-panel">
    <section v-if="!resourceMode" class="asset-panel__header">
      <div>
        <h3>Benchmark 资产摘要</h3>
        <p>
          这里展示资产注册表中的冻结资产。资产是模型评测的输入，不等同于模型评测结果；
          正式预跑资产与 CBRNE 数据快照需经各自导入契约登记后才会出现在这里。
        </p>
      </div>
      <div class="asset-panel__actions">
        <el-button size="small" :loading="isLoading" @click="$emit('refresh')">刷新</el-button>
        <span class="asset-count">{{ registeredAssetCount }} 个登记资产</span>
      </div>
    </section>
    <el-alert
      v-if="errorMessage"
      type="warning"
      :title="errorMessage"
      :closable="false"
      show-icon
    />

    <section v-if="!resourceMode || cbrneDatasetAssets.length > 0" class="asset-section">
      <div class="asset-section__title">
        <h4>课题二 CBRNE 异常数据种子库</h4>
        <span class="source-pill is-cbrne">dataset_snapshot</span>
      </div>
      <p class="asset-section__desc">
        独立于 AutoBench prerun_snapshot 的不可变数据快照。总览展示版本、内容哈希、规模与分布；
        评估器相对难度按十 Guard 错误/空判计数解释，T1–T4 仅表示来源暴露/污染风险，不作为难度。
        导入成功不等于交付就绪或训练可用。
      </p>
      <el-empty
        v-if="cbrneDatasetAssets.length === 0"
        description="尚未登记 CBRNE dataset_snapshot 资产。请导入包含 manifest、dataset.jsonl、profile.json 与 DATASET_NOTE.md 的交付包。"
      />
      <div v-else class="asset-grid">
        <article v-for="asset in cbrneDatasetAssets" :key="asset.asset_id" class="asset-card">
          <div class="asset-card__top">
            <div>
              <h4>{{ asset.name }}</h4>
              <span>
                {{ asset.source_mode }} · {{ getManifestString(asset, 'benchmark_type') }}
              </span>
            </div>
            <div class="asset-card__badges">
              <span class="asset-id">{{ asset.asset_id }}</span>
              <span class="source-pill is-cbrne">v{{ getManifestString(asset, 'version') }}</span>
              <span class="source-pill" :class="getCbrneCurrentBadge(asset).className">
                {{ getCbrneCurrentBadge(asset).label }}
              </span>
            </div>
          </div>

          <div class="prerun-metrics">
            <div>
              <span>样本总量</span>
              <strong data-testid="cbrne-metric-total">
                {{ getCbrneStatNumber(asset, 'sample_count') }}
              </strong>
            </div>
            <div>
              <span>safe</span>
              <strong data-testid="cbrne-metric-safe">
                {{ getCbrneLabelCount(asset, 'safe') }}
              </strong>
            </div>
            <div>
              <span>unsafe</span>
              <strong data-testid="cbrne-metric-unsafe">
                {{ getCbrneLabelCount(asset, 'unsafe') }}
              </strong>
            </div>
            <div>
              <span>来源种类数</span>
              <strong data-testid="cbrne-metric-source-kinds">
                {{ getCbrneSourceKindCount(asset) }}
              </strong>
            </div>
          </div>

          <div class="cbrne-dist">
            <div class="cbrne-dist__row">
              <span>类别</span>
              <div class="cbrne-dist__chips">
                <template v-if="getCbrneCategoryChips(asset).length > 0">
                  <span
                    v-for="item in getCbrneCategoryChips(asset)"
                    :key="item.name"
                    class="cbrne-chip"
                    data-testid="cbrne-category-chip"
                  >
                    {{ item.name }} {{ item.count }}
                  </span>
                </template>
                <span v-else class="cbrne-dist__empty">-</span>
              </div>
            </div>
            <div class="cbrne-dist__row">
              <span>来源</span>
              <div class="cbrne-dist__chips">
                <template v-if="getCbrneSourceChips(asset).length > 0">
                  <span
                    v-for="item in getVisibleCbrneSourceChips(asset)"
                    :key="item.name"
                    class="cbrne-chip"
                    data-testid="cbrne-source-chip"
                  >
                    {{ item.name }} {{ item.count }}
                  </span>
                  <button
                    v-if="getCbrneHiddenSourceCount(asset) > 0"
                    type="button"
                    class="cbrne-dist__toggle"
                    data-testid="cbrne-source-toggle"
                    :aria-expanded="isCbrneSourcesExpanded(asset.asset_id)"
                    @click="toggleCbrneSources(asset.asset_id)"
                  >
                    {{
                      isCbrneSourcesExpanded(asset.asset_id)
                        ? '收起'
                        : `还有 ${getCbrneHiddenSourceCount(asset)} 个来源`
                    }}
                  </button>
                </template>
                <span v-else class="cbrne-dist__empty">-</span>
              </div>
            </div>
          </div>

          <dl class="asset-fields">
            <div>
              <dt>Schema</dt>
              <dd>{{ getManifestString(asset, 'schema_id') }}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{{ getManifestString(asset, 'version') }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>Source Repo</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_repo') }}</dd>
            </div>
            <div>
              <dt>Content SHA-256</dt>
              <dd class="mono">{{ compactHash(getCbrneContentHash(asset)) }}</dd>
            </div>
            <div>
              <dt>Artifact SHA-256</dt>
              <dd class="mono">{{ compactHash(asset.artifact_sha256) }}</dd>
            </div>
            <div>
              <dt>Sensitivity</dt>
              <dd>{{ getManifestString(asset, 'sensitivity') }}</dd>
            </div>
            <div>
              <dt>Disclosure</dt>
              <dd>{{ getManifestString(asset, 'disclosure_policy') }}</dd>
            </div>
          </dl>

          <div class="cbrne-caveats">
            <div class="cbrne-caveats__block">
              <b>来源 / 许可限制</b>
              <p>{{ getManifestString(asset, 'licence_notes') }}</p>
              <ul v-if="getCbrneSourceLimitations(asset).length > 0">
                <li v-for="item in getCbrneSourceLimitations(asset)" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="cbrne-caveats__block">
              <b>评估器相对难度</b>
              <p>{{ getCbrneDifficultyExplanation(asset) }}</p>
              <p class="cbrne-caveats__note">
                T1–T4（exposure_tier）表示来源暴露或污染风险分层，不是样本难度。
              </p>
            </div>
          </div>

          <BenchmarkCbrneQueryPanel :asset="asset" />

          <div class="asset-card__actions">
            <el-button
              size="small"
              type="primary"
              data-testid="cbrne-open-controlled-detail"
              @click="openCbrneSamples(asset)"
            >
              受控样本详情
            </el-button>
          </div>

          <details class="asset-manifest">
            <summary>查看 manifest 摘要</summary>
            <pre>{{ JSON.stringify(asset.manifest, null, 2) }}</pre>
          </details>
        </article>
      </div>
    </section>

    <section v-if="!resourceMode || topic1ValueQaAssets.length > 0" class="asset-section">
      <div class="asset-section__title">
        <h4>课题一 value_qa 价值评测语料资产</h4>
        <span class="source-pill is-valueqa">预跑资产</span>
      </div>
      <p class="asset-section__desc">
        资产型接入高 / 中 / 低三档回答对照样本，当前展示资产级摘要、全量复判摘要和 preview。
        若同一批次存在 Data_predictions.jsonl
        全量复判资产，旧的部分复判资产会保留在注册表但默认不展示。
      </p>
      <el-empty
        v-if="topic1ValueQaAssets.length === 0"
        description="尚未导入课题一 value_qa 预跑资产。"
      >
        <template #description>
          <span>尚未导入课题一 value_qa 预跑资产。</span>
          <code>node scripts/import-topic1-value-qa-asset.mjs --path-style windows</code>
        </template>
      </el-empty>
      <div v-else class="asset-grid">
        <article v-for="asset in topic1ValueQaAssets" :key="asset.asset_id" class="asset-card">
          <div class="asset-card__top">
            <div>
              <h4>{{ getValueQaDisplayName(asset) }}</h4>
              <span>{{ getValueQaSubtitle(asset) }}</span>
            </div>
            <div class="asset-card__badges">
              <span class="asset-id">{{ asset.asset_id }}</span>
              <span class="source-pill is-valueqa">高 / 中 / 低三档回答对照</span>
              <span class="source-pill" :class="getValueQaModelEvalBadgeClass(asset)">
                {{ getValueQaModelEvalBadgeLabel(asset) }}
              </span>
            </div>
          </div>

          <div class="valueqa-metrics">
            <div>
              <span>样本数</span>
              <strong>{{ getManifestString(asset, 'sample_count') }}</strong>
            </div>
            <div>
              <span>三档对照组</span>
              <strong>{{ getManifestString(asset, 'group_count') }}</strong>
            </div>
            <div>
              <span>档位分布</span>
              <strong>{{ getValueQaDistributionLabel(asset) }}</strong>
            </div>
            <div>
              <span>人工抽检状态</span>
              <strong>{{ getValueQaQcLabel(asset) }}</strong>
            </div>
          </div>

          <dl class="asset-fields">
            <div>
              <dt>Schema</dt>
              <dd>{{ getManifestString(asset, 'schema_id') }}</dd>
            </div>
            <div>
              <dt>Release</dt>
              <dd>{{ getManifestString(asset, 'release_kind') }}</dd>
            </div>
            <div>
              <dt>复判线索</dt>
              <dd>{{ getValueQaTraceLabel(asset) }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>模型评测</dt>
              <dd>{{ getValueQaModelEvalLabel(asset) }}</dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd class="mono">{{ compactHash(asset.artifact_sha256) }}</dd>
            </div>
          </dl>

          <div class="valueqa-recheck">
            <div class="valueqa-recheck__header">
              <div>
                <b>{{ getValueQaRecheckTitle(asset) }}</b>
                <p>{{ getValueQaRecheckDescription(asset) }}</p>
              </div>
              <span class="source-pill" :class="getValueQaRecheckBadgeClass(asset)">
                {{ getValueQaRecheckBadgeLabel(asset) }}
              </span>
            </div>
            <p v-if="isValueQaRecheckLoading(asset)" class="valueqa-recheck__state">
              复判摘要读取中...
            </p>
            <p v-else-if="getValueQaRecheckError(asset)" class="valueqa-recheck__state">
              复判摘要暂不可用
            </p>
            <template v-else-if="hasValueQaRecheckSummary(asset)">
              <div class="valueqa-recheck__grid">
                <div>
                  <span>覆盖</span>
                  <strong>{{ getValueQaRecheckCoverageLabel(asset) }}</strong>
                </div>
                <div>
                  <span>一致率</span>
                  <strong>{{ getValueQaRecheckAccuracyLabel(asset) }}</strong>
                </div>
                <div>
                  <span>low 问题样本</span>
                  <strong>{{ getValueQaRecheckLowIssueLabel(asset) }}</strong>
                </div>
              </div>
              <div
                v-if="getValueQaRecheckIssueItems(asset).length > 0"
                class="valueqa-recheck__chips"
              >
                <span
                  v-for="item in getValueQaRecheckIssueItems(asset)"
                  :key="item.type"
                  class="valueqa-recheck__chip"
                >
                  {{ item.type }} {{ item.count }}
                </span>
              </div>
            </template>
            <p v-else class="valueqa-recheck__state">暂无档位复判摘要。</p>
          </div>

          <div class="valueqa-summary">
            <div class="valueqa-summary__header">
              <div>
                <b>高 / 中 / 低三档回答对照</b>
                <p>
                  分组来自平台导入时记录的 group_id 规则；当前抽屉只展示 preview。 全文、source
                  reference、下载入口等待课题一确认展示边界后再放开。
                </p>
              </div>
              <el-button size="small" type="primary" @click="openValueQaGroups(asset)">
                查看三档 preview
              </el-button>
            </div>
            <div class="valueqa-level-grid">
              <div v-for="item in getValueQaLevelItems(asset)" :key="item.level">
                <span>{{ item.level }}</span>
                <strong>{{ item.count }}</strong>
              </div>
            </div>
          </div>

          <details class="asset-manifest">
            <summary>查看 manifest 摘要</summary>
            <pre>{{ JSON.stringify(asset.manifest, null, 2) }}</pre>
          </details>
        </article>
      </div>
    </section>

    <BenchmarkTopic3RiskSection
      v-if="!resourceMode || topic3RiskAssets.length > 0"
      :asset-id="resourceMode ? topic3RiskAssets[0]?.asset_id : undefined"
      :fallback-asset="resourceMode ? (topic3RiskAssets[0] ?? null) : null"
      @view-evaluations="$emit('view-evaluations')"
    />

    <section v-if="!resourceMode || topic3CulturalAssets.length > 0" class="asset-section">
      <div class="asset-section__title">
        <h4>课题三文化多样性语料资产</h4>
        <span class="source-pill">prerun_snapshot</span>
      </div>
      <p class="asset-section__desc">
        文化多样性预跑资产用于展示民族覆盖、L1/L2/L3 难度构成与审核通过状态。当前仅导入语料资产，
        模型评测结果保持 pending_import。
      </p>
      <el-empty
        v-if="topic3CulturalAssets.length === 0"
        description="尚未导入课题三文化多样性预跑资产。"
      />
      <div v-else class="asset-grid">
        <article v-for="asset in topic3CulturalAssets" :key="asset.asset_id" class="asset-card">
          <div class="asset-card__top">
            <div>
              <h4>{{ asset.name }}</h4>
              <span>{{ asset.source_mode }}</span>
            </div>
            <div class="asset-card__badges">
              <span class="asset-id">{{ asset.asset_id }}</span>
              <span class="source-pill">reviewed corpus</span>
              <span class="source-pill is-pending">
                {{ getManifestString(asset, 'model_eval_status') }}
              </span>
            </div>
          </div>

          <div class="prerun-metrics">
            <div>
              <span>样本数</span>
              <strong>{{ getManifestString(asset, 'sample_count') }}</strong>
            </div>
            <div>
              <span>民族分布</span>
              <strong>{{ getCulturalDistributionLabel(asset, 'ethnic_distribution') }}</strong>
            </div>
            <div>
              <span>L1/L2/L3</span>
              <strong>{{ getCulturalDistributionLabel(asset, 'difficulty_distribution') }}</strong>
            </div>
            <div>
              <span>review passed</span>
              <strong>{{ getCulturalReviewPassedLabel(asset) }}</strong>
            </div>
          </div>

          <dl class="asset-fields">
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd>{{ getManifestString(asset, 'source_run_id') }}</dd>
            </div>
            <div>
              <dt>Release</dt>
              <dd>{{ getManifestString(asset, 'release_kind') }}</dd>
            </div>
            <div>
              <dt>Source Repo</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_repo') }}</dd>
            </div>
            <div>
              <dt>Source Mode</dt>
              <dd>{{ asset.source_mode }}</dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd class="mono">{{ compactHash(asset.artifact_sha256) }}</dd>
            </div>
          </dl>

          <div class="prerun-summary">
            <div class="prerun-summary__header">
              <div>
                <b>文化多样性样本查看</b>
                <p>支持按民族、难度和关键词筛选样本，查看背景、问题、标准答案与 rubric。</p>
              </div>
              <el-button size="small" type="primary" @click="openCulturalSamples(asset)">
                查看样本
              </el-button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section v-if="!resourceMode || prerunAssets.length > 0" class="asset-section">
      <div class="asset-section__title">
        <h4>课题二 simple / hard 预跑快照</h4>
        <span class="source-pill">prerun_snapshot</span>
      </div>
      <p class="asset-section__desc">
        这组资产用于 Demo 稳定兜底。只有通过严格导入校验的课题二正式交付包才会展示； 缺少
        report、results 或 simple / hard 血缘字段时不由平台补造。
      </p>
      <el-empty
        v-if="prerunAssets.length === 0"
        description="尚未导入正式 prerun_snapshot。请等待课题二补齐 manifest、report、results、dynbench 与 simple / hard 血缘字段。"
      />
      <div v-else class="asset-grid">
        <article v-for="asset in prerunAssets" :key="asset.asset_id" class="asset-card">
          <div class="asset-card__top">
            <div>
              <h4>{{ asset.name }}</h4>
              <span>{{ asset.source_mode }}</span>
            </div>
            <div class="asset-card__badges">
              <span class="asset-id">{{ asset.asset_id }}</span>
              <span
                v-if="getDeliveryValidation(asset)?.strict_import_passed"
                class="source-pill is-valid"
              >
                strict import passed
              </span>
              <span class="source-pill">{{ getDifficultyCoverageLabel(asset) }}</span>
            </div>
          </div>

          <div class="prerun-metrics">
            <div>
              <span>总样本</span>
              <strong>{{ getManifestString(asset, 'sample_count') }}</strong>
            </div>
            <div>
              <span>simple</span>
              <strong>{{ getDifficultyCount(asset, 'simple') }}</strong>
            </div>
            <div>
              <span>hard</span>
              <strong>{{ getDifficultyCount(asset, 'hard') }}</strong>
            </div>
            <div>
              <span>配对数</span>
              <strong>{{ getPlatformSummaryNumber(asset, 'pair_count') }}</strong>
            </div>
          </div>

          <dl class="asset-fields">
            <div>
              <dt>Seed Set</dt>
              <dd class="mono">{{ getManifestString(asset, 'seed_set_id') }}</dd>
            </div>
            <div>
              <dt>Language</dt>
              <dd>{{ getManifestString(asset, 'language') }}</dd>
            </div>
            <div>
              <dt>Sample Count</dt>
              <dd>{{ getManifestString(asset, 'sample_count') }}</dd>
            </div>
            <div>
              <dt>Moderators</dt>
              <dd>{{ getModeratorLabel(asset) }}</dd>
            </div>
            <div>
              <dt>ASR 口径</dt>
              <dd>{{ getManifestString(asset, 'asr_definition') }}</dd>
            </div>
            <div>
              <dt>Evaluator</dt>
              <dd>{{ getManifestString(asset, 'evaluator_version') }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd class="mono">{{ compactHash(asset.artifact_sha256) }}</dd>
            </div>
          </dl>

          <div class="prerun-summary">
            <div class="prerun-summary__header">
              <div>
                <b>simple / hard 难度依据</b>
                <p>难度来自生成过程、改写轮次、策略链和 QA gate，不按单一模型得分倒推。</p>
              </div>
              <el-button size="small" type="primary" @click="openTopic2Pairs(asset)">
                查看配对样本
              </el-button>
            </div>
            <div class="difficulty-pair-grid">
              <article>
                <span>simple</span>
                <strong>{{ getDifficultyCount(asset, 'simple') }}</strong>
                <small>rewrite {{ getRewriteRoundsLabel(asset, 'simple') }}</small>
                <p>{{ getSimpleBasis(asset) }}</p>
              </article>
              <article>
                <span>hard</span>
                <strong>{{ getDifficultyCount(asset, 'hard') }}</strong>
                <small>rewrite {{ getRewriteRoundsLabel(asset, 'hard') }}</small>
                <p>{{ getHardBasis(asset) }}</p>
              </article>
            </div>

            <div class="strategy-row">
              <el-tooltip
                v-for="strategy in getStrategyItems(asset)"
                :key="strategy.name"
                :content="getStrategyTooltip(strategy.name)"
                placement="top"
              >
                <span class="strategy-chip">{{ strategy.name }} · {{ strategy.count }}</span>
              </el-tooltip>
              <span v-if="getStrategyItems(asset).length === 0" class="strategy-chip is-muted">
                hard 策略待聚合
              </span>
            </div>

            <dl class="difficulty-fields">
              <div>
                <dt>血缘字段覆盖</dt>
                <dd>{{ getTraceCoverageLabel(asset) }}</dd>
              </div>
              <div>
                <dt>
                  <el-tooltip :content="termTooltips.qaGate" placement="top">
                    <span>QA Gate</span>
                  </el-tooltip>
                </dt>
                <dd>{{ getQaGateLabel(asset) }}</dd>
              </div>
            </dl>
          </div>

          <div class="validation-details">
            <details class="asset-manifest">
              <summary>交付文件</summary>
              <div class="required-file-grid">
                <span
                  v-for="file in requiredPrerunFiles"
                  :key="file"
                  :class="{ 'is-ready': hasRequiredFile(asset, file) }"
                >
                  {{ file }}
                </span>
              </div>
            </details>
            <details class="asset-manifest">
              <summary>来源与校验</summary>
              <pre>{{ JSON.stringify(getDeliveryValidation(asset) || {}, null, 2) }}</pre>
            </details>
            <details class="asset-manifest">
              <summary>原始 manifest</summary>
              <pre>{{ JSON.stringify(asset.manifest, null, 2) }}</pre>
            </details>
          </div>
        </article>
      </div>
    </section>

    <section
      v-if="!resourceMode || liveAssets.length > 0"
      ref="liveRunSectionRef"
      class="asset-section"
    >
      <div class="asset-section__title">
        <h4>现场生成任务冻结资产</h4>
        <span class="source-pill is-live">
          {{
            liveAssets.length > 0
              ? `最新 1 条已展开 / 历史 ${historicalLiveAssets.length} 条`
              : 'live_run'
          }}
        </span>
      </div>
      <div class="live-run-notice">
        <div>
          <b>现场运行 vs 正式预跑</b>
          <p>
            现场运行 live_run 用于验证 AutoBench 链路是否真实可跑，包括采样、Moderator
            调用、日志流和产物冻结；它不是完整规模的模型评测结论。正式 simple / hard
            指标以通过严格导入校验的 prerun_snapshot 和独立 results.json 为准。
          </p>
        </div>
        <div class="live-run-notice__tags">
          <span>live_run：现场链路验证</span>
          <span>prerun_snapshot：正式预跑快照</span>
          <span>evaluation_summary：模型评测来源</span>
        </div>
      </div>
      <el-empty
        v-if="liveAssets.length === 0"
        description="当前还没有 live_run 冻结资产。完成一次生成任务并成功打包后，这里会显示资产摘要。"
      />
      <div v-else class="live-run-stack">
        <article
          v-if="latestLiveAsset"
          :ref="(el) => registerAssetElement(latestLiveAsset.asset_id, el)"
          class="asset-card live-run-card"
          :class="{ 'is-focused': activeHighlightAssetId === latestLiveAsset.asset_id }"
        >
          <div class="asset-card__top">
            <div>
              <h4>{{ getLiveRunDisplayName(latestLiveAsset) }}</h4>
              <span>{{ getLiveRunSubtitle(latestLiveAsset) }}</span>
            </div>
            <div class="asset-card__right">
              <div class="asset-card__badges">
                <span class="asset-id">{{ latestLiveAsset.asset_id }}</span>
                <span class="source-pill is-live">live_run</span>
                <span class="source-pill is-valid">frozen artifact</span>
              </div>
              <div class="asset-card__actions">
                <el-button size="small" type="primary" @click="openLiveRunSummary(latestLiveAsset)">
                  查看运行摘要
                </el-button>
                <el-button
                  v-if="!isTopic3CulturalAsset(latestLiveAsset)"
                  size="small"
                  @click="openLiveRunConsole(latestLiveAsset)"
                >
                  {{ getLiveRunConsoleButtonLabel(latestLiveAsset) }}
                </el-button>
              </div>
            </div>
          </div>

          <div class="live-run-basis">
            <b>运行摘要</b>
            <p>{{ getLiveRunBasisText(latestLiveAsset) }}</p>
          </div>

          <div class="live-run-metrics">
            <div v-for="item in getLiveRunMetricItems(latestLiveAsset)" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>

          <dl class="asset-fields">
            <div>
              <dt>Agent</dt>
              <dd>{{ getManifestString(latestLiveAsset, 'agent_id') }}</dd>
            </div>
            <div>
              <dt>{{ getLiveRunBudgetLabel(latestLiveAsset) }}</dt>
              <dd>{{ getLiveRunBudgetValue(latestLiveAsset) }}</dd>
            </div>
            <div>
              <dt>{{ getLiveRunSecondaryFieldLabel(latestLiveAsset) }}</dt>
              <dd>
                {{ getLiveRunSecondaryFieldValue(latestLiveAsset) }}
              </dd>
            </div>
            <div>
              <dt>
                {{ getLiveRunModelFieldLabel(latestLiveAsset) }}
              </dt>
              <dd>
                {{ getLiveRunModelFieldValue(latestLiveAsset) }}
              </dd>
            </div>
            <div>
              <dt>
                {{
                  isTopic1ValueQaAsset(latestLiveAsset) || isTopic3CulturalAsset(latestLiveAsset)
                    ? 'Seed'
                    : 'Sampling Seed'
                }}
              </dt>
              <dd>{{ getLiveRunSeedValue(latestLiveAsset) }}</dd>
            </div>
            <div>
              <dt>Source Commit</dt>
              <dd class="mono">{{ getManifestString(latestLiveAsset, 'source_commit') }}</dd>
            </div>
            <div>
              <dt>Artifact SHA-256</dt>
              <dd class="mono">{{ compactHash(latestLiveAsset.artifact_sha256) }}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{{ formatDate(latestLiveAsset.created_at) }}</dd>
            </div>
          </dl>

          <div v-if="isTopic3DifficultyAsset(latestLiveAsset)" class="difficulty-summary">
            <div class="difficulty-summary__header">
              <div>
                <b>动态难度结构</b>
                <p>H1-H4 是混合样本结构层级，hover 查看 span 数量、拼接方式与解释边界。</p>
              </div>
              <span class="difficulty-label">
                {{ getManifestString(latestLiveAsset, 'platform_difficulty_label') }}
              </span>
            </div>

            <div class="difficulty-levels">
              <el-tooltip
                v-for="item in getDifficultyItems(latestLiveAsset)"
                :key="item.level"
                placement="top"
                effect="light"
                popper-class="difficulty-level-tooltip"
              >
                <template #content>
                  <div class="difficulty-tooltip">
                    <b>{{ item.level }} · {{ item.explanation.title }}</b>
                    <span>{{ item.explanation.shape }}</span>
                    <span>构造策略：{{ item.explanation.strategy }}</span>
                    <span>{{ item.explanation.note }}</span>
                  </div>
                </template>
                <div class="difficulty-level" tabindex="0">
                  <span>{{ item.level }}</span>
                  <strong>{{ item.count }}</strong>
                </div>
              </el-tooltip>
            </div>

            <dl class="difficulty-fields">
              <div>
                <dt>原生难度体系</dt>
                <dd>{{ getManifestString(latestLiveAsset, 'native_difficulty_schema') }}</dd>
              </div>
              <div>
                <dt>平台解释依据</dt>
                <dd>{{ getManifestString(latestLiveAsset, 'platform_difficulty_basis') }}</dd>
              </div>
              <div>
                <dt>Benchmark Type</dt>
                <dd>{{ getManifestString(latestLiveAsset, 'benchmark_type') }}</dd>
              </div>
              <div>
                <dt>Adapter</dt>
                <dd>{{ getManifestString(latestLiveAsset, 'adapter_version') }}</dd>
              </div>
            </dl>
          </div>

          <details class="asset-manifest">
            <summary>查看 manifest 摘要</summary>
            <pre>{{ JSON.stringify(latestLiveAsset.manifest, null, 2) }}</pre>
          </details>
        </article>

        <el-collapse
          v-if="historicalLiveAssets.length > 0"
          v-model="expandedLiveRunHistory"
          class="live-run-history"
        >
          <el-collapse-item
            v-for="asset in historicalLiveAssets"
            :key="asset.asset_id"
            :name="asset.asset_id"
          >
            <template #title>
              <div class="live-run-history__title">
                <span>{{ formatDate(asset.created_at) }}</span>
                <b class="mono">{{ asset.asset_id }}</b>
                <span>{{ getManifestString(asset, 'agent_id') }}</span>
                <span class="mono">SHA {{ compactHash(asset.artifact_sha256) }}</span>
              </div>
            </template>
            <div
              :ref="(el) => registerAssetElement(asset.asset_id, el)"
              class="live-run-history__body"
              :class="{ 'is-focused': activeHighlightAssetId === asset.asset_id }"
            >
              <dl class="asset-fields">
                <div>
                  <dt>{{ getLiveRunBudgetLabel(asset) }}</dt>
                  <dd>{{ getLiveRunBudgetValue(asset) }}</dd>
                </div>
                <div>
                  <dt>{{ getLiveRunSecondaryFieldLabel(asset) }}</dt>
                  <dd>{{ getLiveRunSecondaryFieldValue(asset) }}</dd>
                </div>
                <div>
                  <dt>Source Commit</dt>
                  <dd class="mono">{{ getManifestString(asset, 'source_commit') }}</dd>
                </div>
                <div>
                  <dt>Task ID</dt>
                  <dd class="mono">{{ asset.task_id }}</dd>
                </div>
              </dl>
              <div class="asset-card__actions">
                <el-button size="small" type="primary" @click="openLiveRunSummary(asset)">
                  查看运行摘要
                </el-button>
                <el-button
                  v-if="!isTopic3CulturalAsset(asset)"
                  size="small"
                  @click="openLiveRunConsole(asset)"
                >
                  {{ getLiveRunConsoleButtonLabel(asset) }}
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </section>

    <BenchmarkLiveRunSummaryDrawer
      v-model="liveRunSummaryDrawerVisible"
      :asset="selectedLiveRunAsset"
      @open-samples="openCulturalSamplesFromLiveRun"
    />
    <BenchmarkTopic2PrerunSampleDrawer
      v-model="topic2PairDrawerVisible"
      :asset="selectedTopic2Asset"
    />
    <BenchmarkTopic1ValueQaSampleDrawer
      v-model="valueQaGroupDrawerVisible"
      :asset="selectedValueQaAsset"
    />
    <BenchmarkCulturalSampleDrawer
      v-model="culturalSampleDrawerVisible"
      :asset="selectedCulturalAsset"
    />
    <BenchmarkCbrneSampleDrawer
      v-model="cbrneSampleDrawerVisible"
      :asset="selectedCbrneAsset"
      :focus-sample="focusedCbrneSample"
      @closed="handleCbrneDrawerClosed"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import BenchmarkLiveRunSummaryDrawer from './live-run-summary/BenchmarkLiveRunSummaryDrawer.vue'
import BenchmarkCbrneQueryPanel from './BenchmarkCbrneQueryPanel.vue'
import BenchmarkTopic3RiskSection from './BenchmarkTopic3RiskSection.vue'
import BenchmarkTopic1ValueQaSampleDrawer from './BenchmarkTopic1ValueQaSampleDrawer.vue'
import BenchmarkTopic2PrerunSampleDrawer from './BenchmarkTopic2PrerunSampleDrawer.vue'
import BenchmarkCulturalSampleDrawer from './BenchmarkCulturalSampleDrawer.vue'
import BenchmarkCbrneSampleDrawer from './BenchmarkCbrneSampleDrawer.vue'
import { getTopic1ValueQaRecheckSummary } from '@/api/benchmark'
import {
  SCALE_LABELS,
  CULTURAL_STRUCTURE_BAND_LABELS,
  type CulturalStructureBand,
  type StandardBenchmarkScale,
} from '@/utils/benchmark/standardTaskPayload'
import { formatApiDate } from '@/utils/datetime'
import {
  CBRNE_SOURCE_CHIP_LIMIT,
  cbrneCountChips,
  cbrneLabelCount,
} from '@/utils/benchmark/cbrneQuery'
import type {
  BenchmarkArtifactItem,
  BenchmarkAssetFocusRequest,
  BenchmarkCbrneSampleRefResponse,
  BenchmarkTopic1ValueQaRecheckSummary,
} from '@/types'

const props = defineProps<{
  artifacts: BenchmarkArtifactItem[]
  registryAssets: BenchmarkArtifactItem[]
  isLoading: boolean
  isActiveTab: boolean
  errorMessage: string
  focusRequest?: BenchmarkAssetFocusRequest | null
  /** Deep-linked masked sample; selected without disclosing full text (#175). */
  focusSample?: BenchmarkCbrneSampleRefResponse | null
  resourceMode?: boolean
}>()

const emit = defineEmits<{
  (event: 'refresh'): void
  (event: 'view-evaluations'): void
  (event: 'focus-consumed', focusKey: string): void
  (event: 'close-sample-resource'): void
}>()

const selectedCbrneAsset = ref<BenchmarkArtifactItem | null>(null)
const focusedCbrneSample = ref<BenchmarkCbrneSampleRefResponse | null>(null)
const cbrneSampleDrawerVisible = ref(false)
const selectedCulturalAsset = ref<BenchmarkArtifactItem | null>(null)
const culturalSampleDrawerVisible = ref(false)
const selectedTopic2Asset = ref<BenchmarkArtifactItem | null>(null)
const topic2PairDrawerVisible = ref(false)
const selectedValueQaAsset = ref<BenchmarkArtifactItem | null>(null)
const valueQaGroupDrawerVisible = ref(false)
const selectedLiveRunAsset = ref<BenchmarkArtifactItem | null>(null)
const liveRunSummaryDrawerVisible = ref(false)
const valueQaRecheckSummaries = ref<Record<string, BenchmarkTopic1ValueQaRecheckSummary | null>>({})
const valueQaRecheckLoading = ref<Record<string, boolean>>({})
const valueQaRecheckErrors = ref<Record<string, string>>({})
const liveRunSectionRef = ref<HTMLElement | null>(null)
const activeHighlightAssetId = ref<string | null>(null)
const expandedLiveRunHistory = ref<string[]>([])
const expandedCbrneSources = ref<Record<string, boolean>>({})
const processedFocusKeys = ref(new Set<string>())
const focusAttemptCount = ref<Record<string, number>>({})
const assetElementMap = new Map<string, HTMLElement>()
let highlightTimer: ReturnType<typeof setTimeout> | null = null

const allTopic1ValueQaAssets = computed(() =>
  props.registryAssets.filter((asset) => isTopic1ValueQaAsset(asset)),
)
const topic1ValueQaAssets = computed(() =>
  selectVisibleTopic1ValueQaAssets(allTopic1ValueQaAssets.value),
)
const cbrneDatasetAssets = computed(() =>
  props.registryAssets
    .filter((asset) => isCbrneDatasetSnapshotAsset(asset))
    .sort(compareCbrneAssets),
)
const topic3RiskAssets = computed(() =>
  props.registryAssets.filter(
    (asset) =>
      isTopic3RiskAsset(asset) &&
      (props.resourceMode || !hiddenTopic3RiskAssetIds.has(asset.asset_id)),
  ),
)
const topic3CulturalAssets = computed(() =>
  props.registryAssets.filter((asset) => isTopic3CulturalAsset(asset)),
)
const prerunAssets = computed(() =>
  props.registryAssets.filter(
    (asset) =>
      asset.source_mode === 'prerun_snapshot' &&
      !isTopic1ValueQaAsset(asset) &&
      !isTopic3RiskAsset(asset) &&
      !isTopic3CulturalAsset(asset),
  ),
)
const liveAssets = computed(() => {
  const byId = new Map<string, BenchmarkArtifactItem>()
  for (const asset of props.registryAssets.filter((item) => item.source_mode === 'live_run')) {
    byId.set(asset.asset_id, asset)
  }
  for (const asset of props.artifacts) {
    byId.set(asset.asset_id, asset)
  }
  return Array.from(byId.values()).sort(compareAssetsByCreatedAtDesc)
})
const latestLiveAsset = computed(() => liveAssets.value[0] ?? null)
const historicalLiveAssets = computed(() => liveAssets.value.slice(1))
const registeredAssetCount = computed(
  () =>
    prerunAssets.value.length +
    topic1ValueQaAssets.value.length +
    topic3RiskAssets.value.length +
    topic3CulturalAssets.value.length +
    cbrneDatasetAssets.value.length,
)
const valueQaLevels = ['high', 'medium', 'low'] as const
const difficultyLevels = ['H1', 'H2', 'H3', 'H4'] as const
const topic3DifficultyExplanations = {
  H1: {
    title: '同答混合',
    shape: '结构：1 个 harmful span + 1 个 harmless span。',
    strategy: 'same_answer',
    note: '用于验证模型能否在较简单混合结构中定位有害片段，同时保留无害内容。',
  },
  H2: {
    title: '有害片段增压',
    shape: '结构：2 个 harmful spans + 1 个 harmless span。',
    strategy: 'background_nesting',
    note: '更偏向测试多处有害片段识别与编辑，不应直接理解为一定比 H3 更难。',
  },
  H3: {
    title: '无害保留增压',
    shape: '结构：1 个 harmful span + 2 个 harmless spans。',
    strategy: 'near_semantic_mix',
    note: '更偏向测试编辑有害内容时的 harmless retention 压力，不应直接理解为一定比 H2 更难。',
  },
  H4: {
    title: '交错多片段',
    shape: '结构：2 个 harmful spans + 2 个 harmless spans，且 interleaving=true。',
    strategy: 'interleaved_multi_span',
    note: '当前配置中结构复杂度最高，但仍不等同于风险严重度或模型实测难度。',
  },
} as const
const hiddenTopic3RiskAssetIds = new Set(['topic3_risk_workflow_v3_safe_low_400'])
const requiredPrerunFiles = ['manifest.json', 'report.md', 'results.json', 'dynbench.jsonl']
const termTooltips = {
  qaGate: 'QA Gate 是 hard 改写样本的质量验收门，确认改写后仍保持原始风险意图且格式可用。',
}
const strategyTooltipEntries = [
  ['translate_', '翻译或跨语种表达改写'],
  ['roleplay', '角色扮演式包装'],
  ['authority_endorsement', '伪装成权威背书'],
  ['evidence_based_persuasion', '用证据或论证话术包装'],
  ['hypothetical_frame', '假设性场景包装'],
  ['technical_terms', '技术术语包装'],
  ['misrepresentation', '误导性表述'],
  ['slang_style', '俚语或风格化表达'],
] as const
onBeforeUnmount(() => {
  if (highlightTimer) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
  assetElementMap.clear()
})

watch(
  topic1ValueQaAssets,
  (assets) => {
    void loadValueQaRecheckSummaries(assets)
  },
  { immediate: true },
)

watch(
  () => props.focusRequest,
  (request) => {
    if (!request) {
      return
    }
    void focusLiveAsset(request)
  },
  { immediate: true },
)

watch(
  () => [
    props.isLoading,
    props.isActiveTab,
    liveAssets.value.length,
    historicalLiveAssets.value.length,
  ],
  () => {
    if (!props.focusRequest) {
      return
    }
    void focusLiveAsset(props.focusRequest)
  },
)

function formatDate(value?: string | null) {
  return formatApiDate(value)
}

function compactHash(value: string) {
  if (value.length <= 18) {
    return value
  }
  return `${value.slice(0, 10)}...${value.slice(-8)}`
}

function getManifestString(asset: BenchmarkArtifactItem, key: string) {
  const value = asset.manifest[key]
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '-'
}

function getManifestOptionalString(asset: BenchmarkArtifactItem, key: string) {
  const value = asset.manifest[key]
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed !== '' ? trimmed : null
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  return null
}

function getManifestFirstString(asset: BenchmarkArtifactItem, keys: string[]) {
  for (const key of keys) {
    const value = getManifestString(asset, key)
    if (value !== '-') {
      return value
    }
  }
  return '-'
}

function getLiveRunMetricItems(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return [
      { label: '主题', value: getTopic1LiveRunTopicLabel(asset) },
      { label: '三档组', value: getTopic1LiveRunGroupLabel(asset) },
      { label: '样本数', value: getManifestString(asset, 'sample_count') },
      { label: '三档分布', value: getTopic1LiveRunLevelDistributionLabel(asset) },
    ]
  }
  if (isTopic3DifficultyAsset(asset)) {
    return [
      { label: '样本预算', value: getLiveRunBudgetValue(asset) },
      { label: 'Language', value: getLiveRunParameterLabel(asset, 'language') },
      { label: 'Generated Samples', value: getManifestString(asset, 'sample_count') },
      { label: 'H1-H4 配额', value: getTopic3DifficultyCountsLabel(asset) },
    ]
  }
  if (isTopic3CulturalAsset(asset)) {
    return [
      { label: '规模', value: getTopic3CulturalScaleLabel(asset) },
      { label: '难度等级', value: getTopic3CulturalBandLabel(asset) },
      { label: '样本数', value: getManifestString(asset, 'sample_count') },
      { label: 'L1–L3', value: getTopic3CulturalLevelLabel(asset) },
    ]
  }
  return [
    { label: 'Budget', value: getLiveRunParameterLabel(asset, 'budget') },
    { label: 'Language', value: getLiveRunParameterLabel(asset, 'language') },
    { label: 'Sample Count', value: getManifestString(asset, 'sample_count') },
    { label: 'Max Turns', value: getLiveRunParameterLabel(asset, 'max_turns') },
  ]
}

function getLiveRunBudgetLabel(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return 'Corpus'
  }
  if (isTopic3DifficultyAsset(asset)) {
    return '样本预算'
  }
  if (isTopic3CulturalAsset(asset)) {
    return '请求条数'
  }
  return 'Budget'
}

function getLiveRunBudgetValue(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'corpus_jsonl')
  }
  if (isTopic3DifficultyAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'total_sample_count')
  }
  if (isTopic3CulturalAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'total_sample_count')
  }
  return getLiveRunParameterLabel(asset, 'budget')
}

function getLiveRunDisplayName(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return '课题一价值评测语料生成'
  }
  if (isTopic3CulturalAsset(asset)) {
    return '课题三文化多样性语料生成'
  }
  return asset.name
}

function getLiveRunSubtitle(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return 'value_qa 三档样本现场生成与结构校验'
  }
  if (isTopic3DifficultyAsset(asset)) {
    return '动态难度题库现场生成'
  }
  if (isTopic3CulturalAsset(asset)) {
    return '按 L1–L3 生成多民族文化评测语料'
  }
  return '现场小预算链路验证'
}

function getLiveRunBasisText(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    const topic = getTopic1LiveRunTopicLabel(asset)
    const groups = getManifestString(asset, 'generated_group_count')
    const samples = getManifestString(asset, 'sample_count')
    const validation = getNestedObject(asset.manifest as Record<string, unknown>, 'validation')
    const validationText = validation.passed === true ? '结构校验通过' : '结构校验待确认'
    return `本次围绕“${topic}”生成 ${groups} 个三档组，共 ${samples} 条样本；${validationText}，并已冻结为 live_run 资产。`
  }
  if (isTopic3DifficultyAsset(asset)) {
    return '本次完成动态难度题库生成、质量检查和产物冻结，可作为现场链路验证证据。'
  }
  if (isTopic3CulturalAsset(asset)) {
    const scale = getTopic3CulturalScaleLabel(asset)
    const band = getTopic3CulturalBandLabel(asset)
    const samples = getManifestString(asset, 'sample_count')
    const ethnicGroups = getLiveRunParameterLabel(asset, 'allowed_ethnic_groups')
    const ethnicCount =
      ethnicGroups === '-' ? '多' : String(ethnicGroups.split(',').filter(Boolean).length)
    const passed = getManifestString(asset, 'review_passed_count')
    return `本次按「${scale} · ${band}」生成 ${samples} 条文化多样性语料，覆盖 ${ethnicCount} 个民族；审核通过 ${passed}/${samples}，已冻结为 live_run 资产。`
  }
  return '本次 AutoBench 完成 SeedBank 采样、Moderator 测试、Agent 日志流与产物冻结，可作为现场链路验证证据。'
}

function getLiveRunSecondaryFieldLabel(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'generation_mode') === 'dimension' ? '维度' : '检索方式'
  }
  if (isTopic3CulturalAsset(asset)) {
    return '民族'
  }
  return isTopic3DifficultyAsset(asset) ? 'Guard Model' : 'Moderators'
}

function getLiveRunSecondaryFieldValue(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    const mode = getLiveRunParameterLabel(asset, 'generation_mode')
    if (mode === 'dimension') {
      return getLiveRunParameterLabel(asset, 'dimension')
    }
    return getLiveRunParameterLabel(asset, 'retrieval_mode')
  }
  if (isTopic3DifficultyAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'guard_model')
  }
  if (isTopic3CulturalAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'allowed_ethnic_groups')
  }
  return getLiveRunParameterLabel(asset, 'moderators')
}

function getLiveRunModelFieldLabel(asset: BenchmarkArtifactItem) {
  return isTopic3DifficultyAsset(asset) ? 'Generation Model' : 'Agent Model'
}

function getLiveRunModelFieldValue(asset: BenchmarkArtifactItem) {
  if (isTopic3DifficultyAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'generation_model')
  }
  return getLiveRunParameterLabel(asset, 'model')
}

function getLiveRunSeedValue(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'seed')
  }
  if (isTopic3CulturalAsset(asset)) {
    return getLiveRunParameterLabel(asset, 'random_seed')
  }
  return getLiveRunParameterLabel(asset, 'sampling_seed')
}

function getTopic3CulturalScaleLabel(asset: BenchmarkArtifactItem) {
  const scale = getLiveRunParameterLabel(asset, 'scale')
  if (scale in SCALE_LABELS) {
    return SCALE_LABELS[scale as StandardBenchmarkScale]
  }
  return scale
}

function getTopic3CulturalBandLabel(asset: BenchmarkArtifactItem) {
  const band = getLiveRunParameterLabel(asset, 'structure_band')
  if (band in CULTURAL_STRUCTURE_BAND_LABELS) {
    return CULTURAL_STRUCTURE_BAND_LABELS[band as CulturalStructureBand]
  }
  return band
}

function getTopic3CulturalLevelLabel(asset: BenchmarkArtifactItem) {
  const distribution = getManifestObject(asset, 'difficulty_distribution') ?? {}
  const parts = ['L1', 'L2', 'L3']
    .map((level) => `${level}:${toDisplayNumber(distribution[level])}`)
    .filter((part) => !part.endsWith(':0'))
  return parts.length > 0 ? parts.join(' / ') : '-'
}

function getTopic1LiveRunTopicLabel(asset: BenchmarkArtifactItem) {
  const parameters = getLiveRunParameters(asset)
  if (parameters.generation_mode === 'dimension') {
    return formatLiveRunValue(parameters.dimension)
  }
  return formatLiveRunValue(parameters.topic)
}

function getTopic1LiveRunGroupLabel(asset: BenchmarkArtifactItem) {
  const generated = getManifestString(asset, 'generated_group_count')
  const requested = getManifestString(asset, 'requested_group_count')
  return requested !== '-' ? `${generated} / ${requested}` : generated
}

function getTopic1LiveRunLevelDistributionLabel(asset: BenchmarkArtifactItem) {
  const distribution = getManifestObject(asset, 'quality_level_distribution') ?? {}
  const parts = valueQaLevels
    .map((level) => `${level} ${toDisplayNumber(distribution[level])}`)
    .filter((part) => !part.endsWith(' 0'))
  return parts.length > 0 ? parts.join(' / ') : '-'
}

function getLiveRunParameterLabel(asset: BenchmarkArtifactItem, key: string) {
  const parameters = getLiveRunParameters(asset)
  return formatLiveRunValue(parameters[key] ?? asset.manifest[key])
}

function getLiveRunParameters(asset: BenchmarkArtifactItem) {
  const parameters = asset.manifest.parameters
  if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) {
    return {} as Record<string, unknown>
  }
  return parameters as Record<string, unknown>
}

function formatLiveRunValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => String(item)).join(', ') : '-'
  }
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return '-'
}

function compareAssetsByCreatedAtDesc(a: BenchmarkArtifactItem, b: BenchmarkArtifactItem) {
  const left = Date.parse(a.created_at || '')
  const right = Date.parse(b.created_at || '')
  if (Number.isFinite(left) && Number.isFinite(right) && left !== right) {
    return right - left
  }
  if (Number.isFinite(left) && !Number.isFinite(right)) {
    return -1
  }
  if (!Number.isFinite(left) && Number.isFinite(right)) {
    return 1
  }
  return b.asset_id.localeCompare(a.asset_id)
}

function registerAssetElement(assetId: string, element: Element | ComponentPublicInstance | null) {
  if (!element) {
    assetElementMap.delete(assetId)
    return
  }
  const htmlElement =
    element instanceof HTMLElement
      ? element
      : element && '$el' in element && element.$el instanceof HTMLElement
        ? element.$el
        : null
  if (htmlElement) {
    assetElementMap.set(assetId, htmlElement)
  }
}

async function focusLiveAsset(request: BenchmarkAssetFocusRequest) {
  const focusKey = buildFocusKey(request)
  if (processedFocusKeys.value.has(focusKey)) {
    return
  }
  if (props.isLoading || !props.isActiveTab) {
    return
  }
  const attempt = (focusAttemptCount.value[focusKey] ?? 0) + 1
  focusAttemptCount.value = {
    ...focusAttemptCount.value,
    [focusKey]: attempt,
  }

  if (
    request.focusAssetId &&
    historicalLiveAssets.value.some((item) => item.asset_id === request.focusAssetId)
  ) {
    const nextExpanded = new Set(expandedLiveRunHistory.value)
    nextExpanded.add(request.focusAssetId)
    expandedLiveRunHistory.value = Array.from(nextExpanded)
  }

  let target = request.focusAssetId ? await resolveAssetElement(request.focusAssetId, 3) : null
  if (!target && request.focusAssetId && attempt < 4) {
    await waitForFrames(2)
    await focusLiveAsset(request)
    return
  }

  const fallback = liveRunSectionRef.value
  const canFallbackToSection =
    !request.focusAssetId ||
    !liveAssets.value.some((item) => item.asset_id === request.focusAssetId)
  const targetElement = target ?? (canFallbackToSection ? fallback : null)
  if (targetElement) {
    targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  if (target && request.focusAssetId) {
    markFocusedAsset(request.focusAssetId)
    const cbrneAsset = cbrneDatasetAssets.value.find(
      (item) => item.asset_id === request.focusAssetId,
    )
    if (cbrneAsset) {
      openCbrneSamples(cbrneAsset)
    }
  }
  if (target || canFallbackToSection) {
    processedFocusKeys.value.add(focusKey)
    clearFocusAttempt(focusKey)
    emit('focus-consumed', focusKey)
  }
}

function markFocusedAsset(assetId: string) {
  activeHighlightAssetId.value = assetId
  if (highlightTimer) {
    clearTimeout(highlightTimer)
  }
  highlightTimer = setTimeout(() => {
    if (activeHighlightAssetId.value === assetId) {
      activeHighlightAssetId.value = null
    }
  }, 1800)
}

function buildFocusKey(request: BenchmarkAssetFocusRequest) {
  return `${request.focusAssetId || 'section'}::${request.requestedAt}`
}

function clearFocusAttempt(focusKey: string) {
  if (!Object.prototype.hasOwnProperty.call(focusAttemptCount.value, focusKey)) {
    return
  }
  const next = { ...focusAttemptCount.value }
  delete next[focusKey]
  focusAttemptCount.value = next
}

async function resolveAssetElement(assetId: string, maxAttempts: number) {
  for (let i = 0; i < maxAttempts; i += 1) {
    await nextTick()
    await waitForFrames(1)
    const element = assetElementMap.get(assetId)
    if (element) {
      return element
    }
  }
  return null
}

function waitForFrames(frameCount: number) {
  return new Promise<void>((resolve) => {
    let remaining = frameCount
    const tick = () => {
      if (remaining <= 0) {
        resolve()
        return
      }
      remaining -= 1
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

function openLiveRunSummary(asset: BenchmarkArtifactItem) {
  selectedLiveRunAsset.value = asset
  liveRunSummaryDrawerVisible.value = true
}

function openLiveRunConsole(asset: BenchmarkArtifactItem) {
  const url = getLiveRunConsoleUrl(asset)
  window.open(url, '_blank', 'noopener,noreferrer')
}

function getLiveRunConsoleButtonLabel(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    return '查看课题一运行台'
  }
  if (isTopic3DifficultyAsset(asset)) {
    return '查看课题三运行台'
  }
  return '查看课题二运行台'
}

function getLiveRunConsoleUrl(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaAsset(asset)) {
    const upstream = getManifestString(asset, 'upstream_base_url')
    return upstream !== '-' ? upstream.replace(/\/$/, '') : '#'
  }
  const upstream = getManifestString(asset, 'upstream_base_url')
  const path = isTopic3DifficultyAsset(asset) ? '' : '/agent'
  if (upstream !== '-') {
    return `${upstream.replace(/\/$/, '')}${path}`
  }
  if (isTopic3DifficultyAsset(asset)) {
    return 'http://127.0.0.1:6331'
  }
  return 'http://127.0.0.1:8766/agent'
}

function getPlatformSummary(asset: BenchmarkArtifactItem) {
  return getManifestObject(asset, 'platform_summary')
}

function getDeliveryValidation(asset: BenchmarkArtifactItem) {
  return getManifestObject(asset, 'delivery_validation')
}

function getDifficultyCoverageLabel(asset: BenchmarkArtifactItem) {
  const coverage = getNestedArray(getPlatformSummary(asset), 'difficulty_coverage')
  if (coverage.length > 0) {
    return coverage.join(' + ')
  }
  const counts = getDifficultyCounts(asset)
  const available = ['simple', 'hard'].filter(
    (difficulty) => toDisplayNumber(counts[difficulty]) > 0,
  )
  return available.length > 0 ? available.join(' + ') : 'simple + hard'
}

function getDifficultyCounts(asset: BenchmarkArtifactItem) {
  const summaryCounts = getNestedObject(getPlatformSummary(asset), 'difficulty_counts')
  if (Object.keys(summaryCounts).length > 0) {
    return summaryCounts
  }
  return getNestedObject(asset.manifest as Record<string, unknown>, 'sample_count_by_difficulty')
}

function getDifficultyCount(asset: BenchmarkArtifactItem, difficulty: 'simple' | 'hard') {
  return toDisplayNumber(getDifficultyCounts(asset)[difficulty])
}

function getPlatformSummaryNumber(asset: BenchmarkArtifactItem, key: string) {
  return toDisplayNumber(getPlatformSummary(asset)?.[key])
}

function getModeratorLabel(asset: BenchmarkArtifactItem) {
  const moderators = asset.manifest.moderators
  if (Array.isArray(moderators) && moderators.length > 0) {
    return moderators.map((item) => String(item)).join(', ')
  }
  return '-'
}

function getRewriteRoundsLabel(asset: BenchmarkArtifactItem, difficulty: 'simple' | 'hard') {
  const rewriteRounds = getNestedObject(getPlatformSummary(asset), 'rewrite_rounds')
  const summary = getNestedObject(rewriteRounds, difficulty)
  if (summary.avg === null || summary.avg === undefined) {
    return '-'
  }
  return `${summary.min ?? '-'}-${summary.max ?? '-'} / avg ${summary.avg}`
}

function getSimpleBasis(asset: BenchmarkArtifactItem) {
  const basis = getManifestValue(asset, 'difficulty_basis')
  if (typeof basis === 'object' && basis && !Array.isArray(basis)) {
    const simple = (basis as Record<string, unknown>).simple
    if (typeof simple === 'string' && simple.trim()) {
      return simple
    }
  }
  return '原始 SeedBank query 或 0/1 轮轻量改写'
}

function getHardBasis(asset: BenchmarkArtifactItem) {
  const basis = getManifestValue(asset, 'difficulty_basis')
  if (typeof basis === 'object' && basis && !Array.isArray(basis)) {
    const hard = (basis as Record<string, unknown>).hard
    if (typeof hard === 'string' && hard.trim()) {
      return hard
    }
  }
  if (typeof basis === 'string' && basis.trim()) {
    return basis
  }
  return 'QA-passed 2-3 step semantic-preserving rewrite'
}

function getStrategyItems(asset: BenchmarkArtifactItem) {
  const strategies = getNestedObject(getPlatformSummary(asset), 'strategy_counts')
  return Object.entries(strategies)
    .map(([name, count]) => ({ name, count: toDisplayNumber(count) }))
    .filter((item) => item.count > 0)
}

function getStrategyTooltip(name: string) {
  const matched = strategyTooltipEntries.find(([prefix]) => name.includes(prefix))
  return matched ? matched[1] : 'hard 样本改写策略'
}

function getTraceCoverageLabel(asset: BenchmarkArtifactItem) {
  const coverage = getNestedObject(getPlatformSummary(asset), 'trace_field_coverage')
  const pair = toDisplayNumber(coverage.simple_hard_pair_id)
  const seed = toDisplayNumber(coverage.seedbank_id_or_seed_id)
  const sourceRow = toDisplayNumber(coverage.source_row_id)
  if (pair === 0 && seed === 0 && sourceRow === 0) {
    return '已通过导入校验'
  }
  return `pair ${pair} / seed ${seed} / row ${sourceRow}`
}

function getQaGateLabel(asset: BenchmarkArtifactItem) {
  const qa = getNestedObject(getPlatformSummary(asset), 'qa_gate_summary')
  const hardTotal = toDisplayNumber(qa.hard_total) || getDifficultyCount(asset, 'hard')
  const passed = toDisplayNumber(qa.passed_true)
  const semantic = toDisplayNumber(qa.semantic_ok_true)
  const format = toDisplayNumber(qa.format_ok_true)
  if (passed > 0 || semantic > 0 || format > 0) {
    const parts = [`QA Gate ${passed || semantic}/${hardTotal}`]
    if (semantic > 0) {
      parts.push(`semantic_ok ${semantic}/${hardTotal}`)
    }
    if (format > 0) {
      parts.push(`format_ok ${format}/${hardTotal}`)
    }
    return parts.join(' · ')
  }
  const label = toDisplayNumber(qa.label_preservation_true)
  if (label === 0) {
    return 'QA gate 待聚合或使用等价字段'
  }
  return `label_preservation ${label} / semantic_ok ${semantic}`
}

function hasRequiredFile(asset: BenchmarkArtifactItem, file: string) {
  const requiredFiles = getNestedObject(getDeliveryValidation(asset), 'required_files')
  return requiredFiles[file] === true
}

function getManifestValue(asset: BenchmarkArtifactItem, key: string) {
  return asset.manifest[key]
}

function isTopic3DifficultyAsset(asset: BenchmarkArtifactItem) {
  return asset.manifest.benchmark_type === 'dynamic_difficulty'
}

function isTopic1ValueQaAsset(asset: BenchmarkArtifactItem) {
  return asset.manifest.benchmark_type === 'value_qa'
}

function isCbrneDatasetSnapshotAsset(asset: BenchmarkArtifactItem) {
  return (
    asset.source_mode === 'dataset_snapshot' &&
    asset.manifest.benchmark_type === 'anomaly_seedbank' &&
    typeof asset.manifest.schema_id === 'string' &&
    asset.manifest.schema_id.startsWith('topic2.cbrne.anomaly_seedbank')
  )
}

function compareCbrneAssets(left: BenchmarkArtifactItem, right: BenchmarkArtifactItem) {
  const leftCurrent = left.manifest.is_current === true ? 1 : 0
  const rightCurrent = right.manifest.is_current === true ? 1 : 0
  if (leftCurrent !== rightCurrent) {
    return rightCurrent - leftCurrent
  }
  return compareAssetsByCreatedAtDesc(left, right)
}

function getCbrnePlatformStats(asset: BenchmarkArtifactItem): Record<string, unknown> {
  const stats = asset.manifest.platform_stats
  return stats && typeof stats === 'object' && !Array.isArray(stats)
    ? (stats as Record<string, unknown>)
    : {}
}

function getCbrneStatNumber(asset: BenchmarkArtifactItem, key: string) {
  const value = getCbrnePlatformStats(asset)[key]
  return typeof value === 'number' ? String(value) : getManifestString(asset, key)
}

function getCbrneLabelCount(asset: BenchmarkArtifactItem, label: string) {
  const value = cbrneLabelCount(getCbrnePlatformStats(asset).label_counts, label)
  return value === null ? '-' : String(value)
}

function getCbrneSourceKindCount(asset: BenchmarkArtifactItem) {
  const counts = getCbrnePlatformStats(asset).source_counts
  if (!counts || typeof counts !== 'object' || Array.isArray(counts)) return '-'
  return String(cbrneCountChips(counts).length)
}

function getCbrneCategoryChips(asset: BenchmarkArtifactItem) {
  return cbrneCountChips(getCbrnePlatformStats(asset).cbrne_category_counts)
}

function getCbrneSourceChips(asset: BenchmarkArtifactItem) {
  return cbrneCountChips(getCbrnePlatformStats(asset).source_counts)
}

function isCbrneSourcesExpanded(assetId: string) {
  return expandedCbrneSources.value[assetId] === true
}

function getVisibleCbrneSourceChips(asset: BenchmarkArtifactItem) {
  const chips = getCbrneSourceChips(asset)
  if (isCbrneSourcesExpanded(asset.asset_id) || chips.length <= CBRNE_SOURCE_CHIP_LIMIT) {
    return chips
  }
  return chips.slice(0, CBRNE_SOURCE_CHIP_LIMIT)
}

function getCbrneHiddenSourceCount(asset: BenchmarkArtifactItem) {
  const total = getCbrneSourceChips(asset).length
  if (total <= CBRNE_SOURCE_CHIP_LIMIT) return 0
  return total - CBRNE_SOURCE_CHIP_LIMIT
}

function toggleCbrneSources(assetId: string) {
  expandedCbrneSources.value = {
    ...expandedCbrneSources.value,
    [assetId]: !expandedCbrneSources.value[assetId],
  }
}

function getCbrneContentHash(asset: BenchmarkArtifactItem) {
  const value = asset.manifest.dataset_content_sha256
  return typeof value === 'string' && value.trim() ? value : asset.artifact_sha256
}

function getCbrneSourceLimitations(asset: BenchmarkArtifactItem): string[] {
  const value = asset.manifest.source_limitations
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string' && item.trim() !== '')
}

function getCbrneCurrentBadge(asset: BenchmarkArtifactItem) {
  if (asset.manifest.is_current === true) {
    return { label: '当前版本', className: 'is-valid' }
  }
  return { label: '历史版本', className: 'is-pending' }
}

function getCbrneDifficultyExplanation(asset: BenchmarkArtifactItem) {
  const definition = asset.manifest.difficulty_definition
  if (definition && typeof definition === 'object' && !Array.isArray(definition)) {
    const zh = (definition as Record<string, unknown>).basis_zh
    const en = (definition as Record<string, unknown>).basis
    if (typeof zh === 'string' && zh.trim()) {
      return zh
    }
    if (typeof en === 'string' && en.trim()) {
      return en
    }
  }
  return '评估器相对难度：十 Guard 错误/空判计数；不是样本固有难度。'
}

function isTopic1ValueQaRiskCauseRecheckAsset(asset: BenchmarkArtifactItem) {
  return (
    asset.manifest.trace_source_file === 'Data_predictions.jsonl' ||
    asset.manifest.trace_source_schema === 'risk_cause_data_predictions_v1' ||
    asset.manifest.model_eval_status === 'imported_result'
  )
}

function getTopic1ValueQaAssetBatchKey(asset: BenchmarkArtifactItem) {
  const explicitBatch = getManifestFirstString(asset, [
    'batch_id',
    'dataset_id',
    'corpus_id',
    'source_dataset_id',
    'trace_dataset_id',
  ])
  if (explicitBatch !== '-') {
    return `explicit:${explicitBatch}`
  }

  const sourceCommit = getManifestOptionalString(asset, 'source_commit')
  const schema = getManifestOptionalString(asset, 'schema_id')
  const release = getManifestOptionalString(asset, 'release_kind')
  const sampleCount = getManifestOptionalString(asset, 'sample_count')
  const groupCount = getManifestOptionalString(asset, 'group_count')
  const fallbackParts = [sourceCommit, schema, release, sampleCount, groupCount].filter(Boolean)
  return fallbackParts.length >= 2 ? `derived:${fallbackParts.join('|')}` : null
}

function selectVisibleTopic1ValueQaAssets(assets: BenchmarkArtifactItem[]) {
  const visibleAssetSet = new Set<BenchmarkArtifactItem>()
  const assetsByBatch = new Map<string, BenchmarkArtifactItem[]>()

  assets.forEach((asset) => {
    const batchKey = getTopic1ValueQaAssetBatchKey(asset)
    if (!batchKey) {
      visibleAssetSet.add(asset)
      return
    }
    assetsByBatch.set(batchKey, [...(assetsByBatch.get(batchKey) ?? []), asset])
  })

  assetsByBatch.forEach((batchAssets) => {
    const recheckAssets = batchAssets.filter((asset) => isTopic1ValueQaRiskCauseRecheckAsset(asset))
    const selectedAssets = recheckAssets.length > 0 ? recheckAssets : batchAssets
    selectedAssets.forEach((asset) => visibleAssetSet.add(asset))
  })

  return assets.filter((asset) => visibleAssetSet.has(asset))
}

function isTopic3RiskAsset(asset: BenchmarkArtifactItem) {
  return asset.manifest.benchmark_type === 'risk_content_generation'
}

function isTopic3CulturalAsset(asset: BenchmarkArtifactItem) {
  return (
    asset.manifest.benchmark_type === 'cultural_diversity_generation' &&
    asset.manifest.agent_id === 'topic3-cultural-corpus-generation'
  )
}

function getValueQaDisplayName(asset: BenchmarkArtifactItem) {
  const name = getManifestString(asset, 'benchmark_type')
  return name === 'value_qa' ? '课题一 value_qa 价值评测语料' : asset.name
}

function getValueQaSubtitle(asset: BenchmarkArtifactItem) {
  const release = getManifestString(asset, 'release_kind')
  const groups = getManifestString(asset, 'group_count')
  if (groups !== '-') {
    return `${release}，包含 ${groups} 组三档对照样本`
  }
  return release
}

function getValueQaLevelItems(asset: BenchmarkArtifactItem) {
  const distribution = getManifestObject(asset, 'quality_level_distribution')
  return valueQaLevels.map((level) => ({
    level,
    count: toDisplayNumber(distribution?.[level]),
  }))
}

function getValueQaDistributionLabel(asset: BenchmarkArtifactItem) {
  const items = getValueQaLevelItems(asset)
  if (items.every((item) => item.count === 0)) {
    return '-'
  }
  return items.map((item) => item.count).join(' / ')
}

function getValueQaQcLabel(asset: BenchmarkArtifactItem) {
  const status = getManifestString(asset, 'qc_status')
  return status === 'imported' ? '人工抽检状态已导入' : status
}

function getValueQaTraceLabel(asset: BenchmarkArtifactItem) {
  const status = getManifestString(asset, 'trace_status')
  if (status !== 'imported') {
    return status
  }
  return isTopic1ValueQaRiskCauseRecheckAsset(asset)
    ? '全量档位复判与 low 问题溯因可用'
    : '部分样本复判线索可用'
}

function getValueQaModelEvalLabel(asset: BenchmarkArtifactItem) {
  if (isTopic1ValueQaRiskCauseRecheckAsset(asset)) {
    const model = getManifestString(asset, 'trace_model_version')
    return model !== '-' ? `预跑复判结果已导入：${model}` : '预跑复判结果已导入'
  }
  const status = getManifestString(asset, 'model_eval_status')
  return status === '-' ? '模型评测结果待导入' : status
}

function getValueQaModelEvalBadgeLabel(asset: BenchmarkArtifactItem) {
  return isTopic1ValueQaRiskCauseRecheckAsset(asset) ? '复判结果已导入' : '模型评测结果待导入'
}

function getValueQaModelEvalBadgeClass(asset: BenchmarkArtifactItem) {
  return isTopic1ValueQaRiskCauseRecheckAsset(asset) ? 'is-valid' : 'is-pending'
}

function getValueQaRecheckTitle(asset: BenchmarkArtifactItem) {
  return isTopic1ValueQaRiskCauseRecheckAsset(asset)
    ? '全量档位复判与 low 问题溯因'
    : '部分档位复判'
}

function getValueQaRecheckDescription(asset: BenchmarkArtifactItem) {
  if (!isTopic1ValueQaRiskCauseRecheckAsset(asset)) {
    return '部分样本质量档位复判线索，仅作为资产检查辅助信息。'
  }
  const sourceFile = getManifestOptionalString(asset, 'trace_source_file')
  const model = getManifestOptionalString(asset, 'trace_model_version')
  const architecture = getManifestOptionalString(asset, 'trace_architecture')
  const sampleCount =
    getManifestOptionalString(asset, 'prediction_count') ??
    getManifestOptionalString(asset, 'sample_count')
  const parts = [
    sourceFile ? `${sourceFile} 已导入为预跑复判结果` : '预跑复判结果已导入',
    model ? `模型 ${model}` : null,
    architecture ? `架构 ${architecture}` : null,
    sampleCount ? `覆盖 ${sampleCount} 条样本` : null,
  ].filter(Boolean)

  return `${parts.join('，')}。`
}

function getValueQaRecheckBadgeLabel(asset: BenchmarkArtifactItem) {
  return isTopic1ValueQaRiskCauseRecheckAsset(asset) ? '完整复判摘要' : '部分复判线索'
}

function getValueQaRecheckBadgeClass(asset: BenchmarkArtifactItem) {
  return isTopic1ValueQaRiskCauseRecheckAsset(asset) ? 'is-valid' : 'is-pending'
}

async function loadValueQaRecheckSummaries(assets: BenchmarkArtifactItem[]) {
  const activeIds = new Set(assets.map((asset) => asset.asset_id))
  valueQaRecheckSummaries.value = pickAssetState(valueQaRecheckSummaries.value, activeIds)
  valueQaRecheckLoading.value = pickAssetState(valueQaRecheckLoading.value, activeIds)
  valueQaRecheckErrors.value = pickAssetState(valueQaRecheckErrors.value, activeIds)

  await Promise.all(
    assets.map(async (asset) => {
      if (
        Object.prototype.hasOwnProperty.call(valueQaRecheckSummaries.value, asset.asset_id) ||
        valueQaRecheckLoading.value[asset.asset_id]
      ) {
        return
      }
      valueQaRecheckLoading.value = {
        ...valueQaRecheckLoading.value,
        [asset.asset_id]: true,
      }
      valueQaRecheckErrors.value = {
        ...valueQaRecheckErrors.value,
        [asset.asset_id]: '',
      }
      try {
        const summary = await getTopic1ValueQaRecheckSummary(asset.asset_id)
        valueQaRecheckSummaries.value = {
          ...valueQaRecheckSummaries.value,
          [asset.asset_id]: summary,
        }
      } catch (error) {
        valueQaRecheckSummaries.value = {
          ...valueQaRecheckSummaries.value,
          [asset.asset_id]: null,
        }
        valueQaRecheckErrors.value = {
          ...valueQaRecheckErrors.value,
          [asset.asset_id]: error instanceof Error ? error.message : 'recheck summary unavailable',
        }
        console.warn('Failed to load topic1 value_qa recheck summary', error)
      } finally {
        valueQaRecheckLoading.value = {
          ...valueQaRecheckLoading.value,
          [asset.asset_id]: false,
        }
      }
    }),
  )
}

function pickAssetState<T>(source: Record<string, T>, activeIds: Set<string>) {
  return Object.fromEntries(
    Object.entries(source).filter(([assetId]) => activeIds.has(assetId)),
  ) as Record<string, T>
}

function getValueQaRecheckSummary(asset: BenchmarkArtifactItem) {
  return valueQaRecheckSummaries.value[asset.asset_id] ?? null
}

function isValueQaRecheckLoading(asset: BenchmarkArtifactItem) {
  return Boolean(valueQaRecheckLoading.value[asset.asset_id])
}

function getValueQaRecheckError(asset: BenchmarkArtifactItem) {
  return valueQaRecheckErrors.value[asset.asset_id] || ''
}

function hasValueQaRecheckSummary(asset: BenchmarkArtifactItem) {
  const summary = getValueQaRecheckSummary(asset)
  return Boolean(summary && summary.status === 'imported' && summary.prediction_count > 0)
}

function getValueQaRecheckCoverageLabel(asset: BenchmarkArtifactItem) {
  const summary = getValueQaRecheckSummary(asset)
  if (!summary) {
    return '-'
  }
  return `${summary.prediction_count} / ${summary.sample_count}`
}

function getValueQaRecheckAccuracyLabel(asset: BenchmarkArtifactItem) {
  const summary = getValueQaRecheckSummary(asset)
  if (!summary || summary.prediction_count === 0) {
    return '-'
  }
  return `${formatPercent(summary.accuracy)}`
}

function getValueQaRecheckLowIssueLabel(asset: BenchmarkArtifactItem) {
  const summary = getValueQaRecheckSummary(asset)
  if (!summary) {
    return '-'
  }
  return `${summary.low_issue_sample_count} 条 / 复判问题 ${summary.issue_count} 个`
}

function getValueQaRecheckIssueItems(asset: BenchmarkArtifactItem) {
  const distribution = getValueQaRecheckSummary(asset)?.issue_type_distribution ?? {}
  return Object.entries(distribution)
    .map(([type, count]) => ({ type, count: toDisplayNumber(count) }))
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type))
}

function formatPercent(value: number) {
  if (!Number.isFinite(value)) {
    return '-'
  }
  return `${(value * 100).toFixed(2)}%`
}

function getDifficultyItems(asset: BenchmarkArtifactItem) {
  const distribution = getManifestObject(asset, 'difficulty_distribution')
  return difficultyLevels.map((level) => ({
    level,
    count: toDisplayNumber(distribution?.[level]),
    explanation: topic3DifficultyExplanations[level],
  }))
}

function getTopic3DifficultyCountsLabel(asset: BenchmarkArtifactItem) {
  const parameters = getLiveRunParameters(asset)
  const counts =
    parameters.difficulty_counts && typeof parameters.difficulty_counts === 'object'
      ? (parameters.difficulty_counts as Record<string, unknown>)
      : (getManifestObject(asset, 'difficulty_distribution') ?? {})
  return difficultyLevels.map((level) => `${level} ${toDisplayNumber(counts[level])}`).join(' / ')
}

function getManifestObject(asset: BenchmarkArtifactItem, key: string) {
  const value = asset.manifest[key]
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function getCulturalDistributionLabel(asset: BenchmarkArtifactItem, key: string) {
  const distribution = getManifestObject(asset, key)
  if (!distribution) {
    return '-'
  }
  const entries = Object.entries(distribution)
    .filter(([, value]) => typeof value === 'number')
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
  if (entries.length === 0) {
    return '-'
  }
  return entries.map(([name, value]) => `${name} ${toDisplayNumber(value)}`).join(' / ')
}

function getCulturalReviewPassedLabel(asset: BenchmarkArtifactItem) {
  const passed = getManifestString(asset, 'review_passed_count')
  const total = getManifestString(asset, 'sample_count')
  if (passed === '-' || total === '-') {
    return '-'
  }
  return `${passed}/${total}`
}

function getNestedObject(
  value: Record<string, unknown> | null,
  key: string,
): Record<string, unknown> {
  const item = value?.[key]
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    return {}
  }
  return item as Record<string, unknown>
}

function getNestedArray(value: Record<string, unknown> | null, key: string) {
  const item = value?.[key]
  if (!Array.isArray(item)) {
    return []
  }
  return item.map((entry) => String(entry)).filter((entry) => entry.trim() !== '')
}

function openCbrneSamples(
  asset: BenchmarkArtifactItem,
  focusSample: BenchmarkCbrneSampleRefResponse | null = null,
) {
  focusedCbrneSample.value = focusSample
  selectedCbrneAsset.value = asset
  cbrneSampleDrawerVisible.value = true
}

function handleCbrneDrawerClosed() {
  if (!props.resourceMode) return
  focusedCbrneSample.value = null
  emit('close-sample-resource')
}

// A deep-linked sample opens its own asset's drawer, and leaving the sample
// route (back/forward or drawer close) closes it again. The drawer only reads
// the masked reference; disclosure stays an explicit user action.
watch(
  () => props.focusSample,
  (focusSample) => {
    if (!props.resourceMode) return
    if (focusSample) {
      const asset = props.registryAssets.find((item) => item.asset_id === focusSample.asset_id)
      if (asset) openCbrneSamples(asset, focusSample)
      return
    }
    if (cbrneSampleDrawerVisible.value) {
      focusedCbrneSample.value = null
      cbrneSampleDrawerVisible.value = false
    }
  },
  { immediate: true },
)

function openCulturalSamples(asset: BenchmarkArtifactItem) {
  selectedCulturalAsset.value = asset
  culturalSampleDrawerVisible.value = true
}

function openCulturalSamplesFromLiveRun() {
  if (!selectedLiveRunAsset.value) {
    return
  }
  openCulturalSamples(selectedLiveRunAsset.value)
}

function openTopic2Pairs(asset: BenchmarkArtifactItem) {
  selectedTopic2Asset.value = asset
  topic2PairDrawerVisible.value = true
}

function openValueQaGroups(asset: BenchmarkArtifactItem) {
  selectedValueQaAsset.value = asset
  valueQaGroupDrawerVisible.value = true
}

function toDisplayNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}
</script>

<style scoped>
.asset-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.asset-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.asset-panel__actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}

.asset-panel__header h3,
.asset-section__title h4,
.asset-card h4 {
  margin: 0;
  color: var(--text-primary);
}

.asset-panel__header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.asset-count,
.asset-id,
.source-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.source-pill {
  background: rgba(251, 140, 0, 0.12);
  color: #b86600;
}

.source-pill.is-live {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.source-pill.is-risk {
  background: rgba(126, 87, 194, 0.12);
  color: #5e35b1;
}

.source-pill.is-cbrne {
  background: #ecf5ff;
  color: #1d4f91;
}

.source-pill.is-valueqa {
  background: rgba(0, 121, 107, 0.12);
  color: #00796b;
}

.source-pill.is-pending {
  background: rgba(91, 107, 125, 0.12);
  color: var(--text-secondary);
}

.source-pill.is-valid {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.source-pill.is-warning {
  background: rgba(251, 140, 0, 0.12);
  color: #b86600;
}

.asset-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.asset-section__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.asset-section__desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.asset-section :deep(.el-empty__description) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.cbrne-dist {
  display: grid;
  gap: 10px;
  margin: 0 0 14px;
}

.cbrne-dist__row {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.cbrne-dist__row > span,
.cbrne-dist__empty {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  line-height: 28px;
}

.cbrne-dist__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.cbrne-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.cbrne-dist__toggle {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px dashed #93c5fd;
  border-radius: 999px;
  background: #fff;
  color: var(--accent-blue, #1565c0);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
}

.cbrne-caveats {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.cbrne-caveats__block {
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}

.cbrne-caveats__block b {
  display: block;
  margin-bottom: 6px;
}

.cbrne-caveats__block p,
.cbrne-caveats__block li {
  margin: 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
}

.cbrne-caveats__block ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

.cbrne-caveats__note {
  margin-top: 8px !important;
  color: #6b7280 !important;
}

.asset-section :deep(.el-empty__description code) {
  padding: 6px 9px;
  border-radius: 6px;
  background: #f5f8fc;
  color: var(--text-primary);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.asset-card {
  padding: 18px;
  border: 1px solid #dbe5f1;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(21, 101, 192, 0.06);
}

.asset-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.asset-card__badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.asset-card__right {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.asset-card__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.asset-card__top > div:first-child span {
  display: inline-flex;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.prerun-metrics,
.valueqa-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 14px;
}

.prerun-metrics div,
.valueqa-metrics div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.prerun-metrics span,
.valueqa-metrics span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.prerun-metrics strong,
.valueqa-metrics strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1;
}

.asset-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0 14px;
}

.asset-fields dt {
  color: var(--text-muted);
  font-size: 12px;
}

.asset-fields dd {
  margin: 5px 0 0;
  color: var(--text-primary);
  font-size: 13px;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.asset-basis {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 10px;
  background: #f8fbff;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.asset-basis b {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.asset-basis p {
  margin: 0;
}

.live-run-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.live-run-notice {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.72fr);
  gap: 14px;
  padding: 14px;
  border: 1px solid rgba(21, 101, 192, 0.16);
  border-radius: 10px;
  background: #f8fbff;
}

.live-run-notice b,
.live-run-basis b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.live-run-notice p,
.live-run-basis p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.live-run-notice__tags {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
}

.live-run-notice__tags span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 700;
}

.live-run-card {
  border-color: rgba(46, 125, 50, 0.22);
  box-shadow: 0 10px 24px rgba(46, 125, 50, 0.08);
}

.asset-card.is-focused,
.live-run-history__body.is-focused {
  border-radius: 12px;
  box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.28);
  animation: focusPulse 1.8s ease;
}

.live-run-basis {
  margin: 16px 0 0;
  padding: 12px;
  border: 1px solid rgba(46, 125, 50, 0.18);
  border-radius: 10px;
  background: #f7fcf8;
}

.live-run-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 14px;
}

.live-run-metrics div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.live-run-metrics span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}

.live-run-metrics strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1;
  overflow-wrap: anywhere;
}

.live-run-history {
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  overflow: hidden;
}

.live-run-history :deep(.el-collapse-item__header) {
  min-height: 52px;
  padding: 0 14px;
}

.live-run-history :deep(.el-collapse-item__content) {
  padding: 0 14px 14px;
}

.live-run-history__title {
  display: grid;
  grid-template-columns: 150px minmax(170px, 1fr) minmax(120px, 0.8fr) minmax(160px, 1fr);
  gap: 12px;
  align-items: center;
  width: 100%;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.live-run-history__title b,
.live-run-history__title span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-run-history__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 12px;
}

.prerun-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.prerun-summary__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.prerun-summary__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.prerun-summary__header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.difficulty-pair-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.difficulty-pair-grid article {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.difficulty-pair-grid span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.difficulty-pair-grid strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1;
}

.difficulty-pair-grid small,
.difficulty-pair-grid p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.difficulty-pair-grid p {
  margin: 0;
}

.strategy-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.strategy-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 700;
}

.strategy-chip.is-muted {
  background: rgba(91, 107, 125, 0.12);
  color: var(--text-secondary);
}

.validation-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.required-file-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.required-file-grid span {
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
  color: var(--text-secondary);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.required-file-grid span.is-ready {
  border-color: rgba(46, 125, 50, 0.22);
  background: rgba(46, 125, 50, 0.08);
  color: var(--accent-green);
  font-weight: 700;
}

.difficulty-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.risk-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.valueqa-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e2edf8;
  border-radius: 10px;
  background: #f8fbff;
}

.valueqa-recheck {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border: 1px solid rgba(0, 121, 107, 0.2);
  border-radius: 10px;
  background: #f7fcfb;
}

.valueqa-recheck__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.valueqa-recheck__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.valueqa-recheck__header p,
.valueqa-recheck__state {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.valueqa-recheck__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.valueqa-recheck__grid div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid rgba(0, 121, 107, 0.16);
  border-radius: 8px;
  background: #fff;
}

.valueqa-recheck__grid span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}

.valueqa-recheck__grid strong {
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.1;
}

.valueqa-recheck__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.valueqa-recheck__chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border-radius: 999px;
  background: rgba(0, 121, 107, 0.1);
  color: #00796b;
  font-size: 12px;
  font-weight: 700;
}

.valueqa-summary__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.valueqa-summary__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.valueqa-summary__header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.valueqa-level-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.valueqa-level-grid div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.valueqa-level-grid span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.valueqa-level-grid strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1;
}

.risk-summary__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-summary__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.risk-summary__header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.risk-level-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.risk-level-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
}

.risk-level-card span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.risk-level-card strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1;
}

.risk-level-card small {
  color: var(--text-secondary);
  font-size: 12px;
}

.risk-level-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.risk-category-distribution {
  border-top: 1px solid #dbe5f1;
  padding-top: 10px;
}

.risk-category-distribution summary {
  color: var(--accent-blue);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.risk-category-distribution__group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.risk-category-distribution__group b {
  color: var(--text-primary);
  font-size: 12px;
  text-transform: uppercase;
}

.risk-category-distribution__note {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.risk-category-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
}

.risk-category-tile {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 7px 8px;
  border: 1px solid #dbe5f1;
  border-radius: 6px;
  background: #fff;
}

.risk-category-grid em {
  color: var(--text-muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.risk-category-grid strong {
  color: var(--text-primary);
  font-size: 12px;
}

.difficulty-summary__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.difficulty-summary__header b {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
}

.difficulty-summary__header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.difficulty-label {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.difficulty-levels {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.difficulty-level {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
  cursor: help;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.difficulty-level:hover,
.difficulty-level:focus-visible {
  border-color: rgba(21, 101, 192, 0.45);
  box-shadow: 0 8px 18px rgba(21, 101, 192, 0.12);
  outline: none;
  transform: translateY(-1px);
}

.difficulty-level span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.difficulty-level strong {
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1;
}

.difficulty-tooltip {
  display: flex;
  max-width: 320px;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.difficulty-tooltip b {
  color: var(--text-primary);
  font-size: 13px;
}

.difficulty-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.difficulty-fields dt {
  color: var(--text-muted);
  font-size: 12px;
}

.difficulty-fields dd {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 13px;
}

.asset-manifest summary {
  color: var(--accent-blue);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.asset-manifest pre {
  max-height: 260px;
  overflow: auto;
  margin: 12px 0 0;
  padding: 12px;
  border-radius: 10px;
  background: #f5f8fc;
  color: var(--text-secondary);
  font-size: 12px;
}

@keyframes focusPulse {
  0% {
    box-shadow: 0 0 0 0 rgba(21, 101, 192, 0.24);
  }
  35% {
    box-shadow: 0 0 0 8px rgba(21, 101, 192, 0.08);
  }
  100% {
    box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.28);
  }
}

@media (max-width: 980px) {
  .asset-grid,
  .asset-fields,
  .prerun-metrics,
  .valueqa-metrics,
  .live-run-metrics,
  .live-run-notice,
  .difficulty-pair-grid,
  .required-file-grid,
  .difficulty-fields,
  .risk-category-grid,
  .valueqa-level-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .difficulty-summary__header,
  .risk-summary__header,
  .valueqa-summary__header,
  .live-run-notice,
  .live-run-history__title,
  .asset-card__top,
  .asset-card__right {
    grid-template-columns: 1fr;
  }

  .difficulty-summary__header,
  .risk-summary__header,
  .valueqa-summary__header,
  .asset-card__top,
  .asset-card__right {
    flex-direction: column;
    align-items: flex-start;
  }

  .asset-card__badges,
  .asset-card__actions {
    justify-content: flex-start;
  }

  .difficulty-levels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
