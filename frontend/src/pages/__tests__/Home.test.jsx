import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

// Home now draws on TWO api modules:
//   features/dashboard/api  -> fetchPublicOverview (recent public projects)
//   features/public/api     -> fetchPublicInsights / fetchPublicDistricts
//                              (Phase 5 public contract)
// Both are mocked so these tests never touch the network.
vi.mock('../../features/dashboard/api', () => ({ fetchPublicOverview: vi.fn() }))
vi.mock('../../features/public/api', () => ({
  fetchPublicInsights: vi.fn(),
  fetchPublicDistricts: vi.fn(),
}))

import { fetchPublicOverview } from '../../features/dashboard/api'
import { fetchPublicDistricts, fetchPublicInsights } from '../../features/public/api'
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

// fetchPublicOverview / fetchPublicInsights (mocked) already return
// normalized output -- Home never re-normalizes -- so these fixtures use
// the normalized camelCase shape, not the raw snake_case API payload.
const OVERVIEW_WITH_PROJECT = {
  total_projects: 1,
  total_sanctioned_amount: 500000,
  total_expenditure: 400000,
  average_financial_progress: 80,
  by_state: [],
  by_work_type: [],
  status_distribution: [],
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
      sanctionDate: null,
      startDate: null,
      expectedCompletion: null,
      actualCompletion: null,
    },
  ],
}

const EMPTY_TREND = {
  points: [],
  basis: null,
  projectsWithData: 0,
  totalProjects: 0,
  coveragePercent: null,
}

const INSIGHTS = {
  kpis: {
    totalProjects: 43863,
    totalSanctioned: 23048672771,
    totalExpenditure: 3849817769,
    completedProjects: 23283,
    activeWorks: 14537,
    statusNotSpecified: 6043,
    utilisationPercent: 16.7,
    completionRatePercent: 53.08,
    statesCovered: 35,
    districtsCovered: 735,
  },
  trends: {
    expenditure: {
      points: [
        { period: '2025-02', label: 'Feb 2025', projectCount: 1, amount: 0, hasRecords: true },
        { period: '2025-03', label: 'Mar 2025', projectCount: 3, amount: 2624385, hasRecords: true },
      ],
      basis: 'Attributed to the month of the most recent expenditure transaction.',
      projectsWithData: 8950,
      totalProjects: 43863,
      coveragePercent: 20.4,
    },
    completion: {
      points: [
        { period: '2023-08', label: 'Aug 2023', projectCount: 2, amount: null, hasRecords: true },
        { period: '2023-09', label: 'Sep 2023', projectCount: 7, amount: null, hasRecords: true },
      ],
      basis: 'Works counted in the month of their recorded completion date.',
      projectsWithData: 22956,
      totalProjects: 43863,
      coveragePercent: 52.3,
    },
    sanction: EMPTY_TREND,
  },
  byState: [
    {
      state: 'Maharashtra',
      districtCount: 43,
      projectCount: 1408,
      sanctioned: 1101310138,
      expenditure: 433272104,
      completedProjects: 404,
      activeWorks: 525,
      utilisationPercent: 39.34,
      completionRatePercent: 28.69,
    },
    {
      state: 'Bihar',
      districtCount: 38,
      projectCount: 1200,
      sanctioned: 900000000,
      expenditure: 300000000,
      completedProjects: 500,
      activeWorks: 600,
      utilisationPercent: 33.3,
      completionRatePercent: 41.6,
    },
  ],
  byDistrict: [],
  byWorkType: [],
  statusDistribution: [
    { status: 'Completed', count: 23283 },
    { status: 'Sanctioned', count: 8109 },
  ],
  recentProjects: [],
  dataCoverage: {
    fields: [],
    notes: ['Completion dates exist for 22,956 of 43,863 projects.'],
  },
  disclaimer: 'Aggregated from published MPLADS records.',
}

const MAHARASHTRA_DISTRICTS = {
  state: 'Maharashtra',
  districts: [
    {
      state: 'Maharashtra',
      district: 'MUMBAI SUBURBAN',
      projectCount: 112,
      sanctioned: 268300000,
      expenditure: 62429484,
      completedProjects: 0,
      activeWorks: 99,
      utilisationPercent: 23.27,
      completionRatePercent: 0,
    },
  ],
}

