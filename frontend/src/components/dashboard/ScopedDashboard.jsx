import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Banknote, CheckCircle2, FolderKanban, ShieldAlert, TrendingUp } from 'lucide-react'
import { fetchRoleDashboard } from '../../features/dashboard/api'
import { formatCurrency } from '../../lib/formatters'
import { ROLE_VIEW_LABEL } from '../../lib/roles'
import { useAuth } from '../../context/AuthContext'
import { RiskBadge, Progress, Disclaimer } from '../UI'
import KpiCard from '../ui/KpiCard'
import LoadingState from '../ui/LoadingState'
import ErrorState from '../ui/ErrorState'
import EmptyState from '../ui/EmptyState'

// Fetches one large page of REAL projects (the backend has no scoped
// aggregate endpoint per state/district/MP yet) and filters/aggregates
// them client-side by whichever real field the role scopes by. Every
// number below is computed from real project rows -- only the "which
// page of the dataset is currently loaded" limitation is a stand-in for
// a proper server-side scoped query.
const SCAN_LIMIT = 300
const SCOPE_FIELD = { state: 'state', district: 'district', mp: 'constituency' }
const SCOPE_LABEL = { state: 'State', district: 'District', mp: 'Constituency' }

export default function ScopedDashboard({ role }) {
  const { isDemo } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scope, setScope] = useState('')
  const [scopeAvailable, setScopeAvailable] = useState(false)

  useEffect(() => {
    if (isDemo) {
      setScopeAvailable(false)
      setLoading(false)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchRoleDashboard()
      .then(data => {
        if (cancelled) return
        setScopeAvailable(Boolean(data.scope_available))
        setRows(data.scope_available ? (data.scoped_projects || []) : [])
      })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isDemo])

  const field = SCOPE_FIELD[role] || 'state'
  const options = useMemo(() => [...new Set(rows.map(r => r[field]).filter(Boolean))].sort(), [rows, field])

  useEffect(() => {
    if (!scope && options.length > 0) setScope(options[0])
  }, [options, scope])

  const scoped = scope ? rows.filter(r => r[field] === scope) : []

  const districtRows = useMemo(() => {
    if (role !== 'state' || !scope) return []
    const map = {}
    rows.filter(r => r.state === scope).forEach(r => {
      const key = r.district || 'Unspecified'
      if (!map[key]) map[key] = { district: key, projects: 0, sanctioned: 0, expenditure: 0, review: 0 }
      map[key].projects += 1
      map[key].sanctioned += r.sanctioned || 0
      map[key].expenditure += r.expenditure || 0
      if (r.risk === 'High' || r.risk === 'Critical') map[key].review += 1
    })
    return Object.values(map)
  }, [rows, role, scope])

  if (loading) return <LoadingState text="Loading scoped project data…" />
  if (error) return <ErrorState title="Could not load projects" message={error} />
  if (!scopeAvailable) return <UnavailableScopedDashboard role={role} />

  const totalSanctioned = scoped.reduce((a, r) => a + (r.sanctioned || 0), 0)
  const totalExpenditure = scoped.reduce((a, r) => a + (r.expenditure || 0), 0)
  const completed = scoped.filter(r => r.status === 'Completed').length
  const review = scoped.filter(r => r.risk === 'High' || r.risk === 'Critical').length
  const utilizationPct = totalSanctioned ? Math.round((totalExpenditure / totalSanctioned) * 100) : null

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-4">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">{ROLE_VIEW_LABEL[role]} Overview</h1>
          <p className="text-[13px] text-muted mt-0.5">Filtered to a single {SCOPE_LABEL[role]?.toLowerCase()} from the currently loaded project page ({rows.length} of the portfolio).</p>
        </div>
        {options.length > 0 && (
          <select value={scope} onChange={e => setScope(e.target.value)} className="border border-line rounded-md px-3 py-2 text-[13px] bg-white">
            {options.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        )}
      </div>

      {options.length === 0 ? (
        <div className="card p-10 text-center text-sm text-muted">No {SCOPE_LABEL[role]?.toLowerCase()} data found in the currently loaded projects.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <KpiCard label="Projects in scope" value={scoped.length.toLocaleString()} icon={FolderKanban} tone="navy" />
            <KpiCard label="Sanctioned Amount" value={formatCurrency(totalSanctioned)} icon={Banknote} tone="navy" />
            <KpiCard label="Expenditure" value={formatCurrency(totalExpenditure)} hint={utilizationPct !== null ? `${utilizationPct}% utilized` : undefined} icon={TrendingUp} tone="blue" />
            <KpiCard label="Requiring Review" value={review.toLocaleString()} icon={ShieldAlert} tone="red" />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <KpiCard label="Completed" value={completed.toLocaleString()} icon={CheckCircle2} tone="green" />
            <KpiCard label="Active" value={scoped.filter(r => r.status !== 'Completed').length.toLocaleString()} icon={AlertTriangle} tone="amber" />
          </div>

          {role === 'state' && districtRows.length > 0 && (
            <div className="card mb-4">
              <div className="px-4 pt-4 pb-1"><h3 className="text-[13.5px] font-semibold text-ink">District Comparison</h3><p className="text-xs text-muted mt-0.5">{scope}</p></div>
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr>{['District', 'Projects', 'Sanctioned', 'Expenditure', 'Requiring Review'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                  <tbody>
                    {districtRows.map(d => (
                      <tr key={d.district}>
                        <td className="font-medium">{d.district}</td>
                        <td>{d.projects}</td>
                        <td>{formatCurrency(d.sanctioned)}</td>
                        <td>{formatCurrency(d.expenditure)}</td>
                        <td>{d.review}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card overflow-hidden">
            <div className="px-4 pt-4 pb-1"><h3 className="text-[13.5px] font-semibold text-ink">Projects</h3><p className="text-xs text-muted mt-0.5">{scope}</p></div>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr>{['Work ID', 'Category', 'Status', 'Sanctioned', 'Expenditure', 'Risk', ''].map(h => <th key={h}>{h}</th>)}</tr></thead>
                <tbody>
                  {scoped.slice(0, 12).map(p => (
                    <tr key={p.id} className="hover:bg-panel">
                      <td className="font-mono font-semibold text-navy whitespace-nowrap">{p.id}</td>
                      <td>{p.workType || '—'}</td>
                      <td>{p.status || '—'}</td>
                      <td>{formatCurrency(p.sanctioned)}</td>
                      <td>{formatCurrency(p.expenditure)}</td>
                      <td><RiskBadge risk={p.risk} /></td>
                      <td><Link to={`/projects/${encodeURIComponent(p.id)}`} className="text-xs font-semibold text-navy">View →</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4"><Disclaimer compact /></div>
        </>
      )}
    </div>
  )
}

function UnavailableScopedDashboard({ role }) {
  const title = {
    state: 'State Monitoring Overview',
    district: 'District Operations Overview',
    mp: 'Constituency Overview',
  }[role] || `${ROLE_VIEW_LABEL[role]} Overview`
  const scopeLabel = role === 'state' ? 'State' : role === 'district' ? 'District' : 'Constituency'
  const projectTitle = role === 'mp' ? 'My Projects' : role === 'district' ? 'Project Monitoring' : 'Projects in Scope'
  const trendTitle = role === 'mp' ? 'Recommended vs Sanctioned vs Completed' : 'Sanction vs Expenditure Trend'

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-5">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">{title}</h1>
          <p className="text-[13px] text-muted mt-0.5 max-w-2xl">This view uses only records authorized by the backend scope for the authenticated account.</p>
        </div>
        <select disabled value="unavailable" aria-label={`${scopeLabel} selector`} className="border border-line rounded-md px-3 py-2 text-[13px] bg-white text-muted">
          <option value="unavailable">{scopeLabel} scope unavailable</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <KpiCard label={role === 'mp' ? 'Recommended Works' : 'Projects in Scope'} value="—" icon={FolderKanban} tone="navy" />
        <KpiCard label="Sanctioned Amount" value="—" icon={Banknote} tone="navy" />
        <KpiCard label="Expenditure" value="—" icon={TrendingUp} tone="blue" />
        <KpiCard label={role === 'mp' ? 'Completed Works' : 'Requiring Review'} value="—" icon={role === 'mp' ? CheckCircle2 : AlertTriangle} tone="amber" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <div className="card p-4">
          <h3 className="text-[13.5px] font-semibold text-ink">{trendTitle}</h3>
          <p className="text-xs text-muted mt-0.5">Monthly, backend-scoped</p>
          <EmptyState text="Trend data not available from the current source." />
        </div>
        <div className="card p-4">
          <h3 className="text-[13.5px] font-semibold text-ink">Work-Category Distribution</h3>
          <p className="text-xs text-muted mt-0.5">Backend-scoped category data</p>
          <EmptyState text="Work-category data not available from the current source." />
        </div>
      </div>

      {role === 'state' && (
        <div className="card p-4 mb-4">
          <h3 className="text-[13.5px] font-semibold text-ink">District Comparison</h3>
          <p className="text-xs text-muted mt-0.5">Backend-scoped district data</p>
          <EmptyState text="District data not available from the current source." />
        </div>
      )}

      <div className="card p-4">
        <h3 className="text-[13.5px] font-semibold text-ink">{projectTitle}</h3>
        <p className="text-xs text-muted mt-0.5">Only backend-authorized records can appear here.</p>
        <EmptyState text={`${scopeLabel} data not available from the current source.`} />
      </div>
    </div>
  )
}