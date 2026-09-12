import { describe, expect, it, vi } from 'vitest'
import { fetchProjectRisk } from './api'

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
})
