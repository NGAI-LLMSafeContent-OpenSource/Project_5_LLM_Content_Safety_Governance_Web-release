<template>
  <div class="task-runner">
    <section class="runner-grid">
      <el-form label-position="top" class="runner-form">
        <div class="runner-form__header">
          <div>
            <h3>{{ activeAgentConfig.title }}</h3>
            <p>{{ activeAgentConfig.description }}</p>
          </div>
          <span class="live-badge">live_run</span>
        </div>

        <el-form-item label="生成链路">
          <div class="agent-card-group" role="radiogroup" aria-label="选择生成 Agent">
            <button
              v-for="agent in agentCards"
              :key="agent.value"
              type="button"
              class="agent-card"
              :class="{ 'is-active': selectedAgent === agent.value }"
              role="radio"
              :aria-checked="selectedAgent === agent.value"
              @click="selectedAgent = agent.value"
            >
              <span class="agent-card__header">
                <span>
                  <span class="agent-card__title">{{ agent.title }}</span>
                  <span class="agent-card__subtitle">{{ agent.subtitle }}</span>
                </span>
                <span class="agent-card__status">
                  <span class="agent-card__badge">{{ agent.badge }}</span>
                  <span v-if="selectedAgent === agent.value" class="agent-card__current">当前</span>
                </span>
              </span>
              <span class="agent-card__meta">{{ agent.meta }}</span>
              <span class="agent-card__description">{{ agent.description }}</span>
            </button>
          </div>
          <div class="field-help">选择本次要启动的生成链路；切换后会显示对应配置和运行现场。</div>
        </el-form-item>

        <el-alert
          v-if="selectedAgent === 'topic2-autobench'"
          class="runtime-alert"
          :type="runtimeAlertType"
          :title="runtimeStatusTitle"
          :description="runtimeStatusDescription"
          :closable="false"
          show-icon
        />

        <el-alert
          v-else-if="selectedAgent === 'topic1-value-qa'"
          class="runtime-alert"
          :type="topic1RuntimeAlertType"
          :title="topic1RuntimeStatusTitle"
          :description="topic1RuntimeStatusDescription"
          :closable="false"
          show-icon
        />

        <el-alert
          v-else-if="selectedAgent === 'topic3-risk-benchmark-generation'"
          class="runtime-alert"
          type="info"
          title="课题三动态风险 Benchmark 试跑 live_run"
          description="固定生成 5 条 safe + 5 条 low。服务器需 llmsafe-topic3-risk-agent（:6351）并复用动态难度 Qwen :6332；不要改接到动态难度 Agent :6331。试跑不是 17 类均衡集。"
          :closable="false"
          show-icon
        />

        <el-alert
          v-else-if="selectedAgent === 'topic3-cultural-corpus-generation'"
          class="runtime-alert"
          type="info"
          title="课题三文化多样性语料 live_run"
          description="默认试跑 3 条、低难度为主（全 L1）。DeepSeek Key 配置在 Project_3，不进入请求体。混合/中高难度依赖上游质量红线。"
          :closable="false"
          show-icon
        />

        <el-alert
          v-else
          class="runtime-alert"
          type="info"
          title="课题三动态难度出题 live_run"
          description="默认使用 8 条小样本演示配置，完成后通过课题三 artifact download API 冻结为 Benchmark 资产。"
          :closable="false"
          show-icon
        />

        <template v-if="selectedAgent === 'topic2-autobench'">
          <el-form-item label="SeedBank L1">
            <el-select
              v-model="topic2Form.l1"
              multiple
              filterable
              :multiple-limit="2"
              :loading="isLoadingOptions"
              placeholder="选择 SeedBank L1"
            >
              <el-option
                v-for="item in l1Options"
                :key="item.value"
                :label="optionLabelWithCount(item)"
                :value="item.value"
              />
            </el-select>
            <div class="field-help">
              选择本轮生成任务围绕的风险大类；首版限制 1–2 项以控制 Demo 复杂度。
            </div>
          </el-form-item>
          <el-form-item label="Moderators">
            <el-select
              v-model="topic2Form.moderators"
              multiple
              filterable
              :loading="isLoadingOptions"
              placeholder="选择被测审核器"
            >
              <el-option-group
                v-for="group in moderatorGroups"
                :key="group.key"
                :label="group.label"
              >
                <el-option
                  v-for="item in group.options"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                  :disabled="item.disabled"
                >
                  <div class="option-row">
                    <span>{{ item.label }}</span>
                    <span class="option-tags">
                      <el-tag
                        v-for="tag in item.tags"
                        :key="tag"
                        size="small"
                        type="info"
                        effect="plain"
                      >
                        {{ tag }}
                      </el-tag>
                    </span>
                  </div>
                </el-option>
              </el-option-group>
            </el-select>
            <div class="field-help">
              这里的 Moderator 是生成链路中的被测审核器；keyword 仅作为弱 baseline / smoke test。
            </div>
          </el-form-item>
          <div class="form-row">
            <el-form-item label="语言">
              <el-segmented v-model="topic2Form.language" :options="languageOptions" />
              <div class="field-help">控制本轮样本语种范围。</div>
            </el-form-item>
            <el-form-item label="Budget">
              <el-input-number v-model="topic2Form.budget" :min="budgetMin" :max="budgetMax" />
              <div class="field-help">
                课题二原生常见 budget=40；平台 Demo 限制 {{ budgetMin }}–{{ budgetMax }}。
              </div>
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="Sampling Seed">
              <el-input-number v-model="topic2Form.sampling_seed" :min="1" />
            </el-form-item>
            <el-form-item label="Max Turns">
              <el-input-number v-model="topic2Form.max_turns" :min="1" :max="25" />
            </el-form-item>
          </div>
          <el-form-item label="Agent 模型 ID（传给课题二上游）">
            <el-select v-model="topic2Form.model" filterable>
              <el-option
                v-for="item in agentModelOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
                :disabled="item.disabled"
              >
                <div class="option-row">
                  <span>{{ item.label }}</span>
                  <span class="option-tags">
                    <el-tag
                      v-for="tag in item.tags"
                      :key="tag"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      {{ tag }}
                    </el-tag>
                  </span>
                </div>
              </el-option>
            </el-select>
            <div class="field-help">
              {{ agentRuntimeDescription }}
            </div>
          </el-form-item>

          <el-collapse class="advanced-options">
            <el-collapse-item title="高级参数：SeedBank L2 统计（本轮不参与任务提交）" name="l2">
              <el-select
                v-model="selectedL2"
                multiple
                filterable
                placeholder="仅展示统计，不写入 payload"
              >
                <el-option
                  v-for="item in l2Options"
                  :key="item.value"
                  :label="optionLabelWithCount(item)"
                  :value="item.value"
                />
              </el-select>
              <div class="field-help">
                本轮仅按 L1 采样，L2 过滤待确认；即使勾选，这些值也不会提交给后端。
              </div>
            </el-collapse-item>
          </el-collapse>
        </template>

        <template v-else-if="selectedAgent === 'topic1-value-qa'">
          <el-form-item label="生成模式">
            <el-segmented v-model="topic1Form.generation_mode" :options="topic1ModeOptions" />
            <div class="field-help">
              单主题模式最多 10 个三档组；维度随机模式从关键词 yaml 中抽主题，总组数仍限制为
              n_topics × groups_per_topic ≤ 10。
            </div>
          </el-form-item>

          <el-form-item v-if="topic1Form.generation_mode === 'topic'" label="主题">
            <el-input v-model="topic1Form.topic" placeholder="例如：中秋节" />
            <div class="field-help">
              建议现场使用百度百科词条较完整、且已准备本地 corpus 的主题。
            </div>
          </el-form-item>

          <el-form-item v-else label="价值维度">
            <el-select v-model="topic1Form.dimension" filterable>
              <el-option
                v-for="item in topic1DimensionOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
            <div class="field-help">可填一级或二级维度；固定 seed 后可复现抽题结果。</div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="主题数">
              <el-input-number
                v-model="topic1Form.n_topics"
                :min="1"
                :max="2"
                :disabled="topic1Form.generation_mode === 'topic'"
              />
              <div class="field-help">仅维度随机模式有效；与每主题组数相乘后不超过 10。</div>
            </el-form-item>
            <el-form-item label="每主题三档组">
              <el-input-number v-model="topic1Form.groups_per_topic" :min="1" :max="10" />
              <div class="field-help">1 组 = high / medium / low 三条样本。</div>
            </el-form-item>
          </div>

          <el-form-item label="检索语料">
            <el-segmented v-model="topic1Form.retrieval_mode" :options="topic1RetrievalOptions" />
            <div class="field-help">
              现场演示默认使用本地 corpus，避免百度百科在线检索慢或限频。
            </div>
          </el-form-item>

          <el-form-item v-if="topic1Form.retrieval_mode === 'local_corpus'" label="Corpus JSONL">
            <el-input v-model="topic1Form.corpus_jsonl" />
            <div class="field-help">相对路径按课题一仓库根目录解析。</div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="语言">
              <el-segmented v-model="topic1Form.language" :options="topic1LanguageOptions" />
              <div class="field-help">提交给课题一 CLI 时，zh 会映射为 zh-CN。</div>
            </el-form-item>
            <el-form-item label="Seed">
              <el-input-number v-model="topic1Form.seed" :min="0" />
              <div class="field-help">维度随机模式用于复现抽题；单主题模式保留运行记录。</div>
            </el-form-item>
          </div>

          <el-form-item label="LLM 运行环境">
            <div class="topic1-llm-readonly">
              <div class="topic1-llm-readonly__row">
                <span class="topic1-llm-readonly__label">模型</span>
                <span class="topic1-llm-readonly__value">{{ topic1LlmRuntime?.model || '—' }}</span>
              </div>
              <div class="topic1-llm-readonly__row">
                <span class="topic1-llm-readonly__label">Endpoint</span>
                <span class="topic1-llm-readonly__value topic1-llm-readonly__value--mono">
                  {{ topic1LlmRuntime?.api_base || '—' }}
                </span>
              </div>
            </div>
            <div class="field-help">
              实际调用由课题一运行环境的 LLM_API_BASE / LLM_MODEL 决定；如需更换请修改课题一仓库
              .env 或部署环境 TOPIC1_VALUE_QA_LLM_*。
            </div>
          </el-form-item>
        </template>

        <template v-else-if="selectedAgent === 'topic3-risk-benchmark-generation'">
          <el-form-item label="试跑规模">
            <el-input-number :model-value="10" :min="10" :max="10" disabled />
            <div class="field-help">
              固定 5 条 safe + 5 条 low（`--target-per-kind 5`）。标准 / 大批量本轮不开。
            </div>
          </el-form-item>
        </template>

        <template v-else-if="selectedAgent === 'topic3-cultural-corpus-generation'">
          <el-form-item label="规模">
            <el-radio-group v-model="culturalForm.scale">
              <el-radio-button label="trial">试跑</el-radio-button>
              <el-radio-button label="standard">标准</el-radio-button>
              <el-radio-button label="large">大批量</el-radio-button>
            </el-radio-group>
            <div class="field-help">
              预计 {{ culturalTotalSampleCount }} 条（试跑 3 / 标准 9 / 大批量 30）。
            </div>
          </el-form-item>

          <el-form-item label="难度等级">
            <el-radio-group v-model="culturalForm.structureBand">
              <el-radio-button label="explicit">低难度为主</el-radio-button>
              <el-radio-button label="mixed">混合</el-radio-button>
              <el-radio-button label="implicit_heavy">中高难度</el-radio-button>
            </el-radio-group>
            <div class="field-help">{{ culturalStructureHelp }}</div>
            <div
              v-if="
                culturalForm.structureBand === 'mixed' ||
                culturalForm.structureBand === 'implicit_heavy'
              "
              class="field-help field-help--warn"
            >
              中高难度档依赖课题三质量红线；若生成失败（红线/超时），请改回「低难度为主」或反馈任务
              ID。
            </div>
          </el-form-item>

          <el-form-item label="民族">
            <el-checkbox-group v-model="culturalForm.ethnicGroups">
              <el-checkbox
                v-for="group in culturalEthnicOptions"
                :key="group"
                :label="group"
                :disabled="
                  culturalForm.ethnicGroups.length === 1 && culturalForm.ethnicGroups[0] === group
                "
              >
                {{ group }}
              </el-checkbox>
            </el-checkbox-group>
            <div class="field-help">默认四民族全选；至少保留 1 个。</div>
          </el-form-item>

          <el-collapse class="advanced-options">
            <el-collapse-item title="高级参数：batch / seed / 维度" name="cultural-advanced">
              <div class="form-row">
                <el-form-item label="Batch Size">
                  <el-input-number
                    v-model="culturalForm.batchSize"
                    :min="1"
                    :max="culturalTotalSampleCount"
                  />
                  <div class="field-help">默认 min(总条数, 5)。</div>
                </el-form-item>
                <el-form-item label="Random Seed">
                  <el-input-number v-model="culturalForm.randomSeed" :min="0" />
                </el-form-item>
              </div>
              <el-form-item label="评测维度">
                <el-select
                  v-model="culturalForm.allowedDimensions"
                  multiple
                  filterable
                  allow-create
                  default-first-option
                  placeholder="留空表示不限制维度"
                >
                  <el-option
                    v-for="item in culturalDimensionOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                  />
                </el-select>
                <div class="field-help">空列表表示全维度抽样；可自填上游知识库 dimension 名。</div>
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </template>

        <template v-else>
          <el-form-item label="难度配置">
            <el-select v-model="topic3Form.difficulty_preset" @change="applyTopic3Preset">
              <el-option
                v-for="item in topic3PresetOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              >
                <div class="option-row">
                  <span>{{ item.label }}</span>
                  <span class="option-description">{{ item.description }}</span>
                </div>
              </el-option>
            </el-select>
            <div class="field-help">
              默认小样本演示共 8 条；均衡和困难版更适合会前预跑或非现场环境。
            </div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="语言">
              <el-segmented v-model="topic3Form.language" :options="topic3LanguageOptions" />
              <div class="field-help">课题三首版默认中文生成。</div>
            </el-form-item>
            <el-form-item label="样本预算">
              <el-input-number :model-value="topic3TotalSampleCount" :min="1" :max="100" disabled />
              <div class="field-help">由 H1-H4 数量自动求和。</div>
            </el-form-item>
          </div>

          <div class="difficulty-grid">
            <el-form-item label="H1">
              <el-input-number
                v-model="topic3Form.difficulty_counts.H1"
                :min="0"
                :max="100"
                :disabled="topic3Form.difficulty_preset !== 'custom'"
              />
            </el-form-item>
            <el-form-item label="H2">
              <el-input-number
                v-model="topic3Form.difficulty_counts.H2"
                :min="0"
                :max="100"
                :disabled="topic3Form.difficulty_preset !== 'custom'"
              />
            </el-form-item>
            <el-form-item label="H3">
              <el-input-number
                v-model="topic3Form.difficulty_counts.H3"
                :min="0"
                :max="100"
                :disabled="topic3Form.difficulty_preset !== 'custom'"
              />
            </el-form-item>
            <el-form-item label="H4">
              <el-input-number
                v-model="topic3Form.difficulty_counts.H4"
                :min="0"
                :max="100"
                :disabled="topic3Form.difficulty_preset !== 'custom'"
              />
            </el-form-item>
          </div>

          <el-form-item label="Seed 数据集">
            <el-input v-model="topic3Form.seed_dataset" />
            <div class="field-help">对应课题三发布的 harmful seed library。</div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="Generation Model">
              <el-input v-model="topic3Form.generation_model" />
            </el-form-item>
            <el-form-item label="Guard Model">
              <el-input v-model="topic3Form.guard_model" />
            </el-form-item>
          </div>
        </template>

        <div class="runner-actions">
          <el-button
            type="primary"
            :loading="isStarting"
            :disabled="isStartDisabled"
            @click="handleStart"
          >
            启动生成任务
          </el-button>
          <el-button :disabled="isStarting" @click="$emit('reset')">清空状态</el-button>
        </div>

        <el-alert
          v-if="startError || pollingError"
          type="error"
          :title="startError || pollingError"
          :closable="false"
          show-icon
        />
      </el-form>

      <aside class="runner-status">
        <h3>当前生成任务</h3>
        <el-empty v-if="!task" description="尚未启动生成任务。" />
        <dl v-else class="status-fields">
          <div>
            <dt>Task ID</dt>
            <dd class="mono">{{ task.task_id }}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <span class="status-pill" :class="`status-${task.status}`">{{ task.status }}</span>
            </dd>
          </div>
          <div>
            <dt>Source Commit</dt>
            <dd class="mono">{{ task.source_commit || '-' }}</dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{{ formatDate(task.started_at) }}</dd>
          </div>
          <div>
            <dt>Finished</dt>
            <dd>{{ formatDate(task.finished_at) }}</dd>
          </div>
          <div v-if="task.error_message">
            <dt>Error</dt>
            <dd class="error-text">{{ task.error_message }}</dd>
          </div>
        </dl>
        <el-button
          v-if="task?.status === 'completed' && artifacts.length > 0"
          type="primary"
          plain
          @click="handleViewAssets"
        >
          查看冻结资产
        </el-button>
      </aside>
    </section>

    <section class="runner-logs">
      <div class="runner-logs__header">
        <h3>生成任务日志</h3>
        <span>{{ logs.length }} 条事件</span>
      </div>
      <el-table :data="logs" border height="420" empty-text="生成任务启动后显示日志事件。">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="event_type" label="Event" width="130" />
        <el-table-column prop="stage" label="Stage" width="150" show-overflow-tooltip />
        <el-table-column prop="message" label="Message" min-width="260" show-overflow-tooltip />
        <el-table-column prop="turn" label="Turn" width="80" />
        <el-table-column label="Created At" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Raw" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="selectedLog = row">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="isPolling" class="polling-note">正在轮询生成任务状态和日志...</div>
    </section>

    <el-dialog v-model="rawDialogVisible" title="原始事件" width="720px">
      <pre class="raw-json">{{
        selectedLog ? JSON.stringify(selectedLog.raw_json, null, 2) : ''
      }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createBenchmarkTask,
  getTopic1Runtime,
  getTopic2Options,
  getTopic2Runtime,
  getTopic2SeedbankStats,
} from '@/api/benchmark'
import { formatApiDate } from '@/utils/datetime'
import {
  buildCulturalCorpusTaskPayload,
  culturalDifficultyCounts,
  DEFAULT_CULTURAL_ETHNIC_GROUPS,
  type CulturalStructureBand,
  type StandardBenchmarkScale,
} from '@/utils/benchmark/standardTaskPayload'
import {
  normalizeTopic2AgentModels,
  normalizeTopic2L1Options,
  normalizeTopic2L2Options,
  normalizeTopic2Languages,
  normalizeTopic2ModeratorGroups,
  type Topic2SelectOption,
} from '@/utils/benchmarkTopic2Options'
import type {
  BenchmarkAgentId,
  BenchmarkArtifactItem,
  BenchmarkLanguage,
  BenchmarkViewAssetsPayload,
  BenchmarkTask,
  BenchmarkTaskCreatePayload,
  BenchmarkTaskLogItem,
  Topic2OptionsResponse,
  Topic2RuntimeResponse,
  Topic2SeedbankStatsResponse,
  Topic1RuntimeResponse,
} from '@/types'

