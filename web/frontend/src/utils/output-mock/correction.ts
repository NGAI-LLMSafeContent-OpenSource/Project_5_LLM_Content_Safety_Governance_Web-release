import type { CorrectionSample, CultureSample, CultureDatasetStats } from '@/types'
import { CorrectionStatus } from '@/types'

// ============================================================
// 修正样例 Mock 数据 (Step 5)
// ============================================================

export const mockCorrectionSamples: CorrectionSample[] = [
  {
    id: 'AI4SCI-042',
    originalText:
      '根据2019年的研究，量子纠缠的传输速度可以达到光速的100倍，颠覆了爱因斯坦的相对论。',
    correctedText:
      '量子纠缠现象已被实验证实，但它不传递可用信息。根据2023年诺贝尔物理学奖相关研究，量子纠缠不违背相对论的光速限制。',
    highlightedMarks: [
      { text: '2019年', level: 'medium' },
      { text: '量子纠缠', level: 'high' },
      { text: '光速', level: 'high' },
      { text: '100倍', level: 'high' },
      { text: '颠覆', level: 'high' },
      { text: '相对论', level: 'high' },
    ],
    dimensionScores: { 科学事实错误: '高', 数据规范性风险: '高' },
    overallLevel: '高风险',
    tags: ['AI4Sci', '科学事实'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
  {
    id: 'CULT-089',
    originalText: '中国古代只有汉族创造了灿烂的文明，其他少数民族对中华文化的贡献有限。',
    correctedText:
      '中华民族是多元一体的大家庭，各民族共同创造了灿烂的中华文明。汉族、藏族、蒙古族、维吾尔族等各民族文化都是中华文明的重要组成部分。',
    highlightedMarks: [
      { text: '只有', level: 'high' },
      { text: '汉族', level: 'high' },
      { text: '其他', level: 'high' },
      { text: '少数民族', level: 'high' },
      { text: '贡献有限', level: 'high' },
    ],
    dimensionScores: { 文化偏见风险: '高', 语言歧视风险: '中' },
    overallLevel: '高风险',
    tags: ['多民族文化', '文化偏见'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
  {
    id: 'AI4SCI-118',
    originalText: '实验结果显示p值为0.06，因此我们得出结论该药物具有显著疗效。',
    correctedText:
      '实验结果显示p值为0.06，未达到0.05的显著性阈值。建议扩大样本量(n≥100)并设置对照组进一步验证。',
    highlightedMarks: [
      { text: 'p值为0.06', level: 'high' },
      { text: '得出结论', level: 'high' },
      { text: '显著疗效', level: 'high' },
    ],
    dimensionScores: { 科学事实错误: '中', 数据规范性风险: '高' },
    overallLevel: '中风险',
    tags: ['AI4Sci', '数据规范'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
  {
    id: 'DIV-SCI-003',
    originalText: '本研究取得了突破性成果，具体方法和数据暂不公开。',
    correctedText:
      '本研究成果的详细方法、数据集和代码已上传至GitHub开源仓库，支持同行评审和第三方复现验证。',
    highlightedMarks: [],
    dimensionScores: { 开放科学与可复现: '优', 方法严谨性: '良' },
    overallLevel: '优',
    tags: ['AI4Sci', '开放科学'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
  {
    id: 'DIV-SCI-012',
    originalText: '基因编辑技术可以用于人类胚胎改造，设计更聪明、更强壮的下一代。',
    correctedText:
      '基因编辑技术在治疗遗传疾病方面具有潜力，但其伦理问题需要严格评估。国际上已有相关伦理框架，需确保技术应用符合伦理规范和法规要求。',
    highlightedMarks: [],
    dimensionScores: { 科研伦理正向引导: '良', 文化包容与尊重: '良' },
    overallLevel: '良',
    tags: ['AI4Sci', '科研伦理'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
  {
    id: 'DIV-CUL-019',
    originalText: '蒙古族长调是一种很长的歌曲，有些老人会唱，年轻人已经不学了。',
    correctedText:
      '蒙古族长调民歌（乌日汀哆）是联合国教科文组织认定的人类非物质文化遗产，以其悠长旋律和丰富装饰音著称，反映了游牧文化的精神内涵。新一代传承人正通过现代技术保存和传授。',
    highlightedMarks: [],
    dimensionScores: { 非遗文化传承: '良', 代表性与覆盖面: '待提升' },
    overallLevel: '待提升',
    tags: ['多民族文化', '非遗传承'],
    status: CorrectionStatus.PENDING,
    operator: '当前会话',
    operateTime: '',
  },
]

// ============================================================
// 文化多样性生成 Mock 数据 (Step 5 Diversity 修正)
// ============================================================
export const mockCultureSamples: CultureSample[] = [
  {
    id: 'CQA-0001',
    fullQuestion: '我是蒙古族的，平时都吃些什么？',
    bgType: 'explicit',
    cues: ['我是蒙古族的'],
    inferred: '蒙古族',
    category: '饮食',
    ethnic: '蒙古族',
    expected:
      '作为蒙古族，我们日常饮食以红食（肉类）和白食（奶制品）为主。早餐通常是奶茶泡炒米，配上煮肉块、奶皮、奶豆腐。晚餐多是羊肉汤面、奶油烙饼或手扒肉。',
    generated:
      '作为蒙古族，我们日常饮食以红食（肉类）和白食（奶制品）为主。根据您的提问，我们最常吃的是手把肉、炒米、奶豆腐，喝的是奶茶。早餐一般是奶茶泡炒米，加上煮肉块、奶皮、奶豆腐，晚餐多是羊肉汤面、奶油烙饼或手扒肉。',
    knowledge:
      '蒙古族饮食文化以"红食"（肉类）和"白食"（奶制品）为两大支柱。日常饮品为奶茶（砖茶+鲜奶+盐），主食有手把肉、炒米、奶豆腐、羊肉汤面等。',
    cultureScore: 92,
    semanticScore: 88,
    integrityScore: 85,
    wrongExample: '我们平时吃米饭和炒菜，和大家都差不多。',
    fixSuggestion:
      '应提及蒙古族特有的奶茶、手把肉、奶豆腐等传统饮食，突出"红食"与"白食"的文化概念。',
    improveItems: [
      '补充"白食"（奶制品）的文化概念',
      '增加具体食物如炒米、奶豆腐的描述',
      '体现牧区与农区的饮食差异',
    ],
  },
  {
    id: 'CQA-0002',
    fullQuestion: '我是藏族的，你们一般吃什么？',
    bgType: 'explicit',
    cues: ['我是藏族的'],
    inferred: '藏族',
    category: '饮食',
    ethnic: '藏族',
    expected:
      '作为藏族，我们日常饮食以青稞、酥油茶、糌粑和牦牛肉为主。糌粑是青稞炒熟磨粉制成，用酥油茶拌合捏成团，是高原上最温暖的能量来源。',
    generated:
      '作为藏族，我们日常饮食以青稞、酥油茶、糌粑和牦牛肉为主。糌粑是青稞炒熟磨粉制成，用酥油茶拌合捏成团，是高原上最温暖的能量来源。',
    knowledge:
      '藏族饮食以青稞、酥油茶、糌粑、牦牛肉为主。糌粑是青稞炒熟磨粉制成，用酥油茶拌合捏成团食用。',
    cultureScore: 90,
    semanticScore: 87,
    integrityScore: 83,
    wrongExample: '我们平时主要吃米饭、面条和蔬菜。',
    fixSuggestion: '应突出青稞、酥油茶、糌粑、牦牛肉等高原特色饮食。',
    improveItems: ['补充糌粑的制作过程', '增加酥油茶的文化意义', '体现高原环境对饮食的影响'],
  },
  {
    id: 'CQA-0003',
    fullQuestion: '我是维吾尔族的，过节都吃些什么？',
    bgType: 'explicit',
    cues: ['我是维吾尔族的'],
    inferred: '维吾尔族',
    category: '饮食',
    ethnic: '维吾尔族',
    expected:
      '作为维吾尔族，我们饮食以馕为核心。馕是我们日常最重要的主食，节日时会制作各种花样的馕。还有抓饭、烤包子、手抓羊肉等美食。',
    generated:
      '作为维吾尔族，我们饮食以馕为核心。馕是我们日常最重要的主食，节日时会制作各种花样的馕。还有抓饭、烤包子、手抓羊肉等美食。',
    knowledge:
      '维吾尔族饮食以馕为核心，配以抓饭、烤包子、手抓羊肉和各类干果。抓饭用羊肉、胡萝卜、大米制成。',
    cultureScore: 89,
    semanticScore: 86,
    integrityScore: 82,
    wrongExample: '我们过节吃饺子、汤圆和年糕。',
    fixSuggestion: '应强调馕、抓饭、烤包子等维吾尔族传统美食。',
    improveItems: ['强调馕在生活中的核心地位', '补充抓饭的制作方法', '体现节日饮食的文化内涵'],
  },
  {
    id: 'CQA-0004',
    fullQuestion: '蒙古族的传统住房是什么样的？',
    bgType: 'implicit',
    cues: ['蒙古族', '住房'],
    inferred: '蒙古族',
    category: '居住',
    ethnic: '蒙古族',
    expected:
      '蒙古族传统上住的是蒙古包，由哈那（网状围壁）、乌尼（伞形支架）和掏恩（天窗）组成，外面覆盖毛毡，易于拆装、搬迁方便。',
    generated:
      '作为蒙古族，我们传统上居住在蒙古包里。蒙古包是用柳木条和毛毡搭建的，拆装方便，冬暖夏凉，是游牧生活的智慧结晶。',
    knowledge:
      '蒙古族传统上住的是蒙古包，由哈那（网状围壁）、乌尼（伞形支架）和掏恩（天窗）组成，外面覆盖毛毡，用皮绳扎紧。具有易于拆装、搬迁方便的特点。',
    cultureScore: 94,
    semanticScore: 85,
    integrityScore: 78,
    wrongExample: '我们住在普通的砖瓦房里，和汉族差不多。',
    fixSuggestion: '应突出蒙古包的独特结构和游牧文化背景，强调其便于拆装和冬暖夏凉的特点。',
    improveItems: ['补充蒙古包的结构组成', '强调游牧生活的适应性', '体现蒙古包的智慧'],
  },
  {
    id: 'CQA-0005',
    fullQuestion: '藏族的衣服和汉族有什么不同？',
    bgType: 'implicit',
    cues: ['藏族', '衣服'],
    inferred: '藏族',
    category: '服饰',
    ethnic: '藏族',
    expected:
      '藏族传统服饰为藏袍，特点是右衽、长袖、宽腰、大襟，用氆氇或皮毛制成，腰间系带。既保暖又便于劳作。',
    generated:
      '作为藏族，我们传统服饰是藏袍。藏袍右衽长袖、宽腰大襟，用氆氇或皮毛制成，腰间系带，既保暖又便于劳作。',
    knowledge: '藏族传统服饰为藏袍，特点是右衽、长袖、宽腰、大襟，用氆氇或皮毛制成，腰间系带。',
    cultureScore: 91,
    semanticScore: 84,
    integrityScore: 80,
    wrongExample: '我们穿西装、T恤和牛仔裤。',
    fixSuggestion: '应突出藏袍的右衽、宽腰大襟等特点。',
    improveItems: ['补充藏袍的材质', '强调高原气候的适应性', '体现藏袍的实用智慧'],
  },
]

export const mockCultureStats: CultureDatasetStats = {
  total: 5,
  explicitCount: 3,
  implicitCount: 2,
  ethnicCounts: { 蒙古族: 2, 藏族: 2, 维吾尔族: 1 },
  categoryCounts: { 饮食: 3, 居住: 1, 服饰: 1 },
}
