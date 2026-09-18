import React from 'react'
import { GitCompare, TriangleAlert } from 'lucide-react'
import { GLOSSARY, statusTone } from '../../lib/riskModel'
import {
  ComponentIcon,
  ContributionBar,
  InfoTip,
  PanelHeading,
  StatusPill,
} from './RiskPrimitives'

/* ==========================================================================
   SECTION 3 -- RISK BREAKDOWN & CONTRIBUTION
   ==========================================================================
   Answers HOW MUCH each component contributed. (Its companion, WHY each
   component triggered, lives in WhyFlagged.jsx -- the two are deliberately
   separate panels and neither replaces the other.)

   Three columns, three different quantities, labelled separately on purpose:
     Raw score    -- the component's own 0-100 detector output
     Weight       -- its configured cap out of 100
     Contribution -- points it actually added (raw x weight / 100)
   ========================================================================== */

export default function RiskBreakdownTable({ model }) {
  const { components, totalContribution, score, reconciles } = model

  return (
    <div>
      <PanelHeading
        icon={GitCompare}
        title="Risk Breakdown & Contribution"
        subtitle="How much each detection component contributed to the final fused score"
        tooltip={GLOSSARY.risk_fusion}
      />

      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-[12.5px] border-collapse">
          <caption className="sr-only">
            Risk component breakdown: raw score, configured weight, contributed points, share of
            the final score, and status.
          </caption>
          <thead>
            <tr className="text-left text-[11px] text-muted uppercase tracking-wide border-b border-line">
              <th scope="col" className="py-2 pr-3 font-semibold">
                Risk component
              </th>
              <th scope="col" className="py-2 px-3 font-semibold whitespace-nowrap">
                <span className="inline-flex items-center gap-1">
                  Raw score
                  <InfoTip text={GLOSSARY.raw_score} label="Raw score" />
                </span>
              </th>
              <th scope="col" className="py-2 px-3 font-semibold whitespace-nowrap">
                <span className="inline-flex items-center gap-1">
                  Weight
                  <InfoTip text={GLOSSARY.weight} label="Weight" />
                </span>
              </th>
              <th scope="col" className="py-2 px-3 font-semibold whitespace-nowrap">
                <span className="inline-flex items-center gap-1">
                  Contribution
                  <InfoTip text={GLOSSARY.contribution} label="Contribution" />
                </span>
              </th>
              <th scope="col" className="py-2 px-3 font-semibold w-[34%]">
                <span className="inline-flex items-center gap-1">
                  Share of final risk
                  <InfoTip text={GLOSSARY.share} label="Share of final risk" />
                </span>
              </th>
              <th scope="col" className="py-2 pl-3 font-semibold text-right">
                Status
              </th>
            </tr>
          </thead>

          <tbody>
            {components.map(component => {
              const tone = statusTone(component.status)
              return (
                <tr key={component.name} className="border-b border-line/70 align-middle">
                  <th scope="row" className="py-2.5 pr-3 font-normal">
                    <span className="inline-flex items-center gap-2 text-ink font-medium">
                      <span
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md shrink-0"
                        style={{ color: tone.color, backgroundColor: tone.bg }}
                      >
                        <ComponentIcon name={component.name} size={13} />
                      </span>
                      {component.label}
                      <InfoTip text={component.description} label={component.label} />
                    </span>
                  </th>

                  <td className="py-2.5 px-3 tabular-nums text-ink">
                    {component.rawScore.toFixed(1)}
                  </td>

                  <td className="py-2.5 px-3 tabular-nums text-muted">
                    {component.weight.toFixed(0)}%
                  </td>

                  <td className="py-2.5 px-3 tabular-nums font-semibold text-ink">
                    {component.contribution.toFixed(2)}
                  </td>

                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex-1 min-w-[80px]">
                        <ContributionBar pct={component.barPct} color={tone.color} />
                      </div>
                      <span className="w-[46px] shrink-0 text-right tabular-nums text-muted text-[11.5px]">
                        {component.sharePct.toFixed(1)}%
                      </span>
                    </div>
                  </td>

                  <td className="py-2.5 pl-3 text-right">
                    <StatusPill status={component.status} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile stacked cards -- same numbers, readable at narrow widths */}
      <div className="md:hidden space-y-2.5">
        {components.map(component => {
          const tone = statusTone(component.status)
          return (
            <div key={component.name} className="rounded-md border border-line px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-2 text-[12.5px] font-medium text-ink min-w-0">
                  <ComponentIcon name={component.name} size={13} className="shrink-0" />
                  <span className="truncate">{component.label}</span>
                </span>
                <StatusPill status={component.status} />
              </div>

              <div className="mt-2">
                <ContributionBar pct={component.barPct} color={tone.color} />
              </div>

              <dl className="grid grid-cols-4 gap-2 mt-2 text-[11px]">
                <div>
                  <dt className="text-muted">Raw</dt>
                  <dd className="text-ink font-medium tabular-nums">
                    {component.rawScore.toFixed(1)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Weight</dt>
                  <dd className="text-ink font-medium tabular-nums">
                    {component.weight.toFixed(0)}%
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Points</dt>
                  <dd className="text-ink font-semibold tabular-nums">
                    {component.contribution.toFixed(2)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Share</dt>
                  <dd className="text-ink font-medium tabular-nums">
                    {component.sharePct.toFixed(1)}%
                  </dd>
                </div>
              </dl>
            </div>
          )
        })}
      </div>

      {/* Reconciliation strip -- the arithmetic, stated openly */}
      <div className="mt-4 rounded-md bg-panel border border-line px-3.5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold text-navy uppercase tracking-wide">
              Risk fusion formula (as implemented)
            </div>
            <p className="text-[11.5px] text-muted leading-4 mt-1">
              Each component contributes its own score scaled by its configured weight. The final
              score is the sum of those contributions, produced entirely by the backend.
            </p>
          </div>

          <div className="text-[12.5px] text-ink tabular-nums whitespace-nowrap">
            Σ (raw score × weight ÷ 100) ={' '}
            <span className="font-semibold">{totalContribution.toFixed(2)}</span>
            {score !== null && (
              <>
                {' '}
                <span className="text-muted">/ reported score</span>{' '}
                <span className="font-semibold">{score.toFixed(2)}</span>
              </>
            )}
          </div>
        </div>

        {reconciles === false && (
          <p className="flex items-start gap-1.5 text-[11.5px] mt-2" style={{ color: '#b7791f' }}>
            <TriangleAlert size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
            The contributions shown do not sum to the reported score. The reported score remains
            authoritative — this breakdown may be incomplete for this project.
          </p>
        )}
      </div>
    </div>
  )
}