import type { DataSource, DatasetSubType } from '@/types'

const subTypeLabelMap: Record<string, string> = {
  'science-fact': 'AI4Sci 科学事实',
  'science-data': 'AI4Sci 数据规范',
  'science-ethics': 'AI4Sci 学术伦理',
  'science-kg': 'AI4Sci 知识准确性',
  'science-clinical': 'AI4Sci 临床规范',
  'science-climate': 'AI4Sci 模型验证',
  'culture-lang': '多民族文化 文化包容',
  'culture-folk': '多民族文化 文化传承',
  'culture-religion': '多民族文化 宗教尊重',
  'culture-regional': '多民族文化 文化覆盖',
  'culture-heritage': '多民族文化 非遗传承',
  'culture-history': '多民族文化 历史客观',
}

export function subTypeLabel(subType?: DatasetSubType | string): string {
  if (!subType) return ''
  return subTypeLabelMap[subType] ?? subType
}

export function badgeClass(level: string): string {
  return level.toLowerCase()
}

export function badgeText(level: string): string {
  const map: Record<string, string> = { HIGH: 'HIGH', MEDIUM: 'MED', LOW: 'LOW' }
  return map[level] ?? level
}

export function dataSourceLabel(source?: DataSource | string): string {
  const labels: Partial<Record<DataSource, string>> = {
    api: '真实服务',
    benchmark: 'Benchmark 实时',
    benchmark_static: 'Benchmark 静态结果',
    backend_snapshot: '后端快照',
    corpus_static: '文化语料批次集合',
    culture_assessment_static: '文化评测 Benchmark',
    demo_fixture: '示例数据',
    error: '服务不可用',
    local: '本地资产',
    mock: '示例数据',
    real: 'Cultural Gen 实时',
    static: '静态资产',
    unavailable: '服务不可用',
  }
  return source ? labels[source as DataSource] || source : '加载中'
}

// ============================================================
// 共享 Level 映射（Diversity + Risk 组件共用）
// ============================================================

/** 风险等级 / 多样性等级 → 标签颜色（green / orange / red） */
export function levelTagColor(level: string): 'green' | 'orange' | 'red' {
  if (level === 'excellent' || level === 'LOW') return 'green'
  if (level === 'good' || level === 'MEDIUM') return 'orange'
  return 'red'
}

/** 风险等级 / 多样性等级 → 短中文标签（优/良/待提升/高/中/低） */
export function levelShortLabel(level: string): string {
  const map: Record<string, string> = {
    excellent: '优',
    good: '良',
    needsImprovement: '待提升',
    HIGH: '高',
    MEDIUM: '中',
    LOW: '低',
  }
  return map[level] ?? level
}

/** Diversity 标注节点信号优先级（数值越大越严重） */
export const LEVEL_PRIORITY: Record<string, number> = {
  excellent: 0,
  good: 1,
  needsImprovement: 2,
  HIGH: 2,
  MEDIUM: 1,
  LOW: 0,
}
