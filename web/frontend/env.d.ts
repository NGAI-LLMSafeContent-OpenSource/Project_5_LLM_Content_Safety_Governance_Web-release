/// <reference types="vite/client" />

declare module '*.md?raw' {
  const content: string
  export default content
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_HTTP_METHOD_OVERRIDE?: string
  readonly VITE_INTEGRATION_HOST?: string
  readonly VITE_TOPIC3_BENCHMARK_URL?: string
  readonly VITE_USE_MOCK: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
