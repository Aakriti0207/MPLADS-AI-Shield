import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../features/public/api', () => ({
  fetchExplorerProjects: vi.fn(),
  fetchExplorerProject: vi.fn(),
  fetchExplorerFilters: vi.fn(),
  fetchPublicMeta: vi.fn(),
  fetchExplorerSummary: vi.fn(),
  fetchExplorerAreas: vi.fn(),
}))

import { fetchExplorerFilters, fetchExplorerProject, fetchExplorerProjects, fetchPublicMeta } from '../../features/public/api'
import PublicProjects from '../public/PublicProjects'
import PublicProjectDetail from '../public/PublicProjectDetail'

const OPTIONS = {
  states: [{ value: 'Bihar', count: 10 }], districts: [{ value: 'PATNA', count: 4 }],
  categories: [{ value: 'Roads & Connectivity', count: 5 }], statuses: [{ value: 'Completed', count: 6 }], years: [{ value: '2024', count: 3 }],
}
const project = (n, extra = {}) => ({
  id: `WS/MP1/2024/${n}`, title: `Road work ${n}`, state: 'Bihar', district: 'PATNA', constituency: 'PATNA SAHIB',
  category: 'Roads & Connectivity', status: 'Ongoing', sanctioned: 1000000, expenditure: 250000, utilisationPercent: 25,
  sanctionDate: '2024-03-01', completionDate: null, ...extra,
})

afterEach(() => { cleanup(); vi.clearAllMocks() })
const setup = (ui, path, route) => render(<MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={ui} /></Routes></MemoryRouter>)

describe('PublicProjects', () => {
  it('requests a server-side page with the URL filters and shows the range', async () => {
    fetchExplorerFilters.mockResolvedValue(OPTIONS)
    fetchPublicMeta.mockResolvedValue({ refreshedAt: null, latestRecordDate: null, sourceNote: null })
    fetchExplorerProjects.mockResolvedValue({ items: [project(1), project(2)], total: 45, page: 2, pageSize: 20, totalPages: 3 })

    setup(<PublicProjects />, '/public/projects?state=Bihar&status=Completed&page=2&q=road', '/public/projects')

    await screen.findByText('Road work 1')
    const args = fetchExplorerProjects.mock.calls[0][0]
    expect(args).toMatchObject({ search: 'road', state: 'Bihar', status: 'Completed', page: 2, pageSize: 20 })
    expect(document.body.textContent).toMatch(/Showing\s*21.?.?40\s*of\s*45/)
    expect(screen.getByRole('button', { name: /Remove filter State: Bihar/ })).toBeTruthy()
  })

  it('shows an empty state with suggestions, never a blank area', async () => {
    fetchExplorerFilters.mockResolvedValue(OPTIONS)
    fetchPublicMeta.mockResolvedValue(null)
    fetchExplorerProjects.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    setup(<PublicProjects />, '/public/projects?q=zzz', '/public/projects')
    expect(await screen.findByText('No projects found')).toBeTruthy()
    expect(screen.getByText(/another district/)).toBeTruthy()
  })

  it('shows a friendly error and retries', async () => {
    fetchExplorerFilters.mockResolvedValue(OPTIONS)
    fetchPublicMeta.mockResolvedValue(null)
    fetchExplorerProjects.mockRejectedValueOnce(new Error('Backend returned 500')).mockResolvedValue({ items: [project(9)], total: 1, page: 1, pageSize: 20, totalPages: 1 })
    setup(<PublicProjects />, '/public/projects', '/public/projects')
    expect(await screen.findByText(/couldn't load project data right now/i)).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Backend returned/)
    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))
    expect(await screen.findByText('Road work 9')).toBeTruthy()
  })

  it('cards show public facts only', async () => {
    fetchExplorerFilters.mockResolvedValue(OPTIONS)
    fetchPublicMeta.mockResolvedValue(null)
    fetchExplorerProjects.mockResolvedValue({ items: [project(1, { expenditure: null, utilisationPercent: null })], total: 1, page: 1, pageSize: 20, totalPages: 1 })
    setup(<PublicProjects />, '/public/projects', '/public/projects')
    await screen.findByText('Road work 1')
    expect(screen.getByText('Not recorded')).toBeTruthy()
    expect(screen.getByText('Patna, Bihar')).toBeTruthy()
    const text = document.body.textContent.toLowerCase()
    for (const w of ['risk', 'anomaly', 'undefined', 'nan']) expect(text).not.toContain(w)
  })
})

describe('PublicProjectDetail', () => {
  it('renders only timeline dates that exist and never fake steps', async () => {
    fetchPublicMeta.mockResolvedValue(null)
    fetchExplorerProject.mockResolvedValue(project(7, {
      description: 'Construction of road', recommendedDate: '2023-12-01', sanctionDate: '2024-03-01',
      firstExpenditureDate: null, lastExpenditureDate: null, completionDate: null,
    }))
    setup(<PublicProjectDetail />, '/public/projects/' + encodeURIComponent('WS/MP1/2024/7'), '/public/projects/:id')
    await screen.findByRole('heading', { level: 1 })
    expect(fetchExplorerProject.mock.calls[0][0]).toBe('WS/MP1/2024/7')
    const timeline = document.getElementById('timeline').parentElement
    expect(timeline.textContent).toMatch(/Recommended/)
    expect(timeline.textContent).toMatch(/Sanctioned/)
    expect(timeline.textContent).not.toMatch(/Completed|First payment|Expected/)
    expect(screen.getByText(/Physical progress.*not part of the public data/i)).toBeTruthy()
  })

  it('shows a clear not-found message for an unknown project', async () => {
    fetchPublicMeta.mockResolvedValue(null)
    fetchExplorerProject.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    setup(<PublicProjectDetail />, '/public/projects/NOPE', '/public/projects/:id')
    expect(await screen.findByText(/couldn't find that project/i)).toBeTruthy()
  })
})