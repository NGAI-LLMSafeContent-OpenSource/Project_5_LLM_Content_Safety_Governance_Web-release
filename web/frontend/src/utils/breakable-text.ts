const SEPARATORS = new Set(['_', '/', '·'])

/** Split after `_`, `/`, and `·` so long identifiers wrap at separators. */
export function splitAfterSeparators(value: string): string[] {
  if (value.length === 0) return ['']
  const parts: string[] = []
  let current = ''
  for (const char of value) {
    current += char
    if (SEPARATORS.has(char)) {
      parts.push(current)
      current = ''
    }
  }
  if (current) parts.push(current)
  return parts
}
