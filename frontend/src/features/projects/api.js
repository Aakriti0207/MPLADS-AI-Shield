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
  category = '',
  status = '',
  search = '',
} = {}) {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  })

  if (state && state !== 'All') {
    params.set('state', state)
  }

  if (category && category !== 'All') {
    params.set('category', category)
  }

  if (status && status !== 'All') {
    params.set('status', status)
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