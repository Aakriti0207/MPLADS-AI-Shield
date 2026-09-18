import { apiFetch } from '../../lib/api'
import { normalizeDashboardStats, normalizeProject } from '../../lib/normalizers'
import { normalizePublicOverview } from '../../lib/publicNormalizers'
import { isDemoModeEnabled, getDemoRole } from '../../lib/demoSession'

export async function fetchDashboardStats() {
  const endpoint = isDemoModeEnabled() && getDemoRole()
    ? '/demo/dashboard/stats'
    : '/dashboard/stats'

  const response = await apiFetch(endpoint)

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeDashboardStats(await response.json())
}

export async function fetchRoleDashboard() {
  const endpoint = isDemoModeEnabled() && getDemoRole()
    ? '/demo/dashboard/role-overview'
    : '/dashboard/role-overview'

  const response = await apiFetch(endpoint)

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  const payload = await response.json()

  /*
   * The RBAC payload -- scope, kpis, district_performance,
   * attention_projects, scoped_projects, permissions -- is passed
   * through UNCHANGED via the spread below.
   *
   * That is deliberate. Those blocks are already shaped for the role
   * dashboards, and every figure in them was computed by the backend
   * over the authorized record set. Re-deriving or "normalising" them
   * here would be the frontend recomputing values it has no authority
   * over -- and would risk the displayed number quietly disagreeing
   * with what the API actually returned.
   *
   * Only the two legacy Ministry blocks are normalised, because the
   * national dashboard components have always expected that shape.
   */
  return {
    ...payload,
    stats: payload.stats
      ? normalizeDashboardStats(payload.stats)
      : null,

    priority_projects: (
      payload.priority_projects || []
    ).map(normalizeProject),
  }
}

/**
 * Anonymous overview.
 *
 * Phase 5: normalized through `normalizePublicOverview` (the dedicated
 * public contract) instead of the risk-aware `normalizeDashboardStats`,
 * so `risk_level_counts` is not carried into the public UI even if a
 * future backend change reintroduced it. `GET /public/overview` no longer
 * returns that field either.
 */
export async function fetchPublicOverview() {
  const response = await apiFetch('/public/overview?limit=8')

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizePublicOverview(
    await response.json()
  )
}