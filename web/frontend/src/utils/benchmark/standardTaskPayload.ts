import type {
  BenchmarkAgentId,
  BenchmarkTaskCreatePayload,
  Topic1ValueQaTaskCreatePayload,
  Topic3DifficultyTaskCreatePayload,
} from '@/types'

export type StandardBenchmarkDirection =
  | 'value_qa'
  | 'dynamic_difficulty'
  | 'anomaly_rewrite'
  | 'cultural_diversity'
  | 'risk_content'

export type StandardBenchmarkScale = 'trial' | 'standard' | 'large'

export type StandardRewriteStrength = 'light' | 'strong'

/** 文化多样性难度等级档：低难度为主 / 混合 / 中高难度 → L1–L3 分配 */
export type CulturalStructureBand = 'explicit' | 'mixed' | 'implicit_heavy'

export const DEFAULT_CULTURAL_ETHNIC_GROUPS = ['回族', '蒙古族', '藏族', '维吾尔族'] as const

export const STANDARD_DIRECTION_TO_AGENT: Record<StandardBenchmarkDirection, BenchmarkAgentId> = {
  value_qa: 'topic1-value-qa',
  dynamic_difficulty: 'topic3-difficulty-generation',
  anomaly_rewrite: 'topic2-autobench',
  cultural_diversity: 'topic3-cultural-corpus-generation',
  risk_content: 'topic3-risk-benchmark-generation',
}

export const SCALE_LABELS: Record<StandardBenchmarkScale, string> = {
  trial: '试跑',
  standard: '标准',
  large: '大批量',
}

export const CULTURAL_STRUCTURE_BAND_LABELS: Record<CulturalStructureBand, string> = {
  explicit: '低难度为主',
  mixed: '混合',
  implicit_heavy: '中高难度',
}

export interface StandardTaskFormInput {
  direction: StandardBenchmarkDirection
  scale: StandardBenchmarkScale
  /** 价值语料可选主题；空则用默认 */
  topic?: string
  /** 价值语料大批量多选主题 */
  topics?: string[]
  /** 动态难度：17 类抽样范围；空或全选则传 []（全库随机） */
  riskCategories?: string[]
  /** 异常改写强度 */
  rewriteStrength?: StandardRewriteStrength
  /** 文化多样性民族多选；空则用默认四民族 */
  ethnicGroups?: string[]
  /** 文化多样性难度等级档；默认低难度为主（稳试跑） */
  structureBand?: CulturalStructureBand
}

export type StandardTaskPayloadResult =
  | { ok: true; payload: BenchmarkTaskCreatePayload }
  | { ok: false; error: string }

const DEFAULT_TOPIC2_L1 = 'L1-2 Explicit Harmful Injection'

/** 规模 → H1–H4 每档条数（方案 B：始终四档均衡） */
const DIFFICULTY_COUNT_BY_SCALE: Record<StandardBenchmarkScale, number> = {
  trial: 1,
  standard: 2,
  large: 4,
}

/** 曾博士回执：4 卡 RTX Pro 5000 估计；实际随显卡变化。 */
export const TOPIC3_DIFFICULTY_DURATION_HINT_BY_SCALE: Record<StandardBenchmarkScale, string> = {
  trial: '约 80 秒',
  standard: '约 100 秒',
  large: '约 150 秒',
}

export const TOPIC3_RISK_CATEGORY_COUNT = 17

/** taxonomy 不可用时的 C01–C17 回退（与后端 TOPIC3_RISK_CATEGORIES 对齐） */
export const TOPIC3_RISK_CATEGORY_FALLBACK: ReadonlyArray<{ code: string; name: string }> = [
  { code: 'C01', name: '煽动颠覆国家政权、推翻社会主义制度' },
  { code: 'C02', name: '危害国家安全和利益、损害国家形象' },
  { code: 'C03', name: '煽动分裂国家、破坏国家统一和社会稳定' },
  { code: 'C04', name: '宣扬恐怖主义、极端主义' },
  { code: 'C05', name: '宣扬民族仇恨' },
  { code: 'C06', name: '宣扬暴力、淫秽色情' },
  { code: 'C07', name: '传播虚假有害信息' },
  { code: 'C08', name: '歧视性内容' },
  { code: 'C09', name: '商业违法违规' },
  { code: 'C10', name: '侵犯他人权益' },
  { code: 'C11', name: '无法满足特定服务类型的安全需求' },
  { code: 'C12', name: '经济损失高风险的活动' },
  { code: 'C13', name: '未成年人安全' },
  { code: 'C14', name: '从事欺诈、虐待或掠夺性行为' },
  { code: 'C15', name: '不正确民族叙事' },
  { code: 'C16', name: '民族情感商业化、功利化、娱乐化' },
  { code: 'C17', name: '价值导向偏差' },
]

