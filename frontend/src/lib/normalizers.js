import { formatRiskLevel, toNumber } from './formatters'

export function unwrapList(payload) {
  if (Array.isArray(payload)) return payload

  return (
    payload?.items ||
    payload?.projects ||
    payload?.results ||
    []
  )
}

function cleanWorkDescription(value) {
  const text =
    typeof value === 'string'
      ? value.trim()
      : ''

  if (!text) return null

  const compact = text.replace(/\s/g, '')
  const questionMarks =
    (compact.match(/\?/g) || []).length

  // Hide source text that has been corrupted into '?' characters.
  if (
    questionMarks >= 3 &&
    questionMarks / Math.max(compact.length, 1) > 0.15
  ) {
    return null
  }

  return text
}

export function normalizeProject(project = {}) {
  return {
    id: project.project_id ?? null,

    // Human-readable project name, distinct from workType (the
    // normalized category). The backend already falls back to a
    // cleaned work_description when no explicit project_name exists
    // in the source, and filters out junk values like "Normal/Others"
    // -- so this is preferred over workDescription below wherever both
    // are present.
    projectName:
      project.project_name ??
      project.projectName ??
      null,

    state: project.state ?? null,
    district: project.district ?? null,
    constituency: project.constituency ?? null,

    // Explicit MP type supplied by the backend.
    // Do NOT infer Lok Sabha / Rajya Sabha from constituency.
    mpType:
      project.mp_type ??
      project.mpType ??
      null,

    mpName: project.mp_name ?? null,

    // Normalized project-sector category (e.g. "Education",
    // "Roads & Connectivity"), not the raw work_category value.
    workType: project.work_type ?? null,

    workDescription: cleanWorkDescription(
      project.work_description,
    ),

    agency:
      project.implementing_agency ??
      null,

    sanctioned: toNumber(
      project.sanctioned_amount,
    ),

    expenditure: toNumber(
      project.expenditure,
    ),

    financialProgress: toNumber(
      project.financial_progress,
    ),

    physicalProgress: toNumber(
      project.physical_progress,
    ),

    status: project.status ?? null,

    // Source data's own compliance flag: a payment was recorded for
    // this work with no matching sanction record. See Sanctioned
    // column in Projects.jsx, which shows a warning chip instead of
    // "Not available" when this is true.
    expenditureWithoutSanction:
      project.expenditure_without_sanction ?? null,

    riskScore: toNumber(
      project.risk_score,
    ),

    risk: formatRiskLevel(
      project.risk_level,
    ),

    latitude: toNumber(
      project.latitude,
    ),

    longitude: toNumber(
      project.longitude,
    ),

    raw: project,
  }
}

export function normalizeRisk(risk = {}) {
  return {
    ...risk,

    workId:
      risk.work_id ??
      null,

    riskScore: toNumber(
      risk.risk_score,
    ),

    riskLevel: formatRiskLevel(
      risk.risk_level,
    ),

    reasons: Array.isArray(
      risk.risk_reasons,
    )
      ? risk.risk_reasons
      : [],

    evidence:
      risk.source_signal_summary ??
      null,
  }
}

export function normalizeDashboardStats(stats = {}) {
  return {
    ...stats,

    risk_level_counts:
      stats.risk_level_counts ||
      {},

    by_state:
      stats.by_state ||
      [],

    by_work_type:
      stats.by_work_type ||
      [],

    status_distribution:
      stats.status_distribution ||
      [],

    recent_projects: (
      stats.recent_projects ||
      []
    ).map(normalizeProject),
  }
}

export function normalizeAnalytics(stats = {}) {
  return normalizeDashboardStats(stats)
}

export function normalizeAlert(alert = {}) {
  return {
    ...alert,

    severity: formatRiskLevel(
      alert.severity,
    ),

    projectId:
      alert.project_id ??
      null,
  }
}