type Topic3DifficultyPreset = 'demo_small' | 'balanced_h1h4' | 'hard_h3h4' | 'custom'
type Topic3DifficultyCounts = Record<'H1' | 'H2' | 'H3' | 'H4', number>
type Topic1GenerationMode = 'topic' | 'dimension'
type Topic1RetrievalMode = 'local_corpus' | 'online_baike'

const props = defineProps<{
  selectedAgent: BenchmarkAgentId
  task: BenchmarkTask | null
  logs: BenchmarkTaskLogItem[]
  artifacts: BenchmarkArtifactItem[]
  isPolling: boolean
  pollingError: string
}>()

const emit = defineEmits<{
  (event: 'update:selectedAgent', agentId: BenchmarkAgentId): void
  (event: 'task-created', task: BenchmarkTask): void
  (event: 'reset'): void
  (event: 'view-assets', payload: BenchmarkViewAssetsPayload): void
}>()

const DEFAULT_L1 = 'L1-2 Explicit Harmful Injection'
const isStarting = ref(false)
const isLoadingOptions = ref(false)
const startError = ref('')
const optionsError = ref('')
const topic2Options = ref<Topic2OptionsResponse | null>(null)
const seedbankStats = ref<Topic2SeedbankStatsResponse | null>(null)
const topic2Runtime = ref<Topic2RuntimeResponse | null>(null)
const topic1Runtime = ref<Topic1RuntimeResponse | null>(null)
const isLoadingTopic1Runtime = ref(false)
const topic1RuntimeError = ref('')
const selectedL2 = ref<string[]>([])
const selectedLog = ref<BenchmarkTaskLogItem | null>(null)
const rawDialogVisible = computed({
  get: () => selectedLog.value !== null,
  set: (value: boolean) => {
    if (!value) {
      selectedLog.value = null
    }
  },
})

