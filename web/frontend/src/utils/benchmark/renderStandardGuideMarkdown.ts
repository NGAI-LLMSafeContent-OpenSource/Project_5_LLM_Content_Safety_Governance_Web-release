import { Marked } from 'marked'

export const STANDARD_GUIDE_TITLE = '动态 Benchmark 标准模式使用说明'

const marked = new Marked({
  gfm: true,
  breaks: false,
})

/** Strip optional YAML frontmatter from repo-managed guide markdown. */
export function stripYamlFrontmatter(source: string): string {
  const trimmed = source.trimStart()
  if (!trimmed.startsWith('---')) {
    return source
  }

  const closingIndex = trimmed.indexOf('\n---', 3)
  if (closingIndex === -1) {
    return source
  }

  const bodyStart = trimmed.indexOf('\n', closingIndex + 4)
  if (bodyStart === -1) {
    return ''
  }

  return trimmed.slice(bodyStart + 1).trimStart()
}

export function renderStandardGuideMarkdown(source: string): string {
  const body = stripYamlFrontmatter(source)
  return marked.parse(body, { async: false })
}
