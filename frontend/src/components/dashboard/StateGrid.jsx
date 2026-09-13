import React from 'react'
import { COLORS, Badge } from './DashboardUI'

// Visual layout only (name + grid position), preserved exactly from the
// approved reference (IndiaGridMap in mplads-ai-shield.jsx). No project
// counts, review counts, or tiers are kept from the reference — those are
// mock and are replaced below with real backend figures.
export const STATE_LAYOUT = [
  { name: 'Jammu & Kashmir', row: 1, col: 4 },
  { name: 'Punjab', row: 2, col: 3 },
  { name: 'Himachal Pradesh', row: 2, col: 4 },
  { name: 'Uttarakhand', row: 2, col: 5 },
  { name: 'Haryana', row: 3, col: 3 },
  { name: 'Delhi', row: 3, col: 4 },
  { name: 'Uttar Pradesh', row: 3, col: 5 },
  { name: 'Assam', row: 3, col: 8 },
  { name: 'Rajasthan', row: 4, col: 2 },
  { name: 'Madhya Pradesh', row: 4, col: 4 },
  { name: 'Bihar', row: 4, col: 6 },
  { name: 'West Bengal', row: 4, col: 7 },
  { name: 'Gujarat', row: 5, col: 1 },
  { name: 'Chhattisgarh', row: 5, col: 5 },
  { name: 'Jharkhand', row: 5, col: 6 },
  { name: 'Odisha', row: 5, col: 7 },
  { name: 'Maharashtra', row: 6, col: 3 },
  { name: 'Telangana', row: 6, col: 5 },
  { name: 'Andhra Pradesh', row: 7, col: 5 },
  { name: 'Karnataka', row: 7, col: 3 },
  { name: 'Tamil Nadu', row: 8, col: 4 },
  { name: 'Kerala', row: 8, col: 3 },
]

// Tolerant lookup: real state names in the backend may differ in casing,
// spacing, or use "and" instead of "&".
function normalizeName(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z]/g, '')
}

// Colors for tiles where we *do* have a review-rate signal, matching the
// reference's tier palette exactly.
const TIER_COLOR = { low: '#BFE3D0', medium: '#F3D399', high: '#EAB2AC' }
const TIER_COLOR_STRONG = { low: COLORS.green, medium: COLORS.amber, high: COLORS.red }
// Neutral tiers for honestly-partial or missing data (never colored as if
// they were a real risk signal).
const COUNT_ONLY_COLOR = '#DCE6EF'
const NO_DATA_COLOR = '#EDEFF1'

function firstDefined(obj, keys) {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k]
  }
  return null
}

// Merges STATE_LAYOUT (visual positions) with real by_state rows from
// /dashboard/stats. Never invents a count or a review figure: a state with
// no matching backend row, or with no usable numeric fields, is marked
// noData rather than assigned a fabricated tier.
export function buildStateGridData(byState) {
  const rows = Array.isArray(byState) ? byState : []
  const byNormalizedName = new Map()
  for (const row of rows) {
    const key = normalizeName(row.state ?? row.name)
    if (key) byNormalizedName.set(key, row)
  }

  return STATE_LAYOUT.map(layout => {
    const row = byNormalizedName.get(normalizeName(layout.name))
    if (!row) return { ...layout, projects: null, review: null, expenditure: null, tier: 'noData' }

    const projects = firstDefined(row, ['count', 'project_count', 'total_projects', 'projects'])
    const review = firstDefined(row, ['review_count', 'requires_review_count', 'high_critical_count', 'review'])
    const expenditure = firstDefined(row, ['total_expenditure', 'expenditure'])

    let tier = 'noData'
    if (projects !== null && review !== null && projects > 0) {
      const rate = review / projects
      tier = rate > 0.08 ? 'high' : rate > 0.03 ? 'medium' : 'low'
    } else if (projects !== null || expenditure !== null) {
      tier = 'countOnly'
    }

    return { ...layout, projects, review, expenditure, tier }
  })
}

function tileColor(tier) {
  if (tier === 'low' || tier === 'medium' || tier === 'high') return TIER_COLOR[tier]
  if (tier === 'countOnly') return COUNT_ONLY_COLOR
  return NO_DATA_COLOR
}

export default function IndiaStateGrid({ data, selected, onSelect }) {
  const maxCol = 8, maxRow = 8
  const anyReviewTier = data.some(s => s.tier === 'low' || s.tier === 'medium' || s.tier === 'high')
  const anyCountOnly = data.some(s => s.tier === 'countOnly')
  const anyData = anyReviewTier || anyCountOnly

  return (
    <div>
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${maxCol}, minmax(0,1fr))`, gridTemplateRows: `repeat(${maxRow}, 34px)` }}
      >
        {data.map(s => {
          const initials = s.name.split(' ').map(w => w[0]).join('').slice(0, 3)
          const title = s.tier === 'noData'
            ? `${s.name} — no data available`
            : s.tier === 'countOnly'
              ? `${s.name} — ${s.projects !== null ? s.projects.toLocaleString('en-IN') : 'Not available'} projects`
              : `${s.name} — ${s.projects.toLocaleString('en-IN')} projects, ${s.review} review indicators`
          return (
            <button
              key={s.name}
              onClick={() => onSelect(s.name === selected ? null : s.name)}
              title={title}
              style={{
                gridColumn: s.col, gridRow: s.row,
                backgroundColor: tileColor(s.tier),
                border: `1.5px solid ${s.name === selected ? COLORS.navy : 'transparent'}`,
              }}
              className="rounded-[3px] flex items-center justify-center text-[8px] font-semibold leading-tight px-0.5 transition-colors hover:brightness-95"
            >
              <span style={{ color: COLORS.ink, opacity: s.tier === 'noData' ? 0.35 : 0.75 }}>{initials}</span>
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-3 text-[11px]" style={{ color: COLORS.inkSoft }}>
        {anyReviewTier ? (
          <>
            <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_COLOR.low }} /> Low review volume</span>
            <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_COLOR.medium }} /> Medium</span>
            <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: TIER_COLOR.high }} /> Elevated</span>
          </>
        ) : anyCountOnly ? (
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: COUNT_ONLY_COLOR }} /> Project count available</span>
        ) : null}
        <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: NO_DATA_COLOR }} /> No data available</span>
      </div>

      {!anyData && (
        <p className="text-[11.5px] mt-2" style={{ color: COLORS.inkSoft }}>
          State-level figures are not currently exposed by the dashboard API.
        </p>
      )}

      {selected && (() => {
        const s = data.find(x => x.name === selected)
        if (!s) return null
        return (
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 px-3 py-2 rounded" style={{ backgroundColor: COLORS.bg, border: `1px solid ${COLORS.border}` }}>
            <span className="text-[12.5px] font-semibold" style={{ color: COLORS.ink }}>{s.name}</span>
            <span className="text-[11.5px]" style={{ color: COLORS.inkSoft }}>
              {s.projects !== null ? `${s.projects.toLocaleString('en-IN')} projects` : 'Projects: Not available'}
            </span>
            <span className="text-[11.5px]" style={{ color: COLORS.inkSoft }}>
              {s.review !== null ? `${s.review.toLocaleString('en-IN')} review indicators` : 'Review indicators: Not available'}
            </span>
            {(s.tier === 'low' || s.tier === 'medium' || s.tier === 'high') && (
              <Badge color={TIER_COLOR_STRONG[s.tier]} bg={TIER_COLOR[s.tier]}>{s.tier.toUpperCase()}</Badge>
            )}
          </div>
        )
      })()}
    </div>
  )
}
