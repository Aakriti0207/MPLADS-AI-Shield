import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ---------------------------------------------------------------------
// Test doubles
// ---------------------------------------------------------------------
// Leaflet needs a real layout engine; the behaviour under test here is
// which requests the page makes and what it renders from the answers.
const mockFitBounds = vi.fn()
// react-leaflet's useMap() hands back the same map instance on every
// render, so the double must be referentially stable too.
const mockMap = { fitBounds: mockFitBounds }

vi.mock('leaflet', () => ({
  default: { Icon: { Default: { prototype: {}, mergeOptions: vi.fn() } } },
}))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Marker: ({ children, position }) => (
    <div data-testid="marker" data-position={position.join(',')}>{children}</div>
  ),
  Popup: ({ children }) => <div>{children}</div>,
  useMap: () => mockMap,
}))

let mockAuth = { status: 'authenticated', isAuthenticated: true, isDemo: false }
vi.mock('../../context/AuthContext', () => ({ useAuth: () => mockAuth }))

vi.mock('../../features/projects/api', () => ({
  fetchProjectPage: vi.fn(),
  fetchDemoProjectPage: vi.fn(),
  fetchPublicProjectPage: vi.fn(),
  fetchProjectFilterOptions: vi.fn(),
  fetchDemoProjectFilterOptions: vi.fn(),
}))

import {
  fetchProjectPage,
  fetchDemoProjectPage,
  fetchPublicProjectPage,
  fetchProjectFilterOptions,
  fetchDemoProjectFilterOptions,
} from '../../features/projects/api'
import MapPage from '../MapPage'

// ---------------------------------------------------------------------
// Fixtures -- already in normalizeProject() shape, which is what the
// api layer hands the page.
// ---------------------------------------------------------------------
function project(id, overrides = {}) {
  return {
    id,
    state: 'Bihar',
    district: 'Samastipur',
    constituency: 'Ujiarpur',
    workType: 'Roads & Connectivity',
    status: 'Ongoing',
    risk: 'Low',
    latitude: 25.86,
    longitude: 85.78,
    raw: { location_precision: 'district_centroid' },
    ...overrides,
  }
}

const PAGE = (items, total = items.length, extra = {}) => ({ items, total, skip: 0, limit: 100, ...extra })

const NATIONAL_OPTIONS = {
  states: ['Bihar', 'Maharashtra'],
  districts: ['Patna', 'Pune', 'Samastipur'],
  constituencies: ['Patna Sahib', 'Pune', 'Ujiarpur'],
  locked_filters: [],
  scope: null,
}

// Emulates the backend cascade: districts/constituencies narrow with the
// selected state / district.
function cascadingOptions(cascade = {}) {
  const byState = {
    Bihar: { districts: ['Patna', 'Samastipur'], constituencies: ['Patna Sahib', 'Ujiarpur'] },
    Maharashtra: { districts: ['Pune'], constituencies: ['Pune'] },
  }
  const state = cascade.state && cascade.state !== 'All' ? cascade.state : null
  const district = cascade.district && cascade.district !== 'All' ? cascade.district : null
  const picked = state ? byState[state] : null
  return Promise.resolve({
    ...NATIONAL_OPTIONS,
    districts: picked ? picked.districts : NATIONAL_OPTIONS.districts,
    constituencies: district === 'Samastipur'
      ? ['Ujiarpur']
      : picked ? picked.constituencies : NATIONAL_OPTIONS.constituencies,
  })
}

function lastCall(mock) {
  const calls = mock.mock.calls
  return calls[calls.length - 1][0]
}

function renderMap() {
  return render(<MemoryRouter><MapPage /></MemoryRouter>)
}

async function loaded() {
  await waitFor(() => expect(screen.queryByText('Loading project locations…')).toBeNull())
}

