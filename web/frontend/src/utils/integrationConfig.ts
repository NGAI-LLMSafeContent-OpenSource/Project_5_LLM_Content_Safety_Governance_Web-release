import {
  INTEGRATION_HOST,
  systemPorts,
  type IntegrationSystemPortId,
} from './integrationPorts.generated'
import { resolveIntegrationSystemUiUrl } from './integrationUrls'

export type IntegrationTopicId = 'topic1' | 'topic2' | 'topic3'

export type IntegrationSystemStatus = 'ready' | 'offline' | 'pending' | 'native'

export type IntegrationOpenMode = 'iframe' | 'route'

export interface IntegrationTopicMeta {
  id: IntegrationTopicId
  title: string
  subtitle: string
}

export interface IntegrationSystemItem {
  id: string
  topic: IntegrationTopicId
  title: string
  description: string
  status: IntegrationSystemStatus
  openMode: IntegrationOpenMode
  url?: string
  route?: string
}

export interface IntegrationTopicGroup extends IntegrationTopicMeta {
  systems: IntegrationSystemItem[]
}

function resolveIntegrationUrl(systemId: IntegrationSystemPortId): string {
  return resolveIntegrationSystemUiUrl(systemId, {
    integrationHost: import.meta.env.VITE_INTEGRATION_HOST,
    fallbackHost: INTEGRATION_HOST,
    topic3BenchmarkUrl: import.meta.env.VITE_TOPIC3_BENCHMARK_URL,
    systemPorts,
  })
}

function resolveIntegrationStatus(systemId: IntegrationSystemPortId): IntegrationSystemStatus {
  const entry = systemPorts[systemId]
  if (!entry) {
    return 'pending'
  }
  if (entry.integrationStatus === 'ready') {
    return 'ready'
  }
  return 'pending'
}

export const integrationTopics: IntegrationTopicMeta[] = [
  {
    id: 'topic1',
    title: '课题一',
    subtitle: '指标构建、动态评测与输入语料分析',
  },
  {
    id: 'topic2',
    title: '课题二',
    subtitle: '动态 Benchmark 与异常样本生命周期',
  },
  {
    id: 'topic3',
    title: '课题三',
    subtitle: '输出风险与多样性相关系统',
  },
]

export const integrationSystems: IntegrationSystemItem[] = [
  {
    id: 'topic1-indicator-mining',
    topic: 'topic1',
    title: '指标自动挖掘与审校',
    description: '上传政策与标准文档，通过多 Agent 挖掘候选指标，完成人工审校与指标库沉淀。',
    status: resolveIntegrationStatus('topic1-indicator-mining'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic1-indicator-mining'),
  },
  {
    id: 'topic1-evobench',
    topic: 'topic1',
    title: 'EvoBench 评估与溯因',
    description:
      '对价值评测样本执行小批量评估，展示标签、Evidence 高亮、问题定位与 DataAttribution 溯因结果。',
    status: resolveIntegrationStatus('topic1-evobench'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic1-evobench'),
  },
  {
    id: 'topic1-semantic-evaluation',
    topic: 'topic1',
    title: '语义稀缺与任务关联',
    description: '评估输入语料的语义稀缺性和任务关联度，展示总分、子维度及 Top5 高低样本解释。',
    status: resolveIntegrationStatus('topic1-semantic-evaluation'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic1-semantic-evaluation'),
  },
  {
    id: 'topic2-dynbench',
    topic: 'topic2',
    title: '动态 Benchmark 与异常样本生命周期',
    description:
      '课题二成果展示服务：DynBench 动态评测、预跑结果、CBRNE 统计与生命周期案例（UI 6201）。',
    status: resolveIntegrationStatus('topic2-dynbench'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic2-dynbench'),
  },
  {
    id: 'topic3-benchmark',
    topic: 'topic3',
    title: '风险分级分类 Benchmark',
    description: '课题三风险分级分类与标注平台（UI 6006）。',
    status: resolveIntegrationStatus('topic3-benchmark'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic3-benchmark'),
  },
  {
    id: 'topic3-compliance-edit',
    topic: 'topic3',
    title: '合规编辑工具',
    description: '输出内容合规编辑与复检工具（UI 6311，原 8080）。',
    status: resolveIntegrationStatus('topic3-compliance-edit'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic3-compliance-edit'),
  },
  {
    id: 'topic3-diversity-rewrite',
    topic: 'topic3',
    title: '文化多样性改写',
    description: '文化多样性评估与增强改写工具（UI 6321 / API 6322 / 数据 6323；原 3000/8081）。',
    status: resolveIntegrationStatus('topic3-diversity-rewrite'),
    openMode: 'iframe',
    url: resolveIntegrationUrl('topic3-diversity-rewrite'),
  },
]

export function groupIntegrationSystems(): IntegrationTopicGroup[] {
  return integrationTopics.map((topic) => ({
    ...topic,
    systems: integrationSystems.filter((system) => system.topic === topic.id),
  }))
}

export function getDefaultIntegrationSystem(): IntegrationSystemItem | null {
  return integrationSystems[0] ?? null
}

export function getIntegrationSystemById(id: string): IntegrationSystemItem | null {
  return integrationSystems.find((system) => system.id === id) ?? null
}