const selectedAgent = computed({
  get: () => props.selectedAgent,
  set: (agentId: BenchmarkAgentId) => {
    emit('update:selectedAgent', agentId)
  },
})
const agentCards = [
  {
    value: 'topic2-autobench',
    title: '课题二异常语料改写',
    headerTitle: '课题二异常语料改写任务',
    subtitle: 'SeedBank + Moderator 动态评测',
    badge: 'live_run',
    meta: '上游 8766 / 小预算',
    description: '验证 SeedBank 采样、Moderator 评测、日志流和产物冻结链路。',
  },
  {
    value: 'topic3-difficulty-generation',
    title: '课题三动态难度出题',
    headerTitle: '课题三动态难度出题任务',
    subtitle: 'H1-H4 难度结构生成',
    badge: 'live_run',
    meta: '8 条样本 / 可冻结',
    description: '按 H1-H4 难度结构生成样本，完成后冻结为动态 Benchmark 资产。',
  },
  {
    value: 'topic1-value-qa',
    title: '课题一价值评测语料',
    headerTitle: '课题一 value_qa 生成任务',
    subtitle: 'high / medium / low 三档问答',
    badge: 'live_run',
    meta: '3–6 条样本 / 本地 corpus',
    description: '调用课题一 CLI 生成价值评测三档样本，完成结构校验后冻结为 live_run 资产。',
  },
  {
    value: 'topic3-risk-benchmark-generation',
    title: '课题三动态风险 Benchmark',
    headerTitle: '课题三动态风险试跑任务',
    subtitle: 'safe / low 对照样本',
    badge: 'live_run',
    meta: '10 条试跑 / 5+5',
    description: '参数化 CLI 生成 5 条 safe + 5 条 low，trial QA 后冻结为 live_run 资产。',
  },
  {
    value: 'topic3-cultural-corpus-generation',
    title: '课题三文化多样性语料',
    headerTitle: '课题三文化多样性生成任务',
    subtitle: '按 L1–L3 生成多民族文化评测语料',
    badge: 'live_run',
    meta: '试跑 3 条 / 低难度为主',
    description: '本地子进程生成文化评测语料，完成后冻结为 Benchmark 资产。',
  },
] satisfies Array<{
  value: BenchmarkAgentId
  title: string
  headerTitle: string
  subtitle: string
  badge: string
  meta: string
  description: string
}>
const activeAgentConfig = computed(() => {
  const agent = agentCards.find((item) => item.value === selectedAgent.value)
  return {
    title: agent?.headerTitle ?? '生成任务',
    description: agent?.description ?? '',
  }
})

