import { computed, onBeforeUnmount, onMounted, ref, watch, type WatchSource } from 'vue'

export function useRevealProgress(options?: {
  durationMs?: number
  restartOn?: WatchSource
  autoStart?: boolean
}) {
  const durationMs = options?.durationMs ?? 1200
  const revealT = ref(0)
  const isForming = computed(() => revealT.value < 0.999)
  let raf = 0
  let start = 0

  function easeOutCubic(t: number) {
    return 1 - (1 - t) ** 3
  }

  function stopReveal() {
    if (raf) {
      cancelAnimationFrame(raf)
      raf = 0
    }
  }

  function startReveal() {
    stopReveal()
    revealT.value = 0
    start = 0
    const tick = (now: number) => {
      if (!start) start = now
      const raw = Math.min(1, (now - start) / durationMs)
      revealT.value = easeOutCubic(raw)
      if (raw < 1) {
        raf = requestAnimationFrame(tick)
        return
      }
      revealT.value = 1
      raf = 0
    }
    raf = requestAnimationFrame(tick)
  }

  if (options?.autoStart !== false) {
    onMounted(() => {
      startReveal()
    })
  }

  if (options?.restartOn) {
    watch(options.restartOn, () => {
      startReveal()
    })
  }

  onBeforeUnmount(() => {
    stopReveal()
  })

  return { revealT, isForming, startReveal, stopReveal }
}

export function scaleInt(value: number, t: number) {
  return Math.round(value * t)
}

export function scalePctText(ratio: number, t: number) {
  return `${Math.round(Math.min(Math.max(ratio * 100 * t, 0), 100))}%`
}

export function scalePctWidth(ratio: number, t: number) {
  return `${Math.min(Math.max(ratio * 100 * t, 0), 100)}%`
}