beforeEach(() => {
  mockAuth = { status: 'authenticated', isAuthenticated: true, isDemo: false }
  fetchProjectPage.mockResolvedValue(PAGE([project('WS/1'), project('WS/2')]))
  fetchDemoProjectPage.mockResolvedValue(PAGE([project('WS/D1')]))
  fetchPublicProjectPage.mockResolvedValue(PAGE([project('WS/P1')]))
  fetchProjectFilterOptions.mockImplementation(cascadingOptions)
  fetchDemoProjectFilterOptions.mockImplementation(cascadingOptions)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------
// API routing: authenticated vs demo vs public
// ---------------------------------------------------------------------
describe('MapPage data source', () => {
  it('authenticated: uses the protected query + options endpoints, bounded, unfiltered', async () => {
    renderMap()
    await loaded()

    expect(fetchProjectPage).toHaveBeenCalledTimes(1)
    expect(lastCall(fetchProjectPage)).toMatchObject({
      skip: 0,
      limit: 100,
      state: 'All',
      district: 'All',
      constituency: 'All',
      riskLevel: 'All',
      search: '',
    })
    expect(fetchProjectFilterOptions).toHaveBeenCalled()
    expect(fetchDemoProjectPage).not.toHaveBeenCalled()
    expect(fetchDemoProjectFilterOptions).not.toHaveBeenCalled()
    expect(fetchPublicProjectPage).not.toHaveBeenCalled()
    expect(screen.getAllByTestId('marker')).toHaveLength(2)
  })

  it('demo: uses ONLY the demo endpoints and never the protected ones', async () => {
    mockAuth = { status: 'authenticated', isAuthenticated: true, isDemo: true }
    renderMap()
    await loaded()

    expect(fetchDemoProjectPage).toHaveBeenCalledTimes(1)
    expect(fetchDemoProjectFilterOptions).toHaveBeenCalled()
    expect(fetchProjectPage).not.toHaveBeenCalled()
    expect(fetchProjectFilterOptions).not.toHaveBeenCalled()
    expect(fetchPublicProjectPage).not.toHaveBeenCalled()
    expect(screen.getAllByTestId('marker')).toHaveLength(1)
  })

  it('demo: filters are sent to the demo endpoint too', async () => {
    mockAuth = { status: 'authenticated', isAuthenticated: true, isDemo: true }
    renderMap()
    await loaded()

    await screen.findByRole('option', { name: 'Bihar' })
    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    await waitFor(() => expect(lastCall(fetchDemoProjectPage)).toMatchObject({ state: 'Bihar' }))
    fireEvent.click(screen.getByRole('button', { name: 'High' }))
    await waitFor(() => expect(lastCall(fetchDemoProjectPage)).toMatchObject({ state: 'Bihar', riskLevel: 'High' }))
    expect(fetchProjectPage).not.toHaveBeenCalled()
  })

  it('public fallback: uses the anonymous endpoint and offers only search (no risk, no dropdowns)', async () => {
    mockAuth = { status: 'unauthenticated', isAuthenticated: false, isDemo: false }
    renderMap()
    await loaded()

    expect(fetchPublicProjectPage).toHaveBeenCalledTimes(1)
    expect(fetchProjectPage).not.toHaveBeenCalled()
    expect(fetchDemoProjectPage).not.toHaveBeenCalled()
    expect(fetchProjectFilterOptions).not.toHaveBeenCalled()
    expect(fetchDemoProjectFilterOptions).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'High' })).toBeNull()
    expect(screen.queryByLabelText('State')).toBeNull()
    expect(screen.getByLabelText('Search')).toBeTruthy()
  })

  it('does not fire any request while auth is still being checked', async () => {
    mockAuth = { status: 'checking', isAuthenticated: false, isDemo: false }
    renderMap()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(fetchProjectPage).not.toHaveBeenCalled()
    expect(fetchDemoProjectPage).not.toHaveBeenCalled()
    expect(fetchPublicProjectPage).not.toHaveBeenCalled()
    expect(fetchProjectFilterOptions).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------
// State / district / constituency
// ---------------------------------------------------------------------
describe('MapPage location filters', () => {
  it('district and constituency wait for a state, then cascade from it', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })

    // National view: nothing to pick until a state is chosen.
    expect(screen.getByLabelText('District').disabled).toBe(true)
    expect(screen.getByLabelText('Constituency').disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ state: 'Bihar' }))
    await waitFor(() => expect(lastCall(fetchProjectFilterOptions)).toMatchObject({ state: 'Bihar' }))

    await screen.findByRole('option', { name: 'Samastipur' })
    // Only Bihar's districts are offered, not Pune.
    expect(screen.queryByRole('option', { name: 'Pune' })).toBeNull()
    expect(screen.getByLabelText('District').disabled).toBe(false)

    fireEvent.change(screen.getByLabelText('District'), { target: { value: 'Samastipur' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ state: 'Bihar', district: 'Samastipur' }))
    await waitFor(() => expect(lastCall(fetchProjectFilterOptions)).toMatchObject({ state: 'Bihar', district: 'Samastipur' }))

    await waitFor(() => expect(screen.getByLabelText('Constituency').disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('Constituency'), { target: { value: 'Ujiarpur' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({
      state: 'Bihar',
      district: 'Samastipur',
      constituency: 'Ujiarpur',
    }))
  })

  it('changing the state clears the district and constituency', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    await screen.findByRole('option', { name: 'Samastipur' })
    fireEvent.change(screen.getByLabelText('District'), { target: { value: 'Samastipur' } })
    await waitFor(() => expect(screen.getByLabelText('Constituency').disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('Constituency'), { target: { value: 'Ujiarpur' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ constituency: 'Ujiarpur' }))

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Maharashtra' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({
      state: 'Maharashtra',
      district: 'All',
      constituency: 'All',
    }))
  })

  it('changing the district clears only the constituency', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    await screen.findByRole('option', { name: 'Samastipur' })
    fireEvent.change(screen.getByLabelText('District'), { target: { value: 'Samastipur' } })
    await waitFor(() => expect(screen.getByLabelText('Constituency').disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('Constituency'), { target: { value: 'Ujiarpur' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ constituency: 'Ujiarpur' }))

    fireEvent.change(screen.getByLabelText('District'), { target: { value: 'Patna' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({
      state: 'Bihar',
      district: 'Patna',
      constituency: 'All',
    }))
  })
})

