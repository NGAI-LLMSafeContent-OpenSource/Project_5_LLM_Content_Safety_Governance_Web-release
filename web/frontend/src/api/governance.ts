import request from './request'
import type {
  CreateGovernanceShareRequest,
  CulturalPrerunEvidencePack,
  InputRiskRescanEvidencePack,
  RiskPrerunEvidencePack,
  GovernanceDomainKey,
  GovernanceHistoryPage,
  GovernanceSessionDetail,
  GovernanceShareCreated,
  GovernanceShareReviewPayload,
  GovernanceSkillCatalogResult,
  GovernanceTaskConfirmAccepted,
  GovernanceTaskDetail,
  GovernanceTaskSuggestionResult,
} from '@/types'

function clientHeaders(clientId: string) {
  return { 'X-Governance-Client-Id': clientId }
}

export function registerGovernanceClient(clientId: string) {
  return request.post<{ client_id: string; created_at: string }>('/governance/clients', {
    client_id: clientId,
  })
}

export function listGovernanceSessions(clientId: string, offset = 0, limit = 50) {
  return request.get<GovernanceHistoryPage>('/governance/sessions', {
    headers: clientHeaders(clientId),
    params: { offset, limit },
  })
}

export function getGovernanceSession(clientId: string, sessionId: string) {
  return request.get<GovernanceSessionDetail>(`/governance/sessions/${sessionId}`, {
    headers: clientHeaders(clientId),
  })
}

/**
 * Longer than the planner's 60s model wait. The page clock starts when the
 * request is sent; the model wait starts only after the server begins planning.
 */
export const GOVERNANCE_SESSION_WAIT_MS = 90_000

/**
 * A trusted control-plane binding for one turn. A recommendation that carries
 * a capability (or skill) key sends it verbatim, so the server must plan for
 * that target instead of inferring one from the prompt text.
 */
export interface GovernanceTurnBinding {
  capability?: string
  skillKey?: string
  /**
   * Parameters bound by a deterministic control-plane action (for example a
   * list card's "open detail"). Only sent together with ``capability``; the
   * server validates them against that capability's registered model.
   */
  parameters?: Record<string, unknown>
}

function turnBody(
  domain: GovernanceDomainKey,
  prompt: string,
  requestId: string,
  binding?: GovernanceTurnBinding,
  clarificationPlan?: { planId: string; version: number },
) {
  const capability = binding?.capability?.trim()
  const skillKey = binding?.skillKey?.trim()
  const parameters = binding?.parameters
  return {
    domain,
    prompt,
    request_id: requestId,
    ...(capability ? { requested_capability: capability } : {}),
    ...(capability && parameters ? { requested_parameters: parameters } : {}),
    ...(skillKey ? { requested_skill_key: skillKey } : {}),
    ...(clarificationPlan
      ? {
          clarification_plan_id: clarificationPlan.planId,
          clarification_plan_version: clarificationPlan.version,
        }
      : {}),
  }
}

export function createGovernanceSession(
  clientId: string,
  domain: GovernanceDomainKey,
  prompt: string,
  requestId: string,
  binding?: GovernanceTurnBinding,
  clarificationPlan?: { planId: string; version: number },
) {
  return request.post<GovernanceSessionDetail>(
    '/governance/sessions',
    turnBody(domain, prompt, requestId, binding, clarificationPlan),
    { headers: clientHeaders(clientId), timeout: GOVERNANCE_SESSION_WAIT_MS },
  )
}

export function appendGovernanceTurn(
  clientId: string,
  sessionId: string,
  domain: GovernanceDomainKey,
  prompt: string,
  requestId: string,
  binding?: GovernanceTurnBinding,
  clarificationPlan?: { planId: string; version: number },
) {
  return request.post<GovernanceSessionDetail>(
    `/governance/sessions/${sessionId}/turns`,
    turnBody(domain, prompt, requestId, binding, clarificationPlan),
    { headers: clientHeaders(clientId), timeout: GOVERNANCE_SESSION_WAIT_MS },
  )
}

export function deleteGovernanceSession(clientId: string, sessionId: string) {
  return request.delete<{ session_id: string; deleted_at: string }>(
    `/governance/sessions/${sessionId}`,
    { headers: clientHeaders(clientId) },
  )
}

export function getGovernanceTask(clientId: string, taskId: string) {
  return request.get<GovernanceTaskDetail>(`/governance/tasks/${taskId}`, {
    headers: clientHeaders(clientId),
  })
}

export function confirmGovernanceTask(clientId: string, taskId: string) {
  // 202 enqueue ack only — never a session detail (#63 async Worker path).
  return request.post<GovernanceTaskConfirmAccepted>(
    `/governance/tasks/${taskId}/confirm`,
    undefined,
    {
      headers: clientHeaders(clientId),
    },
  )
}