const topic2Form = reactive({
  l1: [DEFAULT_L1],
  moderators: ['keyword'],
  language: 'zh+en' as BenchmarkLanguage,
  budget: 1,
  sampling_seed: 20260707,
  model: 'claude-sonnet-4-6',
  max_turns: 5,
})
const topic3Form = reactive({
  language: 'zh' as BenchmarkLanguage,
  difficulty_preset: 'demo_small' as Topic3DifficultyPreset,
  difficulty_counts: {
    H1: 2,
    H2: 2,
    H3: 2,
    H4: 2,
  } as Topic3DifficultyCounts,
  seed_dataset: 'harmful_zh_17class_v1',
  generation_model: 'Qwen3.5-9B',
  guard_model: 'Qwen3Guard-Gen-4B',
})
const topic1Form = reactive({
  generation_mode: 'topic' as Topic1GenerationMode,
  topic: '中秋节',
  dimension: '文化元素符合度',
  n_topics: 1,
  groups_per_topic: 2,
  retrieval_mode: 'local_corpus' as Topic1RetrievalMode,
  corpus_jsonl: 'data/corpus/baidu/中秋节.jsonl',
  language: 'zh' as 'zh' | 'zh-CN' | 'en' | 'zh+en',
  seed: 20260727,
})
const culturalForm = reactive({
  scale: 'trial' as StandardBenchmarkScale,
  structureBand: 'explicit' as CulturalStructureBand,
  ethnicGroups: [...DEFAULT_CULTURAL_ETHNIC_GROUPS],
  batchSize: 3,
  randomSeed: 20260727,
  allowedDimensions: [] as string[],
})
const culturalEthnicOptions = [...DEFAULT_CULTURAL_ETHNIC_GROUPS]
const culturalDimensionOptions = ['饮食文化', '礼仪习俗', '节庆文化', '服饰文化']

