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

const ALERT_TYPE_LABEL = {
  high_risk_project: 'High risk project',
  possible_duplicate: 'Possible duplicate',
  financial_risk: 'Financial risk',
  payment_risk: 'Payment risk',
  execution_risk: 'Execution risk',
  peer_anomaly: 'Peer anomaly',
  anomaly_detection: 'Anomaly detection',
  anomaly_risk: 'Anomaly risk',
}

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
      .then(data => { if (!cancelled) setRows(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [skip])

  const filtered = rows.filter(a => sev === 'All' || (a.severity || '').toLowerCase() === sev.toLowerCase())

  return (
    <PageContainer maxWidth="1100px">
      <div className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">Alerts</h1>
        <p className="text-[13px] text-muted mt-0.5">Generated live from risk signals. AI-assisted advisory signal -- human verification required. Anomaly does not mean fraud.</p>
      </div>

      <div className="flex gap-1.5 mb-4 flex-wrap">
        {FILTERS.map(x => (
          <button key={x} onClick={() => setSev(x)} className={sev === x ? 'btn bg-navy text-white' : 'btn-secondary'}>{x}</button>
        ))}
      </div>

      {loading && <LoadingState text="Loading alerts…" />}

      {!loading && error && <ErrorState title="Could not load alerts" message={error} onRetry={() => setSkip(skip)} />}

      {!loading && !error && (
        <>
          <div className="space-y-2.5">
            {filtered.map(a => {
              const tone = riskTone(a.severity)
              return (
                <div className="card p-4" key={a.alert_id}>
                  <div className="flex gap-3.5">
                    <div className="h-9 w-9 rounded-md flex items-center justify-center shrink-0" style={{ backgroundColor: tone.bg, color: tone.color }}><BellRing size={16} /></div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap gap-2 items-center">
                        <Badge color={tone.color} bg={tone.bg}>{tone.label}</Badge>
                        <span className="text-xs text-muted">{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
                      </div>
                      <p className="text-[12.5px] text-ink mt-2 leading-5">{a.message}</p>
                      <div className="text-xs text-muted mt-2.5 font-mono">{a.projectId}</div>
                    </div>
                  </div>
                  <div className="mt-3.5">
                    <Link to={`/projects/${encodeURIComponent(a.projectId)}`} className="btn-secondary !py-1.5">Open project</Link>
                  </div>
                </div>
              )
            })}
          </div>
          {filtered.length === 0 && <div className="card"><EmptyState text="No alerts match this filter on the current page." /></div>}

          <div className="mt-4 card">
            <Pagination
              page={Math.floor(skip / PAGE_SIZE) + 1}
              canGoPrev={skip !== 0 && !loading}
              canGoNext={!loading && rows.length >= PAGE_SIZE}
              onPrev={() => setSkip(s => Math.max(0, s - PAGE_SIZE))}
              onNext={() => setSkip(s => s + PAGE_SIZE)}
            />
          </div>
        </>
      )}
    </PageContainer>
  )
}