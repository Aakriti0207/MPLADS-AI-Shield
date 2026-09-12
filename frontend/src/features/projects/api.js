import { apiFetch } from '../../lib/api'
import { normalizeProject, normalizeRisk, unwrapList } from '../../lib/normalizers'

export async function fetchProjects({ skip = 0, limit = 50 } = {}) {
  const response = await apiFetch(`/projects?skip=${skip}&limit=${limit}`)
  if (!response.ok) throw new Error(`Backend returned ${response.status} ${response.statusText}`)
  return unwrapList(await response.json()).map(normalizeProject)
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