const topic3LanguageOptions: BenchmarkLanguage[] = ['zh', 'en', 'zh+en']
const topic1ModeOptions: Topic1GenerationMode[] = ['topic', 'dimension']
const topic1RetrievalOptions: Topic1RetrievalMode[] = ['local_corpus', 'online_baike']
const topic1LanguageOptions = ['zh', 'en', 'zh+en'] satisfies Array<'zh' | 'en' | 'zh+en'>
const topic1DimensionOptions = [
  '文化忠实度',
  '文化元素符合度',
  '行为社会规范符合度',
  '价值观忠实度',
  '伦理合规度',
  '公平合规度',
  '伤害风险合规度',
  '隐私合规度',
]
const topic3PresetOptions = [
  { label: '小样本演示', value: 'demo_small', description: '8 条，H1-H4 各 2 条' },
  { label: '标准 H1-H4 均衡', value: 'balanced_h1h4', description: '100 条，四档均衡' },
  { label: '困难版偏 H3-H4', value: 'hard_h3h4', description: '100 条，聚焦高难度样本' },
  { label: '自定义', value: 'custom', description: '手动填写 H1-H4 数量' },
] satisfies Array<{ label: string; value: Topic3DifficultyPreset; description: string }>
const TOPIC3_PRESET_COUNTS: Record<Topic3DifficultyPreset, Topic3DifficultyCounts> = {
  demo_small: { H1: 2, H2: 2, H3: 2, H4: 2 },
  balanced_h1h4: { H1: 25, H2: 25, H3: 25, H4: 25 },
  hard_h3h4: { H1: 0, H2: 10, H3: 40, H4: 50 },
  custom: { H1: 2, H2: 2, H3: 2, H4: 2 },
}

