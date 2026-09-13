import React from 'react'
import { formatCurrency, formatNumber, formatPercent } from '../../lib/formatters'
import KpiCard from '../ui/KpiCard'

function formatValue(value, format) {
  if (format === 'currency') return formatCurrency(value)
  if (format === 'percent') return formatPercent(value)
  return formatNumber(value)
}

/**
 * Renders a responsive grid of KPI cards from real /dashboard/stats
 * figures via the shared <KpiCard> primitive. Every value is formatted
 * through lib/formatters -- a missing/null figure always renders as
 * "Not available" rather than being silently coerced to 0.
 *
 * `items`: [{ key, label, value, format?, hint?, icon, tone? }]
 */
export default function DashboardKpiGrid({ items }) {
  return (
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
      {items.map(({ key, label, value, format = 'number', hint, icon, tone = 'navy' }) => (
        <KpiCard key={key} label={label} value={formatValue(value, format)} hint={hint} icon={icon} tone={tone} />
      ))}
    </div>
  )
}