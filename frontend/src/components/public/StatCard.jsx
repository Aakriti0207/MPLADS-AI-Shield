import React from 'react'
import { NOT_AVAILABLE } from '../../lib/publicFormat'
import { ACCENT_TONES } from '../../lib/theme'

/**
 * One headline number a citizen can read in two seconds:
 * icon, big value, short title, one plain-language line.
 * `value === null` renders "Not available" -- never 0 or NaN.
 *
 * `tone` picks a restrained accent (icon colour + a 3px top border)
 * from the shared ACCENT_TONES palette so a row of stat cards reads
 * as a set of distinct, meaningful figures rather than five identical
 * navy boxes -- default falls back to the neutral brand navy.
 */
export default function StatCard({ icon: Icon, label, value, description, tone }) {
  const missing = value === null || value === undefined || value === ''
  const t = tone && ACCENT_TONES[tone]
  return (
    <div className={`pub-card p-5 h-full ${t ? `border-t-[3px] ${t.top}` : ''}`}>
      {Icon && (
        <span
          className={`inline-flex w-10 h-10 rounded-full items-center justify-center ${t ? `${t.bg} ${t.fg}` : 'bg-navy-bg text-navy'}`}
          aria-hidden="true"
        >
          <Icon size={19} />
        </span>
      )}
      <div className={`mt-3 font-bold leading-tight ${missing ? 'text-[18px] text-muted' : 'text-[25px] xl:text-[27px] text-navy'}`}>
        {missing ? NOT_AVAILABLE : value}
      </div>
      <div className="text-[14px] font-semibold text-ink mt-1">{label}</div>
      {description && <p className="text-[13px] text-muted mt-1.5 leading-snug">{description}</p>}
    </div>
  )
}