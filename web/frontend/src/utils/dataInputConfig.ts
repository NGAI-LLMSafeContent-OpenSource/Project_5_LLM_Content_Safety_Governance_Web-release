export type DataInputTrack = 'value' | 'risk'

export interface DatasetFormModel {
  name: string
  domain: string
  volume: string
  desc: string
}

export interface DataInputSelectOption {
  label: string
  value: string
}

export interface ScreeningStandardViewModel {
  id: string
  name: string
  desc: string
  tag: string
  enabled: boolean
  /** Lightweight expand panel fields */
  detailKind?: string
  coverageText?: string
  sourceText?: string
  roleText?: string
  l1Code?: string
  rawName?: string
  /** UI: parent L1 unchecked */
  disabled?: boolean
  groupLabel?: string
}

export const valueTrackStepLabels: Record<number, string> = {
  3: '治理标准体系',
  4: '评估',
  5: '归因',
  6: '修正',
}

export const riskTrackStepLabels: Record<number, string> = {
  3: '治理标准体系',
  4: '评估',
  5: '归因',
  6: '修正',
}

export const nextDataInputStepButtonLabels: Record<number, string> = {
  1: '进入血缘图谱生成',
  2: '进入治理标准体系',
  3: '进入评估',
  4: '进入归因',
  5: '进入修正',
}

export const datasetSceneOptions: DataInputSelectOption[] = [
  { label: '少数民族语言', value: '少数民族语言' },
  { label: '民俗文化', value: '民俗文化' },
  { label: '宗教文化', value: '宗教文化' },
  { label: '地域文化', value: '地域文化' },
  { label: '学术论文', value: '学术论文' },
  { label: '科学实验数据', value: '科学实验数据' },
]

export const datasetVolumeOptions: DataInputSelectOption[] = [
  { label: '1-10 万条', value: '1-10 万条' },
  { label: '10 万-100 万条', value: '10 万-100 万条' },
  { label: '>100 万条', value: '>100 万条' },
]

const datasetUploadFormats = [
  {
    label: 'Word（DOCX）',
    extensions: ['.docx'],
    mimeTypes: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  },
  { label: 'PDF', extensions: ['.pdf'], mimeTypes: ['application/pdf'] },
  {
    label: 'PowerPoint',
    extensions: ['.pptx'],
    mimeTypes: ['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
  },
  {
    label: 'Excel',
    extensions: ['.xlsx'],
    mimeTypes: ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  },
  { label: 'TXT', extensions: ['.txt'], mimeTypes: ['text/plain'] },
  { label: 'Markdown', extensions: ['.md'], mimeTypes: ['text/markdown'] },
  { label: 'HTML', extensions: ['.html', '.htm'], mimeTypes: ['text/html'] },
  { label: 'JSON', extensions: ['.json'], mimeTypes: ['application/json'] },
  { label: 'CSV', extensions: ['.csv'], mimeTypes: ['text/csv', 'application/csv'] },
] as const

export const datasetUploadAccept = datasetUploadFormats
  .flatMap((format) => [...format.extensions, ...format.mimeTypes])
  .join(',')

export const datasetUploadSupportLabel = datasetUploadFormats
  .map((format) => format.label)
  .join('、')

export const datasetUploadMaxBytes = 500 * 1024 * 1024

export const datasetUploadAllowedExtensions = datasetUploadFormats.flatMap((format) => [
  ...format.extensions,
])

export const datasetUploadAllowedMimeTypes = [
  'application/octet-stream',
  ...datasetUploadFormats.flatMap((format) => [...format.mimeTypes]),
]
