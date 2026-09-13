import React from 'react'
import { Search } from 'lucide-react'

export default function ProjectFilters({ query, onQueryChange, risk, onRiskChange, workType, onWorkTypeChange, workTypes }) {
  return (
    <div className="card p-3.5 mb-4">
      <div className="grid md:grid-cols-4 gap-3">
        <div className="md:col-span-2 relative flex items-center">
          <Search className="absolute left-3 text-muted" size={15} />
          <input
            value={query}
            onChange={event => onQueryChange(event.target.value)}
            placeholder="Search project ID, MP, state, district…"
            className="w-full border border-line rounded-md py-2 pl-9 pr-3 text-[13px] outline-none focus:border-navy"
          />
        </div>
        <select value={risk} onChange={event => onRiskChange(event.target.value)} className="border border-line rounded-md px-3 py-2 text-[13px] bg-white">
          <option>All</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option>
        </select>
        <select value={workType} onChange={event => onWorkTypeChange(event.target.value)} className="border border-line rounded-md px-3 py-2 text-[13px] bg-white">
          <option>All</option>{workTypes.map(type => <option key={type}>{type}</option>)}
        </select>
      </div>
    </div>
  )
}