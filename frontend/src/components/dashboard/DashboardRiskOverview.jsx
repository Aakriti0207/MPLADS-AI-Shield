import React from 'react'
import { Info } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Section } from '../UI'
import EmptyState from '../ui/EmptyState'
import { RISK_COLORS, RISK_ORDER, riskLabel } from './dashboardColors'

/**
 * Risk distribution donut built only from the real risk_level_counts
 * breakdown. Never invents categories beyond LOW/MEDIUM/HIGH/CRITICAL,
 * and is explicit that these are advisory signals, not findings of fact.
 */
export default function DashboardRiskOverview({ riskCounts, hasRiskCounts, highPlusCritical }) {
  const data = RISK_ORDER.map(key => ({ key, name: riskLabel(key), value: riskCounts[key] ?? 0 }))

  return (
    <div className="card p-5 h-full flex flex-col">
      <Section title="Risk overview" subtitle="AI-assisted advisory signal" />

      <div className="h-48">
        {hasRiskCounts
          ? (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={3}>
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
                <div className="font-bold text-sm" style={{ color: RISK_COLORS[d.key] }}>{d.value.toLocaleString()}</div>
                <div className="text-slate-500 mt-0.5">{d.name}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-slate-500 border-t border-slate-100 pt-3">
            <span className="font-semibold text-ink">{highPlusCritical.toLocaleString()}</span> High or Critical risk project{highPlusCritical === 1 ? '' : 's'} may need prioritized review.
          </div>
        </>
      )}

      <div className="mt-3 flex items-start gap-2 rounded-lg bg-blue-50/60 border border-blue-100 px-3 py-2">
        <Info size={14} className="text-blue-700 mt-0.5 shrink-0" />
        <p className="text-[11px] leading-4 text-slate-600">
          AI outputs are advisory risk-prioritization signals to support authorized human review. An elevated or anomalous score does not, by itself, establish fraud, misconduct, or wrongdoing.
        </p>
      </div>
    </div>
  )
}
