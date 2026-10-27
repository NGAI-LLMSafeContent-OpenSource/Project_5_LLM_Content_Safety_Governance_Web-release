/** 数字格式化（千分位） */
export function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

/** 保留指定小数位数 */
export function formatDecimal(n: number, decimals = 1): string {
  return n.toFixed(decimals)
}

/** 格式化日期 */
export function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
