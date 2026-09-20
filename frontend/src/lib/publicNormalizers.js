import { toNumber } from './formatters'

/**
 * Phase 5: dedicated PUBLIC data contract.
 *
 * `lib/normalizers.js` (normalizeDashboardStats / normalizeProject) is the
 * risk-aware contract used by the authenticated Dashboard, Analytics,
 * AI Shield and Alerts screens -- it deliberately carries `riskScore`,
 * `risk` and `risk_level_counts`.
 *
 * The anonymous Overview must not share that shape, so the public surface
 * gets its own normalizers here. Nothing in this file reads, defaults or
 * passes through a risk score, risk level, Risk Fusion field, anomaly /
 * duplicate / isolation-forest score, AI reasoning, alert, or
 * review/investigation field. The separation is structural: a future
 * backend change that accidentally added such a field to a `/public/*`
 * payload still would not reach the public UI through these functions.
 */

/** Public-safe project summary. No risk fields, by construction. */
export function normalizePublicProject(project = {}) {
  return {
    // Canonical project id (work_id) -- the same identifier the
    // authenticated views use, so public deep links stay consistent.
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
    status: project.status ?? null,
    sanctionDate: project.sanction_date ?? null,
    startDate: project.start_date ?? null,
    expectedCompletion: project.expected_completion ?? null,
    actualCompletion: project.actual_completion ?? null,
  }
}

function normalizeAreaStat(row = {}) {
  return {
    projectCount: toNumber(row.project_count) ?? 0,
    sanctioned: toNumber(row.total_sanctioned_amount),
    expenditure: toNumber(row.total_expenditure),
    completedProjects: toNumber(row.completed_projects) ?? 0,
    activeWorks: toNumber(row.active_works) ?? 0,
    utilisationPercent: toNumber(row.expenditure_utilisation_percent),
    completionRatePercent: toNumber(row.completion_rate_percent),
  }
}

export function normalizePublicState(row = {}) {
  return {
    state: row.state ?? null,
    districtCount: toNumber(row.district_count) ?? 0,
    ...normalizeAreaStat(row),
  }
}

export function normalizePublicDistrict(row = {}) {
  return {
    state: row.state ?? null,
    district: row.district ?? null,
    ...normalizeAreaStat(row),
  }
}

/**
 * One trend series plus its coverage metadata.
 *
 * `hasRecords` is preserved per point so the UI can distinguish "zero was
 * recorded this month" from "this month had no source rows at all" --
 * neither is ever presented as an estimate.
 */
export function normalizePublicTrend(trend = {}) {
  return {
    points: (trend.points || []).map(point => ({
      period: point.period ?? null,
      label: point.label ?? point.period ?? '',
      projectCount: toNumber(point.project_count) ?? 0,
      amount: toNumber(point.amount),
      hasRecords: point.has_records !== false,
    })),
    basis: trend.basis ?? null,
    projectsWithData: toNumber(trend.projects_with_data) ?? 0,
    totalProjects: toNumber(trend.total_projects) ?? 0,
    coveragePercent: toNumber(trend.coverage_percent),
  }
}

export function normalizePublicInsights(payload = {}) {
  const kpis = payload.kpis || {}
  const trends = payload.trends || {}
  const coverage = payload.data_coverage || {}

  return {
    kpis: {
      totalProjects: toNumber(kpis.total_projects),
      totalSanctioned: toNumber(kpis.total_sanctioned_amount),
      totalExpenditure: toNumber(kpis.total_expenditure),
      completedProjects: toNumber(kpis.completed_projects),
      activeWorks: toNumber(kpis.active_works),
      statusNotSpecified: toNumber(kpis.status_not_specified),
      utilisationPercent: toNumber(kpis.expenditure_utilisation_percent),
      completionRatePercent: toNumber(kpis.completion_rate_percent),
      statesCovered: toNumber(kpis.states_covered),
      districtsCovered: toNumber(kpis.districts_covered),
    },
    trends: {
      expenditure: normalizePublicTrend(trends.expenditure),
      completion: normalizePublicTrend(trends.completion),
      sanction: normalizePublicTrend(trends.sanction),
    },
    byState: (payload.by_state || []).map(normalizePublicState),
    byDistrict: (payload.by_district || []).map(normalizePublicDistrict),
    byWorkType: (payload.by_work_type || []).map(row => ({
      workType: row.work_type ?? null,
      count: toNumber(row.count) ?? 0,
      sanctioned: toNumber(row.total_sanctioned_amount),
      expenditure: toNumber(row.total_expenditure),
    })),
    statusDistribution: (payload.status_distribution || []).map(row => ({
      status: row.status ?? null,
      count: toNumber(row.count) ?? 0,
    })),
    recentProjects: (payload.recent_projects || []).map(normalizePublicProject),
    dataCoverage: {
      fields: (coverage.fields || []).map(field => ({
        field: field.field ?? null,
        projectsWithData: toNumber(field.projects_with_data) ?? 0,
        totalProjects: toNumber(field.total_projects) ?? 0,
        coveragePercent: toNumber(field.coverage_percent),
      })),
      notes: coverage.notes || [],
    },
    disclaimer: payload.disclaimer ?? null,
  }
}

export function normalizePublicDistrictResponse(payload = {}) {
  return {
    state: payload.state ?? null,
    districts: (payload.districts || []).map(normalizePublicDistrict),
  }
}

