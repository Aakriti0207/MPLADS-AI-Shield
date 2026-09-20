import React from 'react'
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap
} from 'react-leaflet'
import L from 'leaflet'
import { Link } from 'react-router-dom'
import { RiskBadge, StatusBadge } from '../components/UI'
import {
  fetchProjectPage as fetchProjectPageApi,
  fetchDemoProjectPage as fetchDemoProjectPageApi,
  fetchPublicProjectPage as fetchPublicProjectPageApi,
  fetchProjectFilterOptions as fetchProjectFilterOptionsApi,
  fetchDemoProjectFilterOptions as fetchDemoProjectFilterOptionsApi,
} from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'
import MapFilters from '../components/map/MapFilters'
import { useAuth } from '../context/AuthContext'

delete L.Icon.Default.prototype._getIconUrl

// Project coordinates are administrative-area centroids (see
// location_precision below), not real per-project GPS points, so it is
// normal/expected for dozens of projects to share the exact same
// lat/lng. Leaflet's default marker SHADOW is a translucent PNG; when
// many markers land on the identical pixel, their shadows compose on
// top of one another and the compounded translucency reads as a solid
// black blob next to the pin. Disabling the shadow (shadowUrl: null)
// removes that artifact without changing marker placement, popups, or
// any other map behavior -- the icon itself is unaffected.
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: null,
})

function FitBounds({ projects }) {
  const map = useMap()

  React.useEffect(() => {
    const validProjects = projects.filter(p => p.latitude != null && p.longitude != null)
    if (validProjects.length > 0) {
      const bounds = validProjects.map(p => [Number(p.latitude), Number(p.longitude)])
      map.fitBounds(bounds, { padding: [30, 30] })
    }
  }, [map, projects])

  return null
}

// Markers plotted per request. Filtering is done by the server, so this is
// only a payload bound, not a filter: the page always reports the true
// number of matches, and narrowing the filters brings the rest into view.
// (The anonymous public API caps a page at 100 as well.)
const MAP_PAGE_LIMIT = 100
const SEARCH_DEBOUNCE_MS = 350

// location_precision is never a literal project coordinate -- see
// app/geo_centroids.py on the backend. Both values below are
// administrative-area centroids, so the map must label them as
// approximate rather than implying a project-specific location.
const LOCATION_PRECISION_LABEL = {
  district_centroid: 'Approximate location (district-level)',
  state_centroid: 'Approximate location (state-level)',
}

