export const metricNotes = [
  {
    name: '数据权重 / 价值档位判别准确率',
    desc: '模型或算法判断 high / medium / low 档位的准确性，正式跑分待课题一提供 baseline 结果后导入。',
  },
  {
    name: '档位一致率',
    desc: '复判档位与原始档位一致的比例，当前可由 Data_predictions.jsonl 支撑展示。',
  },
  {
    name: 'low 问题定位',
    desc: '对低质量回答或问题回答返回问题片段、问题类型和原因的能力。',
  },
  {
    name: '问题类型识别覆盖',
    desc: '复判问题类型覆盖 harmful_content、factual_error、cultural_distortion 等类别的情况。',
  },
  {
    name: '溯因可解释性',
    desc: '是否能给出可读的问题片段和原因说明，支撑专家查看样本级证据。',
  },
]

export const benchmarkValueItems = [
  {
    title: '指标体系定制',
    desc: '围绕主流价值、民族语言、国内标准和项目任务书指标构建，补足公开 Benchmark 覆盖不足的问题。',
  },
  {
    title: '动态生成机制',
    desc: '通过 Agent 配置动态生成评测样本，降低固定题库被针对性优化或过拟合的风险。',
  },
  {
    title: '可交付评测流程',
    desc: '方法、配置、资产和指标均可记录，后续可交由浦江侧复跑、检查和扩展。',
  },
]

export const sampleEntryItems = [
  { title: '复判一致样本', desc: '查看原始档位与复判档位一致的高 / 中 / 低三档样本。' },
  { title: '复判不一致样本', desc: '查看复判档位与原始档位不一致的样本，可在抽屉中按样本核验。' },
  { title: 'low 问题样本', desc: '查看 low 档或有 issues 的回答，理解问题片段和原因。' },
  {
    title: '问题类型代表样本',
    desc: '关注 harmful_content、factual_error、cultural_distortion 等类型。',
  },
]

export const baselineRows = [
  {
    name: '本项目复判 Agent',
    type: 'project',
    score: '待确认',
    status: '已有复判证据',
    note: '当前仅展示复判档位一致率，不包装为正式跑分。',
    width: '62%',
  },
  {
    name: 'baseline-1',
    type: 'baseline',
    score: '待导入',
    status: '待课题一提供',
    note: '现有可做数据权重评价的方法。',
    width: '42%',
  },
  {
    name: 'baseline-2',
    type: 'baseline',
    score: '待导入',
    status: '待课题一提供',
    note: '现有 SOTA 或传统方法。',
    width: '36%',
  },
  {
    name: '主流大模型',
    type: 'LLM',
    score: '待导入',
    status: '待课题一提供',
    note: 'DeepSeek / Qwen / GLM 等候选。',
    width: '48%',
  },
]
