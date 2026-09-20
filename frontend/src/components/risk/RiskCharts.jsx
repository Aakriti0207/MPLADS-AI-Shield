import React, { useMemo } from 'react'
import { Radar, Users } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { extractPeerComparisons, peerCriteria, statusTone } from '../../lib/riskModel'
import { PanelHeading, UnavailableNote } from './RiskPrimitives'

/* ==========================================================================
   RISK CHARTS -- ANOMALY GRAPH + PEER-TO-PEER GRAPH
   ==========================================================================
   Two graphs that sit ABOVE the detailed panels. They only draw numbers the
   backend already produced:

     Anomaly graph  -> each detector's own 0-100 raw score (component.rawScore)
     Peer graph     -> the modified z-score (or deviation %) the backend
                       attached to a signal's peer evidence

   Nothing is recalculated or estimated. If the backend sent no peer
   statistics, the peer graph says so instead of inventing a comparison.
   ========================================================================== */

const GRID = '#dce2e8'
const MUTED = '#55636e'
const INK = '#16232e'
const NEUTRAL_BAR = '#c7ced5'
const PEER_NORMAL = '#7ea3c7'

// 3.5 is the backend's own ANOMALY threshold for the modified z-score
// (ml/risk_config.py). Drawn only as a visual guide.
const Z_THRESHOLD = 3.5

const tooltipStyle = {
  fontSize: 12,
  borderRadius: 6,
  border: `1px solid ${GRID}`,
  boxShadow: '0 4px 14px rgba(11,46,79,0.10)',
}

function shortLabel(label) {
  return String(label || '')
    .replace(/ \(Isolation Forest\)/, '')
    .replace(/ Risk$/, '')
}

/* ---------------------------------------------------------------- anomaly */

function AnomalyTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white px-3 py-2 text-[12px]" style={tooltipStyle}>
      <div className="font-semibold text-ink mb-1">{d.full}</div>
      <div className="text-muted">
        Raw score: <span className="text-ink font-semibold">{d.raw.toFixed(1)} / 100</span>
      </div>
      <div className="text-muted">
        Weight: <span className="text-ink font-semibold">{d.weight.toFixed(0)}%</span>
      </div>
      <div className="text-muted">
        Added to final score:{' '}
        <span className="text-ink font-semibold">{d.contribution.toFixed(2)} pts</span>
      </div>
      <div className="text-muted">
        Status: <span className="font-semibold" style={{ color: d.color }}>{d.statusLabel}</span>
      </div>
    </div>
  )
}

export function AnomalyChart({ model }) {
  const data = useMemo(
    () =>
      model.components
        .map(c => {
          const tone = statusTone(c.status)
          return {
            name: shortLabel(c.label),
            full: c.label,
            raw: c.rawScore,
            weight: c.weight,
            contribution: c.contribution,
            statusLabel: tone.label,
            color: c.triggered ? tone.color : NEUTRAL_BAR,
          }
        })
        .sort((a, b) => b.raw - a.raw),
    [model.components]
  )

  const height = Math.max(200, data.length * 36 + 30)

  return (
    <div>
      <PanelHeading
        icon={Radar}
        title="Anomaly Analysis"
        subtitle="Each detector's own anomaly score (0–100) before weighting"
        tooltip="Bars show the raw score every detection component produced on its own. Coloured bars triggered a signal; grey bars were evaluated and found nothing. The final risk score also depends on each component's weight, see the breakdown below."
      />

      <div style={{ height }} role="img" aria-label="Bar chart of raw anomaly score per detection component">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 34, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={GRID} />
            <XAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fontSize: 11, fill: MUTED }}
              axisLine={{ stroke: GRID }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={138}
              tick={{ fontSize: 11.5, fill: INK }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<AnomalyTooltip />} cursor={{ fill: 'rgba(11,46,79,0.04)' }} />
            <Bar dataKey="raw" radius={[0, 4, 4, 0]} barSize={16}>
              {data.map(d => (
                <Cell key={d.full} fill={d.color} />
              ))}
              <LabelList
                dataKey="raw"
                position="right"
                formatter={v => Number(v).toFixed(0)}
                style={{ fontSize: 11, fill: INK, fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: '#c0392b' }} />
          Triggered
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: NEUTRAL_BAR }} />
          Evaluated, nothing triggered
        </span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ peer */

function PeerTooltip({ active, payload, mode }) {
  if (!active || !payload || !payload.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white px-3 py-2 text-[12px] max-w-[260px]" style={tooltipStyle}>
      <div className="font-semibold text-ink">{d.metric}</div>
      <div className="text-[10.5px] text-muted mb-1">{d.componentLabel}</div>
      <div className="text-muted">
        This project: <span className="text-ink font-semibold">{d.observed ?? 'Not available'}</span>
      </div>
      <div className="text-muted">
        Peer median: <span className="text-ink font-semibold">{d.peerMedian ?? 'Not available'}</span>
      </div>
      <div className="text-muted">
        {mode === 'z' ? 'Modified z-score' : 'Deviation'}:{' '}
        <span className="text-ink font-semibold">
          {mode === 'z' ? d.value.toFixed(2) : `${d.value > 0 ? '+' : ''}${d.value}%`}
        </span>
      </div>
    </div>
  )
}

