import React from 'react'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../features/public/api', () => ({
  fetchExplorerSummary: vi.fn(),
  fetchExplorerProjects: vi.fn(),
}))

import { fetchExplorerProjects, fetchExplorerSummary } from '../../features/public/api'
import Home from '../Home'

const SUMMARY = {
  scopeState: null,
  scopeDistrict: null,
  kpis: { totalProjects: 1234, totalSanctioned: 5e9, totalExpenditure: 1e9, completedProjects: 600, activeWorks: 500, completionRatePercent: 48.6, statesCovered: 30, districtsCovered: 500 },
  utilisation: { percent: 18, projectsWithSanction: 1000, sanctioned: 5e9, expenditureOnThose: 9e8, projectsWithExpenditureRecord: 400, totalProjects: 1234 },
  statusDistribution: [{ status: 'Completed', count: 600 }, { status: 'Ongoing', count: 321 }, { status: 'Sanctioned', count: 200 }, { status: 'Not specified', count: 113 }],
  byState: [{ name: 'Bihar', state: 'Bihar', projectCount: 300, sanctioned: 1e9, expenditure: 1e8, completedProjects: 100, ongoingProjects: 50, utilisationPercent: 10 }],
  byDistrict: [],
  byCategory: [],
  meta: { totalProjects: 1234, refreshedAt: '2026-09-14T18:13:31+00:00', latestRecordDate: '2026-09-06', sourceNote: 'Aggregated from published records.' },
}
const PROJECTS = {
  items: [{ id: 'WS/MP1/2023-2024/103702', title: 'Community hall construction', state: 'Bihar', district: 'PATNA', category: 'Community & Public Buildings', status: 'Completed', sanctioned: 1500000, expenditure: 1200000, utilisationPercent: 80 }],
  total: 1, page: 1, pageSize: 6, totalPages: 1,
}

function renderHome() {
  return render(<MemoryRouter initialEntries={['/']}><Routes><Route path="/" element={<Home />} /></Routes></MemoryRouter>)
}
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('public Home', () => {
  it('shows the hero and the five plain-language statistics from live data', async () => {
    fetchExplorerSummary.mockResolvedValue(SUMMARY)
    fetchExplorerProjects.mockResolvedValue(PROJECTS)
    renderHome()

    expect(screen.getByRole('heading', { level: 1, name: /Explore MPLADS Development Projects Across India/i })).toBeTruthy()
    await waitFor(() => expect(screen.getByText('1,234')).toBeTruthy())
    expect(screen.getByText('Total projects')).toBeTruthy()
    expect(screen.getByText('Total sanctioned')).toBeTruthy()
    expect(screen.getByText('Total expenditure')).toBeTruthy()
    expect(screen.getByText('Completed projects')).toBeTruthy()
    expect(screen.getAllByText('321').length).toBeGreaterThan(0) // ongoing comes from the real status counts
    expect(screen.getByText(/Data last updated/i)).toBeTruthy()
  })

  it('links a recent project to the canonical public detail route', async () => {
    fetchExplorerSummary.mockResolvedValue(SUMMARY)
    fetchExplorerProjects.mockResolvedValue(PROJECTS)
    renderHome()
    const link = (await screen.findAllByRole('link', { name: /Community hall construction/i }))[0]
    expect(link.getAttribute('href')).toBe('/public/projects/' + encodeURIComponent('WS/MP1/2023-2024/103702'))
  })

  it('never shows risk / AI terminology to citizens', async () => {
    fetchExplorerSummary.mockResolvedValue(SUMMARY)
    fetchExplorerProjects.mockResolvedValue(PROJECTS)
    const { container } = renderHome()
    await screen.findByText('1,234')
    const text = container.textContent.toLowerCase()
    for (const word of ['risk', 'anomaly', 'isolation', 'why flagged', 'fusion', 'machine learning']) {
      expect(text).not.toContain(word)
    }
  })

  it('shows a friendly error with Try Again, not raw API text, when data fails', async () => {
    fetchExplorerSummary.mockRejectedValue(Object.assign(new Error('Backend returned 500 boom'), { status: 500 }))
    fetchExplorerProjects.mockRejectedValue(new Error('x'))
    const { container } = renderHome()
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
    expect(screen.getAllByRole('button', { name: /Try Again/i }).length).toBeGreaterThan(0)
    expect(container.textContent).not.toMatch(/boom|500|undefined|NaN|null/)
  })

  it('renders "Not available" instead of 0 when a statistic is missing', async () => {
    fetchExplorerSummary.mockResolvedValue({ ...SUMMARY, kpis: { ...SUMMARY.kpis, totalSanctioned: null } })
    fetchExplorerProjects.mockResolvedValue(PROJECTS)
    renderHome()
    const card = (await screen.findByText('Total sanctioned')).closest('div').parentElement
    expect(within(card).getByText('Not available')).toBeTruthy()
  })
})