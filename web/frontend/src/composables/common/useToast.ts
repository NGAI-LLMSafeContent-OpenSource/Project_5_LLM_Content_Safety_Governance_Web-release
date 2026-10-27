import { ElMessage } from 'element-plus'
import type { ToastType } from '@/types'

/**
 * 全局 Toast 通知 — Element Plus 薄封装。
 * 底层使用 ElMessage，保证与项目 UI 库风格一致。
 */
export function useToast() {
  function show(type: ToastType, title: string, message?: string) {
    const text = message ? `${title}：${message}` : title
    ElMessage({ type, message: text, duration: 3000 })
  }

  function success(title: string, message?: string) {
    show('success', title, message)
  }
  function error(title: string, message?: string) {
    show('error', title, message)
  }
  function warning(title: string, message?: string) {
    show('warning', title, message)
  }
  function info(title: string, message?: string) {
    show('info', title, message)
  }

  return { show, success, error, warning, info }
}