function balancedDifficultyCounts(
  perLevel: number,
): Topic3DifficultyTaskCreatePayload['parameters']['difficulty_counts'] {
  return { H1: perLevel, H2: perLevel, H3: perLevel, H4: perLevel }
}

/** 空或 17 类全选 → 上游 []（全库随机）；子集则原样下发。 */
export function normalizeTopic3RiskCategories(codes?: string[]): string[] {
  const unique = [...new Set((codes ?? []).map((item) => item.trim()).filter(Boolean))]
  if (unique.length === 0 || unique.length >= TOPIC3_RISK_CATEGORY_COUNT) {
    return []
  }
  return unique
}

const TOPIC2_BUDGET_BY_SCALE: Record<StandardBenchmarkScale, number> = {
  trial: 1,
  standard: 2,
  large: 4,
}

/** 课题二确认的对外约条数；与 budget 非 1:1。 */
const TOPIC2_SAMPLE_COUNT_BY_SCALE: Record<StandardBenchmarkScale, number> = {
  trial: 3,
  standard: 20,
  large: 50,
}

export const TOPIC2_DURATION_HINT_BY_SCALE: Record<StandardBenchmarkScale, string> = {
  trial: '约 3 分钟',
  standard: '约 10–20 分钟',
  large: '约 25–40 分钟',
}

/** 1 组 = 高/中/低各 1 条。标准模式单主题最多 2 组（百科单文档上限约 6 条）。 */
const TOPIC1_GROUPS_BY_SCALE: Record<StandardBenchmarkScale, number> = {
  trial: 1,
  standard: 2,
  large: 2,
}

/** 规模 → 文化多样性总条数 */
const CULTURAL_TOTAL_BY_SCALE: Record<StandardBenchmarkScale, number> = {
  trial: 3,
  standard: 9,
  large: 30,
}

/**
 * 规模 × 难度等级档 → L1/L2/L3。
 * 混合：三档均分；中高难度：L2=floor(n/2), L3=n-L2；低难度为主：全 L1。
 */
export function culturalDifficultyCounts(
  scale: StandardBenchmarkScale,
  structureBand: CulturalStructureBand = 'explicit',
): {
  L1: number
  L2: number
  L3: number
} {
  const total = CULTURAL_TOTAL_BY_SCALE[scale]
  if (structureBand === 'explicit') {
    return { L1: total, L2: 0, L3: 0 }
  }
  if (structureBand === 'mixed') {
    const per = total / 3
    return { L1: per, L2: per, L3: per }
  }
  const l2 = Math.floor(total / 2)
  return { L1: 0, L2: l2, L3: total - l2 }
}

export interface CulturalCorpusTaskInput {
  scale: StandardBenchmarkScale
  structureBand?: CulturalStructureBand
  ethnicGroups?: string[]
  language?: 'zh' | 'en' | 'zh+en'
  batchSize?: number
  randomSeed?: number
  allowedDimensions?: string[]
}

