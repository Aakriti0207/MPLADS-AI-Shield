import React, { useEffect, useState } from 'react'
import { AlertTriangle, FolderKanban, Wallet } from 'lucide-react'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Stat } from '../components/UI'
import ChartCard from '../components/ui/ChartCard'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import { fetchAnalytics } from '../features/analytics/api'
import { toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import PageContainer from '../components/layout/PageContainer'
const TOP_N = 9

function topNWithOther(rows, valueKey, labelKey, n) {
  const sorted = [...rows].sort((a, b) => b[valueKey] - a[valueKey])
  if (sorted.length <= n) return sorted
  const top = sorted.slice(0, n)
  const restSum = sorted.slice(n).reduce((a, r) => a + r[valueKey], 0)
  return [...top, { [labelKey]: 'Other', [valueKey]: restSum }]
}

export default function Analytics() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchAnalytics()
      .then(data => { if (!cancelled) setStats(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) return <PageContainer><LoadingState text="Loading analytics…" /></PageContainer>

  if (error) return (
    <PageContainer>
      <ErrorState title="Could not load analytics" message={error} onRetry={() => { setLoading(true); setError(null); fetchAnalytics().then(setStats).catch(err => setError(err.message)).finally(() => setLoading(false)) }} />
    </PageContainer>
  )

  const totalProjects = stats.total_projects ?? null
  const avgFinancialProgress = toNumber(stats.average_financial_progress)
  const riskCounts = stats.risk_level_counts || {}
  const highPlusCritical = (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0)
  const hasRiskCounts = Object.keys(riskCounts).length > 0

  const stateRows = (stats.by_state || []).map(r => ({
    state: r.state,
    utilized: (() => { const n = toNumber(r.total_expenditure); return n !== null ? Number((n / 10000000).toFixed(2)) : 0 })(),
  }))
  const stateChartData = topNWithOther(stateRows, 'utilized', 'state', TOP_N)
    .map(r => ({ ...r, state: r.state.length > 12 ? r.state.slice(0, 11) + '…' : r.state }))

  const workTypeRows = (stats.by_work_type || []).map(r => ({ work_type: r.work_type, count: r.count ?? 0 }))
  const workTypeChartData = topNWithOther(workTypeRows, 'count', 'work_type', TOP_N)
    .map(r => ({ ...r, work_type: r.work_type.length > 16 ? r.work_type.slice(0, 15) + '…' : r.work_type }))

  return (
    <PageContainer>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">Analytics</h1>
        <p className="text-[13px] text-muted mt-0.5">Real aggregate figures across the full project portfolio.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-3 mb-4">
        <Stat label="Average financial progress" value={avgFinancialProgress !== null ? `${Math.round(avgFinancialProgress)}%` : 'Not available'} icon={Wallet} tone="blue" />
        <Stat label="High + Critical risk projects" value={hasRiskCounts ? highPlusCritical.toLocaleString() : 'Not available'} icon={AlertTriangle} tone="amber" />
        <Stat label="Total projects" value={totalProjects !== null ? totalProjects.toLocaleString() : 'Not available'} icon={FolderKanban} tone="navy" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Expenditure by State" subtitle="₹ Crore, top states by expenditure" height={300}>
          {stateChartData.length > 0
            ? (
              <ResponsiveContainer>
                <BarChart data={stateChartData} layout="vertical" margin={{ left: 4 }}>
                  <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={CHART_COLORS.line} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                  <YAxis dataKey="state" type="category" width={88} tick={{ fontSize: 11, fill: CHART_COLORS.ink }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
                  <Bar dataKey="utilized" radius={[0, 4, 4, 0]} barSize={14}>{stateChartData.map((_, i) => <Cell key={i} fill={CHART_COLORS.blue} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            )
            : <div className="h-full flex items-center justify-center text-sm text-muted">State breakdown not available.</div>}
        </ChartCard>
        <ChartCard title="Work-Type Breakdown" subtitle="Project count by work type" height={300}>
          {workTypeChartData.length > 0
            ? (
              <ResponsiveContainer>
                <BarChart data={workTypeChartData} layout="vertical" margin={{ left: 4 }}>
                  <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={CHART_COLORS.line} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                  <YAxis dataKey="work_type" type="category" width={104} tick={{ fontSize: 11, fill: CHART_COLORS.ink }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={14}>{workTypeChartData.map((_, i) => <Cell key={i} fill={CHART_COLORS.navy} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            )
            : <div className="h-full flex items-center justify-center text-sm text-muted">Work-type breakdown not available.</div>}
        </ChartCard>
      </div>

      <div className="card mt-4 p-4">
        <div className="mb-3">
          <h3 className="text-[13.5px] font-semibold text-ink">How to Use This View</h3>
          <p className="text-xs text-muted mt-0.5">Reading the portfolio intelligence view</p>
        </div>
        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <div className="rounded-md bg-panel p-3.5"><b className="text-ink">1. Detect</b><p className="text-muted mt-1 text-xs">Find states or work types with concentrated spend or volume.</p></div>
          <div className="rounded-md bg-panel p-3.5"><b className="text-ink">2. Prioritize</b><p className="text-muted mt-1 text-xs">Open high-risk projects and inspect their evidence.</p></div>
          <div className="rounded-md bg-panel p-3.5"><b className="text-ink">3. Verify</b><p className="text-muted mt-1 text-xs">Authorized officials validate the signal before action.</p></div>
        </div>
      </div>
    </PageContainer>
  )
}