// ---------------------------------------------------------------------
// RBAC: locked dimensions
// ---------------------------------------------------------------------
describe('MapPage role-aware filters', () => {
  it('a district-scoped account sees fixed labels, not dropdowns, for state and district', async () => {
    fetchProjectFilterOptions.mockResolvedValue({
      states: ['Bihar'],
      districts: ['Samastipur'],
      constituencies: ['Ujiarpur'],
      locked_filters: ['state', 'district'],
      scope: { type: 'district', state: 'Bihar', district: 'Samastipur' },
    })
    renderMap()
    await loaded()

    await screen.findByText('Samastipur')
    expect(screen.queryByLabelText('State')).toBeNull()
    expect(screen.queryByLabelText('District')).toBeNull()
    expect(screen.getByText('Bihar')).toBeTruthy()
    expect(screen.getByText('Samastipur')).toBeTruthy()
    // Nothing else about the scope is offered as a choice they could not use,
    // and the fixed values are never sent as user-chosen filters.
    expect(lastCall(fetchProjectPage)).toMatchObject({ state: 'All', district: 'All' })
    // The constituency inside their district is still selectable.
    expect(screen.getByLabelText('Constituency').disabled).toBe(false)
  })

  it('an MP-scoped account sees a fixed constituency and no "All States" selector', async () => {
    fetchProjectFilterOptions.mockResolvedValue({
      states: ['Bihar'],
      districts: ['Samastipur', 'Muzaffarpur'],
      constituencies: ['Ujiarpur'],
      locked_filters: ['state', 'constituency'],
      scope: { type: 'constituency', state: 'Bihar', constituency: 'Ujiarpur', mp_name: 'Test MP' },
    })
    renderMap()
    await loaded()

    await screen.findByText('Ujiarpur')
    expect(screen.queryByLabelText('State')).toBeNull()
    expect(screen.queryByLabelText('Constituency')).toBeNull()
    expect(screen.getByLabelText('District').disabled).toBe(false)
  })

  it('a 403 from the backend for a filter surfaces as an error, not stale data', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })

    fetchProjectPage.mockRejectedValueOnce(new Error('Backend returned 403 Forbidden'))
    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Maharashtra' } })
    await screen.findByText('Unable to load project locations.')
    expect(screen.queryByTestId('marker')).toBeNull()
  })
})

