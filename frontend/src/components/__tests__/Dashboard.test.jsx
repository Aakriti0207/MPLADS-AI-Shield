import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../Dashboard'

function mockFetchSequence(handlers) {
  global.fetch = vi.fn((url) => {
    for (const [match, respond] of handlers) {
      if (url.includes(match)) return Promise.resolve(respond())
    }
    return Promise.reject(new Error(`Unmocked fetch: ${url}`))
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  // recharts' ResponsiveContainer needs a ResizeObserver, which jsdom
  // doesn't implement.
  global.ResizeObserver = global.ResizeObserver || class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Dashboard', () => {
  it('shows a loading state before data arrives', () => {
    global.fetch = vi.fn(() => new Promise(() => {})) // never resolves
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(screen.getByText(/Loading dashboard/i)).toBeTruthy()
  })

  it('renders real backend figures and marks unavailable sections honestly (no fabricated data)', async () => {
    mockFetchSequence([
      ['/dashboard/stats', () => ({
        ok: true,
        status: 200,
        json: async () => ({
          total_projects: 43863,
          total_sanctioned_amount: 230400000000,
          total_expenditure: 20800000000,
          risk_level_counts: { LOW: 42196, MEDIUM: 1662, HIGH: 5, CRITICAL: 0 },
          by_state: [{ state: 'Bihar', count: 3960, review_count: 212 }],
        }),
      })],
      ['/projects', () => ({
        ok: true,
        status: 200,
        json: async () => ([{
          project_id: 'WS/MP1042/2024-2025/017', state: 'Bihar', constituency: 'Muzaffarpur',
          mp_name: 'R. K. Choudhary', work_type: 'Health Infrastructure',
          sanctioned_amount: 145000000, expenditure: 129000000, risk_level: 'HIGH',
        }]),
      })],
    ])

    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    expect(await screen.findByText(/MPLADS Project Monitoring/i)).toBeTruthy()
    // Real KPI figures made it through the formatter.
    expect(await screen.findByText('43,863')).toBeTruthy()
    // Requiring Review = HIGH + CRITICAL, derived from real risk_level_counts.
    expect(await screen.findByText('5')).toBeTruthy()
    // Completed Works has no backend source — must say so, never show a number.
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
    // Recently Monitored Projects table renders the real project row.
    expect(await screen.findByText('WS/MP1042/2024-2025/017')).toBeTruthy()
    expect(screen.getByText('Muzaffarpur')).toBeTruthy()
  })

  it('shows an error state with retry when the stats request fails', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, statusText: 'Server Error', json: async () => ({}) }))
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByText(/Could not load dashboard statistics/i)).toBeTruthy()
  })
})
