import request from './request'

export interface DashboardStats {
  indicatorCount: number
  datasetCount: number
  riskSampleCount: number
  safetyScore: number
  cultureDataCount: number
  cultureAvgScore: number
  scienceDataCount: number
  scienceAvgScore: number
}

export interface TimelineItem {
  time: string
  title: string
  description: string
}

/** 获取首页统计数据 */
export function getDashboardStats() {
  return request.get<DashboardStats>('/dashboard/stats')
}

/** 获取近期活动 */
export function getTimeline() {
  return request.get<TimelineItem[]>('/dashboard/timeline')
}