export default function MapPage() {
  // Demo sessions carry no real JWT and must never hit the protected
  // /projects endpoint (it would just 401). Real authenticated users
  // must never be routed to the demo/public data. This mirrors the
  // apiMode selection already used by Projects.jsx.
  const { status, isAuthenticated, isDemo } = useAuth()
  const authReady = status !== 'checking'
  const useProtectedApi = isAuthenticated && !isDemo
  const useDemoApi = isAuthenticated && isDemo

  const apiMode = useDemoApi ? 'demo' : useProtectedApi ? 'protected' : 'public'
  // The anonymous public API never exposes Risk Fusion data and has no
  // filter-options endpoint, so neither the risk filter nor the location
  // dropdowns are offered there -- only free-text search.
  const showRisk = apiMode !== 'public'
  const showLocation = apiMode !== 'public'

  const [projects, setProjects] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [stateFilter, setStateFilter] = React.useState('All')
  const [districtFilter, setDistrictFilter] = React.useState('All')
  const [constituencyFilter, setConstituencyFilter] = React.useState('All')
  const [risk, setRisk] = React.useState('All')
  const [rawSearch, setRawSearch] = React.useState('')
  const [debouncedSearch, setDebouncedSearch] = React.useState('')
  // Scope-aware option lists + which dimensions the caller's jurisdiction
  // fixes, both supplied by the backend (never derived from the loaded rows).
  const [options, setOptions] = React.useState({ states: [], districts: [], constituencies: [] })
  const [lockedFilters, setLockedFilters] = React.useState([])
  const [scope, setScope] = React.useState(null)
  const [scopeMessage, setScopeMessage] = React.useState(null)
  // `loading` = nothing to show yet (first load only). `refreshing` = a
  // newer result is being fetched while the previous map stays on screen,
  // so typing or picking a filter never unmounts the map or the filter bar.
  const [loading, setLoading] = React.useState(true)
  const [refreshing, setRefreshing] = React.useState(false)
  const [error, setError] = React.useState('')

  // Debounce free-text search so a keystroke is not a request.
  React.useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(rawSearch.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [rawSearch])

  // Load the scope-aware option lists. Re-runs when the state or district
  // changes so the district / constituency lists cascade. Real users get
  // GET /projects/filter-options (restricted to their own jurisdiction);
  // demo sessions carry no JWT and use the unscoped demo twin instead.
  // Progressive enhancement only: if this fails the map still works, the
  // backend scopes and validates every filter regardless.
  React.useEffect(() => {
    if (!authReady || !showLocation) return
    let cancelled = false
    const fetchOptions = useDemoApi ? fetchDemoProjectFilterOptionsApi : fetchProjectFilterOptionsApi
    fetchOptions({ state: stateFilter, district: districtFilter })
      .then(data => {
        if (cancelled || !data) return
        setOptions({
          states: Array.isArray(data.states) ? data.states : [],
          districts: Array.isArray(data.districts) ? data.districts : [],
          constituencies: Array.isArray(data.constituencies) ? data.constituencies : [],
        })
        setLockedFilters(Array.isArray(data.locked_filters) ? data.locked_filters : [])
        if (data.scope) setScope(data.scope)
      })
      .catch(err => { if (!cancelled) console.error('Map filter options error:', err) })
    return () => { cancelled = true }
  }, [authReady, showLocation, useDemoApi, stateFilter, districtFilter])

  // Server-side filtering: every filter below is a query parameter of the
  // /query endpoints, so each request returns one bounded page of the
  // already-narrowed result instead of the whole dataset. RBAC scope is
  // applied by the backend first; these can only narrow it further.
  const query = React.useMemo(() => ({
    skip: 0,
    limit: MAP_PAGE_LIMIT,
    state: stateFilter,
    district: districtFilter,
    constituency: constituencyFilter,
    riskLevel: risk,
    search: debouncedSearch,
    // The canonical universe is sorted alphabetically by state/district,
    // so a plain first-100 page can sit entirely inside one or two
    // states and make the rest of the map look empty. This asks the
    // backend to spread the 100 markers across the whole filtered set
    // instead. Harmless once a state/district/constituency is picked --
    // the filtered set is already narrow, so the spread just covers it
    // evenly rather than changing what's included.
    spreadSample: true,
  }), [stateFilter, districtFilter, constituencyFilter, risk, debouncedSearch])

  React.useEffect(() => {
    // MapPage only ever renders behind ProtectedRoute, so `status` is
    // effectively always 'authenticated' by the time this mounts --
    // this guard just avoids firing a request before that's settled.
    if (!authReady) return

    let cancelled = false
    setRefreshing(true)
    setError('')

    // Demo sessions carry no real JWT and must never hit the protected
    // /projects endpoint (it would just 401). Real authenticated users
    // must never be routed to the demo/public data. The endpoint choice
    // mirrors the apiMode selection used by Projects.jsx.
    const request = useDemoApi
      ? fetchDemoProjectPageApi(query)
      : useProtectedApi
        ? fetchProjectPageApi(query)
        // Defensive fallback only -- MapPage is never reachable by an
        // anonymous visitor (see app/routes.jsx), but if it ever is,
        // this keeps the page working off the anonymous-safe endpoint
        // instead of throwing on a missing token.
        : fetchPublicProjectPageApi(query)

    request
      .then(page => {
        if (cancelled) return
        const items = page.items || []
        setProjects(items.map(p => ({ ...p, project_id: p.id, risk_level: p.risk, work_type: p.workType })))
        setTotal(page.total ?? items.length)
        setScopeMessage(page.empty_state_message || null)
        if (page.scope) setScope(page.scope)
      })
      .catch(err => { if (!cancelled) { console.error('Map projects error:', err); setError('Unable to load project locations.') } })
      .finally(() => { if (!cancelled) { setLoading(false); setRefreshing(false) } })
    return () => { cancelled = true }
  }, [authReady, useProtectedApi, useDemoApi, query])

  // Memoised so FitBounds only re-fits when the plotted set actually
  // changes -- not on every keystroke in the search box.
  const mappedProjects = React.useMemo(
    () => projects.filter(project => project.latitude != null && project.longitude != null),
    [projects],
  )
  const unmappedCount = projects.length - mappedProjects.length

  // Choosing a broader level clears the narrower ones: their option lists
  // are cascaded from it, so the old value would no longer be valid.
  function handleStateChange(value) {
    setStateFilter(value)
    setDistrictFilter('All')
    setConstituencyFilter('All')
  }

  function handleDistrictChange(value) {
    setDistrictFilter(value)
    setConstituencyFilter('All')
  }

  function handleReset() {
    setStateFilter('All')
    setDistrictFilter('All')
    setConstituencyFilter('All')
    setRisk('All')
    setRawSearch('')
    setDebouncedSearch('')
  }

  const canReset =
    stateFilter !== 'All' ||
    districtFilter !== 'All' ||
    constituencyFilter !== 'All' ||
    risk !== 'All' ||
    rawSearch !== ''

  return (
    <PageContainer>
      <div className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">Project Map</h1>
        <p className="text-[13px] text-muted mt-0.5">Explore project distribution and risk signals across India.</p>
      </div>

      <MapFilters
        state={stateFilter}
        district={districtFilter}
        constituency={constituencyFilter}
        risk={risk}
        search={rawSearch}
        onStateChange={handleStateChange}
        onDistrictChange={handleDistrictChange}
        onConstituencyChange={setConstituencyFilter}
        onRiskChange={setRisk}
        onSearchChange={setRawSearch}
        onReset={handleReset}
        canReset={canReset}
        options={options}
        lockedFilters={lockedFilters}
        scope={scope}
        showRisk={showRisk}
        showLocation={showLocation}
      />

      {loading && <div className="card p-8 text-center text-muted text-sm">Loading project locations…</div>}

      {!loading && error && <div className="card p-8 text-center text-sm" style={{ color: '#c0392b' }}>{error}</div>}

      {!loading && !error && projects.length === 0 && (
        <div className="card p-8 text-center text-sm text-muted" role="status">
          {scopeMessage || 'No projects match the current filters.'}
        </div>
      )}

      {!loading && !error && projects.length > 0 && (
        <>
          <div className="card overflow-hidden relative">
            {refreshing && (
              <div
                className="absolute top-3 right-3 z-[1000] rounded-md bg-white/90 border border-line px-2.5 py-1 text-xs text-muted shadow-sm"
                role="status"
              >
                Updating…
              </div>
            )}
            <div className={`h-[600px] transition-opacity ${refreshing ? 'opacity-60' : ''}`}>
              <MapContainer center={[22.5, 79]} zoom={5} scrollWheelZoom className="h-full w-full">
                <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <FitBounds projects={mappedProjects} />
                {mappedProjects.map(project => {
                  const precisionLabel = LOCATION_PRECISION_LABEL[project.raw?.location_precision] || null
                  return (
                    <Marker key={project.project_id} position={[Number(project.latitude), Number(project.longitude)]}>
                      <Popup>
                        <div className="min-w-[210px]">
                          <div className="font-semibold text-[13px]">{project.work_type || 'MPLADS Project'}</div>
                          <div className="text-xs text-muted mt-1 font-mono">{project.project_id}</div>
                          <div className="text-xs text-muted mt-1">{project.district || 'District unavailable'}, {project.state || 'State unavailable'}</div>
                          <div className="flex gap-1.5 mt-2.5">
                            {project.status && <StatusBadge status={project.status} />}
                            {project.risk_level && <RiskBadge risk={project.risk_level} />}
                          </div>
                          {precisionLabel && (
                            <div className="text-[10px] text-muted mt-2 italic">{precisionLabel}</div>
                          )}
                          <Link className="text-xs font-semibold text-navy inline-block mt-2.5" to={`/projects/${encodeURIComponent(project.project_id)}`}>Open project →</Link>
                        </div>
                      </Popup>
                    </Marker>
                  )
                })}
              </MapContainer>
            </div>
          </div>
          <div className="mt-2.5 text-xs text-muted" aria-live="polite">
            <span data-testid="map-summary">
              {total > projects.length
                ? `Showing the first ${projects.length.toLocaleString()} of ${total.toLocaleString()} matching projects. Narrow the filters or search to see others.`
                : `${total.toLocaleString()} matching ${total === 1 ? 'project' : 'projects'}.`}
            </span>
            {unmappedCount > 0 && ` ${unmappedCount.toLocaleString()} of these ${unmappedCount === 1 ? 'has' : 'have'} no coordinates and ${unmappedCount === 1 ? 'is' : 'are'} not plotted.`}
            {mappedProjects.some(p => p.raw?.location_precision) && ' Locations without an exact project address are shown at their district or state centroid.'}
          </div>
        </>
      )}
    </PageContainer>
  )
}