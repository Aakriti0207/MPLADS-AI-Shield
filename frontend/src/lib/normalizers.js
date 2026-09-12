import { formatRiskLevel, toNumber } from './formatters'

export function unwrapList(payload) {
  if (Array.isArray(payload)) return payload
  return payload?.items || payload?.projects || payload?.results || []
}

export function normalizeProject(project = {}) {
  return {
    id: project.project_id ?? null,
    state: project.state ?? null,
    district: project.district ?? null,
    constituency: project.constituency ?? null,
    mpName: project.mp_name ?? null,
    workType: project.work_type ?? null,
    agency: project.implementing_agency ?? null,
    sanctioned: toNumber(project.sanctioned_amount),
    expenditure: toNumber(project.expenditure),
    financialProgress: toNumber(project.financial_progress),
    physicalProgress: toNumber(project.physical_progress),
    status: project.status ?? null,
    riskScore: toNumber(project.risk_score),
    risk: formatRiskLevel(project.risk_level),
    latitude: toNumber(project.latitude),
    longitude: toNumber(project.longitude),
    raw: project,
  }
}

export function normalizeRisk(risk = {}) {
  return {
    ...risk,
    workId: risk.work_id ?? null,
    riskScore: toNumber(risk.risk_score),
    riskLevel: formatRiskLevel(risk.risk_level),
    reasons: Array.isArray(risk.risk_reasons) ? risk.risk_reasons : [],
    evidence: risk.source_signal_summary ?? null,
  }
}

export function normalizeDashboardStats(stats = {}) {
  return { ...stats, risk_level_counts: stats.risk_level_counts || {}, by_state: stats.by_state || [], by_work_type: stats.by_work_type || [] }
}

export function normalizeAnalytics(stats = {}) {
  return normalizeDashboardStats(stats)
}

export function normalizeAlert(alert = {}) {
  return { ...alert, severity: formatRiskLevel(alert.severity), projectId: alert.project_id ?? null }
}
