/** Shown only when create-session or append-turn ends with no server response. */
export const GOVERNANCE_UNCERTAIN_SAVE_MESSAGE =
  '保存状态不确定。请先刷新历史确认；输入内容已保留。'

export function markGovernanceTransportError(error: Error, serverResponded: boolean): Error {
  Object.assign(error, { serverResponded })
  return error
}

function serverReturned(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { serverResponded?: unknown }).serverResponded === true
  )
}

/**
 * Use the server's explanation when a response arrived.
 * The uncertain-save sentence is only for a wait that ended with no response.
 */
export function governanceTurnFailureMessage(error: unknown): string {
  if (!serverReturned(error)) {
    return GOVERNANCE_UNCERTAIN_SAVE_MESSAGE
  }
  if (!(error instanceof Error)) return ''
  return error.message.trim()
}
