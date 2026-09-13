import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, Eye, ShieldCheck } from 'lucide-react'
import { fetchDashboardStats } from '../features/dashboard/api'
import { formatCurrency, toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { DEMO_PUBLIC_SNAPSHOT } from '../lib/mockData'
import { useAuth } from '../context/AuthContext'
import { RiskBadge, Disclaimer, Progress } from '../components/UI'
import IndiaStateGrid from '../components/home/IndiaStateGrid'

/**
 * Public Overview -- always shows the full layout (KPIs, state map,
 * status donut, expenditure trend, recent-projects table), matching the
 * approved visual reference. Real /dashboard/stats figures are overlaid
 * wherever the backend already supports them (KPI row, status donut,
 * via toNumber/formatCurrency); everything the backend doesn't yet
 * expose (state-wise tiers, monthly trend, a public projects sample)
 * falls back to the labeled DEMO_PUBLIC_SNAPSHOT in lib/mockData.js so
 * the page is never empty for an anonymous visitor.
 */
export default function Home() {
  const { isAuthenticated, status } = useAuth()
  const [stats, setStats] = useState(null)

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false
    fetchDashboardStats().then(data => { if (!cancelled) setStats(data) }).catch(() => {})
    return () => { cancelled = true }
  }, [isAuthenticated])

  const live = stats && isAuthenticated
  const totalProjects = live ? toNumber(stats.total_projects) : DEMO_PUBLIC_SNAPSHOT.totalProjects
  const totalSanctioned = live ? toNumber(stats.total_sanctioned_amount) : DEMO_PUBLIC_SNAPSHOT.totalSanctioned
  const totalExpenditure = live ? toNumber(stats.total_expenditure) : DEMO_PUBLIC_SNAPSHOT.totalExpenditure
  const completedProjects = live ? toNumber(stats.completed_projects) : DEMO_PUBLIC_SNAPSHOT.completedProjects
  const riskCounts = live ? (stats.risk_level_counts || {}) : null
  const requiresReview = riskCounts ? (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0) + (riskCounts.MEDIUM || 0) : DEMO_PUBLIC_SNAPSHOT.requiresReview

  const statusData = live
    ? [
        { name: 'Active', value: toNumber(stats.active_projects) || 0, color: CHART_COLORS.blue },
        { name: 'Completed', value: toNumber(stats.completed_projects) || 0, color: CHART_COLORS.green },
        { name: 'Delayed', value: toNumber(stats.delayed_projects) || 0, color: CHART_COLORS.amber },
      ]
    : DEMO_PUBLIC_SNAPSHOT.statusDistribution.map((d, i) => ({ ...d, color: [CHART_COLORS.muted, CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.amber][i] }))

  const kpis = [
    ['Total Projects', totalProjects !== null ? totalProjects.toLocaleString() : 'Not available', 'All recorded works'],
    ['Sanctioned Amount', formatCurrency(totalSanctioned), 'Cumulative sanction'],
    ['Expenditure', formatCurrency(totalExpenditure), live ? 'Live figure' : 'This fiscal year'],
    ['Completed Works', completedProjects !== null ? completedProjects.toLocaleString() : 'Not available', live ? '' : `${Math.round((completedProjects / totalProjects) * 100)}% of total`],
    ['Requiring Review', requiresReview.toLocaleString(), 'AI Shield indicators'],
  ]

  const sampleProjects = DEMO_PUBLIC_SNAPSHOT.sampleProjects

  return (
    <div className="min-h-screen bg-panel">
      <header className="bg-white border-b border-line">
        <div className="max-w-[1200px] mx-auto px-5 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="h-8 w-8 bg-navy text-white rounded-md flex items-center justify-center"><ShieldCheck size={16} /></div>
            <div className="leading-tight">
              <div className="text-[14px] font-bold text-navy">MPLADS Insight</div>
              <div className="text-[10px] text-muted">AI-Powered Project Monitoring</div>
            </div>
          </Link>
          <div className="flex gap-2">
            {isAuthenticated ? <Link to="/dashboard" className="btn-secondary">Dashboard</Link> : null}
            <Link to="/login" className="btn-primary">Secure Login <ArrowRight size={14} /></Link>
          </div>
        </div>
      </header>

      <div className="max-w-[1200px] mx-auto px-5 py-6">
        <h1 className="text-[21px] font-semibold text-ink">MPLADS Project Monitoring &amp; AI-Powered Risk Intelligence</h1>
        <p className="text-[13px] text-muted mt-1.5 max-w-[640px]">
          Transparent monitoring of MPLADS works, expenditure, progress and AI-powered indicators requiring review.
        </p>
        {!live && status !== 'checking' && (
          <p className="text-xs text-muted mt-2">
            Showing illustrative national figures. <Link to="/login" className="text-blue underline">Sign in</Link> to see this replaced with your live portfolio data.
          </p>
        )}

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
            <p className="text-xs text-muted mt-0.5 mb-3">Illustrative state grid -- select a state to view its indicator tier</p>
            <IndiaStateGrid />
          </div>
          <div className="card p-4 lg:col-span-2">
            <h3 className="text-[13.5px] font-semibold text-ink">Project Status Distribution</h3>
            <p className="text-xs text-muted mt-0.5">{live ? 'Live, national' : 'Illustrative, national'}</p>
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
          </div>
        </div>

        <div className="card p-4 mt-4">
          <h3 className="text-[13.5px] font-semibold text-ink">Expenditure Trend</h3>
          <p className="text-xs text-muted mt-0.5">Illustrative, monthly (₹ crore) -- pending a real time-series endpoint</p>
          <div style={{ height: 220 }}>
            <ResponsiveContainer>
              <AreaChart data={DEMO_PUBLIC_SNAPSHOT.trend} margin={{ left: -14, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_COLORS.muted }} axisLine={false} tickLine={false} />
                <Tooltip formatter={v => `₹${v} Cr`} />
                <Area type="monotone" dataKey="expenditure" name="Expenditure (₹ Cr)" stroke={CHART_COLORS.blue} fill={CHART_COLORS.blue} fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card mt-4 overflow-hidden">
          <div className="px-4 pt-4 pb-3">
            <h3 className="text-[13.5px] font-semibold text-ink">Recently Monitored Projects</h3>
            <p className="text-xs text-muted mt-0.5">Illustrative sample -- sign in for the full, live Project Explorer</p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr>{['Work ID', 'State', 'District', 'MP', 'Category', 'Sanctioned', 'Expenditure', 'Risk'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {sampleProjects.map(p => (
                  <tr key={p.id}>
                    <td className="font-mono font-semibold text-navy whitespace-nowrap">{p.id}</td>
                    <td className="whitespace-nowrap">{p.state}</td>
                    <td className="whitespace-nowrap">{p.district}</td>
                    <td className="whitespace-nowrap">{p.mpName}</td>
                    <td className="whitespace-nowrap">{p.workType}</td>
                    <td className="whitespace-nowrap">{formatCurrency(p.sanctioned)}</td>
                    <td className="whitespace-nowrap">{formatCurrency(p.expenditure)}</td>
                    <td><RiskBadge risk={p.risk} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-4"><Disclaimer /></div>
      </div>

      <footer className="border-t border-line bg-white mt-10">
        <div className="max-w-[1200px] mx-auto px-5 py-5 text-xs text-muted flex flex-wrap justify-between gap-3">
          <span>© 2026 MPLADS Insight -- SIH prototype</span>
          <span className="flex items-center gap-1.5"><Eye size={12} /> AI-assisted advisory signals -- not an official Government of India portal</span>
        </div>
      </footer>
    </div>
  )
}