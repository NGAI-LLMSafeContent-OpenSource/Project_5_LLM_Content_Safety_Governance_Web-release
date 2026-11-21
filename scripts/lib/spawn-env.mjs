const PROXY_ENV_KEYS = [
  'ALL_PROXY',
  'HTTP_PROXY',
  'HTTPS_PROXY',
  'all_proxy',
  'http_proxy',
  'https_proxy',
]

const LOCAL_NO_PROXY_HOSTS = ['127.0.0.1', 'localhost', '::1']

function splitNoProxy(value) {
  if (typeof value !== 'string' || !value.trim()) {
    return []
  }
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function mergeNoProxy(...values) {
  const seen = new Set()
  const merged = []
  for (const value of values) {
    for (const host of splitNoProxy(value)) {
      const key = host.toLowerCase()
      if (seen.has(key)) {
        continue
      }
      seen.add(key)
      merged.push(host)
    }
  }
  return merged.join(',')
}

/**
 * Strip system HTTP(S)/SOCKS proxy vars and ensure localhost bypass.
 * Used so platform children always reach 127.0.0.1 upstreams directly.
 */
export function sanitizeProxyEnv(env) {
  const next = { ...env }
  let stripped = false
  for (const key of PROXY_ENV_KEYS) {
    if (key in next) {
      delete next[key]
      stripped = true
    }
  }

  const noProxy = mergeNoProxy(
    next.NO_PROXY,
    next.no_proxy,
    LOCAL_NO_PROXY_HOSTS.join(','),
  )
  next.NO_PROXY = noProxy
  next.no_proxy = noProxy

  return {
    env: next,
    stripped,
    noProxySet: Boolean(noProxy),
  }
}

export function buildSpawnEnv(baseEnv, extraEnv = {}, options = {}) {
  const merged = options.exactEnv
    ? { ...extraEnv }
    : { ...baseEnv, ...extraEnv }
  return sanitizeProxyEnv(merged).env
}

export function describeProxySanitize(baseEnv = process.env) {
  const { stripped, noProxySet } = sanitizeProxyEnv({ ...baseEnv })
  return { stripped, noProxySet }
}
