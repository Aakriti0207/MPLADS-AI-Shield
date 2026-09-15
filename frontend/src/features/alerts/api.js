import { apiFetch } from '../../lib/api'
import { normalizeAlert } from '../../lib/normalizers'
import { isDemoModeEnabled, getDemoRole } from '../../lib/demoSession'

export async function fetchAlerts({ skip = 0, limit = 50 } = {}) {
  const endpoint = isDemoModeEnabled() && getDemoRole()
    ? `/demo/alerts?skip=${skip}&limit=${limit}`
    : `/alerts?skip=${skip}&limit=${limit}`

  const response = await apiFetch(endpoint)

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  const data = await response.json()

  return Array.isArray(data) ? data.map(normalizeAlert) : []
}