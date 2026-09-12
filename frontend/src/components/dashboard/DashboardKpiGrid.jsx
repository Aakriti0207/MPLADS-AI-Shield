import React from 'react'
import { formatCurrency, formatNumber, formatPercent } from '../../lib/formatters'

// Fully static class strings (never template-interpolated) so Tailwind's
// build-time content scanner can pick them up -- the same pattern already
// used by RiskBadge/StatusBadge in components/UI.jsx.
const TONE_CLASSES = {
  navy: 'bg-slate-100 text-navy',
  blue: 'bg-blue-50 text-blue-700',
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-rose-50 text-rose-700',
}

function formatValue(value, format) {
  if (format === 'currency') return formatCurrency(value)
  if (format === 'percent') return formatPercent(value)
  return formatNumber(value)
}

/**
 * Renders a responsive grid of KPI cards from real /dashboard/stats
 * figures. Every value is formatted through the shared lib/formatters
 * utilities (never re-implemented here) -- a missing/null figure always
 * renders as "Not available" rather than being silently coerced to 0.
 *
 * `items`: [{ key, label, value, format?, hint?, icon, tone? }]
 */
export default function DashboardKpiGrid({ items }) {
  return (
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {items.map(({ key, label, value, format = 'number', hint, icon: Icon, tone = 'navy' }) => (
        <div className="card p-5" key={key}>
          <div className="flex justify-between items-start gap-3">
            <div className="min-w-0">
              <div className="text-sm text-slate-500">{label}</div>
              <div className="text-2xl font-extrabold mt-2 text-ink truncate">
                {formatValue(value, format)}
              </div>
              {hint && <div className="text-xs text-slate-500 mt-2">{hint}</div>}
            </div>
            {Icon && (
              <div className={`h-10 w-10 shrink-0 rounded-xl flex items-center justify-center ${TONE_CLASSES[tone] || TONE_CLASSES.navy}`}>
                <Icon size={19} />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
