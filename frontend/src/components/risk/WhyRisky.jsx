import React from 'react'

// Renders each risk reason as its own evidence card, matching the
// artifact's "Why is this flagged?" pattern, rather than a plain bullet
// list -- makes each independent signal visually distinct.
export default function WhyRisky({ reasons = [], evidence = [] }) {
  if (!reasons.length) {
    return <p className="text-sm text-muted">No risk driver was recorded for the available data.</p>
  }
  return (
    <div>
      <div className="grid md:grid-cols-2 gap-3">
        {reasons.map((reason, index) => (
          <div className="rounded-md border border-line p-3.5" key={`${reason}-${index}`}>
            <p className="text-[12.5px] text-ink leading-5">{reason}</p>
          </div>
        ))}
      </div>
      {evidence.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-4">
          {evidence.map(item => (
            <span className="rounded-full bg-info-bg text-navy px-3 py-1 text-xs font-semibold" key={item}>{item}</span>
          ))}
        </div>
      )}
    </div>
  )
}