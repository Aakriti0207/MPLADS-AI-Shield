import React from 'react'
import { CircleCheck, Database, TriangleAlert } from 'lucide-react'
import { GLOSSARY } from '../../lib/riskModel'
import { PanelHeading, UnavailableNote } from './RiskPrimitives'

/* ==========================================================================
   DATA QUALITY -- WHAT COULD AND COULD NOT BE EVALUATED
   ==========================================================================
   "No anomaly detected" and "could not be evaluated" are different states and
   are never rendered the same. When the backend did not record per-domain
   detail at all, that is shown as unknown -- never as complete.
   ========================================================================== */

const STATUS_COPY = {
  SUFFICIENT: 'Sufficient evidence',
  LIMITED: 'Limited evidence',
  INSUFFICIENT: 'Insufficient evidence',
}

export default function DataQualityPanel({ model }) {
  const { dataQuality } = model
  const statusText = STATUS_COPY[dataQuality.evidenceStatus] || null
  const missing = dataQuality.unevaluable.length

  return (
    <div>
      <PanelHeading
        icon={Database}
        title="Data Quality"
        subtitle="Which evidence domains could actually be evaluated for this project"
        tooltip={GLOSSARY.evidence_status}
        action={
          statusText ? (
            <span className="text-[10.5px] font-semibold text-navy bg-info-bg rounded-full px-2 py-0.5 shrink-0">
              {statusText}
            </span>
          ) : null
        }
      />

      {!dataQuality.detailAvailable ? (
        <UnavailableNote>
          Per-domain data-quality detail was not recorded for this project. This does not mean the
          data is complete, only that it cannot be confirmed.
        </UnavailableNote>
      ) : (
        <>
          <ul className="space-y-1.5">
            {dataQuality.domains.map(domain => (
              <li
                key={domain.label}
                className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2"
              >
                <span className="inline-flex items-center gap-2 text-[12.5px] text-ink min-w-0">
                  {domain.evaluable ? (
                    <CircleCheck size={15} style={{ color: '#1b8a5a' }} className="shrink-0" aria-hidden="true" />
                  ) : (
                    <TriangleAlert size={15} style={{ color: '#b7791f' }} className="shrink-0" aria-hidden="true" />
                  )}
                  <span className="truncate">{domain.label}</span>
                </span>
                <span
                  className="text-[11px] font-semibold shrink-0"
                  style={{ color: domain.evaluable ? '#1b8a5a' : '#b7791f' }}
                >
                  {domain.evaluable ? 'Evaluated' : 'Could not be evaluated'}
                </span>
              </li>
            ))}
          </ul>

          <p className="text-[11.5px] text-muted leading-4 mt-2.5">
            {missing === 0
              ? 'Every evidence domain had the data it needed.'
              : `${missing} domain${missing === 1 ? '' : 's'} could not be evaluated because required data is missing. A missing domain is not evidence of low risk.`}
          </p>
        </>
      )}
    </div>
  )
}