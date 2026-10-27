import type { RadarChartData, MultiDatasetRadarData } from '@/types'

// ============================================================
// 雷达图 Mock 数据 (Step 3)
// ============================================================

export const mockRadarDiversityData: RadarChartData = {
  dimensions: ['文化适应性', '跨文化理解', '文化包容性', '多民族覆盖', '方言覆盖', '节庆习俗'],
  series: [
    {
      name: '优',
      values: [92, 89, 88, 85, 78, 82],
      fill: 'rgba(63,185,129,0.12)',
      stroke: '#3fb981',
    },
    {
      name: '良',
      values: [75, 72, 70, 68, 60, 65],
      fill: 'rgba(245,158,11,0.10)',
      stroke: '#f59e0b',
    },
    {
      name: '待提升',
      values: [50, 45, 48, 42, 38, 40],
      fill: 'rgba(239,68,68,0.06)',
      stroke: '#ef4444',
    },
  ],
}

export const mockRadarRiskData: RadarChartData = {
  dimensions: ['科学准确性', '数据规范性', '学术严谨性', '文化偏见', '语言歧视', '宗教冲突'],
  series: [
    {
      name: '高风险',
      values: [82, 78, 75, 68, 62, 70],
      fill: 'rgba(239,68,68,0.12)',
      stroke: '#ef4444',
    },
    {
      name: '中风险',
      values: [65, 60, 58, 55, 50, 52],
      fill: 'rgba(245,158,11,0.10)',
      stroke: '#f59e0b',
    },
    {
      name: '低风险',
      values: [40, 35, 42, 30, 28, 35],
      fill: 'rgba(63,185,129,0.08)',
      stroke: '#3fb981',
    },
  ],
}

// ============================================================
// 多数据集雷达图 Mock 数据 (Step 3, ECharts 兼容)
// ============================================================

export const mockRadarMultiDatasetData: MultiDatasetRadarData = {
  dimensions: [
    'C01',
    'C02',
    'C03',
    'C04',
    'C05',
    'C06',
    'C07',
    'C08',
    'C09',
    'C10',
    'C11',
    'C12',
    'C13',
    'C14',
    'C15',
    'C16',
    'C17',
  ],
  dimensionLabels: {
    C01: '煽动颠覆国家政权',
    C02: '危害国家安全',
    C03: '煽动分裂国家',
    C04: '宣扬恐怖主义',
    C05: '宣扬民族仇恨',
    C06: '宣扬暴力淫秽',
    C07: '传播虚假信息',
    C08: '歧视性内容',
    C09: '商业违法违规',
    C10: '侵犯他人权益',
    C11: '安全需求不满足',
    C12: '经济损失高风险',
    C13: '未成年人安全',
    C14: '欺诈掠夺行为',
    C15: '不正确民族叙事',
    C16: '民族情感商业化',
    C17: '价值导向偏差',
  },
  selectedMetric: 'f1',
  series: [
    {
      datasetId: 'ds-science-001',
      datasetName: '科学论文验证集',
      values: [0, 0, 0, 0, 0, 0, 88.5, 0, 84.2, 0, 0, 79.8, 0, 0, 0, 0, 0],
      color: '#1565c0',
    },
    {
      datasetId: 'ds-culture-001',
      datasetName: '多民族语言测试集',
      values: [82.1, 85.2, 0, 0, 79.5, 77.8, 0, 0, 0, 0, 0, 0, 0, 0, 81.3, 78.9, 75.4],
      color: '#e65100',
    },
    {
      datasetId: 'ds-culture-006',
      datasetName: '民族历史叙事测试集',
      values: [86.8, 87.3, 0, 0, 81.4, 76.5, 0, 0, 0, 0, 0, 0, 0, 0, 82.7, 80.1, 79.3],
      color: '#c62828',
    },
    {
      datasetId: 'ds-science-005',
      datasetName: '药物临床数据集',
      values: [0, 0, 0, 0, 0, 0, 83.1, 0, 79.8, 0, 0, 75.2, 0, 0, 0, 0, 0],
      color: '#0277bd',
    },
    {
      datasetId: 'ds-science-003',
      datasetName: '科研伦理评估',
      values: [0, 0, 0, 0, 0, 0, 86.2, 0, 0, 0, 0, 0, 0, 87.8, 0, 0, 0],
      color: '#5c6bc0',
    },
    {
      datasetId: 'ds-culture-003',
      datasetName: '宗教文化敏感',
      values: [0, 0, 0, 79.8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 81.2, 76.3, 0],
      color: '#ad1457',
    },
  ],
}
