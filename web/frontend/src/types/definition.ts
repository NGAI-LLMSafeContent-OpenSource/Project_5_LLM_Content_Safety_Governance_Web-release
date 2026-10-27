import type {
  CandidateIndicator,
  MiningTaskArtifact,
  MiningTaskLog,
  MiningTaskStats,
  MiningTaskStatus,
  MiningTaskSummary,
  ParsedSourceDocument,
} from '@/api/definition'
import type { DefinitionBranch } from '@/utils/definitionConfig'

export interface DefinitionFormState {
  uploadedDocuments: ParsedSourceDocument[]
  webLinksText: string
  miningDemand: string
}

export interface DefinitionMiningState {
  taskId: string
  inputId: number | null
  status: MiningTaskStatus | 'idle'
  loading: boolean
  timedOut: boolean
  error: string
  stats: MiningTaskStats
  progress: number
  logs: MiningTaskLog[]
  artifacts: MiningTaskArtifact[]
  candidates: CandidateIndicator[]
  finishedAt: string
  createdAt: string
  savedToHistory: boolean
  historyTitle: string
  history: MiningTaskSummary[]
  historyLoading: boolean
  historyError: string
}

export interface DefinitionHistoryViewerState {
  open: boolean
  loading: boolean
  error: string
  taskId: string
  title: string
  subtitle: string
  rootTitle: string
  branches: DefinitionBranch[]
}
