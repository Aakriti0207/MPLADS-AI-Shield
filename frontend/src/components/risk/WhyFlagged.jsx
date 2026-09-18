import React, { useState } from 'react'
import { ChevronDown, CircleCheck, Lightbulb, SearchCheck } from 'lucide-react'
import { GLOSSARY, statusTone } from '../../lib/riskModel'
import {
  ComponentIcon,
  EvidenceFacts,
  InfoTip,
  PanelHeading,
  StatusPill,
  UnavailableNote,
} from './RiskPrimitives'

/* ==========================================================================
   SECTION 5 -- WHY THIS PROJECT WAS FLAGGED   (+ SECTION 6 evidence, inline)
   ==========================================================================
   This is the panel that must never disappear. It is the counterpart to the
   Risk Breakdown table, not a duplicate of it:

     Risk Breakdown  = HOW MUCH each component contributed.
     Why Flagged     = WHY each component triggered, with the actual evidence.

   Each triggered component expands into the full reasoning chain:

     WHY?  ->  EVIDENCE  ->  RISK CALCULATION  ->  WHAT TO REVIEW

   Every reason string and every evidence value is rendered exactly as the
   backend's deterministic explanation engine produced it. Nothing here
   paraphrases, summarises, or generates prose about a project. A component
   with no reason text renders an explicit "not available" state rather than
   an invented sentence.
   ========================================================================== */

function ReasonList({ reasons }) {
  if (reasons.length === 0) {
    return (
      <UnavailableNote>
        This component contributed points, but no reason text was recorded for it in the current
        risk output.
      </UnavailableNote>
    )
  }

  return (
    <ul className="space-y-1.5">
      {reasons.map((reason, index) => (
        <li key={index} className="flex gap-2 text-[12.5px] text-ink leading-5">
          <span className="text-muted mt-[7px] shrink-0 w-1 h-1 rounded-full bg-muted" />
          <span>{reason}</span>
        </li>
      ))}
    </ul>
  )
}

function SubHeading({ children, tooltip }) {
  return (
    <div className="flex items-center gap-1.5 mb-1.5">
      <h5 className="text-[10.5px] font-semibold text-navy uppercase tracking-wide">{children}</h5>
      <InfoTip text={tooltip} label={String(children)} />
    </div>
  )
}

