import React from 'react'
import { NOT_AVAILABLE } from '../../lib/publicFormat'

/**
 * One headline number a citizen can read in two seconds:
 * icon, big value, short title, one plain-language line.
 * `value === null` renders "Not available" -- never 0 or NaN.
 */
export default function StatCard({ icon: Icon, label, value, description }) {
  const missing = value === null || value === undefined || value === ''
  return (
    <div className="pub-card p-5 h-full">
      {Icon && (
        <span className="inline-flex w-10 h-10 rounded-full bg-navy-bg text-navy items-center justify-center" aria-hidden="true">
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