// ---------------------------------------------------------------------
// Risk level: server-side
// ---------------------------------------------------------------------
describe('MapPage risk filter', () => {
  it('is sent to the server, and the page renders exactly what the server returns', async () => {
    renderMap()
    await loaded()
    expect(screen.getAllByTestId('marker')).toHaveLength(2)

    // The server answers with a single HIGH project.
    fetchProjectPage.mockResolvedValueOnce(PAGE([project('WS/H1', { risk: 'High' })], 1))
    fireEvent.click(screen.getByRole('button', { name: 'High' }))

    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ riskLevel: 'High' }))
    await waitFor(() => expect(screen.getAllByTestId('marker')).toHaveLength(1))
    expect(screen.getByRole('button', { name: 'High' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('does not filter the server response again in the browser', async () => {
    renderMap()
    await loaded()

    // Deliberately "wrong" rows for the selected level: a client-side
    // filter would hide the Low one. The server is the authority.
    fetchProjectPage.mockResolvedValueOnce(
      PAGE([project('WS/A', { risk: 'High' }), project('WS/B', { risk: 'Low' })], 2),
    )
    fireEvent.click(screen.getByRole('button', { name: 'High' }))
    await waitFor(() => expect(screen.getAllByTestId('marker')).toHaveLength(2))
  })

  it('All clears the risk filter', async () => {
    renderMap()
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'Medium' }))
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ riskLevel: 'Medium' }))
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ riskLevel: 'All' }))
  })
})

// ---------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------
describe('MapPage search', () => {
  it('debounces typing into a single request with the final text', async () => {
    renderMap()
    await loaded()
    const before = fetchProjectPage.mock.calls.length

    const input = screen.getByLabelText('Search')
    fireEvent.change(input, { target: { value: 'WS' } })
    fireEvent.change(input, { target: { value: 'WS/MP1' } })
    fireEvent.change(input, { target: { value: 'WS/MP1/2023-2024/103702' } })

    // Nothing has been requested yet -- still inside the debounce window.
    expect(fetchProjectPage.mock.calls.length).toBe(before)

    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ search: 'WS/MP1/2023-2024/103702' }))
    const searched = fetchProjectPage.mock.calls.filter(([q]) => q.search)
    expect(searched).toHaveLength(1)
  })

  it('caps the input at the backend limit of 120 characters', async () => {
    renderMap()
    await loaded()
    expect(screen.getByLabelText('Search').getAttribute('maxlength')).toBe('120')
  })

  it('search combines with the other filters in one request', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    fireEvent.click(screen.getByRole('button', { name: 'Medium' }))
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'school' } })

    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({
      state: 'Bihar',
      riskLevel: 'Medium',
      search: 'school',
    }))
  })

  it('keeps the search box and the map mounted while a new result loads', async () => {
    renderMap()
    await loaded()

    let resolve
    fetchProjectPage.mockReturnValueOnce(new Promise(r => { resolve = r }))
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))

    // Still showing the previous markers; the filter bar never unmounted.
    expect(screen.getAllByTestId('marker')).toHaveLength(2)
    expect(screen.getByLabelText('Search')).toBeTruthy()
    await screen.findByText('Updating…')

    resolve(PAGE([project('WS/NEW')]))
    await waitFor(() => expect(screen.queryByText('Updating…')).toBeNull())
    expect(screen.getAllByTestId('marker')).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------
describe('MapPage reset', () => {
  it('is disabled until a filter is active, then clears everything', async () => {
    renderMap()
    await loaded()
    await screen.findByRole('option', { name: 'Bihar' })
    const reset = screen.getByRole('button', { name: 'Reset filters' })
    expect(reset.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'Bihar' } })
    fireEvent.click(screen.getByRole('button', { name: 'High' }))
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'road' } })
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({ search: 'road', riskLevel: 'High', state: 'Bihar' }))
    expect(screen.getByRole('button', { name: 'Reset filters' }).disabled).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'Reset filters' }))
    await waitFor(() => expect(lastCall(fetchProjectPage)).toMatchObject({
      state: 'All',
      district: 'All',
      constituency: 'All',
      riskLevel: 'All',
      search: '',
    }))
    expect(screen.getByLabelText('Search').value).toBe('')
    expect(screen.getByLabelText('State').value).toBe('All')
  })
})

