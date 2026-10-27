export function resolveTopic3BenchmarkUrl(
  configuredUrl: string | undefined,
  fallbackUrl: string,
): string {
  return configuredUrl?.trim() || fallbackUrl
}

export function resolveIntegrationHost(
  configuredHost: string | undefined,
  fallbackHost: string,
): string {
  const normalizedHost = configuredHost?.trim()
  if (!normalizedHost) {
    return fallbackHost
  }
  if (
    normalizedHost.includes('://') ||
    normalizedHost.includes('/') ||
    normalizedHost.includes(':')
  ) {
    return fallbackHost
  }
  return normalizedHost
}

export interface IntegrationSystemUiPortEntry {
  ui: number
}

export interface ResolveIntegrationSystemUiUrlOptions {
  integrationHost?: string
  fallbackHost: string
  topic3BenchmarkUrl?: string
  systemPorts: Record<string, IntegrationSystemUiPortEntry>
}

export function resolveIntegrationSystemUiUrl(
  systemId: string,
  options: ResolveIntegrationSystemUiUrlOptions,
): string {
  const entry = options.systemPorts[systemId]
  if (!entry) {
    throw new Error(`Unknown integration system port id: ${systemId}`)
  }

  const generatedUrl = `http://${resolveIntegrationHost(
    options.integrationHost,
    options.fallbackHost,
  )}:${entry.ui}`

  if (systemId === 'topic3-benchmark') {
    return resolveTopic3BenchmarkUrl(options.topic3BenchmarkUrl, generatedUrl)
  }

  return generatedUrl
}
