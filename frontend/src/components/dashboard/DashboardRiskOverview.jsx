import React from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import ChartCard from '../ui/ChartCard'
import EmptyState from '../ui/EmptyState'
import { Disclaimer } from '../UI'
import { RISK_COLORS, RISK_ORDER, riskLabel } from './dashboardColors'

/**
 * Risk distribution donut built only from the real risk_level_counts
 * breakdown. Never invents categories beyond LOW/MEDIUM/HIGH/CRITICAL,
 * and is explicit that these are advisory signals, not findings of fact.
 */
export default function DashboardRiskOverview({ riskCounts, hasRiskCounts, highPlusCritical }) {
  const data = RISK_ORDER.map(key => ({ key, name: riskLabel(key), value: riskCounts[key] ?? 0 }))

  return (
    <ChartCard title="Risk Overview" subtitle="AI-assisted advisory signal" height={180} className="h-full flex flex-col">
      <div className="h-full">
        {hasRiskCounts
          ? (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={46} outerRadius={68} paddingAngle={2}>
                  {data.map(d => <Cell key={d.key} fill={RISK_COLORS[d.key]} />)}
                </Pie>
                <Tooltip formatter={(value, name) => [Number(value).toLocaleString(), name]} />
              </PieChart>
            </ResponsiveContainer>
          )
          : <EmptyState text="Risk breakdown not available." />}
      </div>

      {hasRiskCounts && (
        <>
          <div className="grid grid-cols-4 gap-2 text-center text-xs mt-2">
            {data.map(d => (
              <div key={d.key}>
                <div className="font-semibold text-[13px]" style={{ color: RISK_COLORS[d.key] }}>{d.value.toLocaleString()}</div>
                <div className="text-muted mt-0.5">{d.name}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-muted border-t border-line pt-3">
            <span className="font-semibold text-ink">{highPlusCritical.toLocaleString()}</span> High or Critical risk project{highPlusCritical === 1 ? '' : 's'} may need prioritized review.
          </div>
        </>
      )}

      <div className="mt-3"><Disclaimer compact /></div>
    </ChartCard>
  )
}