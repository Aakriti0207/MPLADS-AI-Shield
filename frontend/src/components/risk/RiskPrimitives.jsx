import React from 'react'
import {
  CalendarClock,
  CreditCard,
  Database,
  IndianRupee,
  Info,
  Layers,
  Radar,
  Scale,
  ShieldCheck,
} from 'lucide-react'
import {
  NOTE_EVIDENCE_KEYS,
  evidenceKeyLabel,
  formatEvidenceValue,
  statusTone,
} from '../../lib/riskModel'

/* ==========================================================================
   Shared primitives for the Risk Fusion / Explainable AI panels.
   Presentation only -- nothing here reads or derives a risk number.
   ========================================================================== */

// Per-component icon. Paired with the label and the numeric score everywhere,
// never used as the only carrier of meaning.
export const COMPONENT_ICONS = {
  compliance: ShieldCheck,
  financial_anomaly: IndianRupee,
  timeline_anomaly: CalendarClock,
  duplicate: Layers,
  payment: CreditCard,
  isolation_forest: Radar,
  data_quality: Database,
}

export function ComponentIcon({ name, size = 15, className = '' }) {
  const Icon = COMPONENT_ICONS[name] || Scale
  return <Icon size={size} className={className} aria-hidden="true" />
}

/** Hover/focus tooltip. Focusable so it is reachable by keyboard, not mouse only. */
export function Tooltip({ text, children }) {
  if (!text) return children
  return (
    <span className="relative inline-flex items-center group/tip">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 hidden group-hover/tip:block group-focus-within/tip:block w-max max-w-[300px] rounded-md bg-ink text-white text-[11px] leading-4 px-2.5 py-1.5 shadow-lg z-40 text-left font-normal normal-case tracking-normal"
      >
        {text}
      </span>
    </span>
  )
}

/** Small (i) affordance carrying a glossary definition. */
export function InfoTip({ text, label }) {
  if (!text) return null
  return (
    <Tooltip text={text}>
      <button
        type="button"
        aria-label={label ? `What does "${label}" mean?` : 'More information'}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-muted hover:text-navy focus:outline-none focus:ring-2 focus:ring-navy/40 shrink-0 align-middle"
      >
        <Info size={13} />
      </button>
    </Tooltip>
  )
}

/** Severity pill. Always renders the status WORD, never colour alone. */
export function StatusPill({ status, className = '' }) {
  const tone = statusTone(status)
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold tracking-wide shrink-0 ${className}`}
      style={{ color: tone.color, backgroundColor: tone.bg }}
    >
      {tone.label}
    </span>
  )
}

/** Contribution bar. Width is proportional to the real contributed points. */
export function ContributionBar({ pct, color, height = 8 }) {
  const clamped = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0))
  return (
    <div
      className="w-full rounded-full overflow-hidden"
      style={{ backgroundColor: '#e7ebef', height }}
    >
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${clamped}%`, backgroundColor: color }}
      />
    </div>
  )
}

/**
 * One structured evidence dict, rendered as a fact list.
 *
 * Every value shown here came from the backend's evidence payload. Nothing is
 * defaulted, rounded into existence, or filled in when absent -- an evidence
 * dict with no displayable facts renders nothing rather than an empty shell.
 */
export function EvidenceFacts({ evidence }) {
  if (!evidence || typeof evidence !== 'object') return null

  const note =
    evidence.review_note ||
    evidence.peer_comparison_note ||
    evidence.evidence_note ||
    evidence.note ||
    null

  const facts = Object.entries(evidence).filter(
    ([key, value]) =>
      !NOTE_EVIDENCE_KEYS.has(key) &&
      value !== null &&
      value !== undefined &&
      (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
  )

  if (facts.length === 0 && !note) return null

  const hasPeerBenchmark =
    evidence.peer_group_size !== undefined ||
    evidence.peer_median_display !== undefined ||
    evidence.peer_median !== undefined

  return (
    <div className="rounded-md border border-line bg-panel/50 px-3 py-2.5">
      {hasPeerBenchmark && (
        <div className="mb-2 pb-1.5 border-b border-line text-[10.5px] font-semibold text-navy uppercase tracking-wide">
          Peer benchmark
        </div>
      )}

      <dl className="grid sm:grid-cols-2 gap-x-5 gap-y-1.5">
        {facts.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-3 sm:block">
            <dt className="text-muted text-[11px]">{evidenceKeyLabel(key)}</dt>
            <dd className="text-ink font-medium text-[12px] text-right sm:text-left break-words">
              {formatEvidenceValue(key, value)}
            </dd>
          </div>
        ))}
      </dl>

      {note && <p className="text-muted text-[11px] leading-4 mt-2 italic">{note}</p>}
    </div>
  )
}

/**
 * Explicit "we could not evaluate this" state.
 *
 * Deliberately distinct from a zero/clean state: an unavailable signal must
 * never be presentable as an absence of risk.
 */
export function UnavailableNote({ children }) {
  return (
    <p className="text-[12px] text-muted leading-5 rounded-md border border-dashed border-line px-3 py-2">
      {children}
    </p>
  )
}

export function PanelHeading({ icon: Icon, title, subtitle, tooltip, action }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={16} className="text-navy shrink-0" aria-hidden="true" />}
          <h3 className="font-semibold text-[14px] text-ink">{title}</h3>
          <InfoTip text={tooltip} label={title} />
        </div>
        {subtitle && <p className="text-[12px] text-muted mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}