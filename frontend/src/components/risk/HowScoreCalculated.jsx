import React from 'react'
import { ArrowRight, Sparkles } from 'lucide-react'
import { GLOSSARY, statusTone } from '../../lib/riskModel'
import { ComponentIcon, InfoTip, PanelHeading, StatusPill } from './RiskPrimitives'

/* ==========================================================================
   SECTION 4 -- HOW DID WE GET THIS SCORE?
   ==========================================================================
   A deliberately plain walk-through for a non-technical reviewer:

     component -> raw score -> weight -> contribution   (for each component)
                            ... then ...
     all contributions -> risk fusion -> final score -> risk level

   Every number below is read straight off the backend payload. Untriggered
   components are listed too, at zero, because "this was checked and found
   nothing" is itself information a reviewer needs.
   ========================================================================== */

function Step({ label, value, emphasis = false }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-muted uppercase tracking-wide">{label}</div>
      <div
        className={`tabular-nums mt-0.5 ${
          emphasis ? 'text-[13px] font-semibold text-ink' : 'text-[12.5px] text-ink'
        }`}
      >
        {value}
      </div>
    </div>
  )
}

function ComponentFlowRow({ component }) {
  const tone = statusTone(component.status)

  return (
    <div
      className="rounded-md border px-3 py-2.5"
      style={{
        borderColor: component.triggered ? `${tone.color}33` : '#dce2e8',
        backgroundColor: component.triggered ? `${tone.bg}66` : 'transparent',
      }}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-2 min-w-[190px] text-[12.5px] font-medium text-ink">
          <span
            className="inline-flex items-center justify-center w-6 h-6 rounded-md shrink-0"
            style={{ color: tone.color, backgroundColor: tone.bg }}
          >
            <ComponentIcon name={component.name} size={13} />
          </span>
          <span className="truncate">{component.label}</span>
        </span>

        <div className="flex items-center gap-2 flex-1 justify-end flex-wrap">
          <Step label="Raw score" value={`${component.rawScore.toFixed(1)} / 100`} />
          <ArrowRight size={13} className="text-muted shrink-0" aria-hidden="true" />
          <Step label="Weight" value={`${component.weight.toFixed(0)}%`} />
          <ArrowRight size={13} className="text-muted shrink-0" aria-hidden="true" />
          <Step label="Contribution" value={`${component.contribution.toFixed(2)} pts`} emphasis />
          <StatusPill status={component.status} className="ml-1" />
        </div>
      </div>
    </div>
  )
}

export default function HowScoreCalculated({ model }) {
  const { components, triggered, notTriggered, totalContribution, score, level } = model

  return (
    <div>
      <PanelHeading
        icon={Sparkles}
        title="How Did We Get This Score?"
        subtitle="Every detection component, its own score, its configured weight, and the points it added"
        tooltip={GLOSSARY.risk_fusion}
      />

      <div className="space-y-2">
        {triggered.map(component => (
          <ComponentFlowRow key={component.name} component={component} />
        ))}
      </div>

      {notTriggered.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 mb-2">
            <h4 className="text-[11px] text-muted uppercase tracking-wide font-semibold">
              Checked, no signal triggered
            </h4>
            <InfoTip
              text="These components ran and found nothing for this project, so they contributed zero points. This is not the same as a component that could not be evaluated — see the Data Quality panel."
              label="Checked, no signal triggered"
            />
          </div>
          <div className="space-y-2">
            {notTriggered.map(component => (
              <ComponentFlowRow key={component.name} component={component} />
            ))}
          </div>
        </div>
      )}

      {/* Fusion */}
      <div className="mt-4 rounded-md border border-line bg-panel px-4 py-4 text-center">
        <div className="text-[10px] text-muted uppercase tracking-wide">
          Sum of all contributions
        </div>
        <div className="text-[15px] font-semibold text-ink tabular-nums mt-0.5">
          {totalContribution.toFixed(2)} points
        </div>

        <div className="my-2.5 flex items-center justify-center">
          <span className="text-[11px] font-semibold text-navy uppercase tracking-wide rounded-full bg-navy-bg px-3 py-1">
            Risk fusion
          </span>
        </div>

        <div className="text-[10px] text-muted uppercase tracking-wide">Final risk score</div>
        <div className="text-[26px] font-bold text-ink tabular-nums leading-tight">
          {score === null ? '—' : score.toFixed(1)}
          <span className="text-[13px] font-normal text-muted"> / 100</span>
        </div>

        <div className="mt-2">
          <StatusPill
            status={
              { CRITICAL: 'HIGH', HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW' }[level] || 'NONE'
            }
          />
          <span className="ml-2 text-[12px] text-ink font-semibold">{level || 'UNAVAILABLE'}</span>
        </div>

        <p className="text-[11px] text-muted mt-2.5 leading-4 max-w-[520px] mx-auto">
          Risk levels come from the thresholds configured in the backend: below 25 is LOW, 25–50
          MEDIUM, 50–75 HIGH, and 75 or above CRITICAL. {components.length} components were
          evaluated for this project.
        </p>
      </div>
    </div>
  )
}