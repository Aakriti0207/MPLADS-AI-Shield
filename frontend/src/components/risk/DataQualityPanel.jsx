import React from 'react'
import { Users } from 'lucide-react'
import { extractPeerComparisons, peerCriteria } from '../../lib/riskModel'
import { PanelHeading, UnavailableNote } from './RiskPrimitives'

/* ==========================================================================
   SECTION 7 -- PEER COMPARISON
   ==========================================================================
   Built exclusively from peer statistics the backend actually attached to a
   signal's evidence (peer_group_level / peer_group_key / peer_group_size /
   peer_median / peer_deviation_pct). No peer group is constructed here and no
   comparable-project count is estimated.

   Deviation % is shown only when the backend supplied it. ml/risk.py omits it
   on purpose when the peer statistics sit on a log-transformed scale, because
   a percentage would be mathematically meaningless there -- in that case the
   modified z-score is shown instead, and no percentage is substituted.
   ========================================================================== */

function DeviationCell({ row }) {
  if (row.deviationPct !== null) {
    const positive = row.deviationPct > 0
    return (
      <span
        className="font-semibold tabular-nums"
        style={{ color: positive ? '#c0392b' : '#1b8a5a' }}
      >
        {positive ? '+' : ''}
        {row.deviationPct}%
      </span>
    )
  }

  if (row.zScore !== null) {
    return (
      <span className="tabular-nums text-ink" title="Modified z-score">
        z = {row.zScore.toFixed(2)}
      </span>
    )
  }

  return <span className="text-muted">Not available</span>
}

export default function PeerComparison({ model }) {
  const rows = extractPeerComparisons(model.components)
  const criteria = peerCriteria(rows)

  const largestGroup = rows.reduce(
    (max, row) => (row.groupSize !== null && row.groupSize > max ? row.groupSize : max),
    0
  )

  return (
    <div>
      <PanelHeading
        icon={Users}
        title="Peer Comparison"
        subtitle="How this project compares with the peer group the backend actually used"
        tooltip="Peer groups, medians and deviations are taken from the anomaly detector's own output. Metrics with no peer statistics are reported as unavailable rather than estimated."
      />

      {rows.length === 0 ? (
        <UnavailableNote>
          Peer comparison is unavailable for this project. No triggered signal carried peer-group
          statistics, so there is no comparable-project baseline to show.
        </UnavailableNote>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 gap-2.5 mb-3">
            <div className="rounded-md border border-line px-3.5 py-2.5">
              <div className="text-[11px] text-muted">Comparable projects in peer group</div>
              <div className="text-[17px] font-semibold text-ink tabular-nums mt-0.5">
                {largestGroup > 0 ? largestGroup.toLocaleString('en-IN') : 'Not recorded'}
              </div>
            </div>

            <div className="rounded-md border border-line px-3.5 py-2.5">
              <div className="text-[11px] text-muted mb-1.5">Peer grouping criteria used</div>
              {criteria.length === 0 ? (
                <div className="text-[12px] text-muted">Not recorded</div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {criteria.map(item => (
                    <span
                      key={item}
                      className="rounded-full bg-info-bg text-navy px-2 py-0.5 text-[10.5px] font-medium"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-[12px] border-collapse">
              <caption className="sr-only">
                Per-metric comparison of this project against its peer group median.
              </caption>
              <thead>
                <tr className="text-left text-[10.5px] text-muted uppercase tracking-wide border-b border-line">
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Metric
                  </th>
                  <th scope="col" className="py-2 px-3 font-semibold">
                    This project
                  </th>
                  <th scope="col" className="py-2 px-3 font-semibold">
                    Peer median
                  </th>
                  <th scope="col" className="py-2 pl-3 font-semibold text-right">
                    Deviation
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.key} className="border-b border-line/70">
                    <th scope="row" className="py-2 pr-3 font-normal">
                      <span className="text-ink font-medium">{row.metric}</span>
                      <span className="block text-[10.5px] text-muted">{row.componentLabel}</span>
                    </th>
                    <td className="py-2 px-3 text-ink tabular-nums">
                      {row.observed ?? 'Not available'}
                    </td>
                    <td className="py-2 px-3 text-muted tabular-nums">
                      {row.peerMedian ?? 'Not available'}
                    </td>
                    <td className="py-2 pl-3 text-right">
                      <DeviationCell row={row} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[11px] text-muted leading-4 mt-2.5 italic">
            Where a percentage deviation is not shown, the underlying peer statistics are on a
            transformed scale on which a percentage would not be meaningful; the modified z-score
            is shown instead.
          </p>
        </>
      )}
    </div>
  )
}