function ComponentCard({ component, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const tone = statusTone(component.status)
  const hasEvidence = component.evidence.some(
    item => item && typeof item === 'object' && Object.keys(item).length > 0
  )

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: open ? `${tone.color}44` : '#dce2e8' }}
    >
      <button
        type="button"
        onClick={() => setOpen(value => !value)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left hover:bg-panel/60 focus:outline-none focus:ring-2 focus:ring-navy/30"
        style={{ backgroundColor: open ? `${tone.bg}55` : 'transparent' }}
      >
        <span className="flex items-center gap-2.5 min-w-0">
          <span
            className="inline-flex items-center justify-center w-7 h-7 rounded-full shrink-0"
            style={{ color: tone.color, backgroundColor: tone.bg }}
          >
            <ComponentIcon name={component.name} size={14} />
          </span>
          <span className="text-[13px] font-semibold text-ink truncate">{component.label}</span>
          <StatusPill status={component.status} />
        </span>

        <span className="flex items-center gap-3 shrink-0">
          <span className="text-[11.5px] text-muted tabular-nums hidden sm:inline">
            Contribution: {component.contribution.toFixed(1)} ({component.sharePct.toFixed(1)}%)
          </span>
          <ChevronDown
            size={16}
            className={`text-muted transition-transform ${open ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        </span>
      </button>

      {open && (
        <div className="px-3.5 pb-3.5 pt-3 border-t border-line bg-white space-y-3.5">
          {component.description && (
            <p className="text-[11.5px] text-muted leading-4">{component.description}</p>
          )}

          {/* WHY? */}
          <div>
            <SubHeading tooltip="The deterministic explanation produced by this detection component for this project.">
              Why was this flagged?
            </SubHeading>
            <ReasonList reasons={component.reasons} />
          </div>

          {/* EVIDENCE */}
          <div>
            <SubHeading tooltip="The actual observed values behind each reason above, as recorded by the backend. No value here is estimated.">
              Evidence
            </SubHeading>

            {!component.evidenceAvailable ? (
              <UnavailableNote>
                Structured evidence values were not stored in the current processed risk dataset.
                The reasons above are the backend&apos;s own explanations and remain accurate;
                re-running the risk pipeline restores the detailed evidence fields.
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

          {/* RISK CALCULATION */}
          <div>
            <SubHeading tooltip={GLOSSARY.contribution}>Risk calculation</SubHeading>
            <dl className="grid grid-cols-3 gap-3 rounded-md bg-panel/60 border border-line px-3 py-2.5">
              <div>
                <dt className="text-[10.5px] text-muted flex items-center gap-1">
                  Raw score
                  <InfoTip text={GLOSSARY.raw_score} label="Raw score" />
                </dt>
                <dd className="text-[13px] font-semibold text-ink tabular-nums mt-0.5">
                  {component.rawScore.toFixed(1)} / 100
                </dd>
              </div>
              <div>
                <dt className="text-[10.5px] text-muted flex items-center gap-1">
                  Weight
                  <InfoTip text={GLOSSARY.weight} label="Weight" />
                </dt>
                <dd className="text-[13px] font-semibold text-ink tabular-nums mt-0.5">
                  {component.weight.toFixed(0)}%
                </dd>
              </div>
              <div>
                <dt className="text-[10.5px] text-muted flex items-center gap-1">
                  Contribution
                  <InfoTip text={GLOSSARY.contribution} label="Contribution" />
                </dt>
                <dd
                  className="text-[13px] font-semibold tabular-nums mt-0.5"
                  style={{ color: tone.color }}
                >
                  {component.contribution.toFixed(2)} pts
                </dd>
              </div>
            </dl>
          </div>

          {/* WHAT TO REVIEW */}
          {component.reviewActions.length > 0 && (
            <div>
              <SubHeading tooltip="Suggested checks for this category of signal. These are review prompts for a human officer, never automated conclusions about this project.">
                What to review
              </SubHeading>
              <ul className="space-y-1.5">
                {component.reviewActions.map((action, index) => (
                  <li key={index} className="flex gap-2 text-[12px] text-ink leading-5">
                    <SearchCheck
                      size={13}
                      className="mt-[3px] shrink-0 text-navy"
                      aria-hidden="true"
                    />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Legacy fallback: a flat list of the backend's reason strings.
 *
 * Used only when the per-component breakdown is genuinely unavailable. It
 * exists so this panel can NEVER collapse to nothing while the backend is
 * still returning real explanations -- losing that was the regression this
 * whole panel is meant to undo.
 */
function FlatReasonFallback({ reasons }) {
  return (
    <div>
      <UnavailableNote>
        A per-component breakdown is not available from the current risk response, so the reasons
        below are shown as a single list.
      </UnavailableNote>
      <ul className="space-y-2 mt-2.5">
        {reasons.map((reason, index) => (
          <li
            key={index}
            className="rounded-md border border-line px-3 py-2.5 text-[12.5px] text-ink leading-5"
          >
            {reason}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function WhyFlagged({ model }) {
  const { triggered, notTriggered, legacyReasons, hasComponents, dataQuality } = model

  const action = (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-1 text-[11px] font-semibold text-navy whitespace-nowrap">
      <Lightbulb size={12} aria-hidden="true" />
      {triggered.length} active risk signal{triggered.length === 1 ? '' : 's'}
    </span>
  )

  return (
    <div>
      <PanelHeading
        title="Why This Project Was Flagged"
        subtitle="Each triggered signal, the evidence behind it, and what a reviewer should check"
        tooltip="Explains WHY each component triggered. The Risk Breakdown table alongside it explains HOW MUCH each one contributed."
        action={action}
      />

      {!hasComponents && legacyReasons.length > 0 && (
        <FlatReasonFallback reasons={legacyReasons} />
      )}

      {hasComponents && triggered.length === 0 && (
        <div className="rounded-md border border-line bg-good-bg/50 px-3.5 py-3 flex items-start gap-2">
          <CircleCheck
            size={15}
            style={{ color: '#1b8a5a' }}
            className="mt-0.5 shrink-0"
            aria-hidden="true"
          />
          <div>
            <p className="text-[12.5px] text-ink leading-5">
              No risk signal triggered for this project across the components that could be
              evaluated.
            </p>
            {!dataQuality.complete && (
              <p className="text-[11.5px] text-muted leading-4 mt-1">
                Some evidence domains could not be evaluated. A clean result alongside missing data
                is not the same as a confirmed-normal project — see the Data Quality panel.
              </p>
            )}
          </div>
        </div>
      )}

      {triggered.length > 0 && (
        <div className="space-y-2">
          {triggered.map((component, index) => (
            <ComponentCard
              key={component.name}
              component={component}
              // The largest contributor opens by default so the most important
              // explanation is visible without a click.
              defaultOpen={index === 0}
            />
          ))}
        </div>
      )}

      {hasComponents && notTriggered.length > 0 && (
        <div className="mt-3.5">
          <div className="flex items-center gap-1.5 mb-2">
            <h4 className="text-[11px] text-muted uppercase tracking-wide font-semibold">
              Components that did not trigger
            </h4>
            <InfoTip
              text="These ran against this project and produced no signal, contributing zero points. A component that could not run at all is listed separately under Data Quality."
              label="Components that did not trigger"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {notTriggered.map(component => (
              <span
                key={component.name}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel/60 px-2.5 py-1 text-[11px] text-muted"
              >
                <ComponentIcon name={component.name} size={11} />
                {component.label}
                <span className="text-ink font-semibold tabular-nums">0.0</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}