const languageOptions = computed(() => normalizeTopic2Languages(topic2Options.value))
const l1Options = computed(() => normalizeTopic2L1Options(seedbankStats.value))
const l2Options = computed(() => normalizeTopic2L2Options(seedbankStats.value))
const moderatorGroups = computed(() => normalizeTopic2ModeratorGroups(topic2Options.value))
const agentModelOptions = computed(() => normalizeTopic2AgentModels(topic2Options.value))
const agentRuntime = computed(() => topic2Runtime.value?.agent_runtime ?? null)
const isAgentRuntimeMissing = computed(() => agentRuntime.value?.provider === 'missing')
const isTopic2Selected = computed(() => selectedAgent.value === 'topic2-autobench')
const isTopic1Selected = computed(() => selectedAgent.value === 'topic1-value-qa')
const isTopic3RiskSelected = computed(
  () => selectedAgent.value === 'topic3-risk-benchmark-generation',
)
const isTopic3CulturalSelected = computed(
  () => selectedAgent.value === 'topic3-cultural-corpus-generation',
)
const culturalDifficulty = computed(() =>
  culturalDifficultyCounts(culturalForm.scale, culturalForm.structureBand),
)
const culturalTotalSampleCount = computed(
  () => culturalDifficulty.value.L1 + culturalDifficulty.value.L2 + culturalDifficulty.value.L3,
)
const culturalStructureHelp = computed(() => {
  if (culturalForm.structureBand === 'mixed') {
    return '低 / 中 / 高难度均分（L1 / L2 / L3）。这里的低/中/高指文化语境难度，不是风险高低。'
  }
  if (culturalForm.structureBand === 'implicit_heavy') {
    return '仅中、高难度（L2 / L3）。这里的低/中/高指文化语境难度，不是风险高低。'
  }
  return '低难度（L1）；试跑最稳。'
})
const budgetMin = computed(() => topic2Runtime.value?.limits.budget_min ?? 1)
const budgetMax = computed(() => topic2Runtime.value?.limits.budget_max ?? 5)
const topic3TotalSampleCount = computed(() =>
  Object.values(topic3Form.difficulty_counts).reduce((sum, count) => sum + count, 0),
)
const topic1RequestedGroupCount = computed(() => {
  const nTopics = topic1Form.generation_mode === 'topic' ? 1 : topic1Form.n_topics
  return nTopics * topic1Form.groups_per_topic
})
const isStartDisabled = computed(
  () =>
    props.isPolling || isStarting.value || (isTopic2Selected.value && isAgentRuntimeMissing.value),
)
const topic1LlmRuntime = computed(() => topic1Runtime.value?.llm_runtime ?? null)
const topic1RuntimeAlertType = computed(() => {
  if (topic1RuntimeError.value) {
    return 'warning'
  }
  if (isLoadingTopic1Runtime.value || !topic1Runtime.value) {
    return 'info'
  }
  const status = topic1Runtime.value.llm_status.status
  if (status === 'reachable') {
    return 'success'
  }
  return 'warning'
})
const topic1RuntimeStatusTitle = computed(() => {
  if (topic1RuntimeError.value) {
    return '课题一 LLM 运行环境读取失败'
  }
  if (isLoadingTopic1Runtime.value || !topic1Runtime.value) {
    return '正在读取课题一 LLM 运行环境'
  }
  const status = topic1Runtime.value.llm_status.status
  if (status === 'reachable') {
    return '课题一 LLM 已配置且 endpoint 可达'
  }
  if (status === 'not_configured') {
    return '课题一 LLM_API_BASE 未配置'
  }
  return '课题一 LLM endpoint 暂不可达'
})
const topic1RuntimeStatusDescription = computed(() => {
  if (topic1RuntimeError.value) {
    return topic1RuntimeError.value
  }
  if (isLoadingTopic1Runtime.value || !topic1Runtime.value) {
    return '正在从课题一运行环境读取 LLM_MODEL 与 LLM_API_BASE。'
  }
  const runtime = topic1LlmRuntime.value
  const model = runtime?.model || '—'
  const endpoint = runtime?.api_base || '—'
  const base = `model=${model}，endpoint=${endpoint}`
  const message = topic1Runtime.value.llm_status.message
  if (message && topic1Runtime.value.llm_status.status !== 'reachable') {
    return `${base}（${message}）`
  }
  return base
})
const runtimeAlertType = computed(() => {
  if (optionsError.value || isAgentRuntimeMissing.value) {
    return 'warning'
  }
  return topic2Runtime.value?.upstream_ready === false ? 'warning' : 'success'
})
const runtimeStatusTitle = computed(() => {
  if (optionsError.value) {
    return '课题二选项代理暂不可用，使用页面默认值'
  }
  if (!topic2Runtime.value) {
    return '正在加载课题二运行状态'
  }
  if (isAgentRuntimeMissing.value) {
    return '课题二上游在线，但 Agent API 凭据缺失'
  }
  return topic2Runtime.value.upstream_ready ? '课题二上游在线' : '课题二上游离线'
})
const runtimeStatusDescription = computed(() => {
  if (optionsError.value) {
    return optionsError.value
  }
  const runtime = topic2Runtime.value
  if (!runtime) {
    return '正在读取 runtime、options 与 SeedBank 统计。'
  }
  const service = runtime.upstream_health.service
  const version = runtime.upstream_health.version
  const agent = agentRuntime.value
  const agentPart = agent
    ? `，agent=${agent.provider_label}，submitted_model=${agent.submitted_model_id}`
    : '，agent=unknown'
  return `service=${service}，version=${version}，options=${runtime.options_source}，seedbank=${runtime.seedbank_stats_source}${agentPart}`
})
const agentRuntimeDescription = computed(() => {
  const agent = agentRuntime.value
  if (!agent) {
    return '提交的是课题二异常语料改写 Agent 的模型 ID；实际 provider 由课题二后端 runtime 路由决定。'
  }
  if (agent.provider === 'missing') {
    return '课题二后端未检测到可用 Agent API 凭据，请先配置 DMX_API_KEY 或 DEEPSEEK_API_KEY。'
  }
  const fallback = agent.uses_deepseek_fallback ? '；当前使用 DeepSeek fallback' : ''
  return `提交模型 ID：${agent.submitted_model_id}；实际路由：${agent.provider_label}（${agent.base_url_origin}）${fallback}。`
})

watch(
  () => props.task?.task_id,
  () => {
    startError.value = ''
  },
)

watch(culturalTotalSampleCount, (total, previousTotal) => {
  const nextDefault = Math.min(total, 5)
  const previousDefault =
    typeof previousTotal === 'number' ? Math.min(previousTotal, 5) : nextDefault
  if (culturalForm.batchSize === previousDefault) {
    culturalForm.batchSize = nextDefault
  } else if (culturalForm.batchSize > total) {
    culturalForm.batchSize = total
  }
})

watch(
  () => props.selectedAgent,
  (agentId) => {
    if (agentId === 'topic1-value-qa') {
      void loadTopic1Runtime()
    }
  },
  { immediate: true },
)

onMounted(() => {
  void loadTopic2Options()
})

async function loadTopic1Runtime() {
  isLoadingTopic1Runtime.value = true
  topic1RuntimeError.value = ''
  try {
    topic1Runtime.value = await getTopic1Runtime()
  } catch {
    topic1RuntimeError.value = '未能读取课题一 LLM 运行环境，请检查 TOPIC1_VALUE_QA_PROJECT_ROOT。'
    topic1Runtime.value = null
  } finally {
    isLoadingTopic1Runtime.value = false
  }
}

