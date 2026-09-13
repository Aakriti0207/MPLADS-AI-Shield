import React, { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Eye } from 'lucide-react'
import { fetchPublicOverview } from '../features/dashboard/api'
import { formatNumber, toNumber } from '../lib/formatters'
import { CHART_COLORS, RISK_TONE } from '../lib/theme'
import { Disclaimer } from '../components/UI'
import EmptyState from '../components/ui/EmptyState'
import ChartCard from '../components/ui/ChartCard'
import Methodology from '../components/ai/Methodology'
import PublicNavbar from '../components/layout/PublicNavbar'

/**
 * Public AI Insights (Phase 6).
 *
 * Reachable anonymously at /ai-insights -- see app/routes.jsx
 * (publicRoutes) -- and must never redirect to /login. Backed entirely
 * by GET /public/overview (the same anonymous-safe aggregate endpoint
 * Home.jsx already uses), never the authenticated /projects/:id/risk or
 * /dashboard/role-overview endpoints. It therefore never has access to,
 * and never renders, per-project risk reasons, stakeholder/private
 * information, review notes, or anything else scoped to an authenticated
 * account -- only national aggregates.
 *
 * Every number below comes straight from that response; nothing is
 * hardcoded. Sections the current backend response doesn't support
 * (category-level anomaly breakdown, historical trend) render an
 * explicit "not available" state instead of inventing numbers.
 */
export default function AiInsights() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchPublicOverview()
      .then(data => { if (!cancelled) setStats(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
    return () => { cancelled = true }
  }, [])

  const live = !!stats
  const loading = !stats && !error

  const totalProjects = live ? toNumber(stats.total_projects) : null
  const riskCounts = live ? (stats.risk_level_counts || {}) : {}
  const hasRiskCounts = live && Object.keys(riskCounts).length > 0
  const low = toNumber(riskCounts.LOW)
  const medium = toNumber(riskCounts.MEDIUM)
  const high = toNumber(riskCounts.HIGH)
  const critical = toNumber(riskCounts.CRITICAL)
  const requiringReview = hasRiskCounts ? (medium || 0) + (high || 0) + (critical || 0) : null
  const highPlusCritical = hasRiskCounts ? (high || 0) + (critical || 0) : null
  const avgFinancialProgress = live ? toNumber(stats.average_financial_progress) : null

  const kpis = [
    ['Projects Monitored', formatNumber(totalProjects)],
    ['Projects Requiring Review', hasRiskCounts ? formatNumber(requiringReview) : 'Not available'],
    ['High / Critical Risk Indicators', hasRiskCounts ? formatNumber(highPlusCritical) : 'Not available'],
    ['Average Financial Progress', avgFinancialProgress !== null ? `${Math.round(avgFinancialProgress)}%` : 'Not available'],
  ]

  const distributionData = hasRiskCounts
    ? [
      ['LOW', low], ['MEDIUM', medium], ['HIGH', high], ['CRITICAL', critical],
    ].map(([key, value]) => ({ name: RISK_TONE[key].label, key, value: value || 0 }))
    : []

  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />

      <div className="max-w-[1200px] mx-auto px-5 py-6">
        <h1 className="text-[19px] font-semibold text-ink">AI Insights</h1>
        <p className="text-[13px] text-muted mt-1.5 max-w-[680px]">
          AI-assisted indicators for monitoring MPLADS implementation at scale. AI Shield identifies patterns that may warrant review -- it does not identify individuals or establish wrongdoing.
        </p>
        {loading && <p className="text-xs text-muted mt-2">Loading national indicators…</p>}
        {error && <p className="text-xs mt-2" style={{ color: CHART_COLORS.red }}>Could not load public AI indicators: {error}</p>}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          {kpis.map(([label, value]) => (
            <div className="card p-4" key={label}>
              <div className="text-xs text-muted">{label}</div>
              <div className="text-[20px] font-semibold mt-1.5 text-ink">{value}</div>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-4 mt-4">
          <ChartCard title="Risk Distribution" subtitle="National, from currently stored risk levels" height={230}>
            {distributionData.length ? (
              <ResponsiveContainer>
                <BarChart data={distributionData} margin={{ left: -14, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={v => Number(v).toLocaleString()} contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]} fill={CHART_COLORS.blue} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center"><EmptyState text="Risk distribution is not available from the current dataset." /></div>
            )}
          </ChartCard>

          <ChartCard title="Historical Trend" subtitle="Review indicators over time" height={230}>
            <div className="h-full flex items-center">
              <EmptyState text="Historical trend unavailable for the current dataset." />
            </div>
          </ChartCard>
        </div>

        <div className="card p-4 mt-4">
          <h3 className="text-[13.5px] font-semibold text-ink">AI Signal Categories</h3>
          <p className="text-xs text-muted mt-0.5 mb-2">National breakdown by anomaly category</p>
          <EmptyState text="Category-level anomaly data is not available for the current dataset." />
        </div>

        <div className="mt-4"><Methodology /></div>

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