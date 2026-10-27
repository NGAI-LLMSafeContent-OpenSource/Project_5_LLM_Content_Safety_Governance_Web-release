import type { DataInputTrack } from '@/utils/dataInputConfig'
import type { StandardItem } from '@/stores/standard'
import type {
  InputAssessmentRow,
  InputFixItem,
  InputScienceStandard,
  InputStatItem,
} from '@/utils/inputMockData'

export interface DatasetFormPayload {
  name: string
  domain: string
  volume: string
  description: string
}

export interface UploadedFilePayload {
  name: string
  size: number
  type: string
}

export interface InputTrackThresholdPayload {
  value?: {
    excellent: number
    good: number
  }
  risk?: {
    high: number
    medium: number
    low: number
  }
}

export interface InputTrackPayload {
  track: DataInputTrack
  selectedStandardIds: string[]
  selectedScienceStandardIds: string[]
  customRules: string[]
  thresholds: InputTrackThresholdPayload
  assessmentStats: InputStatItem[]
  assessmentRows: InputAssessmentRow[]
  correctionItems: InputFixItem[]
}

export interface DataInputWorkflowPayload {
  dataset: DatasetFormPayload
  uploadedFiles: UploadedFilePayload[]
  uploadedCorpusTrack: DataInputTrack | null
  selectedLineageNodeId: string
  lineageNodeIds: string[]
  tracks: Record<DataInputTrack, InputTrackPayload>
}

export interface UploadedDatasetFileInput {
  file: File
}

export interface BuildDataInputWorkflowPayloadOptions {
  datasetForm: { name: string; domain: string; volume: string; desc: string }
  customCorpusTrack: DataInputTrack
  uploadedFiles: UploadedDatasetFileInput[]
  selectedLineageNodeId: string
  lineageNodes: Array<{ id: string }>
  valueStandards: StandardItem[]
  riskStandards: StandardItem[]
  valueScienceStandards: InputScienceStandard[]
  riskScienceStandards: InputScienceStandard[]
  valueCustomRules: string[]
  riskCustomRules: string[]
  valueThresholdExcellent: string
  valueThresholdGood: string
  riskThresholdHigh: string
  riskThresholdMid: string
  riskThresholdLow: string
  valueAssessmentStats: InputStatItem[]
  riskAssessmentStats: InputStatItem[]
  valueAssessmentRows: InputAssessmentRow[]
  riskAssessmentRows: InputAssessmentRow[]
  valueFixes: InputFixItem[]
  riskFixes: InputFixItem[]
}

export function buildDataInputWorkflowPayload(
  options: BuildDataInputWorkflowPayloadOptions,
): DataInputWorkflowPayload {
  return {
    dataset: {
      name: options.datasetForm.name.trim(),
      domain: options.datasetForm.domain,
      volume: options.datasetForm.volume,
      description: options.datasetForm.desc.trim(),
    },
    uploadedFiles: options.uploadedFiles.map((item) => ({
      name: item.file.name,
      size: item.file.size,
      type: item.file.type,
    })),
    uploadedCorpusTrack: options.uploadedFiles.length > 0 ? options.customCorpusTrack : null,
    selectedLineageNodeId: options.selectedLineageNodeId,
    lineageNodeIds: options.lineageNodes.map((node) => node.id),
    tracks: {
      value: buildTrackPayload({
        track: 'value',
        standards: options.valueStandards,
        scienceStandards: options.valueScienceStandards,
        customRules: options.valueCustomRules,
        thresholds: {
          value: {
            excellent: toNumber(options.valueThresholdExcellent),
            good: toNumber(options.valueThresholdGood),
          },
        },
        assessmentStats: options.valueAssessmentStats,
        assessmentRows: options.valueAssessmentRows,
        correctionItems: options.valueFixes,
      }),
      risk: buildTrackPayload({
        track: 'risk',
        standards: options.riskStandards,
        scienceStandards: options.riskScienceStandards,
        customRules: options.riskCustomRules,
        thresholds: {
          risk: {
            high: toNumber(options.riskThresholdHigh),
            medium: toNumber(options.riskThresholdMid),
            low: toNumber(options.riskThresholdLow),
          },
        },
        assessmentStats: options.riskAssessmentStats,
        assessmentRows: options.riskAssessmentRows,
        correctionItems: options.riskFixes,
      }),
    },
  }
}

function buildTrackPayload(options: {
  track: DataInputTrack
  standards: StandardItem[]
  scienceStandards: InputScienceStandard[]
  customRules: string[]
  thresholds: InputTrackThresholdPayload
  assessmentStats: InputStatItem[]
  assessmentRows: InputAssessmentRow[]
  correctionItems: InputFixItem[]
}): InputTrackPayload {
  return {
    track: options.track,
    selectedStandardIds: options.standards.filter((item) => item.enabled).map((item) => item.id),
    selectedScienceStandardIds: options.scienceStandards
      .filter((item) => item.enabled)
      .map((item) => item.id),
    customRules: options.customRules,
    thresholds: options.thresholds,
    assessmentStats: options.assessmentStats,
    assessmentRows: options.assessmentRows,
    correctionItems: options.correctionItems,
  }
}

function toNumber(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}