function mockHappyPath() {
  fetchPublicOverview.mockResolvedValue(OVERVIEW_WITH_PROJECT)
  fetchPublicInsights.mockResolvedValue(INSIGHTS)
  fetchPublicDistricts.mockResolvedValue(MAHARASHTRA_DISTRICTS)
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Home / Recently Monitored Projects', () => {
  it('renders each recent project Work ID as a clickable link to /projects/:id', async () => {
    mockHappyPath()
    renderHome()

    const link = await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    expect(link.getAttribute('href')).toBe('/projects/WS%2FMP001%2F2023-2024%2F103702')
  })

  it('clicking a recent project row navigates to the correct /projects/:id route and opens Project Detail', async () => {
    mockHappyPath()
    renderHome()

    const link = await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    link.click()

    await waitFor(() => expect(screen.getByTestId('project-details-probe')).toBeTruthy())
    expect(screen.getByTestId('project-details-probe').textContent).toBe('/projects/WS%2FMP001%2F2023-2024%2F103702')
  })

  it('clicking anywhere in the row (not just the link text) also navigates', async () => {
    mockHappyPath()
    renderHome()

    await screen.findByRole('link', { name: 'WS/MP001/2023-2024/103702' })
    const row = screen.getByText('Road construction').closest('tr')
    row.click()

    await waitFor(() => expect(screen.getByTestId('project-details-probe')).toBeTruthy())
  })

  it('shows an empty state instead of a broken table when there are no recent projects', async () => {
    mockHappyPath()
    fetchPublicOverview.mockResolvedValue({ ...OVERVIEW_WITH_PROJECT, recent_projects: [] })
    renderHome()

    await waitFor(() => expect(screen.getByText(/no monitored projects found/i)).toBeTruthy())
    expect(screen.queryByRole('link', { name: /WS\// })).toBeNull()
  })
})

describe('Home / public KPIs', () => {
  it('renders the five public portfolio KPIs from the public insights contract', async () => {
    mockHappyPath()
    renderHome()

    await screen.findByText('Total Projects')

    expect(screen.getByText('43,863')).toBeTruthy()
    expect(screen.getByText('Completed Works')).toBeTruthy()
    expect(screen.getByText('23,283')).toBeTruthy()
    expect(screen.getByText('Active Works')).toBeTruthy()
    expect(screen.getByText('14,537')).toBeTruthy()
  })

  // NOTE: exact strings, not regexes. The shared <Disclaimer> still
  // carries the sentence "AI Shield identifies indicators requiring
  // review ..." -- that is a generic caveat, not published risk DATA, and
  // is intentionally left alone (it is shared with the authenticated
  // screens). What must be gone is the KPI tile and any real risk value.
  it('never renders the removed risk-derived KPI tile', async () => {
    mockHappyPath()
    renderHome()

    await screen.findByText('Total Projects')

    expect(screen.queryByText('Requiring Review')).toBeNull()
    expect(screen.queryByText('AI Shield indicators')).toBeNull()
    expect(screen.queryByText('Risk Distribution')).toBeNull()
    expect(screen.queryByText('High / Critical Risk Indicators')).toBeNull()
  })

  it('renders no risk level, score or anomaly value anywhere on the public page', async () => {
    mockHappyPath()
    const { container } = renderHome()

    await screen.findByText('Total Projects')

    const text = container.textContent
    const forbidden = [
      'LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
      'Risk Score', 'Risk Level', 'Risk Fusion',
      'Anomaly', 'Isolation Forest', 'Duplicate Score',
      'Why Risky', 'Investigation',
    ]
    for (const token of forbidden) {
      expect(text.includes(token)).toBe(false)
    }
  })

  it('reports works with no recorded lifecycle status instead of hiding them', async () => {
    mockHappyPath()
    renderHome()

    await waitFor(() =>
      expect(screen.getByText(/6,043 works have no recorded lifecycle status/i)).toBeTruthy()
    )
  })

  it('surfaces source-data coverage notes rather than silently filling gaps', async () => {
    mockHappyPath()
    renderHome()

    await waitFor(() =>
      expect(screen.getByText(/Completion dates exist for 22,956 of 43,863 projects/i)).toBeTruthy()
    )
  })
})

describe('Home / state and district insights', () => {
  it('lists state-level public aggregates', async () => {
    mockHappyPath()
    renderHome()

    await waitFor(() => expect(screen.getAllByText('Maharashtra').length).toBeGreaterThan(0))
    expect(screen.getByText('1,408')).toBeTruthy()
  })

  it('drills into a state and shows its districts when a state row is selected', async () => {
    mockHappyPath()
    renderHome()

    await waitFor(() => expect(screen.getAllByText('Maharashtra').length).toBeGreaterThan(0))

    const stateRow = screen.getAllByText('Maharashtra')[0].closest('tr')
    stateRow.click()

    await waitFor(() => expect(screen.getByText('MUMBAI SUBURBAN')).toBeTruthy())
    expect(fetchPublicDistricts).toHaveBeenCalledWith('Maharashtra')
    expect(screen.getByText(/Maharashtra — District Insights/)).toBeTruthy()
  })

  it('shows an explicit message when a state has no district records', async () => {
    mockHappyPath()
    fetchPublicDistricts.mockResolvedValue({ state: 'Maharashtra', districts: [] })
    renderHome()

    await waitFor(() => expect(screen.getAllByText('Maharashtra').length).toBeGreaterThan(0))
    screen.getAllByText('Maharashtra')[0].closest('tr').click()

    await waitFor(() =>
      expect(screen.getByText(/No district-level records exist for this state/i)).toBeTruthy()
    )
  })
})

describe('Home / failure handling', () => {
  it('shows an error instead of zeros when the public insights endpoint fails', async () => {
    fetchPublicOverview.mockResolvedValue(OVERVIEW_WITH_PROJECT)
    fetchPublicInsights.mockRejectedValue(new Error('Backend returned 503 Service Unavailable'))
    fetchPublicDistricts.mockResolvedValue(MAHARASHTRA_DISTRICTS)
    renderHome()

    await waitFor(() =>
      expect(screen.getByText(/Could not load public figures/i)).toBeTruthy()
    )
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
  })
})
