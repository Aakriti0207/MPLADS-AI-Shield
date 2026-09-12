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
import { fetchProjects } from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'

// Real backend gives risk_level as 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'.
// RiskBadge / the risk filter expect Title case -- same normalization
// pattern already used in Projects.jsx / ProjectDetails.jsx.
const titleCase = s => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null

delete L.Icon.Default.prototype._getIconUrl

L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'
})

function FitBounds({ projects }) {
  const map = useMap()

  React.useEffect(() => {
    const validProjects = projects.filter(
      p => p.latitude != null && p.longitude != null
    )

    if (validProjects.length > 0) {
      const bounds = validProjects.map(p => [
        Number(p.latitude),
        Number(p.longitude)
      ])

      map.fitBounds(bounds, {
        padding: [30, 30]
      })
    }
  }, [map, projects])

  return null
}

export default function MapPage() {
  const [projects, setProjects] = React.useState([])
  const [risk, setRisk] = React.useState('All')
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    async function fetchProjects() {
      try {
        setLoading(true)
        setError('')

        const list = await fetchProjects({skip: 0, limit: 100})
        setProjects(list.map(p => ({ ...p, project_id: p.id, risk_level: p.risk, latitude: p.latitude, longitude: p.longitude, status: p.status, work_type: p.workType, district: p.district, state: p.state })))
      } catch (err) {
        console.error('Map projects error:', err)
        setError('Unable to load project locations.')
      } finally {
        setLoading(false)
      }
    }

    fetchProjects()
  }, [])

  const filteredProjects = projects.filter(project => {
    if (risk === 'All') return true

    return (
      project.risk_level?.toLowerCase() === risk.toLowerCase()
    )
  })

  const mappedProjects = filteredProjects.filter(
    project =>
      project.latitude != null &&
      project.longitude != null
  )

  return (
    <PageContainer maxWidth="1500px">

      {/* Header */}
      <div className="mb-5 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="eyebrow">
            Geospatial intelligence
          </div>

          <h1 className="text-3xl font-extrabold mt-1">
            Project Map
          </h1>

          <p className="text-slate-500 mt-1">
            Explore project distribution and risk signals across India.
          </p>
        </div>

        {/* Risk filters */}
        <div className="flex gap-2">
          {['All', 'Critical', 'High', 'Medium', 'Low'].map(option => (
            <button
              key={option}
              onClick={() => setRisk(option)}
              className={`btn ${
                risk === option
                  ? 'bg-navy text-white'
                  : 'btn-secondary'
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="card p-8 text-center text-slate-500">
          Loading project locations...
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="card p-8 text-center text-red-500">
          {error}
        </div>
      )}

      {/* Map */}
      {!loading && !error && (
        <>
          <div className="card overflow-hidden">
            <div className="h-[650px]">

              <MapContainer
                center={[22.5, 79]}
                zoom={5}
                scrollWheelZoom
                className="h-full w-full"
              >

                <TileLayer
                  attribution="&copy; OpenStreetMap contributors"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <FitBounds projects={mappedProjects} />

                {mappedProjects.map(project => (
                  <Marker
                    key={project.project_id}
                    position={[
                      Number(project.latitude),
                      Number(project.longitude)
                    ]}
                  >
                    <Popup>
                      <div className="min-w-[220px]">

                        <div className="font-bold">
                          {project.work_type || 'MPLADS Project'}
                        </div>

                        <div className="text-xs text-slate-500 mt-1">
                          {project.project_id}
                        </div>

                        <div className="text-xs text-slate-500 mt-1">
                          {project.district || 'District unavailable'},
                          {' '}
                          {project.state || 'State unavailable'}
                        </div>

                        <div className="flex gap-2 mt-3">
                          {project.status && (
                            <StatusBadge
                              status={project.status}
                            />
                          )}

                          {project.risk_level && (
                            <RiskBadge
                              risk={project.risk_level}
                            />
                          )}
                        </div>

                        <Link
                          className="text-sm font-bold text-navy inline-block mt-3"
                          to={`/projects/${project.project_id}`}
                        >
                          Open project →
                        </Link>

                      </div>
                    </Popup>
                  </Marker>
                ))}

              </MapContainer>

            </div>
          </div>

          <div className="mt-3 text-xs text-slate-400">
            Showing {mappedProjects.length} projects with available
            coordinates from the monitoring API.
          </div>
        </>
      )}

    </PageContainer>
  )
}