export function PeerChart({ model }) {
  const rows = useMemo(() => extractPeerComparisons(model.components), [model.components])
  const criteria = useMemo(() => peerCriteria(rows), [rows])

  const largestGroup = rows.reduce(
    (max, r) => (r.groupSize !== null && r.groupSize > max ? r.groupSize : max),
    0
  )

  // Prefer the modified z-score (comparable across metrics). Fall back to the
  // deviation % only when no row carries a z-score -- never mix the two units
  // on one axis.
  const zRows = rows.filter(r => r.zScore !== null)
  const pctRows = rows.filter(r => r.deviationPct !== null)
  const mode = zRows.length ? 'z' : pctRows.length ? 'pct' : null
  const source = mode === 'z' ? zRows : mode === 'pct' ? pctRows : []

  const seen = new Map()
  const data = source.map(r => {
    const n = (seen.get(r.metric) || 0) + 1
    seen.set(r.metric, n)
    return {
      label: n > 1 ? `${r.metric} (${n})` : r.metric,
      metric: r.metric,
      componentLabel: r.componentLabel,
      observed: r.observed,
      peerMedian: r.peerMedian,
      value: mode === 'z' ? r.zScore : r.deviationPct,
    }
  })

  const maxAbs = data.reduce((m, d) => Math.max(m, Math.abs(d.value)), 0)
  const bound =
    mode === 'z'
      ? Math.max(Z_THRESHOLD + 1, Math.ceil(maxAbs + 1))
      : Math.max(10, Math.ceil((maxAbs * 1.15) / 10) * 10)

  const isFlagged = d => (mode === 'z' ? Math.abs(d.value) >= Z_THRESHOLD : Math.abs(d.value) >= 50)
  const height = Math.max(170, data.length * 46 + 50)

  return (
    <div>
      <PanelHeading
        icon={Users}
        title="Peer-to-Peer Analysis"
        subtitle="How far this project sits from comparable projects, metric by metric"
        tooltip="Distance from the peer-group median as reported by the anomaly detector. Bars to the left mean lower than peers, to the right higher than peers. Bars outside the dashed lines are statistical outliers."
      />

      {mode === null ? (
        <UnavailableNote>
          Peer-to-peer analysis is unavailable for this project. No signal carried peer-group
          statistics, so there is no comparable-project baseline to draw.
        </UnavailableNote>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mb-2 text-[11.5px] text-muted">
            <span>
              Peer group:{' '}
              <span className="font-semibold text-ink tabular-nums">
                {largestGroup > 0 ? `${largestGroup.toLocaleString('en-IN')} comparable projects` : 'size not recorded'}
              </span>
            </span>
            {criteria.slice(0, 4).map(item => (
              <span
                key={item}
                className="rounded-full bg-info-bg text-navy px-2 py-0.5 text-[10.5px] font-medium"
              >
                {item}
              </span>
            ))}
          </div>

          <div style={{ height }} role="img" aria-label="Bar chart of deviation from peer median per metric">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 4, right: 20, top: 14, bottom: 4 }}>
                <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={GRID} />
                <XAxis
                  type="number"
                  domain={[-bound, bound]}
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: MUTED }}
                  axisLine={{ stroke: GRID }}
                  tickLine={false}
                  tickFormatter={v => (mode === 'z' ? v : `${v}%`)}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={128}
                  tick={{ fontSize: 11.5, fill: INK }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={<PeerTooltip mode={mode} />}
                  cursor={{ fill: 'rgba(11,46,79,0.04)' }}
                />
                <ReferenceLine x={0} stroke={MUTED} />
                {mode === 'z' && (
                  <>
                    <ReferenceLine x={-Z_THRESHOLD} stroke="#b7791f" strokeDasharray="4 3" />
                    <ReferenceLine
                      x={Z_THRESHOLD}
                      stroke="#b7791f"
                      strokeDasharray="4 3"
                      label={{ value: '±3.5 outlier', position: 'top', fontSize: 10, fill: '#b7791f' }}
                    />
                  </>
                )}
                <Bar dataKey="value" barSize={16} radius={[3, 3, 3, 3]}>
                  {data.map(d => (
                    <Cell key={d.label} fill={isFlagged(d) ? '#c0392b' : PEER_NORMAL} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="text-[11px] text-muted leading-4 mt-2 italic">
            {mode === 'z'
              ? 'Values are modified z-scores from the backend. Red bars are beyond the ±3.5 anomaly threshold.'
              : 'Values are percentage deviation from the peer median reported by the backend.'}
          </p>
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------- composite */

export default function RiskCharts({ model }) {
  if (!model || !model.hasComponents) return null

  return (
    <div className="grid xl:grid-cols-2 gap-4 items-start">
      <div className="card p-4">
        <AnomalyChart model={model} />
      </div>
      <div className="card p-4">
        <PeerChart model={model} />
      </div>
    </div>
  )
}