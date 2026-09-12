import { apiFetch } from '../../lib/api'
import { normalizeDashboardStats } from '../../lib/normalizers'

export async function fetchDashboardStats() {
  const response = await apiFetch('/dashboard/stats')
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeDashboardStats(await response.json())
}
