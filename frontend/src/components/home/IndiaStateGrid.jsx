import React, { useState } from 'react'
import { STATE_STATS } from '../../lib/mockData'

const TIER_BG = { low: '#bfe3d0', medium: '#f3d399', high: '#eab2ac' }
const TIER_STRONG = { low: '#1b8a5a', medium: '#b7791f', high: '#c0392b' }

// Stylised state-grid cartogram, ported from the approved visual
// reference. Tier data is illustrative (see lib/mockData.js) pending a
// real state-aggregate endpoint -- this component only renders whatever
// STATE_STATS supplies, it doesn't invent numbers of its own.
export default function IndiaStateGrid() {
  const [selected, setSelected] = useState(null)
  const active = STATE_STATS.find(s => s.name === selected)

  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(8, minmax(0,1fr))', gridTemplateRows: 'repeat(8, 30px)' }}>
        {STATE_STATS.map(s => (
          <button
            key={s.name}
            onClick={() => setSelected(s.name === selected ? null : s.name)}
            title={s.name}
            style={{ gridColumn: s.col, gridRow: s.row, backgroundColor: TIER_BG[s.tier], border: `1.5px solid ${s.name === selected ? '#0b3355' : 'transparent'}` }}
            className="rounded-[3px] flex items-center justify-center text-[8px] font-semibold px-0.5 hover:brightness-95 transition"
          >
            <span className="text-ink/70">{s.name.split(' ').map(w => w[0]).join('').slice(0, 3)}</span>
          </button>
        ))}
      </div>
      <div className="flex items-center gap-4 mt-3 text-xs text-muted">
        <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.low }} /> Low review volume</span>
        <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.medium }} /> Medium</span>
        <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_BG.high }} /> Elevated</span>
      </div>
      {active && (
        <div className="mt-3 flex items-center gap-3 px-3 py-2 rounded-md bg-panel border border-line">
          <span className="text-[12.5px] font-semibold text-ink">{active.name}</span>
          <span className="rounded px-2 py-0.5 text-xs font-semibold" style={{ color: TIER_STRONG[active.tier], backgroundColor: TIER_BG[active.tier] }}>
            {active.tier.toUpperCase()} REVIEW VOLUME
          </span>
        </div>
      )}
    </div>
  )
}