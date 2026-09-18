import { apiFetch } from '../../lib/api'
import {
  normalizePublicDistrictResponse,
  normalizePublicInsights,
} from '../../lib/publicNormalizers'

/**
 * Phase 5: API client for the anonymous public dashboard.
 *
 * Kept in its own feature folder (rather than in features/dashboard/api.js)
 * because features/dashboard is the authenticated, risk-aware data path.
 * Every call here targets a `/public/*` route, needs no token, and is
 * normalized through lib/publicNormalizers.js -- so the public screens
 * never import the risk-aware contract at all.
 *
 * `apiFetch` is reused for the shared base URL and error handling; it
 * simply sends no Authorization header when no token is stored, which is
 * the normal case for these routes.
 */

function buildQuery(params) {
  const search = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    search.set(key, String(value))
  })

  const query = search.toString()

  return query ? `?${query}` : ''
}

async function getPublic(path) {
  const response = await apiFetch(path)

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return response.json()
}

/**
 * National (or state/district-scoped) public dashboard payload:
 * KPIs, real expenditure/completion/sanction trends, state and district
 * insights, category and status breakdowns, recent public projects, and
 * explicit source-data coverage notes.
 */
export async function fetchPublicInsights({
  state = null,
  district = null,
  recentLimit = 8,
} = {}) {
  const path = `/public/insights${buildQuery({
    state,
    district,
    recent_limit: recentLimit,
  })}`

  return normalizePublicInsights(await getPublic(path))
}

/**
 * District aggregates for one state, used by the State -> District
 * drilldown so selecting a state doesn't refetch the whole national
 * payload.
 */
export async function fetchPublicDistricts(state) {
  const path = `/public/insights/districts${buildQuery({ state })}`

  return normalizePublicDistrictResponse(await getPublic(path))
}
