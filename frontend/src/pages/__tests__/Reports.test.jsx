import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../features/reports/api', () => ({
  fetchReportsMeta: vi.fn(),
  fetchReportPreview: vi.fn(),
  downloadReportFile: vi.fn(),
  downloadProjectReport: vi.fn(),
}))
vi.mock('../../features/dashboard/api', () => ({ fetchDashboardStats: vi.fn() }))

let mockIsDemo = false
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ isDemo: mockIsDemo }) }))

import { fetchReportsMeta, fetchReportPreview, downloadReportFile } from '../../features/reports/api'
import { fetchDashboardStats } from '../../features/dashboard/api'
import Reports from '../Reports'

const META_MINISTRY = {
  role: 'Administrator',
  scope_available: true,
  scope_label: 'National',
  report_types: [
    { id: 'project_monitoring', label: 'Project Monitoring Report', description: 'Portfolio summary.' },
    { id: 'risk_anomaly', label: 'Risk & Anomaly Report', description: 'Risk distribution.' },
  ],
  filters_supported: ['state', 'district', 'constituency', 'category', 'risk_level', 'date_from', 'date_to'],
  export_formats: ['json', 'csv', 'pdf'],
}

const META_UNAVAILABLE = {
  role: 'District Authority',
  scope_available: false,
  unavailable_reason: 'Report generation currently requires national (Ministry/Admin) scope.',
}

const DASHBOARD_STATS = { by_state: [{ state: 'Delhi' }], by_work_type: [{ work_type: 'Road construction' }] }

const SAMPLE_REPORT = {
  report_type: 'project_monitoring',
  title: 'Project Monitoring Report',
  generated_at: '2026-09-14T10:00:00Z',
  scope: 'National',
  filters_applied: {},
  total_projects: 2,
  total_sanctioned_amount: 1500000,
  total_expenditure: 900000,
  average_financial_progress: 60,
  risk_level_counts: { HIGH: 1, LOW: 1 },
  projects_requiring_review: 1,
  duplicate_indicators: 0,
  anomaly_indicators: 1,
  priority_projects: [
    {
      project_id: 'WS/TEST/000001',
      work_type: 'Road construction',
      state: 'Delhi',
      constituency: 'New Delhi',
      sanctioned_amount: 1000000,
      expenditure: 400000,
      financial_progress: 40,
      risk_level: 'HIGH',
      risk_score: 70,
      risk_reasons: ['Expenditure recorded without a matching sanction record.'],
    },
  ],
  data_quality_notes: [],
  disclaimer: 'AI Shield identifies indicators that may require review. It does not establish fraud, wrongdoing, or non-compliance.',
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  mockIsDemo = false
})

function renderReports() {
  return render(<Reports />)
}

describe('Reports page availability', () => {
  it('shows the unavailable message for demo mode without calling the backend', async () => {
    mockIsDemo = true
    renderReports()

    await waitFor(() => expect(screen.getByText('Scoped reporting is not available for this account.')).toBeTruthy())
    expect(fetchReportsMeta).not.toHaveBeenCalled()
  })

  it('shows the unavailable message for a non-Ministry/Admin account, using the backend-provided reason', async () => {
    fetchReportsMeta.mockResolvedValue(META_UNAVAILABLE)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    renderReports()

    await waitFor(() => expect(screen.getByText('Report generation currently requires national (Ministry/Admin) scope.')).toBeTruthy())
    expect(screen.queryByText('Generate Report')).toBeNull()
  })

  it('shows an error state if GET /reports/meta fails', async () => {
    fetchReportsMeta.mockRejectedValue(new Error('Backend returned 500 Internal Server Error'))
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    renderReports()

    await waitFor(() => expect(screen.getByText(/Backend returned 500/)).toBeTruthy())
  })
})

describe('Reports page generation (Ministry/Admin)', () => {
  it('renders only the real, backend-supplied report types -- no invented options', async () => {
    fetchReportsMeta.mockResolvedValue(META_MINISTRY)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    renderReports()

    await waitFor(() => expect(screen.getByText('Project Monitoring Report')).toBeTruthy())
    expect(screen.getByText('Risk & Anomaly Report')).toBeTruthy()
  })

  it('shows "Generating report…" while awaiting the backend, then renders real data on success', async () => {
    fetchReportsMeta.mockResolvedValue(META_MINISTRY)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    let resolvePreview
    fetchReportPreview.mockReturnValue(new Promise(res => { resolvePreview = res }))
    renderReports()

    const generateButton = await screen.findByRole('button', { name: 'Generate Report' })
    fireEvent.click(generateButton)

    await waitFor(() => expect(screen.getByText('Generating report…')).toBeTruthy())
    resolvePreview(SAMPLE_REPORT)

    await waitFor(() => expect(screen.getByText('Report generated successfully.')).toBeTruthy())
    expect(screen.getByText('WS/TEST/000001', { exact: false })).toBeTruthy()
    expect(screen.getByText(/does not establish fraud/i)).toBeTruthy()
  })

  it('shows the backend error message (e.g. 403) instead of crashing or faking success', async () => {
    fetchReportsMeta.mockResolvedValue(META_MINISTRY)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    fetchReportPreview.mockRejectedValue(new Error('You do not have permission to generate this report.'))
    renderReports()

    const generateButton = await screen.findByRole('button', { name: 'Generate Report' })
    fireEvent.click(generateButton)

    await waitFor(() => expect(screen.getByText('You do not have permission to generate this report.')).toBeTruthy())
    expect(screen.queryByText('Report generated successfully.')).toBeNull()
  })

  it('downloads a real CSV file via the authenticated API, not a client-side fake', async () => {
    fetchReportsMeta.mockResolvedValue(META_MINISTRY)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    fetchReportPreview.mockResolvedValue(SAMPLE_REPORT)
    downloadReportFile.mockResolvedValue(undefined)
    renderReports()

    fireEvent.click(await screen.findByRole('button', { name: 'Generate Report' }))
    await waitFor(() => expect(screen.getByText('Report generated successfully.')).toBeTruthy())

    fireEvent.click(screen.getByText('Download CSV'))
    await waitFor(() => expect(downloadReportFile).toHaveBeenCalledWith(
      expect.objectContaining({ reportType: 'project_monitoring' }),
      'csv',
    ))
  })

  it('shows an empty-state message instead of a fake report history table', async () => {
    fetchReportsMeta.mockResolvedValue(META_MINISTRY)
    fetchDashboardStats.mockResolvedValue(DASHBOARD_STATS)
    renderReports()

    await waitFor(() => expect(screen.getByText('Report history is not currently stored by the backend.')).toBeTruthy())
  })
})