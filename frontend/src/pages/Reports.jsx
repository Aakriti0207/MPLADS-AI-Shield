import React, { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, FileText, Loader2, Printer } from 'lucide-react'
import { money } from '../data'
import { API_BASE } from '../lib/api'
import { fetchDashboardStats } from '../features/dashboard/api'
import { fetchProjects } from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'

// How many of the most recently loaded projects to scan for the
// "high-priority projects" list below. The backend has no risk-level
// filter query param, so this reads one page (the API's own page cap)
// rather than the full table -- see the note under the list.
const SCAN_LIMIT = 100
const LIST_LIMIT = 8

export default function Reports() {
  const [stats, setStats] = useState(null)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      fetchDashboardStats(),
      fetchProjects({ skip: 0, limit: SCAN_LIMIT }),
    ]).then(([statsData, projectsData]) => {
      if (cancelled) return
      setStats(statsData)
      setRows(projectsData)
    }).catch(err => {
      if (!cancelled) setError(err.message || 'Failed to reach the API')
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  const projects = useMemo(() => rows.map(r => ({
    id: r.id ?? '—',
    state: r.state ?? null,
    district: r.district ?? null,
    workType: r.workType ?? null,
    sanctioned: r.sanctioned,
    expenditure: r.expenditure,
    financialProgress: r.financialProgress,
    risk: r.risk,
  })), [rows])

  const highPriority = useMemo(
    () => projects.filter(p => p.risk === 'High' || p.risk === 'Critical').slice(0, LIST_LIMIT),
    [projects]
  )

  const financialPct = p => p.financialProgress !== null
    ? Math.round(p.financialProgress)
    : ((p.sanctioned && p.expenditure !== null) ? Math.min(100, Math.round((p.expenditure / p.sanctioned) * 100)) : null)

  const totalProjects = stats ? stats.total_projects ?? null : null
  const riskCounts = stats ? (stats.risk_level_counts || {}) : {}
  const highRiskCount = (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0)
  const delayedCount = stats ? stats.delayed_projects ?? null : null

  const summaryItems = [
    ['Total projects', totalProjects !== null ? totalProjects.toLocaleString() : 'Not available'],
    ['High risk', stats ? highRiskCount.toLocaleString() : 'Not available'],
    ['Delayed', delayedCount !== null ? delayedCount.toLocaleString() : 'Not available'],
  ]

  const print = () => window.print()

  return (
    <PageContainer maxWidth="950px">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-5 no-print">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">Reports</h1>
          <p className="text-[13px] text-muted mt-0.5">A presentation-ready summary for review meetings.</p>
        </div>
        <button onClick={print} className="btn-primary" disabled={loading || !!error}><Printer size={15} /> Print / Save PDF</button>
      </div>

      <div className="card p-6 print:shadow-none">
        <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
          <div>
            <div className="eyebrow">MPLADS Insight</div>
            <h2 className="text-[17px] font-semibold mt-1 text-ink">Project Monitoring Summary</h2>
            <p className="text-xs text-muted mt-1">Live backend data, generated {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' })}</p>
          </div>
          <FileText className="text-navy" size={18} />
        </div>

        {loading && <div className="py-14 flex flex-col items-center gap-2 text-muted"><Loader2 className="animate-spin" size={20} /><span className="text-sm">Loading report data from the API…</span></div>}

        {!loading && error && (
          <div className="py-10 text-center">
            <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#c0392b' }} />
            <div className="font-semibold text-[13.5px]" style={{ color: '#c0392b' }}>Could not load report data</div>
            <p className="text-sm text-muted mt-1">{error}</p>
            <p className="text-xs text-muted mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
          </div>
        )}

        {!loading && !error && (
          <>
            <div className="grid sm:grid-cols-3 gap-3 my-5">
              {summaryItems.map(x => (
                <div className="rounded-md bg-panel p-3.5" key={x[0]}><div className="text-xs text-muted">{x[0]}</div><div className="text-[20px] font-semibold mt-1 text-ink">{x[1]}</div></div>
              ))}
            </div>

            <h3 className="font-semibold text-[13.5px] text-ink">High-priority projects</h3>
            {highPriority.length === 0
              ? <p className="text-sm text-muted mt-2.5">No high or critical risk projects found in the currently loaded page of results.</p>
              : (
                <div className="mt-2.5 divide-y divide-line">
                  {highPriority.map(p => {
                    const pct = financialPct(p)
                    return (
                      <div className="py-3.5 flex justify-between gap-4" key={p.id}>
                        <div><b className="text-ink text-[13px]">{p.workType || 'Untitled work'}</b><div className="text-xs text-muted mt-1 font-mono">{p.id} · {p.state || '—'} · {p.district || '—'}</div></div>
                        <div className="text-right text-sm shrink-0"><b className="text-ink">{pct !== null ? `${pct}%` : 'Not available'}</b><div className="text-xs text-muted">financial progress</div></div>
                      </div>
                    )
                  })}
                </div>
              )}
            <p className="text-xs text-muted mt-2.5">Based on the first {rows.length} projects returned by the backend (maximum page size {SCAN_LIMIT}); this is not a complete portfolio ranking.</p>

            <div className="mt-6 rounded-md bg-info-bg p-3.5 text-sm text-ink"><b>Recommended review:</b> Validate delayed projects, compare physical and financial progress, and record authorized follow-up actions in the official workflow.</div>
          </>
        )}

        <div className="mt-6 text-xs text-muted">This is a SIH prototype backed by live project data. It is not an official Government of India report.</div>
      </div>
    </PageContainer>
  )
}