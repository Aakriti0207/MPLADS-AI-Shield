import { apiFetch } from '../../lib/api'
import { normalizeDashboardStats, normalizeProject } from '../../lib/normalizers'
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

export async function fetchPublicOverview() {
  const response = await apiFetch('/public/overview?limit=8')

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeDashboardStats(
    await response.json()
  )
}