import { apiFetch } from '../../lib/api'
import { normalizeDashboardStats, normalizeProject } from '../../lib/normalizers'

export async function fetchDashboardStats() {
  const response = await apiFetch('/dashboard/stats')
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeDashboardStats(await response.json())
}

export async function fetchRoleDashboard() {
  const response = await apiFetch('/dashboard/role-overview')
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  const payload = await response.json()
  return {
    ...payload,
    stats: payload.stats ? normalizeDashboardStats(payload.stats) : null,
    priority_projects: (payload.priority_projects || []).map(normalizeProject),
  }
}

export async function fetchPublicOverview() {
  const response = await apiFetch('/public/overview?limit=8')
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeDashboardStats(await response.json())
}
