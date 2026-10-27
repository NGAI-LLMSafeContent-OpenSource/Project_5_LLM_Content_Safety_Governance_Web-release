import { OutputTrack, type DataAsset } from '@/types'

/**
 * Step 1 里保留的历史演示数据集。
 * 课题三风险分级分类资产的版本、条数和结果文件不在这里写死，
 * 风险页通过同版本接口读取服务端选中的资产。
 */
export const staticEvaluableDatasets: DataAsset[] = [
  {
    id: 'seed_v4_multilabel',
    name: 'seed-v4 多标签评测集',
    assetState: 'evaluable',
    scenario: '风险内容',
    source: 'Benchmark',
    track: OutputTrack.RISK,
    description:
      'Benchmark 综合风险分类数据集，已有静态结果，可进入 Step 2 taxonomy 筛选并在 Step 3 展示多标签指标。',
    datasetId: 'seed_v4_multilabel',
    task: 'multilabel_then_severity',
    modelId: 'qwen3.5-9b',
    sampleCount: 1947,
    resultVersion: 'seed-v4-20260617-152249',
    runName: 'qwen3_5_9b_multilabel_then_severity_seed_v4_20260617_152249',
    language: '中 / 英 / 多民族语言',
    hasStaticResult: true,
    canDynamicEval: true,
  },
  {
    id: 'seed_v3_multilabel',
    name: 'seed-v3 多标签评测集',
    assetState: 'evaluable',
    scenario: '风险内容',
    source: 'Benchmark',
    track: OutputTrack.RISK,
    description: 'Benchmark 综合风险分类数据集，已有静态结果。',
    datasetId: 'seed_v3_multilabel',
    task: 'multilabel_then_severity',
    modelId: 'qwen3.5-9b',
    sampleCount: 1680,
    resultVersion: 'seed-v3-20260610-091532',
    runName: 'qwen3_5_9b_multilabel_then_severity_seed_v3_20260610_091532',
    language: '中 / 英',
    hasStaticResult: true,
    canDynamicEval: false,
  },
  {
    id: 'seed_v2_multilabel',
    name: 'seed-v2 多标签评测集',
    assetState: 'evaluable',
    scenario: '风险内容',
    source: 'Benchmark',
    track: OutputTrack.RISK,
    description: 'Benchmark 综合风险分类数据集，已有静态结果。',
    datasetId: 'seed_v2_multilabel',
    task: 'multilabel_then_severity',
    modelId: 'bingoguard-local',
    sampleCount: 1200,
    resultVersion: 'seed-v2-20260520-184400',
    runName: 'bingoguard_local_multilabel_then_severity_seed_v2_20260520_184400',
    language: '中文',
    hasStaticResult: true,
    canDynamicEval: false,
  },
  {
    id: 'seed_v1_1_response_en',
    name: 'seed-v1.1 多语言评测集',
    assetState: 'evaluable',
    scenario: '风险内容',
    source: 'Benchmark',
    track: OutputTrack.RISK,
    description: 'Benchmark 风险内容数据集，可用于 binary_then_severity 展示。',
    datasetId: 'seed_v1_1_response_en',
    task: 'binary_then_severity',
    modelId: 'bingoguard-local',
    sampleCount: 890,
    resultVersion: 'seed-v1.1-20260401-120000',
    runName: 'bingoguard_local_seed_v1_1_20260401_120000',
    language: '中 / 英 / 多民族语言',
    hasStaticResult: false,
    canDynamicEval: true,
  },
  {
    id: 'binary_response_hist',
    name: 'binary_response 历史结果',
    assetState: 'evaluable',
    scenario: '通用安全基线',
    source: 'Benchmark',
    track: OutputTrack.RISK,
    description: '历史二分类评测快照。',
    datasetId: 'binary_response_hist',
    task: 'binary',
    modelId: 'qwen3.5-9b',
    sampleCount: 560,
    resultVersion: 'binary-h20260401',
    runName: 'qwen3_5_9b_binary_historical_20260401',
    language: '英文',
    hasStaticResult: false,
    canDynamicEval: false,
  },
]

/**
 * Step 1 静态数据资产 — 待映射资产 + 待导入数据源。
 * 这些资产当前无后端接口，待后续接入后替换为 API 调用。
 */
