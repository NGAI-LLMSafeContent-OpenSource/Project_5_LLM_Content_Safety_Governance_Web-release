export function scrollToPageTop() {
  if (typeof window === 'undefined') return

  window.requestAnimationFrame(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  })
}
