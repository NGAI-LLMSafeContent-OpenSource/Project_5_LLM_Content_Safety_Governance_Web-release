import { recordValue } from './benchmarkLiveRunFormatters'
import type { BenchmarkArtifactItem } from '@/types'

export function getBenchmarkManifestParameters(asset: BenchmarkArtifactItem) {
  const manifest = asset.manifest
  const parameters = recordValue(manifest.parameters)
  return parameters ?? manifest
}

export function topic3TermTooltip(term: string) {
  const tooltips: Record<string, string> = {
    Interleaving:
      '表示 harmful 与 harmless 片段是否交错穿插。false 是相对顺序拼接，true 是多片段交错出现。',
    'Final Guard':
      '生成完成后的安全门禁，用于确认最终文本是否仍有可识别风险，不代表被测模型最终得分。',
    Unsafe:
      'Final Guard 明确判断最终文本包含不安全内容。对这类题库资产来说，Unsafe 通常说明 harmful 片段被保留下来了。',
    Controversial:
      'Final Guard 判断为边界或有争议样本，通常涉及敏感语义、攻防讨论上下文，或风险边界不稳定。',
    Bridge:
      'Bridge 检查片段之间是否自然接上，accepted 表示拼接被接受，advisory 表示可保留但建议关注。',
    'Bridge accepted': 'Bridge 检查通过，表示拼接自然、核心片段保留、结构符合要求。',
    'Bridge advisory': 'Bridge 检查带提醒，表示样本可保留，但衔接或边界需要人工关注。',
    Coherence: '整体连贯性检查，关注最终 edited_input 前后文是否逻辑通顺。',
    'Bridge Reason': 'Bridge 判断的解释，说明片段拼接为什么被接受或为什么需要提醒。',
    'Coherence Reason': 'Coherence 判断的解释，说明整段文本为什么被认为连贯或不连贯。',
    'Bridge Texts': '拼接时使用或识别出的过渡文字，用来连接安全背景与风险片段。',
    'Final Guard Categories': 'Final Guard 在最终文本中识别出的风险类别。',
  }
  return tooltips[term] ?? ''
}
