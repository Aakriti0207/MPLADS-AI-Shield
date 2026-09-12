import React from 'react'

export default function WhyRisky({ reasons = [], evidence = [] }) {
  return <div>{reasons.length ? <ul className="space-y-2 text-sm list-disc list-inside">{reasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul> : <p className="text-sm text-slate-500">No risk driver was recorded for the available data.</p>}{evidence.length > 0 && <div className="flex flex-wrap gap-2 mt-4">{evidence.map(item => <span className="rounded-full bg-blue-50 text-navy px-3 py-1 text-xs font-semibold" key={item}>{item}</span>)}</div>}</div>
}
