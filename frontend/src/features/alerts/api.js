import { apiFetch } from '../../lib/api'
import { normalizeAlert } from '../../lib/normalizers'

export async function fetchAlerts({ skip = 0, limit = 50 } = {}) {
  const response = await apiFetch(`/alerts?skip=${skip}&limit=${limit}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  const data = await response.json()
  return Array.isArray(data) ? data.map(normalizeAlert) : []
}