export function buildCulturalCorpusTaskPayload(
  input: CulturalCorpusTaskInput,
): StandardTaskPayloadResult {
  const ethnicGroups = (
    input.ethnicGroups?.length ? input.ethnicGroups : [...DEFAULT_CULTURAL_ETHNIC_GROUPS]
  )
    .map((item) => item.trim())
    .filter(Boolean)
  if (!ethnicGroups.length) {
    return { ok: false, error: '请至少选择一个民族' }
  }
  const structureBand = input.structureBand ?? 'explicit'
  const difficulty_counts = culturalDifficultyCounts(input.scale, structureBand)
  const total_sample_count = difficulty_counts.L1 + difficulty_counts.L2 + difficulty_counts.L3
  const requestedBatch = input.batchSize
  const batch_size =
    typeof requestedBatch === 'number' && requestedBatch >= 1
      ? Math.min(requestedBatch, total_sample_count)
      : Math.min(total_sample_count, 5)
  const random_seed =
    typeof input.randomSeed === 'number' && input.randomSeed >= 0 ? input.randomSeed : 20260727
  const allowed_dimensions = (input.allowedDimensions ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
  return {
    ok: true,
    payload: {
      agent_id: 'topic3-cultural-corpus-generation',
      mode: 'live_run',
      parameters: {
        language: input.language ?? 'zh',
        total_sample_count,
        batch_size,
        difficulty_counts,
        allowed_ethnic_groups: ethnicGroups,
        allowed_dimensions,
        random_seed,
        scale: input.scale,
        structure_band: structureBand,
      },
    },
  }
}

function uniqueTopics(topics?: string[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const item of topics ?? []) {
    const text = item.trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }
  return out
}

export function buildStandardBenchmarkTaskPayload(
  input: StandardTaskFormInput,
): StandardTaskPayloadResult {
  const { direction, scale } = input

  if (direction === 'value_qa') {
    const topic = (input.topic ?? '').trim()
    const selectedTopics = uniqueTopics(input.topics)
    if (scale === 'large') {
      if (selectedTopics.length < 2) {
        return { ok: false, error: '大批量请至少选择 2 个主题' }
      }
      const payload: Topic1ValueQaTaskCreatePayload = {
        agent_id: 'topic1-value-qa',
        mode: 'live_run',
        parameters: {
          generation_mode: 'topic',
          topic: selectedTopics[0],
          topics: selectedTopics,
          n_topics: selectedTopics.length,
          groups_per_topic: TOPIC1_GROUPS_BY_SCALE.large,
          language: 'zh',
          seed: 20260727,
          run_qc: false,
          run_trace: false,
          scale,
        },
      }
      return { ok: true, payload }
    }
    if (!topic) {
      return { ok: false, error: '请填写主题' }
    }
    const groups = TOPIC1_GROUPS_BY_SCALE[scale]
    const payload: Topic1ValueQaTaskCreatePayload = {
      agent_id: 'topic1-value-qa',
      mode: 'live_run',
      parameters: {
        generation_mode: 'topic',
        topic,
        n_topics: 1,
        groups_per_topic: groups,
        language: 'zh',
        seed: 20260727,
        run_qc: false,
        run_trace: false,
        scale,
      },
    }
    return {
      ok: true,
      payload,
    }
  }

  if (direction === 'dynamic_difficulty') {
    const selected = (input.riskCategories ?? []).map((item) => item.trim()).filter(Boolean)
    if (selected.length === 0) {
      return { ok: false, error: '请至少保留一个风险类别，或全选以从 17 类随机抽样' }
    }
    const perLevel = DIFFICULTY_COUNT_BY_SCALE[scale]
    const difficulty_counts = balancedDifficultyCounts(perLevel)
    const total_sample_count = Object.values(difficulty_counts).reduce((sum, n) => sum + n, 0)
    if (total_sample_count <= 0) {
      return { ok: false, error: '样本预算必须大于 0' }
    }
    return {
      ok: true,
      payload: {
        agent_id: 'topic3-difficulty-generation',
        mode: 'live_run',
        parameters: {
          language: 'zh',
          total_sample_count,
          difficulty_preset: 'custom',
          difficulty_counts,
          seed_dataset: 'harmful_zh_17class_v1',
          risk_categories: normalizeTopic3RiskCategories(selected),
          generation_model: 'Qwen3.5-9B',
          guard_model: 'Qwen3Guard-Gen-4B',
          scale,
        },
      },
    }
  }

  if (direction === 'cultural_diversity') {
    return buildCulturalCorpusTaskPayload({
      scale,
      structureBand: input.structureBand,
      ethnicGroups: input.ethnicGroups,
    })
  }

  if (direction === 'risk_content') {
    if (scale !== 'trial') {
      return { ok: false, error: '风险内容生成本期仅支持试跑（10 条）' }
    }
    return {
      ok: true,
      payload: {
        agent_id: 'topic3-risk-benchmark-generation',
        mode: 'live_run',
        parameters: {
          scale: 'trial',
          target_per_kind: 5,
          workers: 1,
        },
      },
    }
  }

  const strength = input.rewriteStrength ?? 'light'
  const budget = TOPIC2_BUDGET_BY_SCALE[scale]
  const max_turns = strength === 'strong' ? 8 : 5
  return {
    ok: true,
    payload: {
      agent_id: 'topic2-autobench',
      mode: 'live_run',
      parameters: {
        l1: [DEFAULT_TOPIC2_L1],
        moderators: ['keyword'],
        language: 'zh+en',
        budget,
        sampling_seed: 20260707,
        model: 'claude-sonnet-4-6',
        max_turns,
        scale,
        rewrite_strength: strength,
      },
    },
  }
}

export function estimateStandardSampleCount(input: StandardTaskFormInput): number {
  if (input.direction === 'value_qa') {
    if (input.scale === 'large') {
      return uniqueTopics(input.topics).length * 6
    }
    return TOPIC1_GROUPS_BY_SCALE[input.scale] * 3
  }
  if (input.direction === 'dynamic_difficulty') {
    const perLevel = DIFFICULTY_COUNT_BY_SCALE[input.scale]
    return Object.values(balancedDifficultyCounts(perLevel)).reduce((sum, n) => sum + n, 0)
  }
  if (input.direction === 'cultural_diversity') {
    return CULTURAL_TOTAL_BY_SCALE[input.scale]
  }
  if (input.direction === 'risk_content') {
    return 10
  }
  return TOPIC2_SAMPLE_COUNT_BY_SCALE[input.scale]
}
