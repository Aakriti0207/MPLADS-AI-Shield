import { apiFetch } from '../../lib/api'
import { normalizeAnalytics } from '../../lib/normalizers'

export async function fetchAnalytics() {
  const response = await apiFetch('/analytics')
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeAnalytics(await response.json())
}
