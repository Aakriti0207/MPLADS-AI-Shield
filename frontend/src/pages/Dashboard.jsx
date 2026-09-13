import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Banknote, BarChart3, CheckCircle2, FolderKanban, Gauge, Info, ShieldAlert, TrendingUp } from 'lucide-react'
import { toNumber } from '../lib/formatters'
import { normalizeRole } from '../lib/roles'
import { useAuth } from '../context/AuthContext'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import EmptyState from '../components/ui/EmptyState'
import ChartCard from '../components/ui/ChartCard'
import PageContainer from '../components/layout/PageContainer'
import DashboardKpiGrid from '../components/dashboard/DashboardKpiGrid'
import DashboardFinancialOverview from '../components/dashboard/DashboardFinancialOverview'
import DashboardRiskOverview from '../components/dashboard/DashboardRiskOverview'
import DashboardPortfolioInsights from '../components/dashboard/DashboardPortfolioInsights'
import DashboardQuickAccess from '../components/dashboard/DashboardQuickAccess'
import ScopedDashboard from '../components/dashboard/ScopedDashboard'
import { RiskBadge } from '../components/UI'
import { fetchPublicOverview, fetchRoleDashboard } from '../features/dashboard/api'
import { CHART_COLORS } from '../components/dashboard/dashboardColors'

export default function Dashboard() {
  const { user } = useAuth()
  const role = normalizeRole(user?.role)

  // Only the Ministry/Admin role gets the national command-center view
  // below (matches the product brief: Ministry sees cross-state
  // aggregates, other roles see their own scope). State/District/MP
  // render ScopedDashboard instead, computed from real per-project data
  // filtered to their scope -- see that component for how "scope" works
  // pending a real backend scoping endpoint.
  if (role !== 'ministry') {
    return <PageContainer><ScopedDashboard role={role} /></PageContainer>
  }

  return <MinistryDashboard />
}

