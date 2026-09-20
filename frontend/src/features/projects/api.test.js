import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchDemoProjectFilterOptions,
  fetchDemoProjectPage,
  fetchProjectFilterOptions,
  fetchProjectPage,
  fetchProjectRisk,
  fetchPublicProject,
  fetchPublicProjectPage,
} from './api'

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

const EMPTY_PAGE = { items: [], total: 0, skip: 0, limit: 100 }

function requestedUrl() {
  const calls = apiFetch.mock.calls
  return calls[calls.length - 1][0]
}

function requestedParams() {
  const url = requestedUrl()
  return new URLSearchParams(url.slice(url.indexOf('?') + 1))
}

describe('project query filters (Map filters and search)', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({ ok: true, json: async () => EMPTY_PAGE })
  })

  it('sends every filter to the protected query endpoint as a server-side parameter', async () => {
    await fetchProjectPage({
      skip: 0,
      limit: 100,
      state: 'Bihar',
      district: 'Samastipur',
      constituency: 'Ujiarpur',
      riskLevel: 'High',
      search: '  WS/MP1/2023-2024/103702  ',
    })
    expect(requestedUrl().startsWith('/projects/query?')).toBe(true)
    const params = requestedParams()
    expect(params.get('limit')).toBe('100')
    expect(params.get('state')).toBe('Bihar')
    expect(params.get('district')).toBe('Samastipur')
    expect(params.get('constituency')).toBe('Ujiarpur')
    // The backend validates against upper-case Risk Fusion levels.
    expect(params.get('risk_level')).toBe('HIGH')
    expect(params.get('search')).toBe('WS/MP1/2023-2024/103702')
  })

  it('sends the same filters to the demo query endpoint', async () => {
    await fetchDemoProjectPage({ state: 'Bihar', district: 'Samastipur', constituency: 'Ujiarpur', riskLevel: 'Medium' })
    expect(requestedUrl().startsWith('/demo/projects/query?')).toBe(true)
    const params = requestedParams()
    expect(params.get('district')).toBe('Samastipur')
    expect(params.get('constituency')).toBe('Ujiarpur')
    expect(params.get('risk_level')).toBe('MEDIUM')
  })

  it('omits "All" and blank values instead of sending them', async () => {
    await fetchProjectPage({
      state: 'All',
      district: 'All',
      constituency: 'All',
      riskLevel: 'All',
      search: '   ',
    })
    const params = requestedParams()
    expect([...params.keys()].sort()).toEqual(['limit', 'skip'])
  })

  it('keeps existing callers unchanged: no riskLevel means no risk_level parameter', async () => {
    await fetchProjectPage({ skip: 50, limit: 50, state: 'Bihar', category: 'Education', status: 'Ongoing' })
    const params = requestedParams()
    expect(params.has('risk_level')).toBe(false)
    expect(params.get('category')).toBe('Education')
    expect(params.get('status')).toBe('Ongoing')
  })

  it('the public endpoint still receives the location filters', async () => {
    await fetchPublicProjectPage({ state: 'Bihar', district: 'Samastipur', search: 'road' })
    expect(requestedUrl().startsWith('/public/projects?')).toBe(true)
    const params = requestedParams()
    expect(params.get('district')).toBe('Samastipur')
    expect(params.get('search')).toBe('road')
  })
})

describe('filter-options (scope-aware, cascading)', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ states: ['Bihar'], districts: [], constituencies: [], locked_filters: [] }),
    })
  })

  it('protected: the plain call is exactly the URL Projects.jsx has always used', async () => {
    await fetchProjectFilterOptions()
    expect(apiFetch).toHaveBeenCalledWith('/projects/filter-options')
  })

  it('protected: cascades by state and district', async () => {
    await fetchProjectFilterOptions({ state: 'Bihar', district: 'Samastipur' })
    expect(requestedUrl().startsWith('/projects/filter-options?')).toBe(true)
    const params = requestedParams()
    expect(params.get('state')).toBe('Bihar')
    expect(params.get('district')).toBe('Samastipur')
  })

  it('demo: hits the demo endpoint, never the protected one', async () => {
    await fetchDemoProjectFilterOptions()
    expect(apiFetch).toHaveBeenCalledWith('/demo/projects/filter-options')
    await fetchDemoProjectFilterOptions({ state: 'Bihar' })
    expect(requestedUrl()).toBe('/demo/projects/filter-options?state=Bihar')
    expect(apiFetch.mock.calls.every(([url]) => url.startsWith('/demo/'))).toBe(true)
  })

  it('treats "All" as no selection', async () => {
    await fetchDemoProjectFilterOptions({ state: 'All', district: 'All' })
    expect(requestedUrl()).toBe('/demo/projects/filter-options')
  })

  it('returns the backend payload as-is (including locked_filters)', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ states: ['Bihar'], locked_filters: ['state', 'district'] }),
    })
    const data = await fetchProjectFilterOptions()
    expect(data.locked_filters).toEqual(['state', 'district'])
  })

  it('throws with the status on a non-ok response', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 401, statusText: 'Unauthorized' })
    await expect(fetchProjectFilterOptions()).rejects.toThrow(/401/)
    await expect(fetchDemoProjectFilterOptions()).rejects.toThrow(/401/)
  })
})