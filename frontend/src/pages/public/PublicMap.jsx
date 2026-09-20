import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { LocateOff, RotateCcw, Search } from 'lucide-react'
import PublicLayout from '../../components/public/PublicLayout'
import { PageHeading, PublicEmpty, PublicError } from '../../components/public/PublicStates'
import { LoadingRegion, Skeleton } from '../../components/public/Skeleton'
import DataFreshness from '../../components/public/DataFreshness'
import usePublicQuery from '../../lib/usePublicQuery'
import { fetchExplorerAreas, fetchExplorerFilters, fetchPublicMeta } from '../../features/public/api'
import { INDIA_BOUNDS, STATE_CENTROIDS } from '../../lib/stateCentroids'
import { formatCount, showInr, titleCase, formatPercent } from '../../lib/publicFormat'
import { locationPath, projectsLink } from '../../lib/publicTheme'

const MARKER_COLOR = '#1d63a8'

function MapController({ controlRef, target }) {
  const map = useMap()
  useEffect(() => {
    const fit = () => { map.invalidateSize(); map.fitBounds(INDIA_BOUNDS, { padding: [4, 4] }) }
    controlRef.current = { reset: fit }
    const timer = setTimeout(fit, 150)
    return () => clearTimeout(timer)
  }, [map, controlRef])
  useEffect(() => {
    if (target) map.flyTo(target, 7, { duration: 0.8 })
  }, [map, target])
  return null
}

function radiusFor(count, max) {
  if (!count || !max) return 6
  return 7 + Math.sqrt(count / max) * 24
}

/**
 * Explore Projects Across India.
 *
 * The public MPLADS dataset has NO project-level coordinates, so this map
 * plots one circle per State/UT (sized by number of projects) instead of
 * inventing project pins. Drilling in lists districts, and every list
 * links through to the real project search. State/district/status/category
 * filters are applied by the backend.
 */
