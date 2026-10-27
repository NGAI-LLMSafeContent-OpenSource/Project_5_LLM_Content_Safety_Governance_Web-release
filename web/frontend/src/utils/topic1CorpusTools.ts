import type { Topic1CorpusTool } from '@/types/topic1CorpusTools'

const RUNTIME_STATUS_LABELS: Record<Topic1CorpusTool['runtime_status'], string> = {
  metadata_ready: '元信息已接入',
  source_only: '源码待服务化',
  blocked_missing_artifacts: '运行资源待补充',
  pending: '待交付',
}

const WORKFLOW_STAGE_LABELS: Record<Topic1CorpusTool['workflow_stage'], string> = {
  assessment: '语料评估',
  correction: '语料修正',
  delivery: '语料交付',
}

const LABEL_DISTRIBUTION_LABELS: Record<string, string> = {
  member: '成员样本',
  non_member: '非成员样本',
}

const OPERATION_LABELS: Record<string, string> = {
  remove_lines: '删除行',
  remove_str: '删除片段',
  keep_all: '保留全文',
}

export function topic1ToolRuntimeStatusLabel(status: Topic1CorpusTool['runtime_status']) {
  return RUNTIME_STATUS_LABELS[status]
}

export function topic1ToolDeliveryStatusLabel(status: Topic1CorpusTool['delivery_status']) {
  return status === 'source_delivered' ? '源码已交付' : '源码待交付'
}

export function topic1ToolWorkflowStageLabel(stage: Topic1CorpusTool['workflow_stage']) {
  return WORKFLOW_STAGE_LABELS[stage]
}

export function topic1ToolMetadataRows(tool: Topic1CorpusTool) {
  const rows: Array<{ label: string; value: string }> = []
  const datasetName = tool.metadata.dataset_name
  if (typeof datasetName === 'string' && datasetName.trim()) {
    rows.push({ label: '数据集', value: datasetName.trim() })
  }

  const sampleCount = tool.metadata.sample_count
  if (typeof sampleCount === 'number') {
    rows.push({ label: '样本规模', value: `${sampleCount.toLocaleString('zh-CN')} 条` })
  }

  const distribution = tool.metadata.label_distribution
  if (distribution && typeof distribution === 'object' && !Array.isArray(distribution)) {
    const values = Object.entries(distribution)
      .map(([label, count]) => {
        const displayLabel = LABEL_DISTRIBUTION_LABELS[label] ?? label
        const displayCount =
          typeof count === 'number' ? count.toLocaleString('zh-CN') : String(count)
        return `${displayLabel} ${displayCount} 条`
      })
      .join(' / ')
    if (values) rows.push({ label: '标签分布', value: values })
  }

  for (const [key, label] of [
    ['supported_operations', '处理操作'],
    ['pipeline_stages', '流程阶段'],
  ] as const) {
    const value = tool.metadata[key]
    if (Array.isArray(value) && value.length) {
      const formatted = value.map((item) => {
        const normalized = String(item)
        return key === 'supported_operations'
          ? (OPERATION_LABELS[normalized] ?? normalized)
          : normalized
      })
      rows.push({ label, value: formatted.join('、') })
    }
  }
  return rows
}
