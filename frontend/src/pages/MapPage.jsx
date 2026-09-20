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
  fetchProjects as fetchProjectsApi,
  fetchDemoProjects as fetchDemoProjectsApi,
  fetchPublicProjectPage as fetchPublicProjectPageApi,
} from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'
import { useAuth } from '../context/AuthContext'

delete L.Icon.Default.prototype._getIconUrl

L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
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

const RISK_FILTERS = ['All', 'Critical', 'High', 'Medium', 'Low']

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

  const [projects, setProjects] = React.useState([])
  const [risk, setRisk] = React.useState('All')
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    // MapPage only ever renders behind ProtectedRoute, so `status` is
    // effectively always 'authenticated' by the time this mounts --
    // this guard just avoids firing a request before that's settled.
    if (!authReady) return

    let cancelled = false
    setLoading(true)
    setError('')

    const request = useDemoApi
      ? fetchDemoProjectsApi({ skip: 0, limit: 100 })
      : useProtectedApi
        ? fetchProjectsApi({ skip: 0, limit: 100 })
        // Defensive fallback only -- MapPage is never reachable by an
        // anonymous visitor (see app/routes.jsx), but if it ever is,
        // this keeps the page working off the anonymous-safe endpoint
        // instead of throwing on a missing token.
        : fetchPublicProjectPageApi({ skip: 0, limit: 100 }).then(page => page.items || [])

    request
      .then(list => {
        if (cancelled) return
        setProjects(list.map(p => ({ ...p, project_id: p.id, risk_level: p.risk, work_type: p.workType })))
      })
      .catch(err => { if (!cancelled) { console.error('Map projects error:', err); setError('Unable to load project locations.') } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [authReady, useProtectedApi, useDemoApi])

  const filteredProjects = projects.filter(project => risk === 'All' || project.risk_level?.toLowerCase() === risk.toLowerCase())
  const mappedProjects = filteredProjects.filter(project => project.latitude != null && project.longitude != null)

  return (
    <PageContainer>
      <div className="mb-4 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">Project Map</h1>
          <p className="text-[13px] text-muted mt-0.5">Explore project distribution and risk signals across India.</p>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {RISK_FILTERS.map(option => (
            <button
              key={option}
              onClick={() => setRisk(option)}
              className={option === risk ? 'btn bg-navy text-white' : 'btn-secondary'}
            >{option}</button>
          ))}
        </div>
      </div>

      {loading && <div className="card p-8 text-center text-muted text-sm">Loading project locations…</div>}

      {!loading && error && <div className="card p-8 text-center text-sm" style={{ color: '#c0392b' }}>{error}</div>}

      {!loading && !error && (
        <>
          <div className="card overflow-hidden">
            <div className="h-[600px]">
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
          <div className="mt-2.5 text-xs text-muted">
            Showing {mappedProjects.length} projects with available coordinates from the monitoring API.
            {mappedProjects.some(p => p.raw?.location_precision) && ' Locations without an exact project address are shown at their district or state centroid.'}
          </div>
        </>
      )}
    </PageContainer>
  )
}