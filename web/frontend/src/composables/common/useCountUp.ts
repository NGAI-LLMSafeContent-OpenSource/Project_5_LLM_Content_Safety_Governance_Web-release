import { ref, watch, onUnmounted } from 'vue'

/**
 * 数值缓动动画 — 当 target 变化时，从旧值平滑过渡到新值
 * @param target 目标值的 getter
 * @param durationMs 动画时长 (ms)
 * @returns 当前动画中间值 (ref)
 */
export function useCountUp(target: () => number, durationMs = 600) {
  const display = ref(0)
  let rafId = 0
  let startTime = 0
  let startVal = 0
  let endVal = 0

  function easeOutCubic(t: number): number {
    return 1 - Math.pow(1 - t, 3)
  }

  function step() {
    const elapsed = performance.now() - startTime
    const progress = Math.min(elapsed / durationMs, 1)
    display.value = startVal + (endVal - startVal) * easeOutCubic(progress)
    if (progress < 1) {
      rafId = requestAnimationFrame(step)
    }
  }

  watch(
    target,
    (newVal) => {
      cancelAnimationFrame(rafId)
      startVal = display.value || newVal * 0.6 // 首次从较低值开始
      endVal = newVal
      startTime = performance.now()
      rafId = requestAnimationFrame(step)
    },
    { immediate: true },
  )

  onUnmounted(() => cancelAnimationFrame(rafId))

  return display
}
