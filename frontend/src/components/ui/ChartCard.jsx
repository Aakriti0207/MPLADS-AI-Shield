import React from 'react'

// Shared chart wrapper: title/subtitle header + fixed-height plot area.
// Every Recharts <ResponsiveContainer> in the app should sit inside one
// of these so chart cards look identical across Dashboard/Analytics/
// ProjectDetails instead of each screen hand-rolling its own header.
export default function ChartCard({ title, subtitle, action, height = 260, children, className = '' }) {
  return (
    <div className={`card p-4 ${className}`}>
      <div className="flex items-end justify-between mb-2 gap-3">
        <div>
          <h3 className="text-[13.5px] font-semibold text-ink">{title}</h3>
          {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div style={{ height }}>{children}</div>
    </div>
  )
}