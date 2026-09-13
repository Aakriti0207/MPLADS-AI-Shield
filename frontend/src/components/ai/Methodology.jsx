import React from 'react'
import { Database, ListChecks, ScanSearch, SlidersVertical } from 'lucide-react'

// Institutional "How AI Shield Works" strip, reused by both the public
// /ai-insights page and the authenticated /ai-shield page (Phase 6) so
// the wording never drifts between the two.
//
// Each step below is worded to match techniques that are actually
// observable in this codebase's real risk fields -- financial_risk_score,
// payment_risk_score, execution_risk_score, peer_anomaly_score,
// isolation_forest_score and duplicate_risk_score (see
// components/risk/RiskBreakdown.jsx and pages/AiShield.jsx). It
// deliberately avoids claiming deep learning, generative AI, fraud
// prediction or "explainable AI models" -- none of which have any
// corresponding field in the data this frontend actually receives.
const STEPS = [
  {
    icon: Database,
    title: '1. Ingest',
    body: 'Project and financial records are collected from the available MPLADS datasets.',
  },
  {
    icon: ListChecks,
    title: '2. Normalize',
    body: 'Records are cleaned and standardized before analysis.',
  },
  {
    icon: ScanSearch,
    title: '3. Detect',
    body: 'Statistical and rule-based checks -- financial, payment and execution-timeline scoring, peer-relative comparison, isolation-forest anomaly detection, and duplicate-description similarity -- identify unusual patterns.',
  },
  {
    icon: SlidersVertical,
    title: '4. Prioritize',
    body: 'Projects with stronger combined risk signals are surfaced for human review, highest first.',
  },
]

export default function Methodology({ compact = false }) {
  return (
    <div className={compact ? 'card p-4' : 'card p-5'}>
      <h3 className="text-[13.5px] font-semibold text-ink">How AI Shield Works</h3>
      <p className="text-xs text-muted mt-0.5 mb-4 max-w-2xl">
        AI Shield does not accuse or convict -- it prioritizes. The steps below reflect the real scoring signals used, not a generic AI pipeline.
      </p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {STEPS.map(({ icon: Icon, title, body }) => (
          <div className="rounded-md border border-line p-3.5" key={title}>
            <div className="h-7 w-7 rounded-md flex items-center justify-center bg-panel text-navy mb-2">
              <Icon size={14} aria-hidden="true" />
            </div>
            <div className="text-[12.5px] font-semibold text-ink">{title}</div>
            <p className="text-xs text-muted mt-1 leading-4">{body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}