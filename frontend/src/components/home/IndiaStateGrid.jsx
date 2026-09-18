import React, { useMemo } from 'react'
import { STATE_STATS } from '../../lib/mockData'
import { formatCurrency, toNumber } from '../../lib/formatters'

const TIER_BG = { low: '#bfe3d0', medium: '#f3d399', high: '#eab2ac' }
const TIER_STRONG = { low: '#1b8a5a', medium: '#b7791f', high: '#c0392b' }
const LOCKED_BG = '#e7ebef'

// Cartogram of India used for the state-wise monitoring panel.
//
// STATE_STATS (lib/mockData.js) supplies ONLY the grid position (row/col)
// for each state -- that's pure layout, not a statistic, so it's safe to
// keep regardless of auth state. Any colored tier / number shown on top
// of that layout must come from `data`, never from a fabricated figure.
//
// Phase 5 update
// --------------
// The grid now accepts BOTH shapes and is used on the public Overview:
//
//   - the authenticated `by_state` rows  ({ state, total_expenditure })
//   - the public `byState` rows          ({ state, expenditure,
//                                           projectCount, ... })
//
// Selection is now CONTROLLED (`selected` + `onSelect`) so the public
// Overview can drive its State -> District drilldown from the same click,
// instead of the grid owning a private selection that nothing else can
// see. When no `onSelect` is passed the component still works standalone.
//
// A state with no matching row renders neutral gray rather than being
// force-fit into a tier, and `data` being absent/empty renders the whole
// grid locked with no colors and no numbers.
export default function IndiaStateGrid({
  data = null,
  selected = null,
  onSelect = null,
  lockedMessage = 'Sign in to view live, state-wise expenditure figures.',
}) {
  const locked = !data || data.length === 0

  // Accepts either contract's expenditure field; `projectCount` is only
  // present on the public contract and is simply omitted when absent.
  const byState = useMemo(() => {
    const map = new Map()
    ;(data || []).forEach(row => {
      if (!row?.state) return
      map.set(row.state, {
        expenditure: toNumber(row.expenditure ?? row.total_expenditure),
        sanctioned: toNumber(row.sanctioned ?? row.total_sanctioned_amount),
        projectCount: toNumber(row.projectCount ?? row.project_count),
        completedProjects: toNumber(row.completedProjects ?? row.completed_projects),
      })
    })
    return map
  }, [data])

  const thresholds = useMemo(() => {
    const values = [...byState.values()]
      .map(entry => entry.expenditure)
      .filter(value => value !== null)
      .sort((a, b) => a - b)
    if (!values.length) return null
    const at = p => values[Math.min(values.length - 1, Math.floor(p * (values.length - 1)))]
    return { low: at(0.34), medium: at(0.67) }
  }, [byState])

  function tierFor(value) {
    if (value === null || value === undefined || !thresholds) return null
    if (value <= thresholds.low) return 'low'
    if (value <= thresholds.medium) return 'medium'
    return 'high'
  }

  function handleSelect(name) {
    if (locked) return
    const next = name === selected ? null : name
    if (onSelect) onSelect(next)
  }

  const active = STATE_STATS.find(s => s.name === selected)
  const activeEntry = active ? byState.get(active.name) ?? null : null
  const activeExpenditure = activeEntry ? activeEntry.expenditure : null
  const activeTier = active ? tierFor(activeExpenditure) : null

  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(8, minmax(0,1fr))', gridTemplateRows: 'repeat(8, 30px)' }}>
        {STATE_STATS.map(s => {
          const entry = byState.get(s.name) ?? null
          const value = entry ? entry.expenditure : null
          const tier = locked ? null : tierFor(value)
          const bg = tier ? TIER_BG[tier] : LOCKED_BG
          const hasData = !locked && entry !== null
          return (
            <button
              key={s.name}
              onClick={() => handleSelect(s.name)}
              title={
                locked
                  ? `${s.name} — figures unavailable`
                  : hasData
                    ? `${s.name} — ${formatCurrency(value)} cumulative expenditure`
                    : `${s.name} — no recorded projects`
              }
              aria-pressed={s.name === selected}
              disabled={locked}
              style={{ gridColumn: s.col, gridRow: s.row, backgroundColor: bg, border: `1.5px solid ${s.name === selected ? '#0b2e4f' : 'transparent'}` }}
              className="rounded-[3px] flex items-center justify-center text-[8px] font-semibold px-0.5 hover:brightness-95 transition disabled:cursor-default disabled:hover:brightness-100"
            >
              <span className="text-ink/70">{s.name.split(' ').map(w => w[0]).join('').slice(0, 3)}</span>
            </button>
          )
        })}
      </div>

      {locked ? (
        <p className="text-xs text-muted mt-3">{lockedMessage}</p>
      ) : (
        <div className="flex items-center gap-4 mt-3 text-xs text-muted">
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.low }} /> Lower expenditure</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.medium }} /> Medium</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.high }} /> Higher</span>
        </div>
      )}

      {!locked && active && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 rounded-md bg-panel border border-line">
          <span className="text-[12.5px] font-semibold text-ink">{active.name}</span>
          <span className="text-[11.5px] text-muted">{formatCurrency(activeExpenditure)} cumulative expenditure</span>
          {activeEntry?.projectCount !== null && activeEntry?.projectCount !== undefined && (
            <span className="text-[11.5px] text-muted">
              {activeEntry.projectCount.toLocaleString()} projects
            </span>
          )}
          {activeTier && (
            <span className="rounded px-2 py-0.5 text-xs font-semibold" style={{ color: TIER_STRONG[activeTier], backgroundColor: TIER_BG[activeTier] }}>
              {activeTier.toUpperCase()}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
