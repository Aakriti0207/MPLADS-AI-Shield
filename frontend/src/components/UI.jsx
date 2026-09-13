import React from 'react'
import { riskTone, statusTone } from '../lib/theme'

// Generic pill. Colour/background are always passed explicitly (from
// src/lib/theme.js) rather than via Tailwind utility classes, so the
// exact hex tokens stay in one place instead of drifting per-component.
export function Badge({ children, color = '#55636e', bg = '#eef1f3', className = '' }) {
  return (
    <span className={`badge ${className}`} style={{ color, backgroundColor: bg, borderColor: `${color}22` }}>
      {children}
    </span>
  )
}

export function RiskBadge({ risk }) {
  const tone = riskTone(risk)
  return <Badge color={tone.color} bg={tone.bg}>{risk ? `${tone.label}` : 'Unknown'}</Badge>
}

export function StatusBadge({ status }) {
  const tone = statusTone(status)
  return <Badge color={tone.color} bg={tone.bg}>{status || 'Unknown'}</Badge>
}

export function Section({ title, subtitle, action, children }) {
  return (
    <section className="mb-5">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div>
          <h2 className="font-semibold text-[14.5px] text-ink">{title}</h2>
          {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

// Same visual language as the Dashboard's own DashboardKpiGrid cards, for
// screens (Analytics, Reports) that only need one or two standalone
// stat tiles rather than the full grid component.
export function Stat({ label, value, hint, icon: Icon, tone = 'navy' }) {
  const chipClass = {
    navy: 'bg-panel text-navy',
    blue: 'bg-info-bg text-blue',
    green: 'bg-good-bg text-good',
    amber: 'bg-warn-bg text-warn',
    red: 'bg-bad-bg text-bad',
  }[tone] || 'bg-panel text-navy'

  return (
    <div className="card p-4">
      <div className="flex justify-between items-start gap-3">
        <div className="min-w-0">
          <div className="text-xs text-muted">{label}</div>
          <div className="text-[22px] font-semibold mt-1.5 text-ink truncate leading-none">{value}</div>
          {hint && <div className="text-xs text-muted mt-2">{hint}</div>}
        </div>
        {Icon && (
          <div className={`h-9 w-9 shrink-0 rounded-md flex items-center justify-center ${chipClass}`}>
            <Icon size={16} />
          </div>
        )}
      </div>
    </div>
  )
}

export function Progress({ value, color = '#1d63a8' }) {
  const pct = value === null || value === undefined ? 0 : Math.min(100, Math.max(0, value))
  return (
    <div className="w-full">
      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#e7ebef' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      {value !== null && value !== undefined && <div className="text-xs text-muted mt-1">{Math.round(value)}%</div>}
    </div>
  )
}

// Standard disclaimer strip -- reused verbatim on every screen that
// surfaces a risk score or AI-derived indicator, so the wording never
// drifts between pages.
export function Disclaimer({ compact = false }) {
  return (
    <div className={`flex items-start gap-2 rounded-md bg-info-bg border border-line ${compact ? 'px-2.5 py-1.5' : 'px-3 py-2.5'}`}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" style={{ color: '#2b6cb0' }} aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
        <path d="M12 11v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="12" cy="8" r="1" fill="currentColor" />
      </svg>
      <p className="text-xs text-muted leading-4">
        AI Shield identifies indicators requiring review. It does not establish fraud or wrongdoing. Final verification and decisions remain with authorized officials.
      </p>
    </div>
  )
}

export const EmptyState = ({ text }) => <div className="py-12 text-center text-muted text-sm">{text}</div>