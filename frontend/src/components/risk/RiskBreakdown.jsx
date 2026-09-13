import React from 'react'
import { toNumber } from '../../lib/formatters'

// Category caps mirror backend/ml/risk_config.py's RISK_COMPONENT_CAPS
// exactly (28 + 20 + 12 + 12 + 8 + 10 + 10 = 100). These are the current
// Risk Fusion contract's real per-domain point ceilings, not illustrative
// numbers -- do not change them without updating risk_config.py to match.
const CONTRIBUTION_FIELDS = [
  { key: 'compliance_contribution', label: 'Compliance', max: 28 },
  { key: 'financial_anomaly_contribution', label: 'Financial anomaly', max: 20 },
  { key: 'timeline_anomaly_contribution', label: 'Timeline anomaly', max: 12 },
  { key: 'duplicate_contribution', label: 'Duplicate similarity', max: 12 },
  { key: 'data_quality_contribution', label: 'Data quality', max: 8 },
  { key: 'payment_contribution', label: 'Payment pattern', max: 10 },
  { key: 'isolation_forest_contribution', label: 'Statistical outlier (isolation forest)', max: 10 },
]

// Renders the current Phase 9 Risk Fusion contribution breakdown for one
// project -- i.e. the real `GET /projects/:id/risk` response, never a
// value computed or invented on the frontend. `risk` is expected to be
// the raw (non-normalized) Risk Fusion payload so the *_contribution
// field names below match the backend contract directly.
export default function RiskBreakdown({ risk }) {
  const hasContributions = risk && CONTRIBUTION_FIELDS.some(f => toNumber(risk[f.key]) !== null)

  if (!hasContributions) {
    return (
      <p className="text-sm text-muted">
        Category contribution data is not available from the current risk response.
      </p>
    )
  }

  return (
    <div className="space-y-2.5">
      {CONTRIBUTION_FIELDS.map(({ key, label, max }) => {
        const value = toNumber(risk[key])
        const pct = value === null ? 0 : Math.min(100, Math.max(0, (value / max) * 100))
        return (
          <div key={key} className="flex items-center gap-3">
            <span className="w-[190px] shrink-0 text-[12px] text-ink">{label}</span>
            <div className="flex-1 h-2 rounded-full" style={{ backgroundColor: '#e7ebef' }}>
              <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: '#0b2e4f' }} />
            </div>
            <span className="w-[54px] shrink-0 text-right text-[12px] font-semibold text-ink">
              {value === null ? '—' : `+${value.toFixed(1)}`}
            </span>
          </div>
        )
      })}
    </div>
  )
}