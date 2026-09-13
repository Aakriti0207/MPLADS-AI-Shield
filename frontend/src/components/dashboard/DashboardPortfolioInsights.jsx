import React from 'react'
import { Section } from '../UI'
import EmptyState from '../ui/EmptyState'
import { formatNumber } from '../../lib/formatters'
import { CHART_COLORS } from './dashboardColors'

const TOP_N = 5

function topN(rows, valueKey, n = TOP_N) {
  return [...rows]
    .sort((a, b) => {
      const av = typeof a[valueKey] === 'number' ? a[valueKey] : -Infinity
      const bv = typeof b[valueKey] === 'number' ? b[valueKey] : -Infinity
      return bv - av
    })
    .slice(0, n)
}

function ShareBar({ label, value, total, color }) {
  const known = value !== null && total !== null && total > 0
  const pct = known ? Math.min(100, Math.round((value / total) * 100)) : null
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span className="text-muted">{label}</span>
        <span className="font-semibold text-ink">
          {value !== null ? formatNumber(value) : 'Not available'}
          {known && <span className="text-muted font-normal"> · {pct}%</span>}
        </span>
      </div>
      <div className="h-2 rounded-full bg-panel overflow-hidden">
        {known && <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />}
      </div>
    </div>
  )
}

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
              <span className="text-ink/80 truncate pr-2">{row[labelKey]}</span>
              <span className="font-semibold text-ink shrink-0">{formatValue(raw)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-panel overflow-hidden">
              {known && <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: CHART_COLORS.blue }} />}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function DashboardPortfolioInsights({
  totalProjects, activeProjects, completedProjects, delayedProjects,
  avgPhysicalProgress, byState, byWorkType,
}) {
  const stateRows = topN((byState || []).filter(r => r && r.state), 'total_expenditure')
  const workTypeRows = topN((byWorkType || []).filter(r => r && r.work_type), 'count')

  return (
    <div className="grid lg:grid-cols-5 gap-4">
      <div className="card p-4 lg:col-span-2">
        <Section title="Portfolio Status" subtitle="Execution status across the full portfolio" />
        <div className="space-y-4">
          <ShareBar label="Active" value={activeProjects} total={totalProjects} color={CHART_COLORS.blue} />
          <ShareBar label="Completed" value={completedProjects} total={totalProjects} color={CHART_COLORS.green} />
          <ShareBar label="Delayed" value={delayedProjects} total={totalProjects} color={CHART_COLORS.amber} />
        </div>
        <div className="mt-4 pt-3 border-t border-line">
          <div className="text-xs text-muted mb-1">Average physical progress</div>
          {avgPhysicalProgress !== null
            ? (
              <div className="w-full">
                <div className="h-2 bg-panel rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.round(avgPhysicalProgress)}%`, backgroundColor: CHART_COLORS.navy }} />
                </div>
                <div className="text-xs text-muted mt-1">{Math.round(avgPhysicalProgress)}%</div>
              </div>
            )
            : <div className="text-xs text-muted">Not reported by the current backend data.</div>}
        </div>
      </div>

      <div className="card p-4 lg:col-span-3">
        <Section title="Portfolio Composition" subtitle="Top states and work types by volume" />
        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <div className="text-[10.5px] font-semibold text-muted mb-2.5 uppercase tracking-wide">Top states by expenditure</div>
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
            <div className="text-[10.5px] font-semibold text-muted mb-2.5 uppercase tracking-wide">Top work types</div>
            {workTypeRows.length
              ? <RankedList rows={workTypeRows} labelKey="work_type" valueKey="count" formatValue={v => formatNumber(v)} />
              : <EmptyState text="Work-type breakdown not available." />}
          </div>
        </div>
      </div>
    </div>
  )
}