export const staticMappedAssets: DataAsset[] = [
  {
    id: 'project3_culture_db',
    name: 'Cultural Gen 动态文化样本集',
    assetState: 'mapped',
    scenario: '文化多样性内容',
    source: 'Project3:Cultural_Generation_Tool /api/samples',
    track: OutputTrack.DIVERSITY,
    selectable: true,
    description:
      '来源 Project_3_Cultural_Generation_Tool /api/samples。服务启动后可作为动态文化样本集进入多样性轨道，展示文化适配、语义质量和完整度三维评分；不进入风险 Benchmark。',
    sampleCount: 38,
    language: '中文 · 蒙古族/藏族/维吾尔族/哈萨克族',
    existingFields: [
      'id',
      'fullQuestion',
      'expected',
      'generated',
      'cultureScore',
      'semanticScore',
      'integrityScore',
      'wrongExample',
      'fixSuggestion',
      'improveItems',
    ],
    gaps: [
      '缺少已确认的文化多样性正式指标体系，当前不应按“3 类 11 项”宣称评测结论。',
      '不含风险 gold labels，不能进入风险分类、分级与静态结果展示。',
    ],
    suggestedMapping: {
      '候选 prompt': 'fullQuestion',
      '候选 response': 'generated / wrongExample 需要讨论',
      候选参考回答: 'expected',
      建议动作: '进入多样性轨道；后续补齐正式文化评测指标映射',
    },
    suggestedAction: '进入多样性轨道',
    detailBlocks: [
      {
        title: '资产摘要',
        kv: [
          ['来源', 'Project_3_Cultural_Generation_Tool / data/db.json'],
          ['样本规模', '38 条'],
          ['民族覆盖', '蒙古族 20、藏族 5、维吾尔族 5、哈萨克族 5、其他 3'],
          ['内容类别', '饮食 17、服饰 8、礼仪 4、居住 3、其他 6'],
          ['背景类型', 'implicit 21、explicit 17'],
        ],
      },
      {
        title: '已有字段',
        tags: [
          'id',
          'fullQuestion',
          'expected',
          'generated',
          'cultureScore',
          'semanticScore',
          'integrityScore',
          'wrongExample',
          'fixSuggestion',
          'improveItems',
        ],
      },
      {
        title: '适用边界',
        gaps: [
          '缺少已确认的文化多样性正式指标体系，当前不应按“3 类 11 项”宣称评测结论。',
          '不含风险 gold labels，不能进入风险分类、分级与静态结果展示。',
        ],
      },
      {
        title: '建议映射',
        kv: [
          ['候选 prompt', 'fullQuestion'],
          ['候选 response', 'generated / wrongExample 需要讨论'],
          ['候选参考回答', 'expected'],
          ['建议动作', '进入多样性轨道；后续补齐正式文化评测指标映射'],
        ],
      },
    ],
  },
  {
    id: 'project3_cultural_corpus_runs',
    name: '文化语料生成批次集合',
    assetState: 'mapped',
    scenario: '文化多样性内容',
    source: 'Project3:Cultural_Diversity_Corpus_Generation_Tool',
    track: OutputTrack.DIVERSITY,
    selectable: true,
    description:
      '来源文化多样性语料生成工具的 runs 批次集合，包含预跑 samples.jsonl 和 Project5 实时生成批次。选择集合后可在右侧按运行批次、民族和难度筛选进入多样性轨道。',
    sampleCount: 56,
    language: '中文 · 回族/蒙古族/藏族/维吾尔族',
    existingFields: [
      'sample_id',
      'implied_ethnic_group',
      'difficulty_level',
      'background',
      'user_query',
      'cultural_knowledge_points',
      'expected_answer',
      'scoring_rubric',
      'review_result',
    ],
    gaps: [
      '输出样本未保留原始 dimension，无法可靠作为文化主题筛选字段。',
      '缺少待测模型输出及统一的文化评测指标，不能套用风险 Benchmark 指标。',
    ],
    suggestedAction: '进入多样性轨道',
    detailBlocks: [
      {
        title: '资产摘要',
        kv: [
          ['来源', 'Project_3_Cultural_Diversity_Corpus_Generation_Tool / framework/runs'],
          ['当前可读样本', '56 条，随本地 runs 刷新动态变化'],
          ['民族覆盖', '回族、蒙古族、藏族、维吾尔族'],
          ['难度覆盖', 'L1 15、L2 13、L3 13'],
        ],
      },
      {
        title: '已有字段',
        tags: [
          'sample_id',
          'implied_ethnic_group',
          'difficulty_level',
          'cultural_knowledge_points',
          'expected_answer',
          'scoring_rubric',
          'review_result',
        ],
      },
      {
        title: '接入条件',
        gaps: [
          '输出样本未保留原始 dimension，无法可靠作为文化主题筛选字段。',
          '缺少待测模型输出及统一的文化评测指标，不能套用风险 Benchmark 指标。',
        ],
      },
    ],
  },
  {
    id: 'aifsci_cbrne_asset',
    name: 'AI4Sci / CBRNE 种子数据包',
    assetState: 'mapped',
    scenario: 'AI for Science',
    source: '张岸老师提供',
    description:
      '来源为张岸老师提供的 CBRNE_data 与 lifecycle HTML。数据包较接近风险评测资产，但尚未纳入课题五仓库和 Benchmark dataset option。',
    sampleCount: 1873,
    language: '英文',
    existingFields: [
      'id',
      'record_key',
      'harm_category_L1',
      'harm_category_L2',
      'prompt',
      'label',
      'seed_type',
      'source_benchmark',
      'payload',
    ],
    gaps: [
      '需确认 CBRNE_data 是否为正式共享版本。',
      '需定义 CBRNE L1/L2 到 seed-v1.1 taxonomy 的映射规则。',
      '需确认是否导入课题三 Benchmark，生成 dataset_id、run_name 和 result_version。',
      '需确认敏感样本正文的仓库存放与展示边界。',
    ],
    suggestedMapping: {
      '候选 task': 'binary 或 binary_then_severity',
      候选标签: 'label → safe/unsafe，harm_category_L2 → 风险子类候选',
      建议动作: '先确认导入规则和 taxonomy 映射，再生成 Benchmark dataset option',
    },
    suggestedAction: '查看接入准备',
    detailBlocks: [
      {
        title: '资产摘要',
        kv: [
          ['来源', '张岸老师提供，CBRNE_data + lifecycle HTML'],
          ['全量数据', 'CBRNE_full.jsonl：1873 条'],
          ['过滤数据', 'CBRNE_filtered.jsonl：1658 条'],
          ['已有标签', 'label、harm_category_L1、harm_category_L2'],
          ['来源基准', 'WMDP、FORTRESS、PHTest、XSTest'],
        ],
      },
      {
        title: '已有字段',
        tags: [
          'id',
          'record_key',
          'harm_category_L1',
          'harm_category_L2',
          'prompt',
          'label',
          'seed_type',
          'source_benchmark',
          'payload',
        ],
      },
      {
        title: '缺失字段 / 接入条件',
        gaps: [
          '需确认 CBRNE_data 是否为正式共享版本。',
          '需定义 CBRNE L1/L2 到 seed-v1.1 taxonomy 的映射规则。',
          '需确认是否导入课题三 Benchmark，生成 dataset_id、run_name 和 result_version。',
          '需确认敏感样本正文的仓库存放与展示边界。',
        ],
      },
      {
        title: '建议映射',
        kv: [
          ['候选 task', 'binary 或 binary_then_severity'],
          ['候选标签', 'label → safe/unsafe，harm_category_L2 → 风险子类候选'],
          ['建议动作', '先确认导入规则和 taxonomy 映射，再生成 Benchmark dataset option'],
        ],
      },
    ],
  },
]

