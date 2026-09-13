import { apiFetch } from '../../lib/api'
import { normalizeProject, normalizeRisk, unwrapList } from '../../lib/normalizers'

export async function fetchProjects({ skip = 0, limit = 50 } = {}) {
  const response = await apiFetch(`/projects?skip=${skip}&limit=${limit}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return unwrapList(await response.json()).map(normalizeProject)
}

function buildQuery({ skip = 0, limit = 50, state = '', category = '', status = '', search = '' } = {}) {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) })
  if (state && state !== 'All') params.set('state', state)
  if (category && category !== 'All') params.set('category', category)
  if (status && status !== 'All') params.set('status', status)
  if (search.trim()) params.set('search', search.trim())
  return params.toString()
}

export async function fetchProjectPage(filters = {}) {
  const response = await apiFetch(`/projects/query?${buildQuery(filters)}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  const payload = await response.json()
  return { ...payload, items: (payload.items || []).map(normalizeProject) }
}

export async function fetchPublicProjectPage(filters = {}) {
  const response = await apiFetch(`/public/projects?${buildQuery(filters)}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  const payload = await response.json()
  return { ...payload, items: (payload.items || []).map(normalizeProject) }
}

export async function fetchProject(projectId) {
  const response = await apiFetch(`/projects/${encodeURIComponent(projectId)}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeProject(await response.json())
}

export async function fetchProjectRisk(projectId) {
  const response = await apiFetch(`/projects/${encodeURIComponent(projectId)}/risk`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return normalizeRisk(await response.json())
}
