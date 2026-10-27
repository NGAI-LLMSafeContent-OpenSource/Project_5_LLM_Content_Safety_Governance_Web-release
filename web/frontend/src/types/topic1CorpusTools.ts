export interface Topic1CorpusTool {
  tool_key: 'scarcity_evaluation' | 'data_denoising' | 'data_detoxification' | 'data_selection'
  display_name: string
  implementation_name: string
  purpose: string
  workflow_stage: 'assessment' | 'correction' | 'delivery'
  delivery_status: 'source_delivered' | 'pending_source_delivery'
  runtime_status: 'metadata_ready' | 'source_only' | 'blocked_missing_artifacts' | 'pending'
  execution_mode: 'metadata_only' | 'precomputed_asset' | 'remote_service' | 'unavailable'
  executable: boolean
  source_package: string
  source_sha256: string
  input_contract: string
  output_contract: string
  requirements: string[]
  blockers: string[]
  next_action: string
  metadata: Record<string, unknown>
}

export interface Topic1CorpusToolCatalogResult {
  capability: 'topic1_corpus_tool_catalog'
  available: boolean
  error_code: string
  message: string
  catalog_version: string
  source_snapshot_date: string
  tools: Topic1CorpusTool[]
}

export interface GovernanceTopic1CorpusToolCatalogPayload extends Topic1CorpusToolCatalogResult {
  capability_version: string
}
