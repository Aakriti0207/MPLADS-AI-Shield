import React, { useMemo, useState } from 'react'
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
// of that layout must come from `data` (the real GET /dashboard/stats
// `by_state` array, e.g. { state, total_expenditure }), never from a
// fabricated figure.
//
// - `data` present (authenticated, live figures loaded): states are
//   bucketed into low/medium/high tiers by their real cumulative
//   expenditure. A state with no matching backend row renders neutral
//   gray rather than being force-fit into a tier.
// - `data` absent (anonymous visitor, or not loaded yet): the whole grid
//   renders neutral/locked with no colors and no numbers, since there is
//   no public state-aggregate endpoint to source real values from.
export default function IndiaStateGrid({ data = null }) {
  const [selected, setSelected] = useState(null)
  const locked = !data || data.length === 0

  const byState = useMemo(() => {
    const map = new Map()
    ;(data || []).forEach(row => {
      if (!row?.state) return
      map.set(row.state, toNumber(row.total_expenditure))
    })
    return map
  }, [data])

  const thresholds = useMemo(() => {
    const values = [...byState.values()].filter(v => v !== null).sort((a, b) => a - b)
    if (!values.length) return null
    const at = p => values[Math.min(values.length - 1, Math.floor(p * (values.length - 1)))]
    return { low: at(0.34), medium: at(0.67) }
  }, [byState])

  function tierFor(value) {
    if (value === null || !thresholds) return null
    if (value <= thresholds.low) return 'low'
    if (value <= thresholds.medium) return 'medium'
    return 'high'
  }

  const active = STATE_STATS.find(s => s.name === selected)
  const activeExpenditure = active ? byState.get(active.name) ?? null : null
  const activeTier = active ? tierFor(activeExpenditure) : null

  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(8, minmax(0,1fr))', gridTemplateRows: 'repeat(8, 30px)' }}>
        {STATE_STATS.map(s => {
          const value = byState.get(s.name) ?? null
          const tier = locked ? null : tierFor(value)
          const bg = tier ? TIER_BG[tier] : LOCKED_BG
          return (
            <button
              key={s.name}
              onClick={() => !locked && setSelected(s.name === selected ? null : s.name)}
              title={locked ? `${s.name} -- sign in to view live figures` : `${s.name} -- ${formatCurrency(value)} cumulative expenditure`}
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
        <p className="text-xs text-muted mt-3">Sign in to view live, state-wise expenditure figures.</p>
      ) : (
        <div className="flex items-center gap-4 mt-3 text-xs text-muted">
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.low }} /> Lower expenditure</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.medium }} /> Medium</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.high }} /> Higher</span>
        </div>
      )}

      {!locked && active && (
        <div className="mt-3 flex items-center gap-3 px-3 py-2 rounded-md bg-panel border border-line">
          <span className="text-[12.5px] font-semibold text-ink">{active.name}</span>
          <span className="text-[11.5px] text-muted">{formatCurrency(activeExpenditure)} cumulative expenditure</span>
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