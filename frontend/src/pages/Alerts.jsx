import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing } from 'lucide-react'
import { Badge } from '../components/UI'
import { riskTone } from '../lib/theme'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import EmptyState from '../components/ui/EmptyState'
import Pagination from '../components/ui/Pagination'
import { fetchAlerts } from '../features/alerts/api'
import PageContainer from '../components/layout/PageContainer'

const PAGE_SIZE = 50

const FILTERS = ['All', 'Critical', 'High', 'Medium', 'Low']

export default function Alerts() {
  const [sev, setSev] = useState('All')
  const [skip, setSkip] = useState(0)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError(null)

    fetchAlerts({ skip, limit: PAGE_SIZE })
      .then(data => {
        if (!cancelled) {
          setRows(Array.isArray(data) ? data : [])
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to reach the API')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [skip])

  const filtered = rows.filter(
    alert =>
      sev === 'All' ||
      (alert.severity || '').toLowerCase() === sev.toLowerCase()
  )

  return (
    <PageContainer maxWidth="1100px">

      {/* Header */}
      <div className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">
          Alerts
        </h1>

        <p className="text-[13px] text-muted mt-0.5">
          Generated live from risk signals. AI-assisted advisory signal --
          human verification required. Anomaly does not mean fraud.
        </p>
      </div>

      {/* Severity filters */}
      <div className="flex gap-1.5 mb-4 flex-wrap">
        {FILTERS.map(filter => (
          <button
            key={filter}
            onClick={() => {
              setSev(filter)
              setSkip(0)
            }}
            className={
              sev === filter
                ? 'btn bg-navy text-white'
                : 'btn-secondary'
            }
          >
            {filter}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <LoadingState text="Loading alerts…" />
      )}

      {/* Error */}
      {!loading && error && (
        <ErrorState
          title="Could not load alerts"
          message={error}
          onRetry={() => setSkip(skip)}
        />
      )}

      {/* Alerts */}
      {!loading && !error && (
        <>
          <div className="space-y-2.5">

            {filtered.map(alert => {
              const tone = riskTone(alert.severity)

              // Backend uses project_id.
              // Keep projectId fallback so this also works with
              // an older API adapter during the transition.
              const projectId =
                alert.project_id ||
                alert.projectId ||
                ''

              return (
                <div
                  className="card p-4"
                  key={alert.alert_id || projectId}
                >
                  <div className="flex gap-3.5">

                    {/* Alert icon */}
                    <div
                      className="h-9 w-9 rounded-md flex items-center justify-center shrink-0"
                      style={{
                        backgroundColor: tone.bg,
                        color: tone.color,
                      }}
                    >
                      <BellRing size={16} />
                    </div>

                    {/* Project information */}
                    <div className="min-w-0 flex-1">

                      {/* Severity + triggered component */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge
                          color={tone.color}
                          bg={tone.bg}
                        >
                          {tone.label}
                        </Badge>

                        {alert.triggered_component && (
                          <span className="text-[11px] font-medium text-navy bg-panel rounded-full px-2 py-0.5">
                            {alert.triggered_component}
                          </span>
                        )}

                        {alert.risk_score !== null && alert.risk_score !== undefined && (
                          <span className="text-[11px] text-muted">
                            Risk score: <span className="font-semibold text-ink">{alert.risk_score}</span>
                          </span>
                        )}
                      </div>

                      {/* Project ID */}
                      <div className="text-[13px] text-ink mt-2 font-mono break-all">
                        {projectId || 'Project ID unavailable'}
                      </div>

                      {/* Top reason */}
                      {alert.top_reason && (
                        <p className="text-[12px] text-muted mt-1.5 leading-4">
                          {alert.top_reason}
                        </p>
                      )}

                      {/* Location */}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[12px] text-muted">

                        {alert.state && (
                          <span>
                            <span className="text-ink font-medium">
                              State:
                            </span>{' '}
                            {alert.state}
                          </span>
                        )}

                        {alert.district && (
                          <span>
                            <span className="text-ink font-medium">
                              District:
                            </span>{' '}
                            {alert.district}
                          </span>
                        )}

                        {alert.constituency && (
                          <span>
                            <span className="text-ink font-medium">
                              Constituency:
                            </span>{' '}
                            {alert.constituency}
                          </span>
                        )}

                      </div>

                    </div>
                  </div>

                  {/* Open project */}
                  <div className="mt-3.5">
                    {projectId ? (
                      <Link
                        to={`/projects/${encodeURIComponent(projectId)}`}
                        className="btn-secondary !py-1.5"
                      >
                        Open project
                      </Link>
                    ) : (
                      <button
                        className="btn-secondary !py-1.5 opacity-50 cursor-not-allowed"
                        disabled
                      >
                        Open project
                      </button>
                    )}
                  </div>
                </div>
              )
            })}

          </div>

          {/* Empty */}
          {filtered.length === 0 && (
            <div className="card">
              <EmptyState text="No alerts match this filter on the current page." />
            </div>
          )}

          {/* Pagination */}
          <div className="mt-4 card">
            <Pagination
              page={Math.floor(skip / PAGE_SIZE) + 1}
              canGoPrev={skip !== 0 && !loading}
              canGoNext={!loading && rows.length >= PAGE_SIZE}
              onPrev={() =>
                setSkip(s => Math.max(0, s - PAGE_SIZE))
              }
              onNext={() =>
                setSkip(s => s + PAGE_SIZE)
              }
            />
          </div>
        </>
      )}

    </PageContainer>
  )
}