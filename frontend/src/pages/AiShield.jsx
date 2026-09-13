import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { AlertTriangle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { normalizeRole, ROLE_VIEW_LABEL } from '../lib/roles'
import { fetchProjects } from '../features/projects/api'
import { fetchDashboardStats } from '../features/dashboard/api'
import { formatCurrency, toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { Disclaimer, RiskBadge, Stat } from '../components/UI'
import ChartCard from '../components/ui/ChartCard'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import PageContainer from '../components/layout/PageContainer'

const SCAN_LIMIT = 300
const SCOPE_FIELD = { state: 'state', district: 'district', mp: 'constituency' }

// Real per-project risk sub-scores (see lib/normalizers.js -- financial_
// risk_score, payment_risk_score, execution_risk_score, peer_anomaly_
// score, duplicate_risk_score all come straight from the /risk endpoint)
// used here to build a genuine "anomaly categories" breakdown, instead
// of a fabricated one -- each bucket below is a real count of projects
// whose real sub-score for that category exceeds a review threshold.
const CATEGORY_FIELDS = [
  ['Financial', 'financial_risk_score'],
  ['Payment', 'payment_risk_score'],
  ['Execution', 'execution_risk_score'],
  ['Peer anomaly', 'peer_anomaly_score'],
  ['Duplicate similarity', 'duplicate_risk_score'],
]
const REVIEW_THRESHOLD = 50

export default function AiShield() {
  const { user } = useAuth()
  const role = normalizeRole(user?.role)

  const [rows, setRows] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scope, setScope] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([fetchProjects({ skip: 0, limit: SCAN_LIMIT }), fetchDashboardStats().catch(() => null)])
      .then(([projects, dashStats]) => { if (!cancelled) { setRows(projects); setStats(dashStats) } })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const field = SCOPE_FIELD[role]
  const options = useMemo(() => field ? [...new Set(rows.map(r => r[field]).filter(Boolean))].sort() : [], [rows, field])

  useEffect(() => {
    if (field && !scope && options.length > 0) setScope(options[0])
  }, [field, options, scope])

  const scoped = field ? rows.filter(r => r[field] === scope) : rows

  const categoryData = useMemo(() => CATEGORY_FIELDS.map(([label, key]) => ({
    name: label,
    value: scoped.filter(r => toNumber(r.raw?.[key]) !== null && toNumber(r.raw[key]) >= REVIEW_THRESHOLD).length,
  })), [scoped])

  const scatterData = useMemo(() => scoped
    .filter(r => r.sanctioned && r.expenditure !== null)
    .map(r => ({ x: Number((r.sanctioned / 10000000).toFixed(2)), y: Math.min(2, Number((r.expenditure / r.sanctioned).toFixed(2))), risk: r.risk, id: r.id })),
  [scoped])

  const priorityQueue = scoped.filter(r => r.risk === 'High' || r.risk === 'Critical').slice(0, 12)

  if (loading) return <PageContainer><LoadingState text="Loading AI Shield intelligence…" /></PageContainer>
  if (error) return <PageContainer><ErrorState title="Could not load AI Shield data" message={error} /></PageContainer>

  const riskCounts = stats?.risk_level_counts || {}
  const hasRiskCounts = Object.keys(riskCounts).length > 0
  const highPlusCritical = (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0)
  const totalAnalyzed = toNumber(stats?.total_projects)

  return (
    <PageContainer>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-5">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">AI Shield{role !== 'ministry' ? ` — ${ROLE_VIEW_LABEL[role]}` : ' Command Center'}</h1>
          <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
            {role === 'ministry'
              ? 'National AI risk & monitoring overview, built from real per-project risk data.'
              : `Scoped to your ${field} selection below. All figures are computed from the currently loaded project page (${rows.length} projects), pending a server-side scoped endpoint.`}
          </p>
        </div>
        {field && options.length > 0 && (
          <select value={scope} onChange={e => setScope(e.target.value)} className="border border-line rounded-md px-3 py-2 text-[13px] bg-white">
            {options.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        )}
      </div>

      {role === 'ministry' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Stat label="Total Analyzed" value={totalAnalyzed !== null ? totalAnalyzed.toLocaleString() : rows.length.toLocaleString()} tone="navy" />
          <Stat label="Low Risk" value={hasRiskCounts ? (riskCounts.LOW || 0).toLocaleString() : 'Not available'} tone="green" />
          <Stat label="Medium Risk" value={hasRiskCounts ? (riskCounts.MEDIUM || 0).toLocaleString() : 'Not available'} tone="amber" />
          <Stat label="High + Critical" value={hasRiskCounts ? highPlusCritical.toLocaleString() : 'Not available'} tone="red" />
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <ChartCard title="Anomaly Categories" subtitle={`Projects with a real sub-score ≥ ${REVIEW_THRESHOLD}, by category`} height={260}>
          <ResponsiveContainer>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={CHART_COLORS.line} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
              <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11.5, fill: CHART_COLORS.ink }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
              <Bar dataKey="value" fill={CHART_COLORS.blue} radius={[0, 4, 4, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Peer-Relative Analysis" subtitle="Sanction amount (₹ Cr) vs. expenditure ratio — real project data" height={260}>
          <ResponsiveContainer>
            <ScatterChart margin={{ left: -10, right: 12, top: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} />
              <XAxis type="number" dataKey="x" name="Sanction (₹ Cr)" tick={{ fontSize: 10.5, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
              <YAxis type="number" dataKey="y" name="Expenditure ratio" tick={{ fontSize: 10.5, fill: CHART_COLORS.muted }} axisLine={false} tickLine={false} />
              <ZAxis range={[24, 24]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
              <Scatter data={scatterData.filter(d => d.risk !== 'High' && d.risk !== 'Critical')} fill="#9fb6cc" fillOpacity={0.6} />
              <Scatter data={scatterData.filter(d => d.risk === 'High' || d.risk === 'Critical')} fill={CHART_COLORS.red} fillOpacity={0.85} />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="card overflow-hidden mb-4">
        <div className="px-4 pt-4 pb-1"><h3 className="text-[13.5px] font-semibold text-ink">Priority Review Queue</h3><p className="text-xs text-muted mt-0.5">Real High/Critical risk projects, in scope</p></div>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead><tr>{['Work ID', 'Location', 'Risk Score', 'Risk', 'Assigned To', ''].map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {priorityQueue.map(p => (
                <tr key={p.id}>
                  <td className="font-mono font-semibold text-navy whitespace-nowrap">{p.id}</td>
                  <td className="whitespace-nowrap">{p.district || '—'}, {p.state || '—'}</td>
                  <td className="font-semibold text-ink">{p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}</td>
                  <td><RiskBadge risk={p.risk} /></td>
                  <td className="text-muted">Unassigned</td>
                  <td><Link to={`/projects/${encodeURIComponent(p.id)}`} className="text-xs font-semibold text-navy">Review →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {priorityQueue.length === 0 && <div className="p-8 text-center text-sm text-muted">No High or Critical risk projects in the current scope.</div>}
        </div>
      </div>

      <Disclaimer />
    </PageContainer>
  )
}