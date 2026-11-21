export function createChildExitHandler({
  label,
  critical,
  isCleanupStarted,
  onCriticalExit,
  onWarning,
}) {
  return (code, signal) => {
    if (isCleanupStarted()) {
      return
    }

    const details = { label, code, signal }
    if (critical) {
      onCriticalExit(details)
      return
    }
    onWarning(details)
  }
}

export function shouldCleanupBeforeExit({
  cleanupStarted,
  ownedChildCount,
  ownsBenchmark,
}) {
  return (
    !cleanupStarted && (ownedChildCount > 0 || Boolean(ownsBenchmark))
  )
}
