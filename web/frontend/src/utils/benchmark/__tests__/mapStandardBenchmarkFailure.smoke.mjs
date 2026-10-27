/**
 * Runnable smoke checks for standard-mode failure mapping.
 * Keep in sync with mapStandardBenchmarkFailure.ts (Vitest not wired yet).
 *
 *   node web/frontend/src/utils/benchmark/__tests__/mapStandardBenchmarkFailure.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '../mapStandardBenchmarkFailure.ts'), 'utf8')

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

function assert(condition, label) {
  if (!condition) {
    throw new Error(label)
  }
}

const scrubIdx = src.indexOf('RETRIEVAL_IMPL_TERM_RE.test(trimmed)')
const friendlyIdx = src.indexOf('isFriendlyUiMessage(trimmed)')
assert(scrubIdx >= 0, 'missing retrieval scrub gate')
assert(friendlyIdx >= 0, 'missing friendly early-return')
assert(scrubIdx < friendlyIdx, 'retrieval scrub must run before friendly early-return')

/** Mirrors mapStandardBenchmarkFailure.ts — keep in sync. */
function isFriendlyUiMessage(text) {
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

function sanitizeFailureBrief(raw) {
  const firstLine = raw.split(/\r?\n/)[0] ?? ''
  return firstLine
    .replace(/\b[a-f0-9]{32,}\b/gi, '')
    .replace(/traceback.*/i, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120)
}

const RETRIEVAL_IMPL_TERM_RE = /local_corpus|online_baike|corpus_jsonl|切换 online|本地 corpus/i
const RETRIEVAL_IMPL_FALLBACK =
  '当前主题暂时无法生成样本。请换一个资料更完整的主题后重试，或反馈任务 ID'

function mapStandardBenchmarkFailure(raw) {
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
  return '生成未完成，请重试或反馈任务 ID'
}

assertEqual(
  mapStandardBenchmarkFailure('当前主题公开资料不足，未能生成样本。原因：online_baike 检索失败。'),
  RETRIEVAL_IMPL_FALLBACK,
  'friendly prefix + online_baike must scrub',
)

assertEqual(
  mapStandardBenchmarkFailure(
    '当前主题公开资料不足，未能生成样本。原因：本地 corpus 为空；请检查 corpus_jsonl。',
  ),
  RETRIEVAL_IMPL_FALLBACK,
  'friendly prefix + corpus terms must scrub',
)

assertEqual(
  mapStandardBenchmarkFailure('当前主题公开资料不足，未能生成样本。请换主题后重试'),
  '当前主题公开资料不足，未能生成样本。请换主题后重试',
  'friendly message without impl terms passes through',
)

if (!src.includes('可改「低难度为主」重试或反馈任务 ID')) {
  throw new Error('cultural redline failure must point users to 低难度为主')
}
if (src.includes('明示为主') || src.includes('隐式背景未过质量红线')) {
  throw new Error('cultural failure copy must not use 明示 / 隐式')
}

console.log('mapStandardBenchmarkFailure smoke: ok')
