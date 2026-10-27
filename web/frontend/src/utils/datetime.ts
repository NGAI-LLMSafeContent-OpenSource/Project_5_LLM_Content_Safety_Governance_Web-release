const TIMEZONE_SUFFIX_RE = /(Z|[+-]\d{2}:?\d{2})$/i

export function parseApiDate(value: string): Date {
  const normalized = TIMEZONE_SUFFIX_RE.test(value) ? value : `${value}Z`
  return new Date(normalized)
}

export function formatApiDate(value?: string | null, options?: Intl.DateTimeFormatOptions) {
  if (!value) {
    return '-'
  }

  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    hour12: false,
    ...options,
  })
}
