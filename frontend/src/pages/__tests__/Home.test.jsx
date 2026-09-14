import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../features/dashboard/api', () => ({ fetchPublicOverview: vi.fn() }))
import { fetchPublicOverview } from '../../features/dashboard/api'
import Home from '../Home'

// Minimal stand-in for pages/ProjectDetails -- these tests only care
// that Home navigates to /projects/:id, not about what that page renders.
function ProjectDetailsProbe() {
  const location = useLocation()
  return <div data-testid="project-details-probe">{location.pathname}</div>
}

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects/:id" element={<ProjectDetailsProbe />} />
      </Routes>
    </MemoryRouter>
  )
}

const OVERVIEW_WITH_PROJECT = {
  total_projects: 1,
  total_sanctioned_amount: 500000,
  total_expenditure: 400000,
  average_financial_progress: 80,
  risk_level_counts: {},
  by_state: [],
  by_work_type: [],
  status_distribution: [],
  // fetchPublicOverview (mocked below) already returns normalizeDashboardStats'
  // output -- Home.jsx never re-normalizes it -- so recent_projects here uses
  // the normalized/camelCase shape (id, workType, sanctioned, financialProgress),
  // not the raw snake_case API payload (project_id, work_type, ...).
  recent_projects: [
    {
      id: 'WS/MP001/2023-2024/103702',
      state: 'Delhi',
      district: null,
      constituency: 'New Delhi',
      mpName: null,
      workType: 'Road construction',
      agency: null,
      status: 'Ongoing',
      sanctioned: 500000,
      expenditure: 400000,
      financialProgress: 80,
      physicalProgress: null,
      riskScore: null,
      risk: null,
      latitude: null,
      longitude: null,
      raw: {},
    },
  ],
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Home / Recently Monitored Projects', () => {
  it('renders each recent project Work ID as a clickable link to /projects/:id', async () => {
    fetchPublicOverview.mockResolvedValue(OVERVIEW_WITH_PROJECT)
    renderHome()

    const link = await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    expect(link.getAttribute('href')).toBe('/projects/WS%2FMP001%2F2023-2024%2F103702')
  })

  it('clicking a recent project row navigates to the correct /projects/:id route and opens Project Detail', async () => {
    fetchPublicOverview.mockResolvedValue(OVERVIEW_WITH_PROJECT)
    renderHome()

    const link = await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    link.click()

    await waitFor(() => expect(screen.getByTestId('project-details-probe')).toBeTruthy())
    expect(screen.getByTestId('project-details-probe').textContent).toBe('/projects/WS%2FMP001%2F2023-2024%2F103702')
  })

  it('clicking anywhere in the row (not just the link text) also navigates', async () => {
    fetchPublicOverview.mockResolvedValue(OVERVIEW_WITH_PROJECT)
    renderHome()

    await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    const row = screen.getByText('Road construction').closest('tr')
    row.click()

    await waitFor(() => expect(screen.getByTestId('project-details-probe')).toBeTruthy())
  })

  it('shows an empty state instead of a broken table when there are no recent projects', async () => {
    fetchPublicOverview.mockResolvedValue({ ...OVERVIEW_WITH_PROJECT, recent_projects: [] })
    renderHome()

    await waitFor(() => expect(screen.getByText(/no monitored projects found/i)).toBeTruthy())
    expect(screen.queryByRole('link', { name: /WS\// })).toBeNull()
  })
})