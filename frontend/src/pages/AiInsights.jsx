import React, { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Eye } from 'lucide-react'
import { fetchPublicInsights } from '../features/public/api'
import { formatCurrency, formatNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { Disclaimer } from '../components/UI'
import EmptyState from '../components/ui/EmptyState'
import ChartCard from '../components/ui/ChartCard'
import Methodology from '../components/ai/Methodology'
import PublicNavbar from '../components/layout/PublicNavbar'

/**
 * Public AI Insights (Phase 6, revised in Phase 5's public overhaul).
 *
 * Reachable anonymously at /ai-insights -- see app/routes.jsx
 * (publicRoutes) -- and must never redirect to /login.
 *
 * Phase 5 change
 * --------------
 * This page previously read `risk_level_counts` off GET /public/overview
 * and rendered "Projects Requiring Review", "High / Critical Risk
 * Indicators" and a national Risk Distribution chart to ANONYMOUS
 * visitors. Risk levels are internal review signals, so that field was
 * removed from the public contract and those three elements were removed
 * with it.
 *
 * The page is now backed by GET /public/insights (the dedicated public
 * contract) and shows only public portfolio composition -- works by
 * category and lifecycle status. The Methodology section is kept: it
 * explains in prose how monitoring works, without publishing any score,
 * flag, reason or per-project indicator. Per-project risk intelligence
 * remains behind authentication at /ai-shield and /projects/:id.
 */
export default function AiInsights() {
  const [insights, setInsights] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchPublicInsights()
      .then(data => { if (!cancelled) setInsights(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
    return () => { cancelled = true }
  }, [])

  const loading = !insights && !error

  const kpis = insights ? [
    ['Projects Monitored', formatNumber(insights.kpis.totalProjects)],
    ['Completed Works', formatNumber(insights.kpis.completedProjects)],
    ['Active Works', formatNumber(insights.kpis.activeWorks)],
    [
      'Expenditure Utilised',
      insights.kpis.utilisationPercent === null
        ? 'Not available'
        : `${Math.round(insights.kpis.utilisationPercent)}%`,
    ],
  ] : [
    ['Projects Monitored', 'Not available'],
    ['Completed Works', 'Not available'],
    ['Active Works', 'Not available'],
    ['Expenditure Utilised', 'Not available'],
  ]

  // Public portfolio composition, not an AI signal breakdown.
  const categoryData = (insights?.byWorkType || [])
    .slice(0, 8)
    .map(row => ({ name: row.workType, value: row.count, expenditure: row.expenditure }))

  const statusData = (insights?.statusDistribution || [])
    .map(row => ({ name: row.status, value: row.count }))

  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />

      <div className="max-w-[1200px] mx-auto px-5 py-6">
        <h1 className="text-[19px] font-semibold text-ink">AI Insights</h1>
        <p className="text-[13px] text-muted mt-1.5 max-w-[680px]">
          How MPLADS implementation is monitored at scale, and what the public portfolio looks like. AI-assisted review indicators are internal signals and are not published here.
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
          <ChartCard title="Works by Category" subtitle="National, public portfolio composition" height={230}>
            {categoryData.length ? (
              <ResponsiveContainer>
                <BarChart data={categoryData} margin={{ left: -14, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} interval={0} height={44} angle={-18} textAnchor="end" />
                  <YAxis tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v, _name, item) => [`${Number(v).toLocaleString()} works (${formatCurrency(item.payload.expenditure)} spent)`, 'Works']} contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]} fill={CHART_COLORS.blue} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center"><EmptyState text="Category breakdown is not available from the current dataset." /></div>
            )}
          </ChartCard>

          <ChartCard title="Works by Lifecycle Status" subtitle="National, from recorded project status" height={230}>
            {statusData.length ? (
              <ResponsiveContainer>
                <BarChart data={statusData} margin={{ left: -14, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={v => Number(v).toLocaleString()} contentStyle={{ fontSize: 12, borderRadius: 6, border: `1px solid ${CHART_COLORS.line}` }} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]} fill={CHART_COLORS.green} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center"><EmptyState text="Status breakdown is not available from the current dataset." /></div>
            )}
          </ChartCard>
        </div>

        <div className="card p-4 mt-4">
          <h3 className="text-[13.5px] font-semibold text-ink">Per-project indicators</h3>
          <p className="text-xs text-muted mt-1 leading-relaxed max-w-[720px]">
            AI-assisted review indicators are internal monitoring signals used by authorised officials.
            They are not published on this public page, and they do not establish wrongdoing.
            Public project information — location, category, sanctioned amount, expenditure, progress,
            status and lifecycle dates — is available on the Overview and Projects pages.
          </p>
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