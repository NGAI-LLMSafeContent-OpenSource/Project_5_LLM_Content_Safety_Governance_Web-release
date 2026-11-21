export async function isHttpOk(url, fetchImpl = fetch) {
  try {
    const response = await fetchImpl(url, {
      signal: AbortSignal.timeout(1500),
    })
    return response.ok || (response.status >= 200 && response.status < 400)
  } catch {
    return false
  }
}

export async function waitForHttpOk(url, options = {}) {
  const attempts = options.attempts ?? 12
  const intervalMs = options.intervalMs ?? 250
  const fetchImpl = options.fetchImpl ?? fetch

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await isHttpOk(url, fetchImpl)) {
      return true
    }
    await new Promise((resolve) => {
      setTimeout(resolve, intervalMs)
    })
  }
  return false
}
