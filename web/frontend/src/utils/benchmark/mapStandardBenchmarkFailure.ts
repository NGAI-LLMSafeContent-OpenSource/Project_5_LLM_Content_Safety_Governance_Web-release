export type StandardFailureKind = 'timeout' | 'unavailable' | 'invalid_params' | 'unknown'

const TIMEOUT_RE = /timeout|timed?\s*out|etimedout|econnaborted|超时/i
const UNAVAILABLE_RE =
  /network|econnrefused|enotfound|econnreset|502|503|504|upstream|offline|disconnect|connection refused|连接中断|连接失败|不可用|服务暂/i
const INVALID_RE =
  /invalid|validation|422|unprocessable|参数|must |请填写|请至少|请选择|请先|样本预算|不能超过|民族/i

/** Messages already authored for the standard UI — show as-is. */
function isFriendlyUiMessage(text: string): boolean {
  return (
    text.startsWith('请') ||
    text.includes('样本预算') ||
    text.includes('不能超过') ||
    text.startsWith('生成超时') ||
    text.startsWith('生成服务暂时不可用') ||
    text.startsWith('参数无效') ||
    text.startsWith('生成未完成') ||
    text.startsWith('当前主题') ||
    text.includes('未能生成样本') ||
    text.includes('未在 Project_3 配置') ||
    text.includes('framework 目录不存在') ||
    text.includes('文化语料生成脚本不存在') ||
    text.includes('质量红线未通过') ||
    text.includes('动态风险') ||
    text.includes('TOPIC3_RISK')
  )
}

export function classifyStandardBenchmarkFailure(raw: string): StandardFailureKind {
  const text = raw.trim()
  if (!text) {
    return 'unknown'
  }
  if (TIMEOUT_RE.test(text)) {
    return 'timeout'
  }
  if (UNAVAILABLE_RE.test(text)) {
    return 'unavailable'
  }
  if (INVALID_RE.test(text)) {
    return 'invalid_params'
  }
  return 'unknown'
}

/** Retrieval implementation terms must never reach the standard UI. */
const RETRIEVAL_IMPL_TERM_RE = /local_corpus|online_baike|corpus_jsonl|切换 online|本地 corpus/i

const RETRIEVAL_IMPL_FALLBACK =
  '当前主题暂时无法生成样本。请换一个资料更完整的主题后重试，或反馈任务 ID'

export function sanitizeFailureBrief(raw: string): string {
  const firstLine = raw.split(/\r?\n/)[0] ?? ''
  return firstLine
    .replace(/\b[a-f0-9]{32,}\b/gi, '')
    .replace(/traceback.*/i, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120)
}

/**
 * Map raw create/poll/task errors to short user-facing copy for standard mode.
 * Does not leak SHA / traceback dumps into the primary message.
 * Scrubs retrieval impl terms before any friendly early-return.
 */
export function mapStandardBenchmarkFailure(raw: string | null | undefined): string {
  const trimmed = (raw || '').trim()
  if (!trimmed) {
    return '生成未完成，请重试或反馈任务 ID'
  }
  if (RETRIEVAL_IMPL_TERM_RE.test(trimmed)) {
    return RETRIEVAL_IMPL_FALLBACK
  }
  if (isFriendlyUiMessage(trimmed)) {
    return sanitizeFailureBrief(trimmed) || '生成未完成，请重试或反馈任务 ID'
  }

  if (/公开资料不足|未能生成样本|0 complete groups/i.test(trimmed)) {
    return sanitizeFailureBrief(trimmed) || '当前主题公开资料不足，请换主题后重试'
  }

  if (/implicit_redline|quality_report failed/i.test(trimmed)) {
    return '质量红线未通过，可改「低难度为主」重试或反馈任务 ID'
  }

  const kind = classifyStandardBenchmarkFailure(trimmed)
  if (kind === 'timeout') {
    return '生成超时，请重试；仍失败请反馈任务 ID'
  }
  if (kind === 'unavailable') {
    return '生成服务暂时不可用，请稍后重试'
  }
  if (kind === 'invalid_params') {
    const brief = sanitizeFailureBrief(trimmed)
    return brief ? `参数无效：${brief}` : '参数无效，请检查配置后重试'
  }

  return '生成未完成，请重试或反馈任务 ID'
}