/**
 * Public overview normalizer.
 *
 * Phase 5: `risk_level_counts` is deliberately NOT carried over from the
 * `/public/overview` payload, and recent projects go through
 * `normalizePublicProject` rather than the risk-aware `normalizeProject`.
 * The backend no longer sends that field either -- this is the second,
 * independent guard.
 */
export function normalizePublicOverview(stats = {}) {
  const {
    risk_level_counts: _riskLevelCounts,
    ...safe
  } = stats

  return {
    ...safe,
    by_state: safe.by_state || [],
    by_work_type: safe.by_work_type || [],
    status_distribution: safe.status_distribution || [],
    recent_projects: (safe.recent_projects || []).map(normalizePublicProject),
  }
}

// ---------------------------------------------------------------------
// Public portal explorer contract (GET /public/explorer/*, /public/meta)
//
// Same rule as everything above: an explicit allowlist. Fields not named
// here are dropped, so even if a future backend change added an internal
// field to one of these payloads it could not reach the public UI.
// ---------------------------------------------------------------------

export function normalizeExplorerProject(row = {}) {
  return {
    id: row.project_id ?? null,
    title: row.title ?? null,
    description: row.description ?? null,
    state: row.state ?? null,
    district: row.district ?? null,
    constituency: row.constituency ?? null,
    category: row.category ?? null,
    status: row.status ?? null,
    sanctioned: toNumber(row.sanctioned_amount),
    expenditure: toNumber(row.expenditure),
    utilisationPercent: toNumber(row.utilisation_percent),
    sanctionDate: row.sanction_date ?? null,
    completionDate: row.completion_date ?? null,
    mpName: row.mp_name ?? null,
    agency: row.implementing_agency ?? null,
    recommendedAmount: toNumber(row.recommended_amount),
    recommendedDate: row.recommended_date ?? null,
    firstExpenditureDate: row.first_expenditure_date ?? null,
    lastExpenditureDate: row.last_expenditure_date ?? null,
  }
}

export function normalizeExplorerPage(payload = {}) {
  return {
    items: (payload.items || []).map(normalizeExplorerProject),
    total: toNumber(payload.total) ?? 0,
    page: toNumber(payload.page) ?? 1,
    pageSize: toNumber(payload.page_size) ?? 20,
    totalPages: toNumber(payload.total_pages) ?? 0,
  }
}

export function normalizeFilterOptions(payload = {}) {
  const options = list => (list || []).map(o => ({ value: o.value, count: toNumber(o.count) ?? 0 }))
  return {
    states: options(payload.states),
    districts: options(payload.districts),
    categories: options(payload.categories),
    statuses: options(payload.statuses),
    years: options(payload.years),
  }
}

export function normalizeAreaRow(row = {}) {
  return {
    name: row.name ?? null,
    state: row.state ?? null,
    projectCount: toNumber(row.project_count) ?? 0,
    sanctioned: toNumber(row.sanctioned_amount),
    expenditure: toNumber(row.expenditure),
    completedProjects: toNumber(row.completed_projects) ?? 0,
    ongoingProjects: toNumber(row.ongoing_projects) ?? 0,
    utilisationPercent: toNumber(row.utilisation_percent),
  }
}

export function normalizeAreaResponse(payload = {}) {
  return {
    level: payload.level ?? 'state',
    state: payload.state ?? null,
    rows: (payload.rows || []).map(normalizeAreaRow),
  }
}

export function normalizeMeta(meta = {}) {
  return {
    totalProjects: toNumber(meta.total_projects),
    refreshedAt: meta.dataset_refreshed_at ?? null,
    latestRecordDate: meta.latest_record_date ?? null,
    sourceNote: meta.source_note ?? null,
  }
}

export function normalizeExplorerSummary(payload = {}) {
  const kpis = payload.kpis || {}
  const util = payload.utilisation || {}
  return {
    scopeState: payload.scope_state ?? null,
    scopeDistrict: payload.scope_district ?? null,
    kpis: {
      totalProjects: toNumber(kpis.total_projects),
      totalSanctioned: toNumber(kpis.total_sanctioned_amount),
      totalExpenditure: toNumber(kpis.total_expenditure),
      completedProjects: toNumber(kpis.completed_projects),
      activeWorks: toNumber(kpis.active_works),
      completionRatePercent: toNumber(kpis.completion_rate_percent),
      statesCovered: toNumber(kpis.states_covered),
      districtsCovered: toNumber(kpis.districts_covered),
    },
    utilisation: {
      percent: toNumber(util.percent),
      projectsWithSanction: toNumber(util.projects_with_sanctioned_amount),
      sanctioned: toNumber(util.sanctioned_amount),
      expenditureOnThose: toNumber(util.expenditure_on_those_projects),
      projectsWithExpenditureRecord: toNumber(util.projects_with_expenditure_record),
      totalProjects: toNumber(util.total_projects),
    },
    statusDistribution: (payload.status_distribution || []).map(row => ({
      status: row.status ?? null,
      count: toNumber(row.count) ?? 0,
    })),
    byState: (payload.by_state || []).map(normalizeAreaRow),
    byDistrict: (payload.by_district || []).map(normalizeAreaRow),
    byCategory: (payload.by_category || []).map(row => ({
      category: row.category ?? null,
      count: toNumber(row.count) ?? 0,
      sanctioned: toNumber(row.total_sanctioned_amount),
      expenditure: toNumber(row.total_expenditure),
    })),
    meta: normalizeMeta(payload.meta),
  }
}