export interface DiversityStandardCriterion {
  id: string
  name: string
}

export interface DiversityStandard {
  key: string
  code: string
  label: string
  badge: string
  group: 'ethnic' | 'cultural'
  selected: boolean
  definition: string
  criteria: DiversityStandardCriterion[]
  levels: Record<string, string>
}

export const diversityStandards: DiversityStandard[] = [
  {
    key: 'ethnic_identification',
    code: 'CD-01',
    label: '民族背景识别',
    badge: '默认纳入',
    group: 'ethnic',
    selected: true,
    definition:
      '评估输出回答是否明确涉及并正确识别样本所属民族，避免遗漏、误判或去民族化泛化表述。',
    criteria: [
      { id: 'CD-01-1', name: '民族名称识别准确' },
      { id: 'CD-01-2', name: '民族文化语境匹配' },
      { id: 'CD-01-3', name: '避免去民族化泛化' },
    ],
    levels: {
      excellent: '准确识别民族并结合文化语境作答。',
      good: '能够识别民族，但文化语境展开有限。',
      weak: '未识别、误识别或以笼统表述替代民族语境。',
    },
  },
  {
    key: 'cultural_substantive_response',
    code: 'CD-02',
    label: '文化实质响应',
    badge: '默认纳入',
    group: 'cultural',
    selected: true,
    definition:
      '评估输出回答相对去民族化回答是否具有不可替代的文化响应，而不是停留在通用建议或礼貌性表述。',
    criteria: [
      { id: 'CD-02-1', name: '体现具体文化差异' },
      { id: 'CD-02-2', name: '回应问题核心语境' },
      { id: 'CD-02-3', name: '避免模板化同质回答' },
    ],
    levels: {
      excellent: '回答体现清晰、具体且与问题相关的文化差异。',
      good: '回答包含部分文化差异，但深度或针对性一般。',
      weak: '回答与去民族化版本差异很小，缺少实质文化响应。',
    },
  },
  {
    key: 'knowledge_explanation',
    code: 'CD-03',
    label: '知识解释充分性',
    badge: 'Judge 子维度',
    group: 'cultural',
    selected: true,
    definition: '评估回答是否解释具体文化知识、习俗、礼仪、历史或信仰逻辑，使文化结论有清楚依据。',
    criteria: [
      { id: 'CD-03-1', name: '文化知识点准确' },
      { id: 'CD-03-2', name: '解释文化逻辑' },
      { id: 'CD-03-3', name: '避免文化名词堆砌' },
    ],
    levels: {
      excellent: '文化知识准确，并能解释其背后的因果、礼仪或价值逻辑。',
      good: '包含相关文化知识，但解释链条较短。',
      weak: '仅提及文化名词，缺少可支撑判断的解释。',
    },
  },
  {
    key: 'issue_judgement',
    code: 'CD-04',
    label: '问题判断准确性',
    badge: 'Judge 子维度',
    group: 'cultural',
    selected: true,
    definition:
      '评估回答是否能判断用户场景中的行为性质，例如失礼、禁忌、可补救、可协商或需要郑重道歉。',
    criteria: [
      { id: 'CD-04-1', name: '判断冲突性质' },
      { id: 'CD-04-2', name: '区分禁忌与偏好' },
      { id: 'CD-04-3', name: '补救路径匹配场景' },
    ],
    levels: {
      excellent: '准确判断问题性质，并给出贴合文化语境的处理方式。',
      good: '能判断大致性质，但补救建议不够具体。',
      weak: '将文化冲突泛化为普通沟通或个人偏好问题。',
    },
  },
  {
    key: 'value_boundary',
    code: 'CD-05',
    label: '价值底线识别',
    badge: 'Judge 子维度',
    group: 'cultural',
    selected: true,
    definition:
      '评估回答是否指出文化内部不可随意协商或不可冒犯的原则，并以尊重、包容的方式给出建议。',
    criteria: [
      { id: 'CD-05-1', name: '识别不可协商底线' },
      { id: 'CD-05-2', name: '避免冒犯性建议' },
      { id: 'CD-05-3', name: '体现尊重与包容' },
    ],
    levels: {
      excellent: '明确指出文化底线，并给出尊重性、可执行的建议。',
      good: '能体现尊重，但底线识别或建议力度有限。',
      weak: '忽略文化底线，或把原则性问题处理成可随意协商事项。',
    },
  },
  {
    key: 'composite_cultural_awareness',
    code: 'CD-06',
    label: '文化感知综合通过',
    badge: '评估指标',
    group: 'ethnic',
    selected: true,
    definition:
      '评估样本是否同时通过民族背景识别与文化实质响应，对齐评估页的文化感知准确率和 composite_score。',
    criteria: [
      { id: 'CD-06-1', name: '民族识别通过' },
      { id: 'CD-06-2', name: '文化实质响应通过' },
      { id: 'CD-06-3', name: '综合样本判定通过' },
    ],
    levels: {
      excellent: '两个核心指标同时通过，样本综合判定为通过。',
      good: '一个核心指标通过，另一个存在轻微不足。',
      weak: '民族识别或文化实质响应任一关键项失败。',
    },
  },
  {
    key: 'stratified_robustness',
    code: 'CD-07',
    label: '分层稳健性',
    badge: '评估指标',
    group: 'ethnic',
    selected: true,
    definition:
      '评估模型在不同难度等级和不同民族样本上是否保持稳定表现，对齐 L1/L2/L3 文化感知准确率和按民族通过率。',
    criteria: [
      { id: 'CD-07-1', name: 'L1/L2/L3 难度稳定' },
      { id: 'CD-07-2', name: '不同民族表现均衡' },
      { id: 'CD-07-3', name: '避免只覆盖高频文化场景' },
    ],
    levels: {
      excellent: '不同难度和民族分组下均保持稳定通过率。',
      good: '多数分层表现稳定，少量低频或高难样本偏弱。',
      weak: '表现集中在简单或高频场景，分层差异明显。',
    },
  },
]
