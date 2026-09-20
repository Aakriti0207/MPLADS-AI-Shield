import { apiFetch } from '../../lib/api'
import {
  normalizeProject,
  normalizeRisk,
  unwrapList,
} from '../../lib/normalizers'

export async function fetchProjects({ skip = 0, limit = 50 } = {}) {
  const response = await apiFetch(
    `/projects?skip=${skip}&limit=${limit}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return unwrapList(await response.json()).map(normalizeProject)
}

function buildQuery({
  skip = 0,
  limit = 50,
  state = '',
  district = '',
  constituency = '',
  category = '',
  status = '',
  riskLevel = '',
  search = '',
  spreadSample = false,
} = {}) {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  })

  // Only /projects/query (the real authenticated endpoint) understands
  // this. It asks the backend for an evenly-spaced sample across the
  // whole filtered set instead of a straight first-N page -- without
  // it, a national/state-wide map view can land entirely inside
  // whichever one or two states sort first alphabetically and looks
  // like most of the country has no data. Map-only; Projects.jsx (the
  // Explorer list/pagination) never sets this, so its reading order is
  // unaffected.
  if (spreadSample) {
    params.set('spread_sample', 'true')
  }

  if (state && state !== 'All') {
    params.set('state', state)
  }

  // District/constituency are narrowing filters only. The backend
  // rejects either with 403 if it names a jurisdiction outside the
  // caller's scope, so sending them is always safe -- it can never
  // widen what comes back.
  if (district && district !== 'All') {
    params.set('district', district)
  }

  if (constituency && constituency !== 'All') {
    params.set('constituency', constituency)
  }

  if (category && category !== 'All') {
    params.set('category', category)
  }

  if (status && status !== 'All') {
    params.set('status', status)
  }

  // Risk Fusion level (Critical/High/Medium/Low). Only the protected and
  // demo APIs understand it; the anonymous /public/projects endpoint never
  // exposes risk data, so callers must not offer this filter there.
  if (riskLevel && riskLevel !== 'All') {
    params.set('risk_level', riskLevel.toUpperCase())
  }

  if (search && search.trim()) {
    params.set('search', search.trim())
  }

  return params.toString()
}


// ================================================================
// REAL AUTHENTICATED API
// ================================================================

export async function fetchProjectPage(filters = {}) {
  const response = await apiFetch(
    `/projects/query?${buildQuery(filters)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  const payload = await response.json()

  return {
    ...payload,
    items: (payload.items || []).map(normalizeProject),
  }
}

export async function fetchProject(projectId) {
  const response = await apiFetch(
    `/projects/${encodeURIComponent(projectId)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeProject(
    await response.json()
  )
}

export async function fetchProjectRisk(projectId) {
  const response = await apiFetch(
    `/projects/${encodeURIComponent(projectId)}/risk`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeRisk(
    await response.json()
  )
}


// ================================================================
// PUBLIC / ANONYMOUS API
// ================================================================

// Anonymous-safe project list.
// Does NOT expose Risk Fusion information.
export async function fetchPublicProjectPage(filters = {}) {
  const response = await apiFetch(
    `/public/projects?${buildQuery(filters)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  const payload = await response.json()

  return {
    ...payload,
    items: (payload.items || []).map(normalizeProject),
  }
}

// Anonymous-safe project detail.
// Does NOT expose Risk Fusion information.
export async function fetchPublicProject(projectId) {
  const response = await apiFetch(
    `/public/projects/${encodeURIComponent(projectId)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeProject(
    await response.json()
  )
}


// ================================================================
// DEMO MODE
// ================================================================
// Demo requires NO real authentication/JWT.
//
// Demo endpoints intentionally expose the demonstration
// project universe together with the current Risk Fusion data.
// ================================================================

export async function fetchDemoProjectPage(filters = {}) {
  const response = await apiFetch(
    `/demo/projects/query?${buildQuery(filters)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  const payload = await response.json()

  return {
    ...payload,
    items: (payload.items || []).map(normalizeProject),
  }
}

export async function fetchDemoProjects({
  skip = 0,
  limit = 50,
} = {}) {
  const response = await apiFetch(
    `/demo/projects?skip=${skip}&limit=${limit}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return unwrapList(
    await response.json()
  ).map(normalizeProject)
}

export async function fetchDemoProject(projectId) {
  const response = await apiFetch(
    `/demo/projects/${encodeURIComponent(projectId)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeProject(
    await response.json()
  )
}

export async function fetchDemoProjectRisk(projectId) {
  const response = await apiFetch(
    `/demo/projects/${encodeURIComponent(projectId)}/risk`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return normalizeRisk(
    await response.json()
  )
}

// ================================================================
// SCOPE-AWARE FILTER OPTIONS
// ================================================================

// Optional cascade: with `state` the district list is limited to that
// state, and with `state`/`district` the constituency list is limited too.
// Returns '' (no query string) when nothing is selected, so the plain
// call is identical to what Projects.jsx has always made.
function buildOptionsQuery({ state = '', district = '' } = {}) {
  const params = new URLSearchParams()

  if (state && state !== 'All') {
    params.set('state', state)
  }

  if (district && district !== 'All') {
    params.set('district', district)
  }

  const query = params.toString()

  return query ? `?${query}` : ''
}

/**
 * GET /projects/filter-options
 *
 * Returns only the values present in the caller's own authorized
 * records, plus `locked_filters` naming the dimensions their
 * jurisdiction fixes. This is what lets the filter bar avoid offering a
 * choice the backend would refuse.
 *
 * Goes through apiFetch so the Authorization header is attached and the
 * configured API base is used -- the previous inline `fetch()` call in
 * Projects.jsx did neither, which is why it silently never returned
 * anything.
 */
export async function fetchProjectFilterOptions(cascade = {}) {
  const response = await apiFetch(
    `/projects/filter-options${buildOptionsQuery(cascade)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return response.json()
}

/**
 * GET /demo/projects/filter-options
 *
 * Demo sessions carry no real JWT, so they must not call the protected
 * /projects/filter-options (it would only 401). The demo universe is
 * unscoped, so nothing is ever locked. Same response shape and the same
 * optional `state` / `district` cascade as the protected endpoint.
 */
export async function fetchDemoProjectFilterOptions(cascade = {}) {
  const response = await apiFetch(
    `/demo/projects/filter-options${buildOptionsQuery(cascade)}`
  )

  if (!response.ok) {
    throw new Error(
      `Backend returned ${response.status} ${response.statusText}`
    )
  }

  return response.json()
}