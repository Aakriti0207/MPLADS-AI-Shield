import React from 'react'

const TONE_CHIP = {
  navy: 'bg-panel text-navy',
  blue: 'bg-info-bg text-blue',
  green: 'bg-good-bg text-good',
  amber: 'bg-warn-bg text-warn',
  red: 'bg-bad-bg text-bad',
}

// Standard KPI tile used across Dashboard, Home (public snapshot), and
// Analytics. `value` is pre-formatted by the caller (via lib/formatters)
// so this component stays purely presentational.
export default function KpiCard({ label, value, hint, icon: Icon, tone = 'navy' }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-muted">{label}</span>
        {Icon && <Icon size={15} className={(TONE_CHIP[tone] || TONE_CHIP.navy).split(' ')[1]} />}
      </div>
      <div className="text-[22px] font-semibold leading-none mt-2 text-ink">{value}</div>
      {hint && <div className="text-xs text-muted mt-2">{hint}</div>}
    </div>
  )
}