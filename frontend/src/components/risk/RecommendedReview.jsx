import React from 'react'
import { ClipboardCheck } from 'lucide-react'
import { buildReviewChecklist } from '../../lib/riskModel'
import { PanelHeading, UnavailableNote } from './RiskPrimitives'

/* ==========================================================================
   RECOMMENDED REVIEW -- WHAT A HUMAN SHOULD INSPECT
   ==========================================================================
   Checklist ordered by how much each triggered component contributed, so the
   biggest driver is reviewed first. These are review SUGGESTIONS tied to the
   category of signal (ml/risk_config.py). They are never conclusions and never
   assert anything about this project's records.
   ========================================================================== */

export default function RecommendedReview({ model }) {
  const checklist = buildReviewChecklist(model.triggered)

  return (
    <div>
      <PanelHeading
        icon={ClipboardCheck}
        title="Recommended Review"
        subtitle="What a reviewer should look at first, biggest driver first"
        tooltip="Suggested checks tied to the kinds of signal that triggered. They guide a human reviewer and do not establish wrongdoing."
      />

      {model.triggered.length === 0 ? (
        <UnavailableNote>
          No component triggered for this project, so no specific review actions are suggested.
        </UnavailableNote>
      ) : checklist.length === 0 ? (
        <UnavailableNote>
          Signals were triggered, but no review actions were recorded for them in the current risk
          output.
        </UnavailableNote>
      ) : (
        <ol className="space-y-2">
          {checklist.map((item, index) => (
            <li key={item.action} className="flex items-start gap-3 rounded-md border border-line px-3 py-2.5">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-info-bg text-navy text-[11px] font-semibold shrink-0 mt-0.5 tabular-nums">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="text-[12.5px] text-ink leading-5">{item.action}</p>
                <p className="text-[10.5px] text-muted mt-0.5">From: {item.componentLabel}</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      <p className="text-[11px] text-muted leading-4 mt-3 italic">
        Suggestions only. Final verification and any decision remain with authorised officials.
      </p>
    </div>
  )
}