import React from 'react'
import { Info } from 'lucide-react'

/* ============================================================
   DESIGN TOKENS — from the approved reference (mplads-ai-shield.jsx)
   ============================================================ */
export const COLORS = {
  navy: '#0B2E4F',
  navy700: '#123A5C',
  blue: '#1D63A8',
  bg: '#F3F5F7',
  card: '#FFFFFF',
  border: '#DCE2E8',
  ink: '#16232E',
  inkSoft: '#55636E',
  green: '#1B8A5A',
  amber: '#B7791F',
  red: '#C0392B',
  info: '#2B6CB0',
}

export function Card({ children, className = '', style = {} }) {
  return (
    <div
      className={`bg-white rounded-md ${className}`}
      style={{ border: `1px solid ${COLORS.border}`, ...style }}
    >
      {children}
    </div>
  )
}

export function SectionTitle({ title, subtitle, right }) {
  return (
    <div className="flex items-end justify-between mb-3 gap-3">
      <div>
        <h2 className="text-[15px] font-semibold" style={{ color: COLORS.ink }}>{title}</h2>
        {subtitle && <p className="text-[12.5px] mt-0.5" style={{ color: COLORS.inkSoft }}>{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

export function KpiCard({ label, value, sub, tone = 'default', icon: Icon }) {
  const toneColor = tone === 'danger' ? COLORS.red : tone === 'warn' ? COLORS.amber : tone === 'good' ? COLORS.green : COLORS.navy
  return (
    <Card className="p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-medium" style={{ color: COLORS.inkSoft }}>{label}</span>
        {Icon && <Icon size={16} style={{ color: toneColor }} />}
      </div>
      <div className="text-[24px] font-semibold leading-none" style={{ color: COLORS.ink }}>{value}</div>
      {sub && <div className="text-[11.5px]" style={{ color: COLORS.inkSoft }}>{sub}</div>}
    </Card>
  )
}

export function ChartCard({ title, subtitle, children, height = 260, className = '' }) {
  return (
    <Card className={`p-4 ${className}`}>
      <div className="mb-2">
        <h3 className="text-[13.5px] font-semibold" style={{ color: COLORS.ink }}>{title}</h3>
        {subtitle && <p className="text-[11.5px]" style={{ color: COLORS.inkSoft }}>{subtitle}</p>}
      </div>
      <div style={{ height }}>{children}</div>
    </Card>
  )
}

export function tooltipStyle() {
  return {
    contentStyle: { fontSize: 12, borderRadius: 6, border: `1px solid ${COLORS.border}` },
    labelStyle: { color: COLORS.ink, fontWeight: 600 },
  }
}

export function Badge({ children, color, bg }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tracking-wide whitespace-nowrap"
      style={{ color, backgroundColor: bg, border: `1px solid ${color}22` }}
    >
      {children}
    </span>
  )
}

// Accepts either 'LOW' | 'Low' | 'MEDIUM' | ... — the backend risk_level is
// upper snake case, but normalizeProject()/formatRiskLevel() title-cases it
// for the rest of the app, so this stays tolerant of both.
export function riskMeta(level) {
  const key = String(level || '').toUpperCase()
  switch (key) {
    case 'LOW': return { label: 'LOW', color: COLORS.green, bg: '#E7F4EC' }
    case 'MEDIUM': return { label: 'MEDIUM', color: COLORS.amber, bg: '#FBF0DE' }
    case 'HIGH': return { label: 'HIGH', color: '#B4552E', bg: '#FBE7DF' }
    case 'CRITICAL': return { label: 'CRITICAL', color: COLORS.red, bg: '#FADCD8' }
    default: return { label: 'UNKNOWN', color: COLORS.inkSoft, bg: '#EEF1F3' }
  }
}

export function RiskBadge({ level }) {
  const m = riskMeta(level)
  return <Badge color={m.color} bg={m.bg}>{m.label}</Badge>
}

export function ProgressBar({ pct, color = COLORS.blue }) {
  if (pct === null || pct === undefined) {
    return <div className="w-full h-2 rounded-full" style={{ backgroundColor: '#E7EBEF' }} />
  }
  return (
    <div className="w-full h-2 rounded-full" style={{ backgroundColor: '#E7EBEF' }}>
      <div className="h-2 rounded-full" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, backgroundColor: color }} />
    </div>
  )
}

export function Disclaimer({ compact = false }) {
  return (
    <div
      className={`flex items-start gap-2 rounded ${compact ? 'px-2.5 py-1.5' : 'px-3 py-2'}`}
      style={{ backgroundColor: '#EEF3F8', border: `1px solid ${COLORS.border}` }}
    >
      <Info size={14} style={{ color: COLORS.info, marginTop: 1, flexShrink: 0 }} />
      <p className="text-[11.5px]" style={{ color: COLORS.inkSoft }}>
        AI Shield identifies indicators requiring review. It does not establish fraud or wrongdoing.
      </p>
    </div>
  )
}

// Shown in place of chart bodies when the backend genuinely doesn't expose
// the underlying figures yet — never a fabricated/mock chart.
export function ChartUnavailable({ text }) {
  return (
    <div className="h-full flex items-center justify-center text-center px-6">
      <p className="text-[12.5px]" style={{ color: COLORS.inkSoft }}>{text}</p>
    </div>
  )
}
