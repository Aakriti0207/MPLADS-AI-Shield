import { apiFetch } from '../../lib/api'
import {
  normalizeAreaResponse,
  normalizeExplorerPage,
  normalizeExplorerProject,
  normalizeExplorerSummary,
  normalizeFilterOptions,
  normalizeMeta,
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

// ---------------------------------------------------------------------
// Public portal explorer (canonical-backed, allowlist-only responses)
// ---------------------------------------------------------------------

/**
 * Error thrown by the explorer calls. `status` is the HTTP status (or
 * null when the server could not be reached). The message is always a
 * plain-language sentence -- raw backend text is never surfaced.
 */
export class PublicApiError extends Error {
  constructor(status) {
    super(
      status === 404
        ? 'We could not find what you were looking for.'
        : "We couldn't load project data right now."
    )
    this.name = 'PublicApiError'
    this.status = status
  }
}

async function getExplorer(path, { signal } = {}) {
  let response
  try {
    response = await apiFetch(path, { signal })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new PublicApiError(null)
  }
  if (!response.ok) throw new PublicApiError(response.status)
  return response.json()
}

/** Server-side search + filter + pagination over public projects. */
export async function fetchExplorerProjects(
  { search, state, district, category, status, year, detailed, sort = 'recent', page = 1, pageSize = 20 } = {},
  options = {}
) {
  const path = `/public/explorer/projects${buildQuery({
    search: search?.trim() || null,
    state,
    district: state ? district : null,
    category,
    status,
    year,
    detailed: detailed ? 'true' : null,
    sort,
    page,
    page_size: pageSize,
  })}`
  return normalizeExplorerPage(await getExplorer(path, options))
}

/** One public project by canonical project id. */
export async function fetchExplorerProject(projectId, options = {}) {
  const path = `/public/explorer/projects/${encodeURIComponent(projectId)}`
  return normalizeExplorerProject(await getExplorer(path, options))
}

/** Options that exist in the data (districts only when `state` is set). */
export async function fetchExplorerFilters({ state = null } = {}, options = {}) {
  return normalizeFilterOptions(
    await getExplorer(`/public/explorer/filters${buildQuery({ state })}`, options)
  )
}

/** State rows (or district rows when `state` is set) for map + drill-down. */
export async function fetchExplorerAreas({ state = null, category = null, status = null } = {}, options = {}) {
  return normalizeAreaResponse(
    await getExplorer(`/public/explorer/areas${buildQuery({ state, category, status })}`, options)
  )
}

/** Totals, utilisation, status + category mix for a scope. */
export async function fetchExplorerSummary({ state = null, district = null } = {}, options = {}) {
  return normalizeExplorerSummary(
    await getExplorer(`/public/explorer/summary${buildQuery({ state, district: state ? district : null })}`, options)
  )
}

/** Data freshness + source description. */
export async function fetchPublicMeta(options = {}) {
  return normalizeMeta(await getExplorer('/public/meta', options))
}