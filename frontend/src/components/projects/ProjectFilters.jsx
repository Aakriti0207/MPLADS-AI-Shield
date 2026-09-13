import React from 'react'
import { Search } from 'lucide-react'

const FIELD_LABEL_CLASS = 'text-[11px] font-medium text-muted mb-1 block'
const SELECT_CLASS = 'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink'

/**
 * Compact artifact-style filter bar for the Project Explorer.
 *
 * `states` and `categories` are option lists the caller derives from
 * real backend data (dashboard state/work-type distributions) -- this
 * component never invents option values itself.
 */
export default function ProjectFilters({
  query, onQueryChange,
  state, onStateChange, states = [],
  category, onCategoryChange, categories = [],
  status, onStatusChange,
  onReset,
}) {
  return (
    <div className="card p-3.5 mb-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-auto sm:min-w-[160px]">
          <label className={FIELD_LABEL_CLASS}>State</label>
          <select value={state} onChange={event => onStateChange(event.target.value)} className={SELECT_CLASS}>
            <option>All</option>
            {states.map(value => <option key={value}>{value}</option>)}
          </select>
        </div>

        <div className="w-full sm:w-auto sm:min-w-[180px]">
          <label className={FIELD_LABEL_CLASS}>Category</label>
          <select value={category} onChange={event => onCategoryChange(event.target.value)} className={SELECT_CLASS}>
            <option>All</option>
            {categories.map(value => <option key={value}>{value}</option>)}
          </select>
        </div>

        <div className="w-full sm:w-auto sm:min-w-[160px]">
          <label className={FIELD_LABEL_CLASS}>Status</label>
          <select value={status} onChange={event => onStatusChange(event.target.value)} className={SELECT_CLASS}>
            <option>All</option>
            <option>Recommended</option>
            <option>Sanctioned</option>
            <option>Ongoing</option>
            <option>In Progress</option>
            <option>Completed</option>
            <option>Delayed</option>
          </select>
        </div>

        <div className="flex-1 min-w-[220px]">
          <label className={FIELD_LABEL_CLASS}>Search</label>
          <div className="relative flex items-center">
            <Search className="absolute left-3 text-muted" size={15} aria-hidden="true" />
            <input
              value={query}
              onChange={event => onQueryChange(event.target.value)}
              placeholder="Search by Work ID, MP, state, district…"
              className="w-full border border-line rounded-md py-2 pl-9 pr-3 text-[13px] outline-none focus:border-navy"
            />
          </div>
        </div>

        <button type="button" onClick={onReset} className="btn-secondary shrink-0">
          Reset Filters
        </button>
      </div>
    </div>
  )
}