function MinistryDashboard() {
  const { isDemo } = useAuth()
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const request = isDemo
      ? fetchPublicOverview().then(stats => ({ stats, scope_available: true }))
      : fetchRoleDashboard()
    request
      .then(data => { if (!cancelled) setOverview(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isDemo])

  if (loading) return <PageContainer><LoadingState text="Loading dashboard…" /></PageContainer>

  if (error) return (
    <PageContainer>
      <ErrorState
        title="Could not load dashboard statistics"
        message={error}
        onRetry={() => { setLoading(true); setError(null); fetchRoleDashboard().then(setOverview).catch(err => setError(err.message)).finally(() => setLoading(false)) }}
      />
    </PageContainer>
  )

  const stats = overview?.stats
  if (!stats) return <PageContainer><ErrorState title="Dashboard scope unavailable" message="The backend did not return a Ministry dashboard scope." /></PageContainer>

  const totalProjects = toNumber(stats.total_projects)
  const totalSanctioned = toNumber(stats.total_sanctioned_amount)
  const totalExpenditure = toNumber(stats.total_expenditure)
  const avgFinancialProgress = toNumber(stats.average_financial_progress)
  const avgPhysicalProgress = toNumber(stats.average_physical_progress)
  const activeProjects = toNumber(stats.active_projects)
  const completedProjects = toNumber(stats.completed_projects)
  const delayedProjects = toNumber(stats.delayed_projects)

  const utilizationPct = (totalSanctioned && totalExpenditure !== null)
    ? Math.round((totalExpenditure / totalSanctioned) * 100) : null

  const riskCounts = stats.risk_level_counts || {}
  const hasRiskCounts = Object.keys(riskCounts).length > 0
  const high = toNumber(riskCounts.HIGH)
  const medium = toNumber(riskCounts.MEDIUM)
  const critical = toNumber(riskCounts.CRITICAL)
  const highPlusCritical = (high || 0) + (critical || 0)
  const reviewQueue = hasRiskCounts ? (high || 0) + (medium || 0) + (critical || 0) : null

  const kpiItems = [
    { key: 'critical', label: 'Critical', value: critical, format: 'number', hint: 'Stored critical signals', icon: AlertTriangle, tone: 'red' },
    { key: 'high', label: 'High', value: high, format: 'number', hint: 'Stored high-risk signals', icon: ShieldAlert, tone: 'amber' },
    { key: 'medium', label: 'Medium', value: medium, format: 'number', hint: 'Stored medium-risk signals', icon: Info, tone: 'navy' },
    { key: 'reviewQueue', label: 'Review Queue', value: reviewQueue, format: 'number', hint: 'Medium + High + Critical', icon: CheckCircle2, tone: 'blue' },
  ]

  return (
    <PageContainer>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">National AI Command Center</h1>
        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">Monitor project health, anomalies and review priorities across MPLADS.</p>
      </div>

      <div className="mb-4"><DashboardKpiGrid items={kpiItems} /></div>

      <div className="grid lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <DashboardFinancialOverview
            totalSanctioned={totalSanctioned}
            totalExpenditure={totalExpenditure}
            utilizationPct={utilizationPct}
            avgFinancialProgress={avgFinancialProgress}
          />
        </div>
        <DashboardRiskOverview
          riskCounts={riskCounts}
          hasRiskCounts={hasRiskCounts}
          highPlusCritical={highPlusCritical}
        />
      </div>

      <div className="mb-4">
        <DashboardPortfolioInsights
          totalProjects={totalProjects}
          activeProjects={activeProjects}
          completedProjects={completedProjects}
          delayedProjects={delayedProjects}
          avgPhysicalProgress={avgPhysicalProgress}
          byState={stats.by_state}
          byWorkType={stats.by_work_type}
        />
      </div>

      <div className="mb-4"><StateRiskOverview rows={overview.by_state_risk} /></div>

      <div className="card p-4 mb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="font-semibold text-[13.5px] text-ink">Prioritized Review</div>
          <p className="text-[12.5px] text-muted mt-1 max-w-2xl">
            {hasRiskCounts
              ? <>There are <b className="text-ink">{highPlusCritical.toLocaleString()}</b> High or Critical risk projects across the portfolio. Use the Risk filter on the Projects page to review them individually with full detail and evidence.</>
              : 'Risk-level counts are not available from the current backend data. Open Projects to review individual project risk detail.'}
          </p>
        </div>
        <Link to="/projects" className="btn-primary shrink-0">Review projects</Link>
      </div>

      {overview.priority_projects?.length > 0 && (
        <div className="card overflow-hidden mb-4">
          <div className="px-4 pt-4 pb-3">
            <h3 className="text-[13.5px] font-semibold text-ink">Priority Review Queue</h3>
            <p className="text-xs text-muted mt-0.5">Real projects with stored medium, high, or critical advisory signals</p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr>{['Work ID', 'State', 'Risk Score', 'Risk', 'Progress', ''].map(label => <th key={label}>{label}</th>)}</tr></thead>
              <tbody>
                {overview.priority_projects.map(project => (
                  <tr key={project.id}>
                    <td className="font-mono font-semibold text-navy whitespace-nowrap">{project.id}</td>
                    <td>{project.state || '—'}</td>
                    <td>{project.riskScore !== null ? project.riskScore : '—'}</td>
                    <td><RiskBadge risk={project.risk} /></td>
                    <td>{project.financialProgress !== null ? `${project.financialProgress}%` : '—'}</td>
                    <td><Link to={`/projects/${encodeURIComponent(project.id)}`} className="text-xs font-semibold text-navy">Review →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mb-4"><DashboardQuickAccess /></div>

      <div className="text-xs text-muted flex items-center gap-1.5">
        <CheckCircle2 size={13} /> AI outputs shown on this dashboard are advisory risk-prioritization signals for authorized human review. An anomaly does not, by itself, establish fraud or wrongdoing.
      </div>
    </PageContainer>
  )
}

function StateRiskOverview({ rows }) {
    const ranked = (rows || [])
      .map(row => ({ ...row, review: row.medium + row.high + row.critical }))
      .filter(row => row.review > 0)
      .sort((a, b) => b.review - a.review)
      .slice(0, 8)
    const max = ranked[0]?.review || 1

    return (
      <div className="card p-4">
        <div className="font-semibold text-[13.5px] text-ink">State-wise Risk Overview</div>
        <p className="text-xs text-muted mt-0.5 mb-3">States with the highest stored review indicators</p>
        {ranked.length ? (
          <div className="space-y-2.5">
            {ranked.map(row => (
              <div key={row.state}>
                <div className="flex items-baseline justify-between text-xs mb-1">
                  <span className="text-ink truncate pr-2">{row.state}</span>
                  <span className="font-semibold text-ink">{row.review.toLocaleString()}</span>
                </div>
                <div className="h-1.5 rounded-full bg-panel overflow-hidden">
                  <div className="h-full rounded-full bg-warn" style={{ width: `${Math.max(4, Math.round((row.review / max) * 100))}%` }} />
                </div>
              </div>
            ))}
          </div>
        ) : <EmptyState text="State risk data not available." />}
      </div>
    )
  }