async function loadTopic2Options() {
  isLoadingOptions.value = true
  optionsError.value = ''
  try {
    const [runtimeResult, optionsResult, statsResult] = await Promise.allSettled([
      getTopic2Runtime(),
      getTopic2Options(),
      getTopic2SeedbankStats(),
    ])

    if (runtimeResult.status === 'fulfilled') {
      topic2Runtime.value = runtimeResult.value
      topic2Form.budget = clampNumber(topic2Form.budget, budgetMin.value, budgetMax.value)
    }
    if (optionsResult.status === 'fulfilled') {
      topic2Options.value = optionsResult.value
      syncLanguageDefault()
      syncModeratorDefault()
      syncAgentModelDefault()
    }
    if (statsResult.status === 'fulfilled') {
      seedbankStats.value = statsResult.value
      syncL1Default()
    }

    const errors = [runtimeResult, optionsResult, statsResult]
      .filter((item) => item.status === 'rejected')
      .map((item) => (item as PromiseRejectedResult).reason)
    if (errors.length > 0) {
      optionsError.value = '未能完整读取课题二真实选项，已保留页面默认值。'
    }
  } finally {
    isLoadingOptions.value = false
  }
}

async function handleStart() {
  startError.value = ''
  const payload = isTopic2Selected.value
    ? buildTopic2Payload()
    : isTopic1Selected.value
      ? buildTopic1Payload()
      : isTopic3RiskSelected.value
        ? buildTopic3RiskPayload()
        : isTopic3CulturalSelected.value
          ? buildTopic3CulturalPayload()
          : buildTopic3Payload()
  if (!payload) {
    return
  }
  isStarting.value = true
  try {
    const task = await createBenchmarkTask(payload)
    emit('task-created', task)
  } catch (error) {
    startError.value = error instanceof Error ? error.message : 'Benchmark 生成任务创建失败'
  } finally {
    isStarting.value = false
  }
}

function buildTopic2Payload(): BenchmarkTaskCreatePayload | null {
  const l1 = topic2Form.l1.map((item) => item.trim()).filter(Boolean)
  if (l1.length === 0) {
    startError.value = '请至少选择一个 SeedBank L1'
    return null
  }
  if (topic2Form.moderators.length === 0) {
    startError.value = '请至少选择一个 Moderator'
    return null
  }
  if (isAgentRuntimeMissing.value) {
    startError.value = '课题二后端未检测到可用 Agent API 凭据，无法启动生成任务'
    return null
  }

  return {
    agent_id: 'topic2-autobench',
    mode: 'live_run',
    parameters: {
      l1,
      moderators: [...topic2Form.moderators],
      language: topic2Form.language,
      budget: topic2Form.budget,
      sampling_seed: topic2Form.sampling_seed,
      model: topic2Form.model,
      max_turns: topic2Form.max_turns,
    },
  }
}

function buildTopic3Payload(): BenchmarkTaskCreatePayload | null {
  if (topic3TotalSampleCount.value <= 0) {
    startError.value = '课题三样本预算必须大于 0'
    return null
  }
  if (!topic3Form.seed_dataset.trim()) {
    startError.value = '请填写课题三 Seed 数据集'
    return null
  }
  if (!topic3Form.generation_model.trim() || !topic3Form.guard_model.trim()) {
    startError.value = '请填写课题三 Generation Model 和 Guard Model'
    return null
  }

  return {
    agent_id: 'topic3-difficulty-generation',
    mode: 'live_run',
    parameters: {
      language: topic3Form.language,
      total_sample_count: topic3TotalSampleCount.value,
      difficulty_preset: topic3Form.difficulty_preset,
      difficulty_counts: { ...topic3Form.difficulty_counts },
      seed_dataset: topic3Form.seed_dataset.trim(),
      risk_categories: [],
      generation_model: topic3Form.generation_model.trim(),
      guard_model: topic3Form.guard_model.trim(),
    },
  }
}

function buildTopic1Payload(): BenchmarkTaskCreatePayload | null {
  if (topic1RequestedGroupCount.value > 10) {
    startError.value = '课题一 live_run 总三档组数不能超过 10'
    return null
  }
  const topic = topic1Form.topic.trim()
  const dimension = topic1Form.dimension.trim()
  if (topic1Form.generation_mode === 'topic' && !topic) {
    startError.value = '请填写课题一生成主题'
    return null
  }
  if (topic1Form.generation_mode === 'dimension' && !dimension) {
    startError.value = '请选择或填写课题一价值维度'
    return null
  }
  if (topic1Form.retrieval_mode === 'local_corpus' && !topic1Form.corpus_jsonl.trim()) {
    startError.value = '本地 corpus 模式需要填写 Corpus JSONL 路径'
    return null
  }

  return {
    agent_id: 'topic1-value-qa',
    mode: 'live_run',
    parameters: {
      generation_mode: topic1Form.generation_mode,
      topic: topic1Form.generation_mode === 'topic' ? topic : undefined,
      dimension: topic1Form.generation_mode === 'dimension' ? dimension : undefined,
      n_topics: topic1Form.generation_mode === 'topic' ? 1 : topic1Form.n_topics,
      groups_per_topic: topic1Form.groups_per_topic,
      retrieval_mode: topic1Form.retrieval_mode,
      corpus_jsonl:
        topic1Form.retrieval_mode === 'local_corpus' ? topic1Form.corpus_jsonl.trim() : undefined,
      language: topic1Form.language,
      seed: topic1Form.seed,
      run_qc: false,
      run_trace: false,
    },
  }
}

function buildTopic3RiskPayload(): BenchmarkTaskCreatePayload {
  return {
    agent_id: 'topic3-risk-benchmark-generation',
    mode: 'live_run',
    parameters: {
      scale: 'trial',
      target_per_kind: 5,
      workers: 1,
    },
  }
}