export const staticImportAssets: DataAsset[] = [
  {
    id: 'aifsci_lifecycle_source',
    name: 'AI4Sci lifecycle 典型 case 材料',
    assetState: 'import',
    scenario: 'AI for Science',
    source: '张岸老师提供',
    description:
      '来源为张岸老师提供的两个 lifecycle HTML。它们适合支撑典型 case 讨论，但当前尚未导入课题五仓库，也不应直接暴露敏感样本正文。',
    sampleCount: 2,
    language: 'HTML',
    gaps: [
      '确认 HTML 是否可进入课题五仓库，或只保留在受控材料目录。',
      '确认是否只展示结构摘要，不展示敏感样本正文。',
      '确认是否需要转换成 Step 1 数据源卡片，还是只作为 AI4Sci/CBRNE 接入说明附件。',
    ],
    suggestedMapping: {
      短期: '在 Step 1 中作为"待导入数据源"展示来源和用途，不进入 Step 2。',
      中期: '若进入 Benchmark，需要先定义脱敏摘要、case 索引和展示字段。',
    },
    suggestedAction: '确认导入规则',
    detailBlocks: [
      {
        title: '来源摘要',
        kv: [
          ['来源', '张岸老师提供'],
          [
            '文件形态',
            'case15_lifecycle_L1-1_CBRNE.html；case15_lifecycle_L1-2_Explicit_Harmful_Injection.html',
          ],
          ['主要用途', '典型漏报 / 绕过 case 生命周期材料'],
          ['结构摘要', 'seed 来源、攻击方式、多个 Moderator/guard 结果、阶段、ASR/Overrefusal'],
        ],
      },
      {
        title: '导入前置条件',
        gaps: [
          '确认 HTML 是否可进入课题五仓库，或只保留在受控材料目录。',
          '确认是否只展示结构摘要，不展示敏感样本正文。',
          '确认是否需要转换成 Step 1 数据源卡片，还是只作为 AI4Sci/CBRNE 接入说明附件。',
        ],
      },
      {
        title: '建议动作',
        kv: [
          ['短期', '在 Step 1 中作为"待导入数据源"展示来源和用途，不进入 Step 2。'],
          ['中期', '若进入 Benchmark，需要先定义脱敏摘要、case 索引和展示字段。'],
        ],
      },
    ],
  },
]

/** 合并当前可展示的静态资产（待映射 + 待导入）。 */
export const allStaticAssets: DataAsset[] = [...staticMappedAssets, ...staticImportAssets].filter(
  (asset) => !asset.id.startsWith('aifsci_'),
)