export default function PublicMap() {
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [state, setState] = useState('')
  const [find, setFind] = useState('')
  const controlRef = useRef(null)

  const filters = usePublicQuery(opts => fetchExplorerFilters({}, opts), [])
  const meta = usePublicQuery(opts => fetchPublicMeta(opts), [])
  const areas = usePublicQuery(opts => fetchExplorerAreas({ status: status || null, category: category || null }, opts), [status, category])
  const districts = usePublicQuery(
    opts => (state ? fetchExplorerAreas({ state, status: status || null, category: category || null }, opts) : Promise.resolve(null)),
    [state, status, category]
  )

  const rows = useMemo(
    () => (areas.data?.rows || []).filter(r => STATE_CENTROIDS[r.name] || r.name !== 'Not specified'),
    [areas.data]
  )
  const max = useMemo(() => Math.max(0, ...rows.map(r => r.projectCount)), [rows])
  const unplaced = rows.filter(r => !STATE_CENTROIDS[r.name])
  const visible = rows.filter(r => r.name.toLowerCase().includes(find.trim().toLowerCase()))
  const target = state && STATE_CENTROIDS[state] ? STATE_CENTROIDS[state] : null

  function resetView() {
    setState(''); setFind('')
    controlRef.current?.reset()
  }

  const selectClass = 'pub-input'

  return (
    <PublicLayout>
      <PageHeading
        eyebrow="Explore Map"
        title="Explore Projects Across India"
        description="Each circle is a state or union territory; a bigger circle means more recorded projects. Select one to see its numbers and districts."
      />

      <div className="pub-card p-4 mb-5 border-t-[3px] border-t-info grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor="map-state" className="pub-label">State</label>
          <select id="map-state" className={selectClass} value={state} onChange={e => setState(e.target.value)}>
            <option value="">All India</option>
            {(filters.data?.states || []).map(s => <option key={s.value} value={s.value}>{s.value}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="map-status" className="pub-label">Project status</label>
          <select id="map-status" className={selectClass} value={status} onChange={e => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {(filters.data?.statuses || []).map(s => <option key={s.value} value={s.value}>{s.value}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="map-category" className="pub-label">Work category</label>
          <select id="map-category" className={selectClass} value={category} onChange={e => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {(filters.data?.categories || []).map(s => <option key={s.value} value={s.value}>{s.value}</option>)}
          </select>
        </div>
        <div className="flex items-end">
          <button type="button" className="pub-btn-secondary w-full" onClick={() => { setStatus(''); setCategory(''); resetView() }}>
            <RotateCcw size={16} aria-hidden="true" /> Reset view
          </button>
        </div>
      </div>

      {areas.error ? (
        <PublicError onRetry={areas.retry} />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px] items-start">
          <div className="pub-card overflow-hidden border-t-[3px] border-t-teal">
            <div className="h-[380px] md:h-[560px] relative" role="region" aria-label="Map of projects by state. A list of the same data follows the map.">
              <MapContainer bounds={INDIA_BOUNDS} scrollWheelZoom={false} className="h-full w-full" minZoom={4}>
                <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <MapController controlRef={controlRef} target={target} />
                {rows.filter(r => STATE_CENTROIDS[r.name]).map(r => (
                  <CircleMarker
                    key={r.name}
                    center={STATE_CENTROIDS[r.name]}
                    radius={radiusFor(r.projectCount, max)}
                    pathOptions={{ color: r.name === state ? '#0b2e4f' : '#ffffff', weight: r.name === state ? 3 : 1.5, fillColor: MARKER_COLOR, fillOpacity: 0.65 }}
                    eventHandlers={{ click: () => setState(r.name) }}
                  >
                    <Popup>
                      <div className="min-w-[210px] text-[13.5px]">
                        <div className="text-[15px] font-bold text-navy">{r.name}</div>
                        <dl className="mt-2 space-y-0.5">
                          <div className="flex justify-between gap-3"><dt className="text-muted">Projects</dt><dd className="font-semibold">{formatCount(r.projectCount)}</dd></div>
                          <div className="flex justify-between gap-3"><dt className="text-muted">Completed</dt><dd className="font-semibold">{formatCount(r.completedProjects)}</dd></div>
                          <div className="flex justify-between gap-3"><dt className="text-muted">Ongoing</dt><dd className="font-semibold">{formatCount(r.ongoingProjects)}</dd></div>
                          <div className="flex justify-between gap-3"><dt className="text-muted">Sanctioned</dt><dd className="font-semibold">{showInr(r.sanctioned)}</dd></div>
                          <div className="flex justify-between gap-3"><dt className="text-muted">Expenditure</dt><dd className="font-semibold">{showInr(r.expenditure)}</dd></div>
                        </dl>
                        <div className="mt-3 flex flex-col gap-1.5">
                          <Link className="font-semibold text-blue hover:underline" to={projectsLink({ state: r.name, status, category })}>View projects</Link>
                          <Link className="font-semibold text-blue hover:underline" to={locationPath(r.name)}>Explore districts</Link>
                        </div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
              {areas.loading && !areas.data && (
                <div className="absolute inset-0 z-[500] bg-white/70 flex items-center justify-center" role="status">
                  <span className="text-[14px] font-semibold text-navy">Loading map data…</span>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-line text-[13px] text-muted">
              <div className="font-semibold text-ink mb-2">How to read this map</div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                <span className="inline-flex items-center gap-2">
                  <i className="inline-block rounded-full" style={{ width: 12, height: 12, background: MARKER_COLOR, opacity: 0.65 }} /> Fewer projects
                </span>
                <span className="inline-flex items-center gap-2">
                  <i className="inline-block rounded-full" style={{ width: 26, height: 26, background: MARKER_COLOR, opacity: 0.65 }} /> More projects
                </span>
                <span className="inline-flex items-center gap-1.5"><LocateOff size={14} aria-hidden="true" /> Circles mark the approximate centre of each state, not project sites.</span>
              </div>
              <p className="mt-2">The public dataset does not include project-level coordinates, so individual projects are not plotted.</p>
            </div>
          </div>

          <aside aria-label="States and districts" className="pub-card p-4 border-t-[3px] border-t-indigo">
            {!state ? (
              <>
                <h2 className="text-[17px] font-bold text-navy mb-3">States and UTs</h2>
                <label htmlFor="find-state" className="sr-only">Find a state</label>
                <div className="relative mb-3">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
                  <input id="find-state" type="search" className="pub-input pl-9" placeholder="Find a state" value={find} onChange={e => setFind(e.target.value)} />
                </div>
                {areas.loading && !areas.data ? (
                  <LoadingRegion label="Loading states">{[0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-12 mb-2" />)}</LoadingRegion>
                ) : visible.length === 0 ? (
                  <PublicEmpty title="No matching state" suggestions={['Check the spelling', 'Clear the search']} />
                ) : (
                  <ul className="max-h-[440px] overflow-y-auto divide-y divide-line">
                    {visible.map(r => (
                      <li key={r.name}>
                        <button type="button" onClick={() => setState(r.name)} className="w-full text-left py-2.5 px-1 hover:bg-navy-bg rounded flex items-center justify-between gap-3">
                          <span className="text-[14.5px] font-semibold text-ink">{r.name}</span>
                          <span className="text-[13px] text-muted">{formatCount(r.projectCount)} projects</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {unplaced.length > 0 && <p className="text-[12.5px] text-muted mt-3">{unplaced.map(r => r.name).join(', ')} {unplaced.length === 1 ? 'is' : 'are'} listed here but not drawn on the map.</p>}
              </>
            ) : (
              <>
                <button type="button" className="text-[13.5px] font-semibold text-blue hover:underline mb-2" onClick={resetView}>&larr; All India</button>
                <h2 className="text-[19px] font-bold text-navy">{state}</h2>
                <div className="flex flex-wrap gap-2 my-3">
                  <Link className="pub-btn-primary !py-2 !min-h-[40px] !text-[14px]" to={projectsLink({ state, status, category })}>View projects</Link>
                  <Link className="pub-btn-secondary !py-2 !min-h-[40px] !text-[14px]" to={locationPath(state)}>State overview</Link>
                </div>
                <h3 className="text-[14px] font-semibold text-ink mb-2">Districts</h3>
                {districts.error ? <PublicError compact onRetry={districts.retry} /> :
                  !districts.data ? <LoadingRegion label="Loading districts">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-12 mb-2" />)}</LoadingRegion> :
                  districts.data.rows.length === 0 ? <PublicEmpty title="No projects match these filters" suggestions={['Change the status', 'Change the category']} /> : (
                    <ul className="max-h-[400px] overflow-y-auto divide-y divide-line">
                      {districts.data.rows.map(r => (
                        <li key={r.name}>
                          <Link to={projectsLink({ state, district: r.name, status, category })} className="block py-2.5 px-1 hover:bg-navy-bg rounded">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[14.5px] font-semibold text-ink">{titleCase(r.name)}</span>
                              <span className="text-[13px] text-muted">{formatCount(r.projectCount)}</span>
                            </div>
                            <div className="text-[12.5px] text-muted">{showInr(r.sanctioned)} sanctioned{r.utilisationPercent !== null ? ` · ${formatPercent(r.utilisationPercent)} utilized` : ''}</div>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
              </>
            )}
          </aside>
        </div>
      )}
      <DataFreshness meta={meta.data} className="mt-8" />
    </PublicLayout>
  )
}