import type { DiversityDimension, RiskDimension } from '@/types'
import { RiskLevel } from '@/types'

// ============================================================
// 多样性维度 Mock 数据 (Step 2 Diversity)
// ============================================================

export const mockDiversityDimensions: DiversityDimension[] = [
  { key: 'div_open_science', label: '开放科学与可复现', category: 'ai4sci', selected: true },
  { key: 'div_method_rigor', label: '方法严谨性', category: 'ai4sci', selected: true },
  { key: 'div_ethics_positive', label: '科研伦理正向引导', category: 'ai4sci', selected: true },
  { key: 'div_literacy', label: '科学传播准确性', category: 'ai4sci', selected: false },
  { key: 'div_inclusion', label: '文化包容与尊重', category: 'culture', selected: true },
  { key: 'div_representation', label: '代表性与覆盖面', category: 'culture', selected: true },
  { key: 'div_heritage', label: '非遗文化传承', category: 'culture', selected: true },
  { key: 'div_accuracy_neutral', label: '事实客观表述', category: 'culture', selected: false },
]

// ============================================================
// 风险维度 Mock 数据 (Step 2 Risk)
// ============================================================

export const mockRiskDimensions: RiskDimension[] = [
  {
    key: 'C01',
    code: 'C01',
    label: '煽动颠覆国家政权、推翻社会主义制度',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C02',
    code: 'C02',
    label: '危害国家安全和利益、损害国家形象',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C03',
    code: 'C03',
    label: '煽动分裂国家、破坏国家统一和社会稳定',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C04',
    code: 'C04',
    label: '宣扬恐怖主义、极端主义',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C05',
    code: 'C05',
    label: '宣扬民族仇恨',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C06',
    code: 'C06',
    label: '宣扬暴力、淫秽色情',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: true,
  },
  {
    key: 'C07',
    code: 'C07',
    label: '传播虚假有害信息',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: true,
  },
  {
    key: 'C08',
    code: 'C08',
    label: '歧视性内容',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: true,
  },
  {
    key: 'C09',
    code: 'C09',
    label: '商业违法违规',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: true,
  },
  {
    key: 'C10',
    code: 'C10',
    label: '侵犯他人权益',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: false,
  },
  {
    key: 'C11',
    code: 'C11',
    label: '无法满足特定服务类型的安全需求',
    category: 'ai4sci',
    level: RiskLevel.LOW,
    selected: false,
  },
  {
    key: 'C12',
    code: 'C12',
    label: '经济损失高风险的活动',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: false,
  },
  {
    key: 'C13',
    code: 'C13',
    label: '未成年人安全',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C14',
    code: 'C14',
    label: '从事欺诈、虐待或掠夺性行为',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: false,
  },
  {
    key: 'C15',
    code: 'C15',
    label: '不正确民族叙事',
    category: 'ai4sci',
    level: RiskLevel.HIGH,
    selected: true,
  },
  {
    key: 'C16',
    code: 'C16',
    label: '民族情感商业化、功利化、娱乐化',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: false,
  },
  {
    key: 'C17',
    code: 'C17',
    label: '价值导向偏差',
    category: 'ai4sci',
    level: RiskLevel.MEDIUM,
    selected: false,
  },
]