// ---------------------------------------------------------------------
// Results, counts and Phase 2 coordinates
// ---------------------------------------------------------------------
describe('MapPage results', () => {
  it('reports the true server total when the page is only part of the matches', async () => {
    fetchProjectPage.mockResolvedValue(PAGE([project('WS/1'), project('WS/2')], 250))
    renderMap()
    await loaded()
    expect(screen.getByTestId('map-summary').textContent).toBe(
      'Showing the first 2 of 250 matching projects. Narrow the filters or search to see others.',
    )
  })

  it('states the plain match count when everything fits on the page', async () => {
    renderMap()
    await loaded()
    expect(screen.getByTestId('map-summary').textContent).toBe('2 matching projects.')
  })

  it('plots only projects that have coordinates and says how many were left out', async () => {
    fetchProjectPage.mockResolvedValue(PAGE([
      project('WS/1'),
      project('WS/2', { latitude: null, longitude: null }),
    ]))
    renderMap()
    await loaded()
    expect(screen.getAllByTestId('marker')).toHaveLength(1)
    expect(screen.getByText(/1 of these has no coordinates and is not plotted/)).toBeTruthy()
  })

  it('keeps the Phase 2 approximate-location labelling in the popup', async () => {
    fetchProjectPage.mockResolvedValue(PAGE([
      project('WS/1', { raw: { location_precision: 'district_centroid' } }),
      project('WS/2', { raw: { location_precision: 'state_centroid' } }),
    ]))
    renderMap()
    await loaded()
    expect(screen.getByText('Approximate location (district-level)')).toBeTruthy()
    expect(screen.getByText('Approximate location (state-level)')).toBeTruthy()
    expect(screen.getAllByTestId('marker')[0].getAttribute('data-position')).toBe('25.86,85.78')
  })

  it('shows an empty-state message (the backend one when supplied) instead of an empty map', async () => {
    fetchProjectPage.mockResolvedValue(PAGE([], 0))
    renderMap()
    await loaded()
    expect(screen.getByText('No projects match the current filters.')).toBeTruthy()
    expect(screen.queryByTestId('map')).toBeNull()

    cleanup()
    fetchProjectPage.mockResolvedValue(PAGE([], 0, { empty_state_message: 'No jurisdiction assigned.' }))
    renderMap()
    await loaded()
    expect(screen.getByText('No jurisdiction assigned.')).toBeTruthy()
  })

  it('does not re-fit the map on unrelated re-renders such as typing', async () => {
    renderMap()
    await loaded()
    await waitFor(() => expect(mockFitBounds).toHaveBeenCalled())
    const fits = mockFitBounds.mock.calls.length

    const input = screen.getByLabelText('Search')
    fireEvent.change(input, { target: { value: 'a' } })
    fireEvent.change(input, { target: { value: 'ab' } })
    expect(mockFitBounds.mock.calls.length).toBe(fits)
  })
})

// ---------------------------------------------------------------------
// Failure handling
// ---------------------------------------------------------------------
describe('MapPage failures', () => {
  it('shows an error when the project request fails, but keeps the filter bar', async () => {
    fetchProjectPage.mockRejectedValue(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderMap()
    await screen.findByText('Unable to load project locations.')
    expect(screen.getByLabelText('Search')).toBeTruthy()
  })

  it('still works when the option lists cannot be loaded (search + risk only)', async () => {
    fetchProjectFilterOptions.mockRejectedValue(new Error('options down'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderMap()
    await loaded()
    expect(screen.getAllByTestId('marker')).toHaveLength(2)
    expect(screen.queryByLabelText('State')).toBeNull()
    expect(screen.getByLabelText('Search')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'High' })).toBeTruthy()
  })
})