import React from 'react'
import { ShieldAlert, ShieldCheck, TriangleAlert } from 'lucide-react'
import { levelNarrative } from '../../lib/riskModel'

/* ==========================================================================
   RISK LEVEL BANNER
   ==========================================================================
   One glanceable line at the very top of Project Intelligence: LOW / MEDIUM /
   HIGH / CRITICAL, the score, and a marker on the 0-100 scale.

   The bands below are the SAME thresholds the backend uses
   (ml/risk_config.py RISK_LEVEL_THRESHOLDS: <25 LOW, <50 MEDIUM, <75 HIGH,
   >=75 CRITICAL), so the marker always sits inside the band that matches the
   level the backend assigned. Nothing is recalculated here -- the level and
   score are passed in exactly as the backend returned them.
   ========================================================================== */

const BANDS = [
  { key: 'LOW', from: 0, to: 25, color: '#1b8a5a', bg: '#e7f4ec', Icon: ShieldCheck },
  { key: 'MEDIUM', from: 25, to: 50, color: '#b7791f', bg: '#fbf0de', Icon: TriangleAlert },
  { key: 'HIGH', from: 50, to: 75, color: '#c0392b', bg: '#fadcd8', Icon: ShieldAlert },
  { key: 'CRITICAL', from: 75, to: 100, color: '#8e1b12', bg: '#f6cfca', Icon: ShieldAlert },
]

export default function RiskLevelBanner({ level, score, model }) {
  const key = String(level || '').toUpperCase()
  const band = BANDS.find(b => b.key === key)

  if (!band) return null

  const Icon = band.Icon
  const hasScore = typeof score === 'number' && Number.isFinite(score)
  const markerPct = hasScore ? Math.max(0, Math.min(100, score)) : null
  const signals = model ? model.triggered.length : null

  return (
    <div
      role="status"
      aria-label={`Overall risk level ${band.key}${hasScore ? `, score ${score.toFixed(1)} out of 100` : ''}`}
      className="card mb-4 overflow-hidden"
      style={{ borderColor: `${band.color}55` }}
    >
      {/* the "line" -- a solid colour strip across the top of the card */}
      <div style={{ height: 5, backgroundColor: band.color }} aria-hidden="true" />

      <div className="px-4 py-3.5 flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="inline-flex items-center justify-center w-10 h-10 rounded-full shrink-0"
            style={{ color: band.color, backgroundColor: band.bg }}
          >
            <Icon size={20} aria-hidden="true" />
          </span>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="text-[15px] font-bold tracking-wide"
                style={{ color: band.color }}
              >
                {band.key} RISK
              </span>
              {hasScore && (
                <span className="text-[13px] font-semibold text-ink tabular-nums">
                  {score.toFixed(1)}
                  <span className="text-[11px] font-normal text-muted"> / 100</span>
                </span>
              )}
              {signals !== null && (
                <span className="text-[11.5px] text-muted">
                  · {signals} active signal{signals === 1 ? '' : 's'}
                </span>
              )}
            </div>
            <p className="text-[12px] text-muted leading-4 mt-0.5">
              {levelNarrative(band.key, signals)}
            </p>
          </div>
        </div>

        {/* scale with marker */}
        <div className="flex-1 min-w-[240px]">
          <div className="relative pt-2.5">
            {markerPct !== null && (
              <div
                className="absolute top-0 -translate-x-1/2 transition-all"
                style={{ left: `${markerPct}%` }}
                aria-hidden="true"
              >
                <div
                  style={{
                    width: 0,
                    height: 0,
                    borderLeft: '5px solid transparent',
                    borderRight: '5px solid transparent',
                    borderTop: `7px solid ${band.color}`,
                  }}
                />
              </div>
            )}

            <div className="flex h-2 rounded-full overflow-hidden gap-[2px]" aria-hidden="true">
              {BANDS.map(b => (
                <div
                  key={b.key}
                  className="flex-1"
                  style={{
                    backgroundColor: b.color,
                    opacity: b.key === band.key ? 1 : 0.28,
                  }}
                />
              ))}
            </div>
          </div>

          <div className="flex mt-1" aria-hidden="true">
            {BANDS.map(b => (
              <div
                key={b.key}
                className="flex-1 text-center text-[10px] uppercase tracking-wide"
                style={{
                  color: b.key === band.key ? b.color : '#8a96a0',
                  fontWeight: b.key === band.key ? 700 : 500,
                }}
              >
                {b.key}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}