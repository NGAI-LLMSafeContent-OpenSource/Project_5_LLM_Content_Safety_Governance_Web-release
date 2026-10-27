import type { StrategyRecommendation, ComparisonMetric } from '@/types'
import { StrategyPriority } from '@/types'

// ============================================================
// 策略建议 Mock 数据 (Step 6)
// ============================================================

export const mockStrategyRecommendations: StrategyRecommendation[] = [
  {
    id: 'strategy-p0',
    priority: StrategyPriority.P0,
    title: 'SFT 监督微调',
    description:
      '针对科学事实错误与文化偏见高危语义组合，补充 1,200+ 对齐样本，覆盖 AI4Sci 和多民族文化双场景。预计覆盖 847 个高风险Token组合中的 Top-5 归因链。',
    trainingMethod: 'SFT',
    trainingDataCount: '1,200+ 条',
    expectedDuration: '2-3 天',
    targetMetric: '安全违规率 ≤ 0.5%',
  },
  {
    id: 'strategy-p1',
    priority: StrategyPriority.P1,
    title: 'RLHF 强化学习',
    description:
      '强化文化偏见与科学误导场景下的安全识别，建立「有害-无害化」偏好对比数据集。重点覆盖文化多样性内容的排他性表述与历史虚无模式。',
    trainingMethod: 'RLHF',
    trainingDataCount: '300+ 组',
    expectedDuration: '5-7 天',
    targetMetric: '安全响应率 ≥ 95%',
  },
  {
    id: 'strategy-p2',
    priority: StrategyPriority.P2,
    title: 'DPO 直接偏好优化',
    description:
      '利用本次归因与修正分析自动生成 482 组偏好对，覆盖科学准确性与文化多样性双维度。强化 AI4Sci 领域的事实校验能力与文化包容性输出。',
    trainingMethod: 'DPO',
    trainingDataCount: '482 组',
    expectedDuration: '3-5 天',
    targetMetric: '多样性达成度 ≥ 85%',
  },
]

export const mockComparisonMetrics: ComparisonMetric[] = [
  { label: 'AI4Sci 科学事实准确率', before: '84.2%', after: '≥ 96.5%', improvement: '+12.3%' },
  { label: '文化偏见触发率', before: '18.2%', after: '≤ 3.5%', improvement: '-14.7%' },
  { label: '多样性达成度（平均）', before: '72.8', after: '≥ 88.0', improvement: '+15.2' },
  { label: 'Validator 拦截率', before: '67.9%', after: '≥ 92.0%', improvement: '+24.1%' },
]
