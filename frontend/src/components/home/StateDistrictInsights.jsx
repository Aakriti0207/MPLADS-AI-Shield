import React, { useMemo, useState } from 'react'
import { ChevronRight, X } from 'lucide-react'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import EmptyState from '../ui/EmptyState'

/**
 * Phase 5: public state & district insights with State -> District
 * drilldown.
 *
 * Everything shown here is public portfolio information -- project
 * counts, sanctioned amount, expenditure, utilisation and completion
 * figures. There is no risk score, risk level, AI indicator, alert or
 * review/investigation column, and no such field is even present on the
 * data this component receives (see lib/publicNormalizers.js).
 *
 * Props
 *   states          normalized public state rows (national list)
 *   selectedState   currently drilled-into state name, or null
 *   onSelectState   called with a state name (or null to clear)
 *   districts       normalized district rows for `selectedState`
 *   districtsLoading / districtsError  drilldown fetch state
 */

const PERCENT = value => (value === null || value === undefined
  ? '—'
  : `${Math.round(value)}%`)

function Metric({ label, value }) {
  return (
    <div>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="text-[14px] font-semibold text-ink mt-0.5">{value}</div>
    </div>
  )
}

export default function StateDistrictInsights({
  states = [],
  selectedState = null,
  onSelectState = null,
  districts = [],
  districtsLoading = false,
  districtsError = null,
}) {
  const [showAllStates, setShowAllStates] = useState(false)

  const activeState = useMemo(
    () => states.find(row => row.state === selectedState) || null,
    [states, selectedState]
  )

  const visibleStates = useMemo(
    () => (showAllStates ? states : states.slice(0, 10)),
    [states, showAllStates]
  )

  if (!states.length) {
    return (
      <div className="card p-4">
        <h3 className="text-[13.5px] font-semibold text-ink">State Insights</h3>
        <EmptyState text="State-level public data is not available." />
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-4 pt-4 pb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[13.5px] font-semibold text-ink">
            {selectedState ? `${selectedState} — District Insights` : 'State Insights'}
          </h3>
          <p className="text-xs text-muted mt-0.5">
            {selectedState
              ? 'Public district-level aggregates for the selected state'
              : 'Select a state to inspect its districts'}
          </p>
        </div>

        {selectedState && onSelectState && (
          <button
            type="button"
            onClick={() => onSelectState(null)}
            className="flex items-center gap-1 text-[11.5px] font-medium text-navy rounded px-2 py-1 bg-panel"
          >
            <X size={12} /> Back to all states
          </button>
        )}
      </div>

      {selectedState && activeState && (
        <div className="px-4 pb-3 grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="Projects" value={formatNumber(activeState.projectCount)} />
          <Metric label="Sanctioned" value={formatCurrency(activeState.sanctioned)} />
          <Metric label="Expenditure" value={formatCurrency(activeState.expenditure)} />
          <Metric label="Completed" value={formatNumber(activeState.completedProjects)} />
          <Metric label="Districts" value={formatNumber(activeState.districtCount)} />
        </div>
      )}

      {selectedState ? (
        districtsLoading ? (
          <div className="py-10 px-4 text-center text-sm text-muted">Loading district figures…</div>
        ) : districtsError ? (
          <div className="py-10 px-4">
            <EmptyState text={`District data could not be loaded: ${districtsError}`} />
          </div>
        ) : !districts.length ? (
          <div className="py-10 px-4">
            <EmptyState text="No district-level records exist for this state in the source data." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {['District', 'Projects', 'Sanctioned', 'Expenditure', 'Utilised', 'Completed', 'Active'].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {districts.map(row => (
                  <tr key={`${row.state}-${row.district}`}>
                    <td className="whitespace-nowrap font-medium">{row.district}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.projectCount)}</td>
                    <td className="whitespace-nowrap">{formatCurrency(row.sanctioned)}</td>
                    <td className="whitespace-nowrap">{formatCurrency(row.expenditure)}</td>
                    <td className="whitespace-nowrap">{PERCENT(row.utilisationPercent)}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.completedProjects)}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.activeWorks)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {['State', 'Projects', 'Sanctioned', 'Expenditure', 'Utilised', 'Completed', 'Districts', ''].map(h => (
                    <th key={h || 'drill'}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleStates.map(row => (
                  <tr
                    key={row.state}
                    className={onSelectState ? 'hover:bg-panel cursor-pointer' : undefined}
                    onClick={() => onSelectState && onSelectState(row.state)}
                  >
                    <td className="whitespace-nowrap font-medium">{row.state}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.projectCount)}</td>
                    <td className="whitespace-nowrap">{formatCurrency(row.sanctioned)}</td>
                    <td className="whitespace-nowrap">{formatCurrency(row.expenditure)}</td>
                    <td className="whitespace-nowrap">{PERCENT(row.utilisationPercent)}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.completedProjects)}</td>
                    <td className="whitespace-nowrap">{formatNumber(row.districtCount)}</td>
                    <td className="whitespace-nowrap text-muted"><ChevronRight size={13} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {states.length > 10 && (
            <div className="px-4 py-3 border-t border-line">
              <button
                type="button"
                onClick={() => setShowAllStates(value => !value)}
                className="text-[11.5px] font-medium text-navy"
              >
                {showAllStates
                  ? 'Show top 10 states'
                  : `Show all ${states.length} states`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
