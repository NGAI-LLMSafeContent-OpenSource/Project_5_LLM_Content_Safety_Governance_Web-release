/** Topic 2 harm_category_L1 display labels (EN -> ZH). */

const L1_NAME_ZH: Record<string, string> = {
  CBRNE: 'CBRNE（化生放核爆）',
  'Explicit Harmful Injection': '显式有害注入',
  'Implicit Bias Contamination': '隐性偏见污染',
  'Factual Misleading and Hallucination Contamination': '事实误导与幻觉污染',
}

const L1_CODE_ZH: Record<string, string> = {
  'L1-1': 'CBRNE（化生放核爆）',
  'L1-2': '显式有害注入',
  'L1-3': '隐性偏见污染',
  'L1-4': '事实误导与幻觉污染',
}

export const TOPIC2_L1_RADAR_AXES = [
  { code: 'L1-1', shortZh: '化生放核爆', fullZh: 'CBRNE（化生放核爆）' },
  { code: 'L1-2', shortZh: '显式有害注入', fullZh: '显式有害注入' },
  { code: 'L1-3', shortZh: '隐性偏见污染', fullZh: '隐性偏见污染' },
  { code: 'L1-4', shortZh: '事实误导幻觉', fullZh: '事实误导与幻觉污染' },
] as const

export function formatHarmCategoryL1(raw: string | undefined | null): string {
  const text = String(raw || '').trim()
  if (!text) return ''

  const match = text.match(/^(L1-\d+)\s*(.*)$/i)
  const code = match ? `L1-${match[1].split('-')[1]}` : ''
  const englishPart = (match ? match[2] : text).replace(/^[:：\-—]\s*/, '').trim()

  const zh = (englishPart && L1_NAME_ZH[englishPart]) || (code && L1_CODE_ZH[code]) || ''
  if (code && zh) return `${code} ${zh}`
  if (zh) return zh
  return text
}

/** Topic 2 harm_category_L2 display labels (EN -> ZH). */
const L2_NAME_ZH: Record<string, string> = {
  'B: Biological Risk': '生物风险',
  'C: Chemical Risk': '化学风险',
  'E: Explosives Risk': '爆炸物风险',
  Cybersecurity: '网络安全',
  'Fraud and Economic Harm': '欺诈与经济损害',
  'Hate, Harassment, and Abuse': '仇恨、骚扰与虐待',
  'High-Risk Professional Advice and Critical Decisions': '高风险专业建议与关键决策',
  'Legal and Rights Risks': '法律与权利风险',
  'Misinformation, Political Manipulation, and Extremism': '虚假信息、政治操纵与极端主义',
  'Sexual Content and Child Safety': '色情内容与儿童安全',
  'Violence, Self-Harm, and Physical/Environmental Harm': '暴力、自伤与人身/环境伤害',
  'Body, Age, and Health Bias': '身体、年龄与健康偏见',
  'Gender and Sexual Orientation Bias': '性别与性取向偏见',
  'Occupational, Socioeconomic, and Political Bias': '职业、社会经济与政治偏见',
  'Race, Ethnicity, and Skin Color Bias': '种族、民族与肤色偏见',
  'Religious Bias': '宗教偏见',
  'Factual Errors': '事实错误',
  Hallucination: '幻觉',
  // 兼容无字母前缀写法
  'Biological Risk': '生物风险',
  'Chemical Risk': '化学风险',
  'Explosives Risk': '爆炸物风险',
}

export function formatHarmCategoryL2(raw: string | undefined | null): string {
  const text = String(raw || '').trim()
  if (!text) return ''
  if (L2_NAME_ZH[text]) return L2_NAME_ZH[text]
  // 兼容 "B: Biological Risk" 去掉前缀后再查
  const withoutPrefix = text.replace(/^[A-Z]:\s*/, '').trim()
  if (withoutPrefix && L2_NAME_ZH[withoutPrefix]) return L2_NAME_ZH[withoutPrefix]
  return L1_NAME_ZH[text] || text
}

export function extractL1Code(raw: string | undefined | null): string {
  const text = String(raw || '').trim()
  const match = text.match(/L1-(\d+)/i)
  return match ? `L1-${match[1]}` : ''
}

export function buildTopic2L1RadarScores(
  predictions: Array<{
    is_abnormal?: boolean
    risk_category_l1?: string
    predicted_l1_id?: string
  }>,
): Record<string, number> {
  const total = Math.max(predictions.length, 1)
  const unsafeByCode: Record<string, number> = {
    'L1-1': 0,
    'L1-2': 0,
    'L1-3': 0,
    'L1-4': 0,
  }

  predictions.forEach((item) => {
    if (!item.is_abnormal) return
    const code = extractL1Code(item.risk_category_l1)
    if (code && code in unsafeByCode) unsafeByCode[code] += 1
  })

  const scores: Record<string, number> = {}
  TOPIC2_L1_RADAR_AXES.forEach((axis) => {
    scores[axis.code] = Math.min(1, unsafeByCode[axis.code] / total)
  })
  return scores
}
