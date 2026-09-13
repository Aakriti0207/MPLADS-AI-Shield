import React from 'react'
import { toNumber } from '../../lib/formatters'

export default function RiskBreakdown({ risk = {} }) {
  const fields = [
    ['Financial risk', risk.financial_risk_score],
    ['Payment risk', risk.payment_risk_score],
    ['Execution risk', risk.execution_risk_score],
    ['Peer anomaly', risk.peer_anomaly_score],
    ['Isolation forest', risk.isolation_forest_score],
    ['Duplicate risk', risk.duplicate_risk_score],
  ]
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {fields.map(([label, value]) => {
        const number = toNumber(value)
        return (
          <div className="rounded-md bg-panel p-3.5" key={label}>
            <div className="text-xs text-muted">{label}</div>
            <div className="text-[17px] font-semibold mt-1 text-ink">
              {number === null ? <span className="text-sm font-semibold text-muted">Not available</span> : number.toFixed(2)}
            </div>
          </div>
        )
      })}
    </div>
  )
}