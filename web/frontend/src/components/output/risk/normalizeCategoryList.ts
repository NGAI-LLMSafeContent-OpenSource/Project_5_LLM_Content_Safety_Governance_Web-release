/** 把标注里的风险类别收成 C01–C17 代码。推理页和风险评估共用这一处。 */
export function normalizeCategoryList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean)
  if (typeof value === 'string') {
    const matches = value.match(/C\d{2}/g)
    if (matches?.length) return [...new Set(matches)]
    return value
      .split(/[,\s，、/]+/)
      .map((item) => item.trim())
      .filter((item) => /^C\d{2}$/.test(item))
  }
  return []
}
