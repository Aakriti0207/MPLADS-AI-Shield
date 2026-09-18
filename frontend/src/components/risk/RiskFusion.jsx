import React from 'react'
import { ShieldAlert, TriangleAlert } from 'lucide-react'
import { buildRiskModel } from '../../lib/riskModel'
import RiskOverview from './RiskOverview'
import RiskBreakdownTable from './RiskBreakdownTable'
import HowScoreCalculated from './HowScoreCalculated'
import WhyFlagged from './WhyFlagged'
import PeerComparison from './PeerComparison'
import DataQualityPanel from './DataQualityPanel'
import RecommendedReview from './RecommendedReview'

/* ==========================================================================
   RISK FUSION -- EXPLAINABLE AI
   ==========================================================================
   Composes the full explanation for one project, in the order a reviewer
   actually needs it:

     1. What is the overall risk?          -> RiskOverview
     2. Which components contributed?      -> RiskBreakdownTable
     3. WHY was it flagged?                -> WhyFlagged      (never omitted)
     4. How does it compare with peers?    -> PeerComparison
     5. What data is missing?              -> DataQualityPanel
     6. How was the score assembled?       -> HowScoreCalculated
     7. What should a human inspect?       -> RecommendedReview

   Sections 2 and 3 are BOTH mandatory and answer different questions:
   "how much" versus "why". Neither is a substitute for the other.

   This component renders. It does not calculate. Every number originates in
   GET /projects/:id/risk.
   ========================================================================== */

function Panel({ children, className = '' }) {
  return <div className={`card p-4 ${className}`}>{children}</div>
}

function StateMessage({ tone = 'muted', title, children }) {
  const color = tone === 'error' ? '#c0392b' : tone === 'warn' ? '#b7791f' : '#55636e'
  return (
    <Panel>
      <div className="py-8 text-center">
        <TriangleAlert size={18} className="mx-auto mb-2" style={{ color }} aria-hidden="true" />
        <p className="text-[13px] font-semibold text-ink">{title}</p>
        {children && (
          <p className="text-[12px] text-muted mt-1 max-w-[460px] mx-auto">{children}</p>
        )}
      </div>
    </Panel>
  )
}

export {
  RiskOverview,
  RiskBreakdownTable,
  HowScoreCalculated,
  WhyFlagged,
  PeerComparison,
  DataQualityPanel,
  RecommendedReview,
}

/**
 * @param risk     normalized GET /projects/:id/risk payload (or demo equivalent)
 * @param loading  parent-owned fetch state
 * @param error    parent-owned error message
 */
export default function RiskFusion({ risk, loading = false, error = null }) {
  if (loading) {
    return (
      <Panel>
        <p className="text-[13px] text-muted py-8 text-center">Loading risk analysis…</p>
      </Panel>
    )
  }

  if (error) {
    return (
      <StateMessage tone="error" title="Risk analysis could not be loaded.">
        {error}
      </StateMessage>
    )
  }

  const model = buildRiskModel(risk)

  if (!model) {
    return (
      <StateMessage title="Risk analysis is unavailable for this project.">
        No Risk Fusion result has been produced for this work ID.
      </StateMessage>
    )
  }

  // An INSUFFICIENT evidence status means no domain could be evaluated at all.
  // That must never be rendered as a low-risk result.
  if (model.evidenceStatus === 'INSUFFICIENT') {
    return (
      <StateMessage
        tone="warn"
        title="Risk analysis is limited — required project data is incomplete."
      >
        None of the evidence domains (compliance, financial, timeline, duplicate, payment or
        statistical outlier detection) could be evaluated for this project. The score must not be
        read as evidence that the project is low risk.
      </StateMessage>
    )
  }

  const partial = !model.dataQuality.complete

  return (
    <div className="space-y-4">
      {partial && (
        <div className="flex items-start gap-2.5 rounded-md border border-line bg-warn-bg/50 px-3.5 py-2.5">
          <TriangleAlert
            size={15}
            style={{ color: '#b7791f' }}
            className="mt-0.5 shrink-0"
            aria-hidden="true"
          />
          <p className="text-[12px] text-ink leading-4">
            Risk analysis is available, but some components could not be evaluated because required
            data is missing. See the Data Quality panel below.
          </p>
        </div>
      )}

      <div className="grid xl:grid-cols-2 gap-4 items-start">
        {/* LEFT: what the score is, and how much each component added */}
        <div className="space-y-4">
          <Panel>
            <RiskOverview model={model} />
          </Panel>

          <Panel>
            <RiskBreakdownTable model={model} />
          </Panel>
        </div>

        {/* RIGHT: why it was flagged, against what peers, with what data */}
        <div className="space-y-4">
          <Panel>
            <WhyFlagged model={model} />
          </Panel>

          <Panel>
            <PeerComparison model={model} />
          </Panel>

          <Panel>
            <DataQualityPanel model={model} />
          </Panel>
        </div>
      </div>

      <div className="grid xl:grid-cols-2 gap-4 items-start">
        <Panel>
          <HowScoreCalculated model={model} />
        </Panel>

        <Panel>
          <RecommendedReview model={model} />
        </Panel>
      </div>

      <div className="flex items-start gap-2.5 rounded-md bg-info-bg border border-line px-3.5 py-3">
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-blue" aria-hidden="true" />
        <p className="text-[12px] text-muted leading-5">
          AI Shield identifies risk signals, anomalies and unusual patterns that require human
          review. It does not establish fraud, corruption or wrongdoing of any kind. Every figure
          shown above is produced by the backend Risk Fusion engine; this page explains that result
          rather than producing its own. Final verification and any resulting decision remain with
          authorised officials.
        </p>
      </div>
    </div>
  )
}