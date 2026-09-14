import { describe, expect, it, vi } from 'vitest'
import { fetchProjectRisk, fetchPublicProject } from './api'

vi.mock('../../lib/api', () => ({ apiFetch: vi.fn() }))
import { apiFetch } from '../../lib/api'

describe('project API', () => {
  it('uses the dedicated Risk Fusion endpoint', async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ work_id: 'WS/MP1/2024-2025/1', risk_score: 12, risk_level: 'LOW' }) })
    const result = await fetchProjectRisk('WS/MP1/2024-2025/1')
    expect(apiFetch).toHaveBeenCalledWith('/projects/WS%2FMP1%2F2024-2025%2F1/risk')
    expect(result.riskScore).toBe(12)
    expect(result.riskLevel).toBe('Low')
  })

  it('fetchPublicProject hits the anonymous-safe detail endpoint and never sees risk fields', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        project_id: 'WS/MP1/2024-2025/1',
        state: 'Delhi',
        sanctioned_amount: 500000,
        expenditure: 400000,
      }),
    })
    const result = await fetchPublicProject('WS/MP1/2024-2025/1')
    expect(apiFetch).toHaveBeenCalledWith('/public/projects/WS%2FMP1%2F2024-2025%2F1')
    expect(result.id).toBe('WS/MP1/2024-2025/1')
    expect(result.riskScore).toBeNull()
    expect(result.risk).toBeNull()
  })

  it('fetchPublicProject throws with the status on a non-ok response (e.g. 404)', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 404, statusText: 'Not Found' })
    await expect(fetchPublicProject('WS/DOES/NOT/EXIST')).rejects.toThrow(/404/)
  })
})