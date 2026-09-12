import React from 'react'
import { Section } from '../UI'
import EmptyState from '../ui/EmptyState'
import { formatNumber } from '../../lib/formatters'
import { CHART_COLORS } from './dashboardColors'

const TOP_N = 5

// Ranks by a numeric field without treating a missing/null value as 0 --
// rows with no usable number simply sort to the bottom rather than
// appearing to tie with a genuine zero.
function topN(rows, valueKey, n = TOP_N) {
  return [...rows]
    .sort((a, b) => {
      const av = typeof a[valueKey] === 'number' ? a[valueKey] : -Infinity
      const bv = typeof b[valueKey] === 'number' ? b[valueKey] : -Infinity
      return bv - av
    })
    .slice(0, n)
}

// A single portfolio-status row: raw count on the right, a proportional
// bar only when both the count and the portfolio total are real numbers.
function ShareBar({ label, value, total, color }) {
  const known = value !== null && total !== null && total > 0
  const pct = known ? Math.min(100, Math.round((value / total) * 100)) : null
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span className="text-slate-500">{label}</span>
        <span className="font-semibold text-ink">
          {value !== null ? formatNumber(value) : 'Not available'}
          {known && <span className="text-slate-400 font-normal"> · {pct}%</span>}
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        {known && <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />}
      </div>
    </div>
  )
}

// Compact ranked list (no Recharts) used for the lightweight state /
// work-type breakdowns -- deliberately simpler than the full charts on
// the Analytics page.
function RankedList({ rows, labelKey, valueKey, formatValue }) {
  const max = Math.max(...rows.map(r => (typeof r[valueKey] === 'number' ? r[valueKey] : 0)), 1)
  return (
    <div className="space-y-3">
      {rows.map(row => {
        const raw = row[valueKey]
        const known = typeof raw === 'number' && Number.isFinite(raw)
        const pct = known ? Math.max(4, Math.round((raw / max) * 100)) : 0
        return (
          <div key={row[labelKey]}>
            <div className="flex items-baseline justify-between text-xs mb-1">
              <span className="text-slate-600 truncate pr-2">{row[labelKey]}</span>
              <span className="font-semibold text-ink shrink-0">{formatValue(raw)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
              {known && <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: CHART_COLORS.blue }} />}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/**
 * Portfolio-level status (active/completed/delayed + physical progress)
 * and a lightweight state/work-type composition breakdown. Intentionally
 * restrained -- detailed breakdowns remain on the Analytics page.
 */
export default function DashboardPortfolioInsights({
  totalProjects, activeProjects, completedProjects, delayedProjects,
  avgPhysicalProgress, byState, byWorkType,
}) {
  const stateRows = topN((byState || []).filter(r => r && r.state), 'total_expenditure')
  const workTypeRows = topN((byWorkType || []).filter(r => r && r.work_type), 'count')

  return (
    <div className="grid lg:grid-cols-5 gap-5">
      <div className="card p-5 lg:col-span-2">
        <Section title="Portfolio status" subtitle="Execution status across the full portfolio" />
        <div className="space-y-4">
          <ShareBar label="Active" value={activeProjects} total={totalProjects} color={CHART_COLORS.blue} />
          <ShareBar label="Completed" value={completedProjects} total={totalProjects} color={CHART_COLORS.green} />
          <ShareBar label="Delayed" value={delayedProjects} total={totalProjects} color={CHART_COLORS.amber} />
        </div>
        <div className="mt-5 pt-4 border-t border-slate-100">
          <div className="text-xs text-slate-500 mb-1">Average physical progress</div>
          {avgPhysicalProgress !== null
            ? (
              <div className="w-full">
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.round(avgPhysicalProgress)}%`, backgroundColor: CHART_COLORS.navy }} />
                </div>
                <div className="text-xs text-slate-500 mt-1">{Math.round(avgPhysicalProgress)}%</div>
              </div>
            )
            : <div className="text-xs text-slate-400">Not reported by the current backend data.</div>}
        </div>
      </div>

      <div className="card p-5 lg:col-span-3">
        <Section title="Portfolio composition" subtitle="Top states and work types by volume" />
        <div className="grid sm:grid-cols-2 gap-6">
          <div>
            <div className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">Top states by expenditure</div>
            {stateRows.length
              ? <RankedList
                  rows={stateRows}
                  labelKey="state"
                  valueKey="total_expenditure"
                  formatValue={v => (typeof v === 'number' ? `₹${(v / 10000000).toFixed(1)} Cr` : 'Not available')}
                />
              : <EmptyState text="State breakdown not available." />}
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">Top work types</div>
            {workTypeRows.length
              ? <RankedList rows={workTypeRows} labelKey="work_type" valueKey="count" formatValue={v => formatNumber(v)} />
              : <EmptyState text="Work-type breakdown not available." />}
          </div>
        </div>
      </div>
    </div>
  )
}
