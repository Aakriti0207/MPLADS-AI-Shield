import { apiFetch } from '../../lib/api'

export async function analyzeUpload(file) {
  const form = new FormData()
  form.append('file', file)
  const response = await apiFetch('/upload-analyze', { method: 'POST', body: form })
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail || 'The upload could not be analyzed.')
  if (!body.analysis || body.analysis.status !== 'success') {
    throw new Error(body.analysis?.details?.join(' ') || body.analysis?.message || 'The ML pipeline could not analyze this file.')
  }
  return body.analysis
}
