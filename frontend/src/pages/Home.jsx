import React, { useEffect, useState } from 'react'
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Eye } from 'lucide-react'
import { fetchPublicOverview } from '../features/dashboard/api'
import { formatCurrency, formatNumber, toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { Disclaimer } from '../components/UI'
import EmptyState from '../components/ui/EmptyState'
import IndiaStateGrid from '../components/home/IndiaStateGrid'
import PublicNavbar from '../components/layout/PublicNavbar'

/**
 * Public Overview backed by the anonymous, aggregate-only public endpoint.
 */
export default function Home() {
  const [stats, setStats] = useState(null)
  const [statsError, setStatsError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchPublicOverview()
      .then(data => { if (!cancelled) setStats(data) })
      .catch(err => { if (!cancelled) setStatsError(err.message || 'Failed to reach the API') })
    return () => { cancelled = true }
  }, [])

  const live = !!stats
  const loadingLive = !stats && !statsError

  const totalProjects = live ? toNumber(stats.total_projects) : null
  const totalSanctioned = live ? toNumber(stats.total_sanctioned_amount) : null
  const totalExpenditure = live ? toNumber(stats.total_expenditure) : null
  const completedProjects = live ? toNumber(stats.completed_projects) : null
  const riskCounts = live ? (stats.risk_level_counts || {}) : {}
  const hasRiskCounts = live && Object.keys(riskCounts).length > 0
  const requiresReview = hasRiskCounts ? (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0) + (riskCounts.MEDIUM || 0) : null

  const completedPct = (live && totalProjects && completedProjects !== null)
    ? Math.round((completedProjects / totalProjects) * 100) : null

  const kpis = [
    ['Total Projects', formatNumber(totalProjects), 'All recorded works'],
    ['Sanctioned Amount', formatCurrency(totalSanctioned), 'Cumulative sanction'],
    ['Expenditure', formatCurrency(totalExpenditure), 'Cumulative expenditure'],
    ['Completed Works', formatNumber(completedProjects), completedPct !== null ? `${completedPct}% of total` : ''],
    ['Requiring Review', hasRiskCounts ? formatNumber(requiresReview) : 'Not available', 'AI Shield indicators'],
  ]

  const statusColors = { Active: CHART_COLORS.blue, Completed: CHART_COLORS.green, Delayed: CHART_COLORS.amber, 'Not specified': CHART_COLORS.muted }
  const statusData = live ? (stats.status_distribution || []).map(item => ({
    name: item.status,
    value: toNumber(item.count) || 0,
    color: statusColors[item.status] || CHART_COLORS.muted,
  })).filter(d => d.value > 0) : []

  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />

      <div className="max-w-[1200px] mx-auto px-5 py-6">
        <h1 className="text-[21px] font-semibold text-ink">MPLADS Project Monitoring &amp; AI-Powered Risk Intelligence</h1>
        <p className="text-[13px] text-muted mt-1.5 max-w-[640px]">
          Transparent monitoring of MPLADS works, expenditure, progress and AI-powered indicators requiring review.
        </p>
        {loadingLive && <p className="text-xs text-muted mt-2">Loading national portfolio figures…</p>}
        {statsError && <p className="text-xs mt-2" style={{ color: CHART_COLORS.red }}>Could not load public figures: {statsError}</p>}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          {kpis.map(([label, value, hint]) => (
            <div className="card p-4" key={label}>
              <div className="text-xs text-muted">{label}</div>
              <div className="text-[20px] font-semibold mt-1.5 text-ink">{value}</div>
              {hint && <div className="text-[11px] text-muted mt-1.5">{hint}</div>}
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-5 gap-4 mt-4">
          <div className="card p-4 lg:col-span-3">
            <h3 className="text-[13.5px] font-semibold text-ink">State-wise MPLADS Monitoring</h3>
            <p className="text-xs text-muted mt-0.5 mb-3">{live ? 'Live, by cumulative expenditure -- select a state for detail' : 'State-wise data is not available.'}</p>
            <IndiaStateGrid data={live ? stats.by_state : null} />
          </div>
          <div className="card p-4 lg:col-span-2">
            <h3 className="text-[13.5px] font-semibold text-ink">Project Status Distribution</h3>
            <p className="text-xs text-muted mt-0.5">{live ? 'Live national distribution' : 'Status data is not available.'}</p>
            {statusData.length ? (
              <div style={{ height: 230 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={2}>
                      {statusData.map(d => <Cell key={d.name} fill={d.color} />)}
                    </Pie>
                    <Legend verticalAlign="bottom" height={44} iconSize={9} wrapperStyle={{ fontSize: 11 }} />
                    <Tooltip formatter={v => Number(v).toLocaleString()} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="py-10">
                <EmptyState text="Status breakdown not available." />
              </div>
            )}
          </div>
        </div>

        <div className="card p-4 mt-4">
          <h3 className="text-[13.5px] font-semibold text-ink">Expenditure &amp; Completion Trend</h3>
          <p className="text-xs text-muted mt-0.5 mb-2">Monthly expenditure trend</p>
          <div className="py-8">
            <EmptyState text="Monthly trend data is not available from the current source." />
          </div>
        </div>

        <div className="card mt-4 overflow-hidden">
          <div className="px-4 pt-4 pb-3">
            <h3 className="text-[13.5px] font-semibold text-ink">Recently Monitored Projects</h3>
            <p className="text-xs text-muted mt-0.5">{live ? 'Public summaries of recently updated works' : 'Project data is not available.'}</p>
          </div>
          {live ? (
            !stats.recent_projects?.length ? (
              <div className="py-10 px-4"><EmptyState text="No monitored projects found." /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr>{['Work ID', 'Work', 'State', 'Constituency', 'Status', 'Sanctioned', 'Expenditure', 'Progress'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                  <tbody>
                    {stats.recent_projects.map(p => (
                      <tr key={p.id}>
                        <td className="font-mono font-semibold text-navy whitespace-nowrap">{p.id ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.workType ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.state ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.constituency ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.status ?? '—'}</td>
                        <td className="whitespace-nowrap">{formatCurrency(p.sanctioned)}</td>
                        <td className="whitespace-nowrap">{formatCurrency(p.expenditure)}</td>
                        <td className="whitespace-nowrap">{p.financialProgress !== null ? `${p.financialProgress}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : (
            <div className="py-10 px-4"><EmptyState text="Public project data is not available." /></div>
          )}
        </div>

        <div className="mt-4"><Disclaimer /></div>
      </div>

      <footer className="border-t border-line bg-white mt-10">
        <div className="max-w-[1200px] mx-auto px-5 py-5 text-xs text-muted flex flex-wrap justify-between gap-3">
          <span>© 2026 MPLADS AI Shield -- SIH prototype</span>
          <span className="flex items-center gap-1.5"><Eye size={12} /> AI-assisted advisory signals -- not an official Government of India portal</span>
        </div>
      </footer>
    </div>
  )
}