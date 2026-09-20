import React from 'react'
import { clampPercent, formatPercent } from '../../lib/publicFormat'

/**
 * "Funds used" bar. Width is clamped to 0-100 but the printed figure is
 * the real value (so >100% is shown honestly, not hidden).
 */
export default function UtilisationBar({ percent, label = 'of sanctioned amount spent', compact = false }) {
  const clamped = clampPercent(percent)
  if (clamped === null) return null
  const text = formatPercent(percent, percent < 10 && percent > 0 ? 1 : 0)
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 mb-1.5">
        <span className={`font-bold text-navy ${compact ? 'text-[15px]' : 'text-[20px]'}`}>{text}</span>
        <span className="text-[12.5px] text-muted">{label}</span>
      </div>
      <div
        className="h-2.5 rounded-full bg-[#e3e8ed] overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped)}
        aria-label={`${text} ${label}`}
      >
        <div className="h-full rounded-full bg-blue" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  )
}