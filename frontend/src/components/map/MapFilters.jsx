import React from 'react'
import { Search } from 'lucide-react'

const FIELD_LABEL_CLASS = 'text-[11px] font-medium text-muted mb-1 block'
const SELECT_CLASS =
  'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink disabled:bg-panel disabled:text-muted disabled:cursor-not-allowed'
const LOCKED_CLASS =
  'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-panel text-ink font-medium'

// A fixed (locked) dimension has no control to label, so it gets a plain
// caption instead of a <label> that would point at nothing.
function FieldLabel({ htmlFor, locked, children }) {
  return locked
    ? <span className={FIELD_LABEL_CLASS}>{children}</span>
    : <label htmlFor={htmlFor} className={FIELD_LABEL_CLASS}>{children}</label>
}

export const RISK_FILTERS = ['All', 'Critical', 'High', 'Medium', 'Low']

// Mirrors the backend's `search` max_length (see /projects/query), so a
// long paste can never turn into a 422.
export const SEARCH_MAX_LENGTH = 120

/**
 * Filter bar for the Project Map.
 *
 * The option lists (`options.states/districts/constituencies`) come from
 * GET /projects/filter-options (or its demo twin), which is scope-aware and
 * cascades: the district list is limited to the chosen state and the
 * constituency list to the chosen state/district. This component never
 * invents option values.
 *
 * Role-aware filtering
 * --------------------
 * `lockedFilters` names the dimensions fixed by the caller's
 * jurisdiction. A locked dimension renders as a STATIC LABEL -- not a
 * disabled dropdown and not an "All" option -- because offering a choice
 * the backend would refuse is worse than offering none. This is
 * presentation only: /projects/query re-checks every filter it receives
 * and answers 403 for anything outside the caller's scope.
 *
 * Cascade
 * -------
 * For an unlocked state, District and Constituency stay disabled until a
 * state is chosen. That keeps each list bounded (one state's districts,
 * not all ~700 in the country) and matches the backend's cascade.
 *
 * `showRisk` is false on the anonymous public API, which never exposes
 * Risk Fusion data -- there is nothing meaningful to filter on.
 * `showLocation` is false when there is no options source (public API).
 */
export default function MapFilters({
  state,
  district,
  constituency,
  risk,
  search,
  onStateChange,
  onDistrictChange,
  onConstituencyChange,
  onRiskChange,
  onSearchChange,
  onReset,
  canReset = false,
  options = {},
  lockedFilters = [],
  scope = null,
  showRisk = true,
  showLocation = true,
}) {
  const states = options.states || []
  const districts = options.districts || []
  const constituencies = options.constituencies || []

  const stateLocked = lockedFilters.includes('state')
  const districtLocked = lockedFilters.includes('district')
  const constituencyLocked = lockedFilters.includes('constituency')

  // Until a state is chosen, an unlocked national view has no district or
  // constituency list to offer (see "Cascade" above).
  const awaitingState = !stateLocked && state === 'All'

  const hasStateControl = stateLocked || states.length > 0
  const hasDistrictControl = districtLocked || districts.length > 0
  const hasConstituencyControl = constituencyLocked || constituencies.length > 0

  return (
    <div className="card p-3.5 mb-4">
      <div className="flex flex-wrap items-end gap-3">
        {showLocation && hasStateControl && (
          <div className="w-full sm:w-auto sm:min-w-[160px]">
            <FieldLabel htmlFor="map-filter-state" locked={stateLocked}>State</FieldLabel>
            {stateLocked ? (
              <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
                {scope?.state || states[0] || '—'}
              </div>
            ) : (
              <select
                id="map-filter-state"
                value={state}
                onChange={event => onStateChange(event.target.value)}
                className={SELECT_CLASS}
              >
                <option value="All">All</option>
                {states.map(value => <option key={value} value={value}>{value}</option>)}
              </select>
            )}
          </div>
        )}

        {showLocation && hasDistrictControl && (
          <div className="w-full sm:w-auto sm:min-w-[170px]">
            <FieldLabel htmlFor="map-filter-district" locked={districtLocked}>District</FieldLabel>
            {districtLocked ? (
              <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
                {scope?.district || districts[0] || '—'}
              </div>
            ) : (
              <select
                id="map-filter-district"
                value={district}
                onChange={event => onDistrictChange(event.target.value)}
                disabled={awaitingState}
                title={awaitingState ? 'Select a state first' : undefined}
                className={SELECT_CLASS}
              >
                <option value="All">{awaitingState ? 'Select a state first' : 'All'}</option>
                {!awaitingState && districts.map(value => <option key={value} value={value}>{value}</option>)}
              </select>
            )}
          </div>
        )}

        {showLocation && hasConstituencyControl && (
          <div className="w-full sm:w-auto sm:min-w-[180px]">
            <FieldLabel htmlFor="map-filter-constituency" locked={constituencyLocked}>Constituency</FieldLabel>
            {constituencyLocked ? (
              <div className={LOCKED_CLASS} title="Fixed by your assigned jurisdiction">
                {scope?.constituency || scope?.mp_name || '—'}
              </div>
            ) : (
              <select
                id="map-filter-constituency"
                value={constituency}
                onChange={event => onConstituencyChange(event.target.value)}
                disabled={awaitingState}
                title={awaitingState ? 'Select a state first' : undefined}
                className={SELECT_CLASS}
              >
                <option value="All">{awaitingState ? 'Select a state first' : 'All'}</option>
                {!awaitingState && constituencies.map(value => <option key={value} value={value}>{value}</option>)}
              </select>
            )}
          </div>
        )}

        <div className="flex-1 min-w-[220px]">
          <label htmlFor="map-filter-search" className={FIELD_LABEL_CLASS}>Search</label>
          <div className="relative flex items-center">
            <Search className="absolute left-3 text-muted" size={15} aria-hidden="true" />
            <input
              id="map-filter-search"
              type="search"
              value={search}
              maxLength={SEARCH_MAX_LENGTH}
              onChange={event => onSearchChange(event.target.value)}
              placeholder="Project ID, name, description or location…"
              className="w-full border border-line rounded-md py-2 pl-9 pr-3 text-[13px] outline-none focus:border-navy"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className="btn-secondary shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Reset filters
        </button>
      </div>

      {showRisk && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span id="map-filter-risk-label" className="text-[11px] font-medium text-muted">Risk level</span>
          <div role="group" aria-labelledby="map-filter-risk-label" className="flex gap-1.5 flex-wrap">
            {RISK_FILTERS.map(option => (
              <button
                key={option}
                type="button"
                aria-pressed={option === risk}
                onClick={() => onRiskChange(option)}
                className={option === risk ? 'btn bg-navy text-white' : 'btn-secondary'}
              >{option}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}