export function cancelGovernanceTask(clientId: string, taskId: string) {
  // May return session detail (pre-confirm cancel) or task snapshot (in-flight).
  return request.post<GovernanceSessionDetail | GovernanceTaskDetail>(
    `/governance/tasks/${taskId}/cancel`,
    undefined,
    {
      headers: clientHeaders(clientId),
    },
  )
}

export type GovernanceTaskRetryBody = {
  scope?: 'failed' | 'not_executed' | 'remaining' | 'all'
  sample_ids?: string[]
  evaluator?: 'activation_probe' | 'keyword'
}

export function retryGovernanceTask(
  clientId: string,
  taskId: string,
  body?: GovernanceTaskRetryBody,
) {
  return request.post<GovernanceSessionDetail>(`/governance/tasks/${taskId}/retry`, body, {
    headers: clientHeaders(clientId),
  })
}

// #88: explicit cultural prerun review creation. Only this dedicated call
// creates a `cultural_prerun_review` task; browsing records never does. The
// 201 response is the refreshed session detail carrying the frozen report
// message, so the caller assigns it straight to the active session.
export function createCulturalPrerunReview(
  clientId: string,
  sessionId: string,
  recordId: string,
  recordVersion: string,
) {
  return request.post<GovernanceSessionDetail>(
    `/governance/sessions/${sessionId}/cultural-prerun-reviews`,
    { record_id: recordId, record_version: recordVersion },
    { headers: clientHeaders(clientId) },
  )
}

// #90: explicit risk prerun review creation. Only this dedicated call creates
// a `risk_prerun_review` task; browsing risk records never does.
export function createRiskPrerunReview(
  clientId: string,
  sessionId: string,
  recordId: string,
  recordVersion: string,
) {
  return request.post<GovernanceSessionDetail>(
    `/governance/sessions/${sessionId}/risk-prerun-reviews`,
    { record_id: recordId, record_version: recordVersion },
    { headers: clientHeaders(clientId) },
  )
}

// #89: download the frozen evidence pack (HTML/CSV/JSON/manifest) without
// re-reading Project 3. Artifacts are text payloads the UI turns into files.
export function getCulturalPrerunEvidencePack(clientId: string, taskId: string) {
  return request.get<CulturalPrerunEvidencePack>(
    `/governance/tasks/${taskId}/cultural-prerun-review/evidence-pack`,
    { headers: clientHeaders(clientId) },
  )
}

// #91: restricted risk evidence pack from the frozen completion snapshot only.
export function getRiskPrerunEvidencePack(clientId: string, taskId: string) {
  return request.get<RiskPrerunEvidencePack>(
    `/governance/tasks/${taskId}/risk-prerun-review/evidence-pack`,
    { headers: clientHeaders(clientId) },
  )
}

// #167: input risk corpus online re-detection four-file pack, projected from
// the persisted `risk_corpus_rescan` v2 result (never re-runs detection).
export function getInputRiskRescanEvidencePack(clientId: string, taskId: string) {
  return request.get<InputRiskRescanEvidencePack>(
    `/governance/tasks/${taskId}/input-risk-rescan/evidence-pack`,
    { headers: clientHeaders(clientId) },
  )
}

// #65: read-only skill catalog + boundaries. Cross-domain visible, so no client
// header; an optional domain only reorders the current domain first.
export function getGovernanceSkillCatalog(domain?: GovernanceDomainKey) {
  return request.get<GovernanceSkillCatalogResult>('/governance/skills', {
    params: domain ? { domain } : undefined,
  })
}

// #65: evidence-based follow-up suggestions for one task. Unlike the catalog
// this is client-scoped, so it carries the governance client header.
export function getGovernanceTaskSuggestions(clientId: string, taskId: string) {
  return request.get<GovernanceTaskSuggestionResult>(`/governance/tasks/${taskId}/suggestions`, {
    headers: clientHeaders(clientId),
  })
}

// --- Share* (#66 / #78)：创建/撤销需 client 头；匿名评审 GET 不带 client 头 ---

export function createGovernanceShare(
  clientId: string,
  taskId: string,
  body: CreateGovernanceShareRequest = {},
) {
  return request.post<GovernanceShareCreated>(`/governance/tasks/${taskId}/shares`, body, {
    headers: clientHeaders(clientId),
  })
}

export function revokeGovernanceShare(clientId: string, taskId: string, shareId: string) {
  return request.delete<{ share_id: string; task_id: string; revoked_at: string | null }>(
    `/governance/tasks/${taskId}/shares/${shareId}`,
    { headers: clientHeaders(clientId) },
  )
}

/** 匿名只读评审；路径令牌即凭证，勿附加 X-Governance-Client-Id */
export function getGovernanceShareReview(shareToken: string) {
  return request.get<GovernanceShareReviewPayload>(
    `/governance/review/${encodeURIComponent(shareToken)}`,
  )
}
