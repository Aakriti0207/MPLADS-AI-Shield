import React from 'react'
import { Info } from 'lucide-react'
import { formatDateLong, formatDateTime } from '../../lib/publicFormat'

/**
 * "Data last updated" strip. Only renders values the backend actually
 * provided; if neither exists it renders nothing rather than a guess.
 */
export default function DataFreshness({ meta, className = '' }) {
  if (!meta) return null
  const refreshed = formatDateTime(meta.refreshedAt)
  const latest = formatDateLong(meta.latestRecordDate)
  if (!refreshed && !latest && !meta.sourceNote) return null

  return (
    <div className={`flex items-start gap-2.5 text-[13px] text-muted ${className}`}>
      <Info size={16} className="mt-0.5 shrink-0 text-blue" aria-hidden="true" />
      <div>
        {refreshed && <div><span className="font-semibold text-ink">Data last updated:</span> {refreshed}</div>}
        {latest && <div><span className="font-semibold text-ink">Latest activity in the records:</span> {latest}</div>}
        {meta.sourceNote && <div className="mt-0.5">{meta.sourceNote}</div>}
      </div>
    </div>
  )
}