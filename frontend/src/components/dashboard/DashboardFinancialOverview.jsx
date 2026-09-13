import React from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Progress } from '../UI'
import ChartCard from '../ui/ChartCard'
import EmptyState from '../ui/EmptyState'
import { CHART_COLORS } from './dashboardColors'

function CrTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  return (
    <div className="rounded-md border border-line bg-white px-3 py-2 text-xs shadow-soft">
      <div className="font-semibold text-ink">{name}</div>
      <div className="text-muted mt-0.5">₹{Number(value).toFixed(2)} Cr</div>
    </div>
  )
}

/**
 * Sanctioned vs. expenditure comparison for the whole portfolio, built
 * only from the two real /dashboard/stats totals. Deliberately does NOT
 * render a monthly trend -- the backend has no verified time-series for
 * this figure, so an honest two-bar comparison replaces it.
 */
export default function DashboardFinancialOverview({ totalSanctioned, totalExpenditure, utilizationPct, avgFinancialProgress }) {
  const hasTotals = totalSanctioned !== null && totalExpenditure !== null
  const chartData = hasTotals ? [
    { name: 'Sanctioned', value: Number((totalSanctioned / 10000000).toFixed(2)) },
    { name: 'Expenditure', value: Number((totalExpenditure / 10000000).toFixed(2)) },
  ] : []

  return (
    <ChartCard title="Financial Overview" subtitle="Sanctioned vs. spent, across the full portfolio (₹ Crore)" height={240} className="h-full flex flex-col">
      <div className="h-full">
        {hasTotals
          ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ left: 4, right: 4, top: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke={CHART_COLORS.line} />
                <XAxis dataKey="name" tick={{ fontSize: 11.5, fill: CHART_COLORS.muted }} axisLine={{ stroke: CHART_COLORS.line }} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 11, fill: CHART_COLORS.muted }}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: '₹ Crore', angle: -90, position: 'insideLeft', fontSize: 11, fill: CHART_COLORS.muted }}
                />
                <Tooltip content={<CrTooltip />} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={64}>
                  {chartData.map((entry, i) => (
                    <Cell key={entry.name} fill={i === 0 ? CHART_COLORS.navy : CHART_COLORS.blue} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )
          : <EmptyState text="Financial totals not available." />}
      </div>

      <div className="mt-3 text-sm">
        <span className="text-muted">Utilization: </span>
        <span className="font-semibold text-ink">{utilizationPct !== null ? `${utilizationPct}%` : 'Not available'}</span>
        <span className="text-muted"> of sanctioned funds</span>
      </div>

      {avgFinancialProgress !== null ? (
        <div className="mt-3">
          <div className="text-xs text-muted mb-1">Average financial progress (scored projects)</div>
          <Progress value={Math.round(avgFinancialProgress)} color={CHART_COLORS.blue} />
        </div>
      ) : (
        <div className="mt-3 text-xs text-muted">Average financial progress not available.</div>
      )}
    </ChartCard>
  )
}