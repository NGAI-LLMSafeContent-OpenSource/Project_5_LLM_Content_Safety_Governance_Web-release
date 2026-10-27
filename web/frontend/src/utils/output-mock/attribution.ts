import type { AttributionNode } from '@/types'
import { DiversityLevel, RiskLevel } from '@/types'

// ============================================================
// 归因节点 Mock 数据 (Step 4)
// ============================================================

export const mockDiversityAttributionNodes: AttributionNode[] = [
  {
    id: 'DIV-CUL-001',
    signals: {
      文化包容与尊重: DiversityLevel.EXCELLENT,
      代表性与覆盖面: DiversityLevel.EXCELLENT,
      非遗文化传承: DiversityLevel.EXCELLENT,
    },
    chain: '民族称谓(0.87) + 多元一体表述(0.92) → 文化多样性推理节点(0.95) → 包容性文化输出',
    reasonPath: '民族称谓(0.87) + 片面特征(0.79) → 文化偏见推理节点(0.89) → 排他性文化输出',
    weight: 0.89,
  },
  {
    id: 'DIV-SCI-003',
    signals: {
      开放科学与可复现: DiversityLevel.EXCELLENT,
      方法严谨性: DiversityLevel.GOOD,
      科研伦理正向引导: DiversityLevel.GOOD,
    },
    chain: '研究方法描述(0.72) + 数据开放声明(0.68) → 可复现性判断节点(0.76) → 开放科学友好输出',
    reasonPath:
      '研究方法描述(0.72) + 数据开放声明(0.68) → 可复现性判断节点(0.76) → 开放科学友好输出',
    weight: 0.76,
  },
  {
    id: 'DIV-CUL-019',
    signals: {
      文化包容与尊重: DiversityLevel.NEEDS_IMPROVEMENT,
      代表性与覆盖面: DiversityLevel.NEEDS_IMPROVEMENT,
      非遗文化传承: DiversityLevel.GOOD,
    },
    chain: '文化遗产指称(0.65) + 传承现状描述(0.58) → 文化价值评估节点(0.62) → 非遗价值弱化输出',
    reasonPath:
      '文化遗产指称(0.65) + 传承现状描述(0.58) → 文化价值评估节点(0.62) → 非遗价值弱化输出',
    weight: 0.62,
  },
]

export const mockRiskAttributionNodes: AttributionNode[] = [
  {
    id: 'AI4SCI-042',
    signals: {
      科学事实错误: RiskLevel.HIGH,
      数据规范性风险: RiskLevel.HIGH,
      学术伦理风险: RiskLevel.MEDIUM,
    },
    chain: '过时科学文献(0.83) + 错误事实陈述(0.76) → 科学事实推理节点(0.85) → 输出错误科学结论',
    reasonPath:
      '过时科学文献(0.83) + 错误事实陈述(0.76) → 科学事实推理节点(0.85) → 输出错误科学结论',
    weight: 0.82,
  },
  {
    id: 'CULT-089',
    signals: {
      文化偏见风险: RiskLevel.HIGH,
      语言歧视风险: RiskLevel.MEDIUM,
      宗教冲突风险: RiskLevel.LOW,
    },
    chain: '民族指称(0.87) + 排他性表述(0.82) → 文化偏见推理节点(0.89) → 排他性文化输出',
    reasonPath: '民族指称(0.87) + 排他性表述(0.82) → 文化偏见推理节点(0.89) → 排他性文化输出',
    weight: 0.89,
  },
  {
    id: 'AI4SCI-118',
    signals: {
      科学事实错误: RiskLevel.MEDIUM,
      数据规范性风险: RiskLevel.HIGH,
      研究引用偏差: RiskLevel.MEDIUM,
    },
    chain: '统计术语组合(0.68) + p值误用(0.72) → 数据解读节点(0.72) → 错误统计推断',
    reasonPath: '统计术语组合(0.68) + p值误用(0.72) → 数据解读节点(0.72) → 错误统计推断',
    weight: 0.72,
  },
]
