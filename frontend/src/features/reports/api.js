import { apiFetch } from '../../lib/api'

/**
 * Phase 8 -- Reports & Export.
 *
 * Every function here talks to the real GET /reports/* endpoints
 * (app/routes/reports.py) -- there is no client-side report
 * generation or fabricated data anywhere in this module.
 */

export async function fetchReportsMeta() {
  const response = await apiFetch('/reports/meta')
  if (!response.ok) throw new Error(await _errorMessage(response))
  return response.json()
}

function buildParams({ reportType, format = 'json', state, district, constituency, category, riskLevel, dateFrom, dateTo }) {
  const params = new URLSearchParams({ report_type: reportType, format })
  if (state) params.set('state', state)
  if (district) params.set('district', district)
  if (constituency) params.set('constituency', constituency)
  if (category) params.set('category', category)
  if (riskLevel) params.set('risk_level', riskLevel)
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  return params
}

async function _errorMessage(response) {
  try {
    const body = await response.clone().json()
    if (body && body.detail) return body.detail
  } catch {
    // Response body wasn't JSON (e.g. a failed file download) -- fall
    // through to the generic status-based message below.
  }
  if (response.status === 401) return 'Your session has expired. Please sign in again.'
  if (response.status === 403) return 'You do not have permission to generate this report.'
  if (response.status === 400) return 'This report could not be generated with the selected options.'
  if (response.status === 404) return 'The requested project could not be found.'
  if (response.status === 422) return 'One or more filter values are invalid.'
  return `Report generation failed (${response.status}). Please try again.`
}

/** GET /reports/generate?format=json -- powers the on-screen preview. */
export async function fetchReportPreview(filters) {
  const params = buildParams({ ...filters, format: 'json' })
  const response = await apiFetch(`/reports/generate?${params.toString()}`)
  if (!response.ok) throw new Error(await _errorMessage(response))
  return response.json()
}

function _filenameFromDisposition(response, fallback) {
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  return match ? match[1] : fallback
}

function _triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Downloads the real CSV/PDF file for the current report + filters.
 * Uses apiFetch (not a plain <a href>) so the Authorization header is
 * attached, then triggers a normal browser download from the returned
 * Blob -- the file itself always comes straight from the backend.
 */
export async function downloadReportFile(filters, format) {
  const params = buildParams({ ...filters, format })
  const response = await apiFetch(`/reports/generate?${params.toString()}`)
  if (!response.ok) throw new Error(await _errorMessage(response))
  const blob = await response.blob()
  _triggerDownload(blob, _filenameFromDisposition(response, `mplads-ai-shield-report.${format}`))
}

/** GET /reports/project/{id}?format=pdf -- single-project export, used
 * by the Project Detail "Export Report" action. */
export async function downloadProjectReport(projectId) {
  const response = await apiFetch(`/reports/project/${encodeURIComponent(projectId)}?format=pdf`)
  if (!response.ok) throw new Error(await _errorMessage(response))
  const blob = await response.blob()
  _triggerDownload(blob, _filenameFromDisposition(response, 'mplads-ai-shield-project-report.pdf'))
}