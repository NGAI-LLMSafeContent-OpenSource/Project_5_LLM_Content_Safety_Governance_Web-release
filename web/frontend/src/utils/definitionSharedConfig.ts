import type { DefinitionAgentConfig, DefinitionTimelineItem } from '@/utils/definitionConfig'

export const sharedDefinitionAgents: DefinitionAgentConfig[] = [
  {
    id: 'agent-extract',
    name: '材料解析智能体',
    avatar: 'extractor',
    desc: '整理上传文档、网页链接和输入文本。',
  },
  {
    id: 'agent-match',
    name: '维度匹配智能体',
    avatar: 'generator',
    desc: '匹配一级、二级指标维度和候选路径。',
  },
  {
    id: 'agent-generate',
    name: '指标生成智能体',
    avatar: 'validator',
    desc: '生成三级候选指标并形成审核材料。',
  },
]

export const sharedDefinitionTimeline: DefinitionTimelineItem[] = [
  {
    id: 't1',
    time: '14:21:08',
    title: '材料解析智能体',
    desc: '完成依据材料和链接内容整理。',
  },
  {
    id: 't2',
    time: '14:21:26',
    title: '维度匹配智能体',
    desc: '完成指标维度和路径匹配。',
  },
  {
    id: 't3',
    time: '14:21:44',
    title: '指标生成智能体',
    desc: '生成候选指标并映射到层级结构。',
  },
]
