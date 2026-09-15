import { apiFetch } from '../../lib/api'
import { normalizeAnalytics } from '../../lib/normalizers'
import { isDemoModeEnabled, getDemoRole } from '../../lib/demoSession'

export async function fetchAnalytics() {
  const endpoint = isDemoModeEnabled() && getDemoRole()
    ? '/demo/analytics'
    : '/analytics'

  const response = await apiFetch(endpoint)

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeAnalytics(await response.json())
}