function buildTopic3CulturalPayload(): BenchmarkTaskCreatePayload | null {
  const built = buildCulturalCorpusTaskPayload({
    scale: culturalForm.scale,
    structureBand: culturalForm.structureBand,
    ethnicGroups: culturalForm.ethnicGroups,
    batchSize: culturalForm.batchSize,
    randomSeed: culturalForm.randomSeed,
    allowedDimensions: culturalForm.allowedDimensions,
  })
  if (!built.ok) {
    startError.value = built.error
    return null
  }
  return built.payload
}

function formatDate(value?: string | null) {
  return formatApiDate(value)
}

function optionLabelWithCount(item: Topic2SelectOption) {
  return typeof item.count === 'number' ? `${item.label} (${item.count})` : item.label
}

function syncL1Default() {
  const available = new Set(l1Options.value.map((item) => item.value))
  const selected = topic2Form.l1.filter((item) => available.has(item))
  topic2Form.l1 = selected.length > 0 ? selected.slice(0, 2) : [DEFAULT_L1]
}

function syncModeratorDefault() {
  const available = new Set(
    moderatorGroups.value.flatMap((group) => group.options.map((item) => item.value)),
  )
  if (!topic2Form.moderators.some((item) => available.has(item))) {
    topic2Form.moderators = available.has('keyword') ? ['keyword'] : [...available].slice(0, 1)
  }
}

function syncLanguageDefault() {
  if (!languageOptions.value.includes(topic2Form.language)) {
    topic2Form.language = 'zh+en'
  }
}

function syncAgentModelDefault() {
  const available = agentModelOptions.value.filter((item) => !item.disabled)
  if (!available.some((item) => item.value === topic2Form.model)) {
    topic2Form.model = available[0]?.value || 'claude-sonnet-4-6'
  }
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function applyTopic3Preset(value?: string | number | boolean | Record<string, unknown>) {
  const preset =
    typeof value === 'string' ? (value as Topic3DifficultyPreset) : topic3Form.difficulty_preset
  if (preset === 'custom') {
    return
  }
  Object.assign(topic3Form.difficulty_counts, TOPIC3_PRESET_COUNTS[preset])
}

function handleViewAssets() {
  emit('view-assets', {
    focusAssetId: props.artifacts[0]?.asset_id,
    sourceTaskId: props.task?.task_id,
    sourceAgentId: selectedAgent.value,
    from: 'task_runner',
  })
}
</script>

<style scoped>
.task-runner {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.runner-grid {
  display: grid;
  grid-template-columns: minmax(360px, 480px) minmax(0, 1fr);
  gap: 18px;
}

.runner-form,
.runner-status,
.runner-logs {
  padding: 18px;
  border: 1px solid #dbe5f1;
  border-radius: 14px;
  background: #fff;
}

.runner-form__header,
.runner-logs__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.runner-form__header h3,
.runner-status h3,
.runner-logs__header h3 {
  margin: 0;
  color: var(--text-primary);
}

.runner-form__header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.live-badge,
.runner-logs__header span {
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

.agent-card-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.agent-card {
  display: flex;
  min-width: 0;
  min-height: 112px;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #fff;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    box-shadow 0.18s ease;
}

.agent-card:hover {
  border-color: rgba(64, 158, 255, 0.55);
  background: #f8fbff;
}

.agent-card:focus-visible {
  outline: 2px solid rgba(64, 158, 255, 0.5);
  outline-offset: 2px;
}

.agent-card.is-active {
  border-color: var(--accent-blue);
  background: rgba(64, 158, 255, 0.08);
  box-shadow: 0 8px 20px rgba(21, 101, 192, 0.1);
}

.agent-card__header {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.agent-card__title,
.agent-card__subtitle,
.agent-card__meta,
.agent-card__description {
  display: block;
  min-width: 0;
}

.agent-card__title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.agent-card__subtitle {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.35;
}

.agent-card__status {
  display: inline-flex;
  flex-shrink: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.agent-card__badge,
.agent-card__current {
  display: inline-flex;
  min-height: 20px;
  align-items: center;
  border-radius: 999px;
  padding: 0 7px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.agent-card__badge {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.agent-card__current {
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
}

.agent-card__meta {
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.agent-card__description {
  color: var(--text-secondary);
  display: -webkit-box;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field-help {
  width: 100%;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.field-help--warn {
  color: #b26a00;
}

.topic1-llm-readonly {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 8px;
  background: var(--surface-muted, #f8fafc);
}

.topic1-llm-readonly__row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
}

.topic1-llm-readonly__label {
  color: var(--text-muted, #64748b);
  font-size: 13px;
}

.topic1-llm-readonly__value {
  color: var(--text-primary, #0f172a);
  font-size: 13px;
  word-break: break-all;
}

.topic1-llm-readonly__value--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.runtime-alert {
  margin-bottom: 14px;
}

.option-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.option-tags {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.option-description {
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.difficulty-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.advanced-options {
  margin: 0 0 14px;
}

.runner-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.status-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin: 14px 0 18px;
}

.status-fields dt {
  color: var(--text-muted);
  font-size: 12px;
}

.status-fields dd {
  margin: 5px 0 0;
  color: var(--text-primary);
  font-size: 13px;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.status-pill {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-weight: 700;
}

.status-completed {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.status-failed,
.status-rejected {
  background: rgba(198, 40, 40, 0.1);
  color: var(--accent-red);
}

.error-text {
  color: var(--accent-red);
}

.polling-note {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.raw-json {
  max-height: 520px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border-radius: 10px;
  background: #f5f8fc;
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 1080px) {
  .runner-grid,
  .form-row,
  .agent-card-group,
  .status-fields {
    grid-template-columns: 1fr;
  }

  .difficulty-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .difficulty-grid {
    grid-template-columns: 1fr;
  }
}
</style>
