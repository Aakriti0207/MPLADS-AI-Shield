import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, SlidersHorizontal } from 'lucide-react'
import { formatCurrency } from '../lib/formatters'
import { RiskBadge, Progress } from '../components/UI'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import Pagination from '../components/ui/Pagination'
import { fetchProjects } from '../features/projects/api'
import ProjectFilters from '../components/projects/ProjectFilters'
import PageContainer from '../components/layout/PageContainer'
const PAGE_SIZE = 50

export default function Projects() {
  const [q, setQ] = useState('')
  const [risk, setRisk] = useState('All')
  const [workType, setWorkType] = useState('All')
  const [skip, setSkip] = useState(0)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchProjects({ skip, limit: PAGE_SIZE })
      .then(data => { if (!cancelled) setRows(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [skip])

  const workTypes = useMemo(() => [...new Set(rows.map(p => p.workType).filter(Boolean))], [rows])

  const filtered = useMemo(() => rows.filter(p =>
    (`${p.id} ${p.mpName} ${p.state} ${p.district} ${p.constituency}`.toLowerCase().includes(q.toLowerCase())) &&
    (risk === 'All' || p.risk === risk) &&
    (workType === 'All' || p.workType === workType)
  ), [rows, q, risk, workType])

  const financialPct = p => (p.sanctioned && p.expenditure !== null) ? Math.min(100, Math.round((p.expenditure / p.sanctioned) * 100)) : null

  return (
    <PageContainer>
      <div className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">Project Explorer</h1>
        <p className="text-[13px] text-muted mt-0.5">Search, filter and open a complete project intelligence view.</p>
      </div>

      <ProjectFilters query={q} onQueryChange={setQ} risk={risk} onRiskChange={setRisk} workType={workType} onWorkTypeChange={setWorkType} workTypes={workTypes} />

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2 text-[12.5px] font-semibold text-ink"><SlidersHorizontal size={14} /> {filtered.length} of {rows.length} loaded projects matched</div>
          <div className="text-xs text-muted">Live backend • showing {skip + 1}–{skip + rows.length}</div>
        </div>

        {loading && <LoadingState text="Loading projects from the API…" />}

        {!loading && error && <ErrorState title="Could not load projects" message={error} onRetry={() => setSkip(skip)} />}

        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr>{['Project', 'Location', 'MP / Agency', 'Financial', 'Risk', ''].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {filtered.map(p => {
                  const pct = financialPct(p)
                  return (
                    <tr key={p.id} className="hover:bg-panel">
                      <td className="min-w-[220px]"><div className="font-semibold text-ink">{p.workType || 'Untitled work'}</div><div className="text-xs text-muted mt-0.5 font-mono">{p.id}</div></td>
                      <td className="min-w-[150px]">{p.district || '—'}<div className="text-xs text-muted">{p.state || '—'}</div></td>
                      <td className="min-w-[170px]">{p.mpName || '—'}<div className="text-xs text-muted">{p.agency || '—'}</div></td>
                      <td className="min-w-[150px]">
                        {pct === null ? <span className="text-xs text-muted">Not available</span> : (
                          <>
                            <div className="text-xs text-muted mb-1">{formatCurrency(p.expenditure)} / {formatCurrency(p.sanctioned)}</div>
                            <Progress value={pct} />
                          </>
                        )}
                      </td>
                      <td>
                        <RiskBadge risk={p.risk} />
                        <div className="text-xs text-muted mt-1">{p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}</div>
                      </td>
                      {/* Real project_id values contain "/" (e.g. WS/MP001/2023-2024/103702),
                          so it must be encoded here or the router will read it as extra path
                          segments instead of one :id param. */}
                      <td><Link to={`/projects/${encodeURIComponent(p.id)}`} className="h-8 w-8 rounded-md border border-line inline-flex items-center justify-center text-navy hover:bg-panel"><Eye size={14} /></Link></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {filtered.length === 0 && <div className="p-10 text-center text-muted text-sm">No projects match these filters on the current page.</div>}
          </div>
        )}

        <Pagination
          page={Math.floor(skip / PAGE_SIZE) + 1}
          canGoPrev={skip !== 0 && !loading}
          canGoNext={!loading && rows.length >= PAGE_SIZE}
          onPrev={() => setSkip(s => Math.max(0, s - PAGE_SIZE))}
          onNext={() => setSkip(s => s + PAGE_SIZE)}
        />
      </div>
    </PageContainer>
  )
}