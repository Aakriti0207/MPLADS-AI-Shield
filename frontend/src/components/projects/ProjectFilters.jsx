import React from 'react'
import { Search } from 'lucide-react'

export default function ProjectFilters({ query, onQueryChange, risk, onRiskChange, workType, onWorkTypeChange, workTypes }) {
  return <div className="card p-4 mb-5"><div className="grid md:grid-cols-4 gap-3">
    <div className="md:col-span-2 relative"><Search className="absolute left-3 top-3 text-slate-400" size={18}/><input value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Search project ID, MP, state, district..." className="w-full border border-slate-200 rounded-xl py-2.5 pl-10 pr-3"/></div>
    <select value={risk} onChange={event => onRiskChange(event.target.value)} className="border border-slate-200 rounded-xl px-3"><option>All</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option></select>
    <select value={workType} onChange={event => onWorkTypeChange(event.target.value)} className="border border-slate-200 rounded-xl px-3"><option>All</option>{workTypes.map(type => <option key={type}>{type}</option>)}</select>
  </div></div>
}
