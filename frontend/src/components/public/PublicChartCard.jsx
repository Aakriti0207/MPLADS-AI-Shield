import React from 'react'
import { ACCENT_TONES } from '../../lib/theme'

/**
 * Chart frame for citizens: plain-language title, one line explaining
 * what it shows, a text summary of the takeaway (also read by screen
 * readers), the chart itself, and the same numbers as an accessible
 * table behind "View as table".
 *
 * `tone` adds a restrained 3px top border from the shared accent
 * palette, purely so a row of chart cards doesn't read as one
 * undifferentiated grey/white block -- optional, defaults to none.
 */
export default function PublicChartCard({ title, description, summary, children, table, tone, className = '' }) {
  const t = tone && ACCENT_TONES[tone]
  return (
    <section className={`pub-card p-5 ${t ? `border-t-[3px] ${t.top}` : ''} ${className}`} aria-label={title}>
      <h3 className="text-[17px] font-bold text-navy">{title}</h3>
      {description && <p className="text-[13.5px] text-muted mt-1">{description}</p>}
      {summary && <p className="text-[14px] text-ink mt-3 font-medium">{summary}</p>}
      <div className="mt-4">{children}</div>
      {table && (
        <details className="mt-4">
          <summary className="cursor-pointer text-[13.5px] font-semibold text-blue">View as table</summary>
          <div className="mt-3 overflow-x-auto">{table}</div>
        </details>
      )}
    </section>
  )
}

/** Small accessible data table used inside PublicChartCard. */
export function ChartTable({ caption, columns, rows }) {
  return (
    <table className="w-full text-[13.5px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="text-left border-b border-line text-muted">
          {columns.map(col => <th key={col} scope="col" className="py-2 pr-4 font-semibold">{col}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-line last:border-0">
            {row.map((cell, j) => (
              j === 0
                ? <th key={j} scope="row" className="py-2 pr-4 font-medium text-ink text-left">{cell}</th>
                : <td key={j} className="py-2 pr-4 text-ink">{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}