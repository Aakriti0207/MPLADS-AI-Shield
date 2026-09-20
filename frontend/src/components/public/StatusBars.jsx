import React from 'react'
import { sortStatuses, statusStyle } from '../../lib/publicTheme'
import { formatCount, formatPercent } from '../../lib/publicFormat'

/**
 * Simple status summary: one labelled bar per status with count and
 * share. Uses the backend's existing status categories only -- nothing
 * is invented, and zero-count statuses are omitted.
 */
export default function StatusBars({ rows = [] }) {
  const data = sortStatuses(rows.filter(row => row.count > 0))
  const total = data.reduce((sum, row) => sum + row.count, 0)
  if (!total) return null
  const max = Math.max(...data.map(row => row.count))

  return (
    <ul className="space-y-3.5">
      {data.map(row => {
        const style = statusStyle(row.status)
        const Icon = style.icon
        const share = row.count / total * 100
        return (
          <li key={row.status}>
            <div className="flex items-center justify-between gap-3 text-[14px]">
              <span className="inline-flex items-center gap-1.5 font-semibold" style={{ color: style.text }} title={style.hint}>
                <Icon size={15} aria-hidden="true" /> {row.status}
              </span>
              <span className="text-ink">
                <strong>{formatCount(row.count)}</strong>
                <span className="text-muted"> &middot; {formatPercent(share, share < 10 ? 1 : 0)}</span>
              </span>
            </div>
            <div className="mt-1.5 h-3 rounded-full bg-[#e3e8ed] overflow-hidden" aria-hidden="true">
              <div className="h-full rounded-full" style={{ width: `${Math.max(2, row.count / max * 100)}%`, backgroundColor: style.bar }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}