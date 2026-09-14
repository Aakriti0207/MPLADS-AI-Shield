import React from 'react'

// Renders risk reasons and structured Risk Fusion evidence safely.
export default function WhyRisky({ reasons = [], evidence = [] }) {
  if (!reasons.length && !evidence.length) {
    return (
      <p className="text-sm text-muted">
        No specific risk indicators were returned for this project.
      </p>
    )
  }

  const formatReason = (reason) => {
    if (typeof reason === 'string') return reason
    if (reason === null || reason === undefined) return 'Risk indicator returned without description.'

    if (typeof reason === 'object') {
      return (
        reason.reason ||
        reason.description ||
        reason.message ||
        reason.identifier ||
        'Risk indicator detected.'
      )
    }

    return String(reason)
  }

  const formatEvidence = (item) => {
    if (typeof item === 'string') return item

    if (item === null || item === undefined) {
      return 'Evidence signal'
    }

    if (typeof item === 'object') {
      const identifier = item.identifier || 'Risk signal'
      const points =
        item.points !== null && item.points !== undefined
          ? ` · ${item.points} pts`
          : ''
      const severity = item.severity_tier
        ? ` · ${item.severity_tier}`
        : ''

      return `${identifier}${points}${severity}`
    }

    return String(item)
  }

  return (
    <div>
      {reasons.length > 0 && (
        <div className="grid md:grid-cols-2 gap-3">
          {reasons.map((reason, index) => (
            <div
              className="rounded-md border border-line p-3.5"
              key={`reason-${index}`}
            >
              <p className="text-[12.5px] text-ink leading-5">
                {formatReason(reason)}
              </p>
            </div>
          ))}
        </div>
      )}

      {evidence.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-4">
          {evidence.map((item, index) => (
            <span
              className="rounded-full bg-info-bg text-navy px-3 py-1 text-xs font-semibold"
              key={`evidence-${index}`}
            >
              {formatEvidence(item)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}