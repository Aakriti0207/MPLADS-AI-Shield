import React from 'react'
import { CircleCheck, TriangleAlert } from 'lucide-react'
import { GLOSSARY, levelNarrative, statusTone } from '../../lib/riskModel'
import { InfoTip, PanelHeading } from './RiskPrimitives'

/* ==========================================================================
   SECTION 1 -- RISK FUSION: OVERALL RISK
   SECTION 2 -- RISK CONTRIBUTION SUMMARY
   ==========================================================================
   The score rendered here is the backend's `risk_score` verbatim. The gauge
   arc is a drawing of that number; it is not recomputed from the components.
   ========================================================================== */

/**
 * Score gauge. The arc is segmented by the SAME thresholds the backend uses
 * (ml/risk_config.py RISK_LEVEL_THRESHOLDS: <25 LOW, <50 MEDIUM, <75 HIGH,
 * >=75 CRITICAL), so the visual band a needle sits in always agrees with the
 * risk level the backend assigned.
 */
function ScoreGauge({ score, level }) {
  const size = 148
  const stroke = 13
  const radius = (size - stroke) / 2
  const circumference = Math.PI * radius // semicircle
  const tone = statusTone(
    { CRITICAL: 'HIGH', HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW' }[level] || 'NONE'
  )

  const pct = score === null ? 0 : Math.max(0, Math.min(100, score))
  const arc = (pct / 100) * circumference

  return (
    <div className="relative shrink-0" style={{ width: size, height: size / 2 + 26 }}>
      <svg
        width={size}
        height={size / 2 + 8}
        viewBox={`0 0 ${size} ${size / 2 + 8}`}
        role="img"
        aria-label={
          score === null
            ? 'Risk score not available'
            : `Risk score ${score.toFixed(1)} out of 100, level ${level || 'unknown'}`
        }
      >
        <path
          d={`M ${stroke / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - stroke / 2} ${size / 2}`}
          fill="none"
          stroke="#e7ebef"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {score !== null && (
          <path
            d={`M ${stroke / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - stroke / 2} ${size / 2}`}
            fill="none"
            stroke={tone.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arc} ${circumference}`}
          />
        )}
      </svg>

      <div className="absolute inset-x-0 top-[34px] text-center">
        <div className="text-[30px] font-bold leading-none text-ink tabular-nums">
          {score === null ? '—' : score.toFixed(1)}
        </div>
        <div className="text-[11px] text-muted mt-1">/ 100</div>
      </div>
    </div>
  )
}

function SummaryTile({ label, value, hint, tooltip }) {
  return (
    <div className="rounded-md border border-line px-3.5 py-3">
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] text-muted">{label}</span>
        <InfoTip text={tooltip} label={label} />
      </div>
      <div className="text-[17px] font-semibold text-ink mt-1 leading-tight">{value}</div>
      {hint && <div className="text-[11px] text-muted mt-0.5">{hint}</div>}
    </div>
  )
}

export default function RiskOverview({ model }) {
  const { score, level, components, triggered, dataQuality, totalSignals } = model
  const tone = statusTone(
    { CRITICAL: 'HIGH', HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW' }[level] || 'NONE'
  )
  const top = triggered[0] || null

  const dataQualityLabel = !dataQuality.detailAvailable
    ? 'Not recorded'
    : dataQuality.complete
      ? 'Complete'
      : `${dataQuality.unevaluable.length} domain(s) missing`

  return (
    <div>
      <PanelHeading
        title="Risk Fusion — Overall Risk"
        subtitle="Combined review-priority score from every independent detection component"
        tooltip={GLOSSARY.risk_fusion}
      />

      <div className="grid md:grid-cols-2 gap-5 items-start">
        {/* Score + level + plain-language reading */}
        <div className="flex items-start gap-4">
          <ScoreGauge score={score} level={level} />

          <div className="min-w-0 pt-3">
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold"
              style={{ color: tone.color, backgroundColor: tone.bg }}
            >
              <TriangleAlert size={13} aria-hidden="true" />
              {level ? `${level} RISK` : 'RISK LEVEL UNAVAILABLE'}
            </span>

            <p className="text-[12.5px] text-ink leading-5 mt-2.5">
              {levelNarrative(level, totalSignals)}
            </p>

            <p className="text-[11px] text-muted leading-4 mt-2">
              This is a review-priority signal. It does not establish fraud or wrongdoing.
            </p>
          </div>
        </div>

        {/* Risk contribution summary */}
        <div>
          <h4 className="text-[12.5px] font-semibold text-ink mb-2.5">
            Risk Contribution Summary
          </h4>

          <div className="grid grid-cols-2 gap-2.5">
            <SummaryTile
              label="Risk components evaluated"
              value={components.length}
              tooltip="Every component in the Risk Fusion model, whether or not it triggered for this project."
            />

            <SummaryTile
              label="Active risk signals"
              value={triggered.length}
              hint={
                totalSignals && totalSignals !== triggered.length
                  ? `${totalSignals} individual signal(s)`
                  : null
              }
              tooltip="Components that actually triggered at least one signal for this project."
            />

            <SummaryTile
              label="Highest contributor"
              value={top ? top.label.replace(/ Risk$/, '') : 'None'}
              hint={
                top ? `${top.contribution.toFixed(1)} pts · ${top.sharePct.toFixed(1)}%` : null
              }
              tooltip={GLOSSARY.contribution}
            />

            <SummaryTile
              label="Data quality"
              value={
                <span className="inline-flex items-center gap-1.5">
                  {dataQuality.complete ? (
                    <CircleCheck size={14} style={{ color: '#1b8a5a' }} aria-hidden="true" />
                  ) : (
                    <TriangleAlert size={14} style={{ color: '#b7791f' }} aria-hidden="true" />
                  )}
                  <span className="text-[14px]">{dataQualityLabel}</span>
                </span>
              }
              tooltip={GLOSSARY.evidence_status}
            />
          </div>
        </div>
      </div>
    </div>
  )
}