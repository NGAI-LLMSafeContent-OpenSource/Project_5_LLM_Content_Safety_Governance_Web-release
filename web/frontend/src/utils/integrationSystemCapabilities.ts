export interface IntegrationSystemCapabilitiesInput {
  status: 'ready' | 'offline' | 'pending' | 'native'
  openMode: 'iframe' | 'route'
  url?: string
}

export function canOpenIntegrationSystemExternally(
  system: IntegrationSystemCapabilitiesInput | null,
): boolean {
  return Boolean(system?.status === 'ready' && system.url)
}

export function canRefreshIntegrationSystem(
  system: IntegrationSystemCapabilitiesInput | null,
): boolean {
  return Boolean(system?.status === 'ready' && system.openMode === 'iframe' && system.url)
}
