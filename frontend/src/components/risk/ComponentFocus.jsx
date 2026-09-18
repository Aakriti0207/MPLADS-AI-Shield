import React from 'react'
import { GLOSSARY, statusTone } from '../../lib/riskModel'
import {
  ComponentIcon,
  ContributionBar,
  EvidenceFacts,
  InfoTip,
  StatusPill,
  UnavailableNote,
} from './RiskPrimitives'

/* ==========================================================================
   COMPONENT FOCUS
   ==========================================================================
   One risk component, rendered in full, for the per-domain tabs (Financials,
   Timeline, Payments, Compliance, Duplicates, AI Insights).

   Same data and same reasoning chain as the Why Flagged card on the Risk
   Fusion tab -- always expanded here, because on a dedicated tab the
   component IS the subject of the page rather than one of several.

   Three outcomes, kept strictly distinct:
     - component missing from the payload  -> cannot be reported
     - component present, status NONE      -> ran, found nothing
     - component present, triggered        -> full reasoning chain
   ========================================================================== */

export default function ComponentFocus({ model, name, title }) {
  const component = model?.components?.find(item => item.name === name) || null

  if (!component) {
    return (
      <UnavailableNote>
        {title || 'This risk component'} was not reported in the current risk response for this
        project, so it cannot be explained here.
      </UnavailableNote>
    )
  }

  const tone = statusTone(component.status)
  const hasEvidence = component.evidence.some(
    item => item && typeof item === 'object' && Object.keys(item).length > 0
  )

  return (
    <div>
      {/* Header: label, status, and the three separate quantities */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <span className="inline-flex items-center gap-2.5 min-w-0">
          <span
            className="inline-flex items-center justify-center w-8 h-8 rounded-md shrink-0"
            style={{ color: tone.color, backgroundColor: tone.bg }}
          >
            <ComponentIcon name={component.name} size={16} />
          </span>
          <span className="min-w-0">
            <span className="flex items-center gap-1.5">
              <span className="text-[13.5px] font-semibold text-ink">{component.label}</span>
              <InfoTip text={component.description} label={component.label} />
            </span>
            <span className="block text-[11px] text-muted mt-0.5">
              {component.triggered
                ? `${component.reasons.length} signal(s) recorded`
                : 'Evaluated — no signal triggered'}
            </span>
          </span>
        </span>

        <StatusPill status={component.status} />
      </div>

      <dl className="grid grid-cols-3 gap-3 rounded-md bg-panel/60 border border-line px-3.5 py-3">
        <div>
          <dt className="text-[10.5px] text-muted flex items-center gap-1">
            Raw score
            <InfoTip text={GLOSSARY.raw_score} label="Raw score" />
          </dt>
          <dd className="text-[15px] font-semibold text-ink tabular-nums mt-0.5">
            {component.rawScore.toFixed(1)} <span className="text-[11px] text-muted">/ 100</span>
          </dd>
        </div>
        <div>
          <dt className="text-[10.5px] text-muted flex items-center gap-1">
            Weight
            <InfoTip text={GLOSSARY.weight} label="Weight" />
          </dt>
          <dd className="text-[15px] font-semibold text-ink tabular-nums mt-0.5">
            {component.weight.toFixed(0)}%
          </dd>
        </div>
        <div>
          <dt className="text-[10.5px] text-muted flex items-center gap-1">
            Contribution
            <InfoTip text={GLOSSARY.contribution} label="Contribution" />
          </dt>
          <dd className="text-[15px] font-semibold tabular-nums mt-0.5" style={{ color: tone.color }}>
            {component.contribution.toFixed(2)} <span className="text-[11px] text-muted">pts</span>
          </dd>
        </div>
      </dl>

      <div className="mt-2.5 flex items-center gap-3">
        <ContributionBar pct={component.barPct} color={tone.color} />
        <span className="w-[120px] shrink-0 text-right text-[11px] text-muted tabular-nums">
          {component.sharePct.toFixed(1)}% of final risk
        </span>
      </div>

      {/* Why */}
      <div className="mt-4">
        <h4 className="text-[10.5px] font-semibold text-navy uppercase tracking-wide mb-1.5">
          Why was this flagged?
        </h4>

        {!component.triggered ? (
          <p className="text-[12.5px] text-ink leading-5">
            This component ran against the available data for this project and produced no signal,
            so it contributed zero points. That is a result, not an absence of data — check the Data
            Quality panel on the Risk Fusion tab to confirm this domain was evaluable.
          </p>
        ) : component.reasons.length === 0 ? (
          <UnavailableNote>
            This component contributed points, but no reason text was recorded for it.
          </UnavailableNote>
        ) : (
          <ul className="space-y-1.5">
            {component.reasons.map((reason, index) => (
              <li key={index} className="flex gap-2 text-[12.5px] text-ink leading-5">
                <span className="mt-[7px] shrink-0 w-1 h-1 rounded-full bg-muted" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Evidence */}
      {component.triggered && (
        <div className="mt-4">
          <h4 className="text-[10.5px] font-semibold text-navy uppercase tracking-wide mb-1.5">
            Evidence
          </h4>

          {!component.evidenceAvailable ? (
            <UnavailableNote>
              Structured evidence values were not stored in the current processed risk dataset. The
              reasons above remain the backend&apos;s own explanations; re-running the risk pipeline
              restores the detailed evidence fields.
            </UnavailableNote>
          ) : hasEvidence ? (
            <div className="space-y-2">
              {component.evidence.map((evidence, index) => (
                <EvidenceFacts key={index} evidence={evidence} />
              ))}
            </div>
          ) : (
            <UnavailableNote>
              No structured evidence values were recorded for this signal.
            </UnavailableNote>
          )}
        </div>
      )}

      {/* What to review */}
      {component.triggered && component.reviewActions.length > 0 && (
        <div className="mt-4">
          <h4 className="text-[10.5px] font-semibold text-navy uppercase tracking-wide mb-1.5">
            What to review
          </h4>
          <ul className="space-y-1.5">
            {component.reviewActions.map((action, index) => (
              <li key={index} className="text-[12px] text-ink leading-5 flex gap-2">
                <span className="mt-[7px] shrink-0 w-1 h-1 rounded-full bg-navy" />
                <span>{action}</span>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-muted mt-2 italic">
            Review suggestions, not automated conclusions.
          </p>
        </div>
      )}
    </div>
  )
}