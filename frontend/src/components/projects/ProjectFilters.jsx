import React from 'react'
import { Search } from 'lucide-react'

const FIELD_LABEL_CLASS = 'text-[11px] font-medium text-muted mb-1 block'
const SELECT_CLASS = 'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink'
const LOCKED_CLASS = 'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-panel text-ink font-medium'
// Only used until the real /projects/filter-options `statuses` list
// loads. The old permanent list here ('Recommended', 'In Progress',
// 'Delayed'...) never matched any real backend status value, so
// selecting most of those options silently returned zero results --
// and NOT_SPECIFIED (14% of all projects) wasn't selectable at all.
const FALLBACK_STATUSES = [
  'SANCTIONED',
  'ONGOING',
  'COMPLETED',
  'NOT_SPECIFIED',
]

function prettyStatusLabel(value) {
  const text = String(value ?? '').trim()
  if (!text) return text
  return (
    text.charAt(0).toUpperCase() +
    text.slice(1).toLowerCase()
  ).replace(/_/g, ' ')
}

/**
 * Compact filter bar for the Project Explorer.
 *
 * `states`, `districts` and `categories` are option lists the caller
 * derives from real backend data (GET /projects/filter-options, which is
 * itself scope-restricted). This component never invents option values.
 *
 * Role-aware filtering
 * --------------------
 * `lockedFilters` names the dimensions fixed by the caller's
 * jurisdiction. A locked dimension renders as a STATIC LABEL, not a
 * disabled dropdown and not an "All" option — because offering a choice
 * the backend will refuse is worse than offering none. A District
 * Authority sees "State: Maharashtra / District: Satara" as plain text;
 * an MP never sees an "All States" selector at all.
 *
 * This is presentation only. The backend re-checks every filter it
 * receives and returns 403 for anything outside the caller's scope, so
 * nothing here is load-bearing for security.
 */
export default function ProjectFilters({
  query, onQueryChange,
  state, onStateChange, states = [],
  district, onDistrictChange, districts = [],
  category, onCategoryChange, categories = [],
  status, onStatusChange, statuses = [],
  mpType, onMpTypeChange, mpTypes = [],
  onReset,
  lockedFilters = [],
  scope = null,
}) {
  const stateLocked = lockedFilters.includes('state')
  const districtLocked = lockedFilters.includes('district')
  const constituencyLocked = lockedFilters.includes('constituency')
  const statusOptions = statuses.length ? statuses : FALLBACK_STATUSES

  return (
    <div className="card p-3.5 mb-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-auto sm:min-w-[160px]">
          <label className={FIELD_LABEL_CLASS}>State</label>
          {stateLocked ? (
            <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
              {scope?.state || states[0] || '—'}
            </div>
          ) : (
            <select value={state} onChange={event => onStateChange(event.target.value)} className={SELECT_CLASS}>
              <option>All</option>
              {states.map(value => <option key={value}>{value}</option>)}
            </select>
          )}
        </div>

        {/* District selector appears when the caller's scope spans more
            than one district (Ministry, State Nodal). For a District
            Authority it is a fixed label; for an MP it is offered only
            when their constituency genuinely covers several districts. */}
        {(districtLocked || districts.length > 1) && (
          <div className="w-full sm:w-auto sm:min-w-[170px]">
            <label className={FIELD_LABEL_CLASS}>District</label>
            {districtLocked ? (
              <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
                {scope?.district || districts[0] || '—'}
              </div>
            ) : (
              <select value={district} onChange={event => onDistrictChange(event.target.value)} className={SELECT_CLASS}>
                <option>All</option>
                {districts.map(value => <option key={value}>{value}</option>)}
              </select>
            )}
          </div>
        )}

        {constituencyLocked && (
          <div className="w-full sm:w-auto sm:min-w-[170px]">
            <label className={FIELD_LABEL_CLASS}>Constituency</label>
            <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
              {scope?.constituency || scope?.mp_name || '—'}
            </div>
          </div>
        )}

        <div className="w-full sm:w-auto sm:min-w-[150px]">
          <label className={FIELD_LABEL_CLASS}>MP Type</label>
          <select value={mpType} onChange={event => onMpTypeChange(event.target.value)} className={SELECT_CLASS}>
            <option>All</option>
            {mpTypes.map(value => <option key={value}>{value}</option>)}
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
            {statusOptions.map(value => (
              <option key={value} value={value}>
                {prettyStatusLabel(value)}
              </option>
            ))}
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