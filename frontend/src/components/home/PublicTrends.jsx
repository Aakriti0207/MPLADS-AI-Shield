import React, { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_COLORS } from '../../lib/theme'
import { formatCurrency } from '../../lib/formatters'
import ChartCard from '../ui/ChartCard'
import EmptyState from '../ui/EmptyState'

/**
 * Phase 5: public expenditure & completion trends.
 *
 * Reuses the app's existing Recharts dependency and the shared ChartCard
 * wrapper -- no new charting library.
 *
 * Every point comes from a REAL date in the source dataset
 * (last_expenditure_date / completion_date / sanction_date). Nothing is
 * interpolated, smoothed or back-filled:
 *
 *  - Months are only rendered between the first and last date actually
 *    observed in the data.
 *  - A month inside that range with no source rows arrives with
 *    `hasRecords: false` and is labelled "no records" in the tooltip
 *    rather than shown as a real zero-value measurement.
 *  - When a series has no usable dates at all, an explicit empty state
 *    is rendered instead of a chart.
 *
 * Coverage (how much of the portfolio each series can actually speak
 * for) is printed under each chart, because large parts of the source
 * dataset have no expenditure or completion dates at all.
 */

function coverageNote(trend) {
  if (!trend || !trend.totalProjects) return null

  const percent = trend.coveragePercent === null
    ? null
    : Math.round(trend.coveragePercent)

  return (
    `Based on ${trend.projectsWithData.toLocaleString()} of ` +
    `${trend.totalProjects.toLocaleString()} projects` +
    (percent === null ? '' : ` (${percent}%)`) +
    ' that carry this date in the source data.'
  )
}

function TrendTooltip({ active, payload, label, valueKey, formatValue }) {
  if (!active || !payload || !payload.length) return null

  const point = payload[0].payload

  return (
    <div
      className="bg-white rounded-md px-3 py-2"
      style={{ border: `1px solid ${CHART_COLORS.line}`, fontSize: 12 }}
    >
      <div className="font-semibold text-ink">{label}</div>
      {point.hasRecords ? (
        <div className="text-muted mt-0.5">{formatValue(point[valueKey])}</div>
      ) : (
        <div className="text-muted mt-0.5">No records in this month</div>
      )}
    </div>
  )
}

function axisProps() {
  return {
    tick: { fontSize: 10.5, fill: CHART_COLORS.muted },
    tickLine: false,
  }
}

export default function PublicTrends({ trends, scopeLabel = 'Nationwide' }) {
  const [financialSeries, setFinancialSeries] = useState('expenditure')

  const financial = trends?.[financialSeries] ?? null
  const completion = trends?.completion ?? null

  const financialData = useMemo(
    () => (financial?.points || []).map(point => ({
      label: point.label,
      amount: point.amount ?? 0,
      hasRecords: point.hasRecords,
    })),
    [financial]
  )

  const completionData = useMemo(
    () => (completion?.points || []).map(point => ({
      label: point.label,
      projectCount: point.projectCount,
      hasRecords: point.hasRecords,
    })),
    [completion]
  )

  // With 20-40 monthly points a tick per month is unreadable, so show
  // roughly six evenly spaced labels. This only affects tick labels --
  // every real data point is still plotted.
  const tickInterval = points => Math.max(0, Math.ceil(points.length / 6) - 1)

  const seriesToggle = (
    <div className="flex items-center gap-1">
      {[
        ['expenditure', 'Expenditure'],
        ['sanction', 'Sanctioned'],
      ].map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => setFinancialSeries(key)}
          className="text-[11px] font-medium px-2 py-1 rounded"
          style={{
            backgroundColor: financialSeries === key ? '#0b2e4f' : '#eef1f3',
            color: financialSeries === key ? '#ffffff' : '#55636e',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )

  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <div>
        <ChartCard
          title={financialSeries === 'expenditure' ? 'Expenditure Trend' : 'Sanctioned Amount Trend'}
          subtitle={`${scopeLabel} — monthly, from recorded dates`}
          action={seriesToggle}
          height={240}
        >
          {financialData.length ? (
            <ResponsiveContainer>
              <AreaChart data={financialData} margin={{ left: -6, right: 12, top: 8 }}>
                <defs>
                  <linearGradient id="publicSpendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.blue} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={CHART_COLORS.blue} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                <XAxis
                  dataKey="label"
                  interval={tickInterval(financialData)}
                  axisLine={{ stroke: CHART_COLORS.line }}
                  {...axisProps()}
                />
                <YAxis
                  axisLine={false}
                  tickFormatter={value => `₹${(value / 10000000).toFixed(0)}Cr`}
                  width={56}
                  {...axisProps()}
                />
                <Tooltip
                  content={<TrendTooltip valueKey="amount" formatValue={formatCurrency} />}
                />
                <Area
                  type="monotone"
                  dataKey="amount"
                  stroke={CHART_COLORS.blue}
                  strokeWidth={1.8}
                  fill="url(#publicSpendFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center">
              <EmptyState text="No recorded dates available for this series in the source data." />
            </div>
          )}
        </ChartCard>
        {financial?.basis && (
          <p className="text-[11px] text-muted mt-1.5 px-1 leading-snug">
            {financial.basis} {coverageNote(financial)}
          </p>
        )}
      </div>

      <div>
        <ChartCard
          title="Completion Trend"
          subtitle={`${scopeLabel} — works completed per month`}
          height={240}
        >
          {completionData.length ? (
            <ResponsiveContainer>
              <BarChart data={completionData} margin={{ left: -14, right: 12, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} vertical={false} />
                <XAxis
                  dataKey="label"
                  interval={tickInterval(completionData)}
                  axisLine={{ stroke: CHART_COLORS.line }}
                  {...axisProps()}
                />
                <YAxis axisLine={false} width={46} {...axisProps()} />
                <Tooltip
                  cursor={{ fill: '#eef1f3' }}
                  content={(
                    <TrendTooltip
                      valueKey="projectCount"
                      formatValue={value => `${Number(value).toLocaleString()} works completed`}
                    />
                  )}
                />
                <Bar dataKey="projectCount" radius={[3, 3, 0, 0]} fill={CHART_COLORS.green} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center">
              <EmptyState text="No recorded completion dates available in the source data." />
            </div>
          )}
        </ChartCard>
        {completion?.basis && (
          <p className="text-[11px] text-muted mt-1.5 px-1 leading-snug">
            {completion.basis} {coverageNote(completion)}
          </p>
        )}
      </div>
    </div>
  )
}
