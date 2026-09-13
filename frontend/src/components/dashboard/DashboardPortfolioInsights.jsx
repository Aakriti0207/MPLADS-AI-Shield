import React from 'react'
import { Section } from '../UI'
import EmptyState from '../ui/EmptyState'
import { formatNumber } from '../../lib/formatters'
import { CHART_COLORS } from './dashboardColors'

const TOP_N = 5


function isFiniteNumber(value) {
  return (
    typeof value === 'number' &&
    Number.isFinite(value)
  )
}


function topN(rows, valueKey, n = TOP_N) {
  return [...rows]
    .filter(row => row && isFiniteNumber(row[valueKey]))
    .sort(
      (a, b) => b[valueKey] - a[valueKey]
    )
    .slice(0, n)
}


/* -------------------------------------------------------
   Shared horizontal share/progress bar
------------------------------------------------------- */

function ShareBar({
  label,
  value,
  total,
  color,
  unavailable = false,
  unavailableReason = null,
}) {
  const known =
    !unavailable &&
    isFiniteNumber(value) &&
    isFiniteNumber(total) &&
    total > 0

  const pct = known
    ? Math.min(
        100,
        Math.max(
          0,
          Math.round((value / total) * 100)
        )
      )
    : null

  return (
    <div>

      <div className="flex items-baseline justify-between text-xs mb-1">

        <span className="text-muted">
          {label}
        </span>

        <span className="font-semibold text-ink">

          {unavailable
            ? 'Unavailable'
            : isFiniteNumber(value)
              ? formatNumber(value)
              : 'Not available'}

          {known && (
            <span className="text-muted font-normal">
              {' · '}
              {pct}%
            </span>
          )}

        </span>

      </div>


      <div className="h-2 rounded-full bg-panel overflow-hidden">

        {known && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              backgroundColor: color,
            }}
          />
        )}

      </div>


      {unavailable && unavailableReason && (
        <div className="text-[11px] text-muted mt-1">
          {unavailableReason}
        </div>
      )}

    </div>
  )
}


/* -------------------------------------------------------
   Ranked list
------------------------------------------------------- */

function RankedList({
  rows,
  labelKey,
  valueKey,
  formatValue,
}) {
  if (!rows.length) {
    return null
  }

  const max = Math.max(
    ...rows.map(row =>
      isFiniteNumber(row[valueKey])
        ? row[valueKey]
        : 0
    ),
    1
  )

  return (
    <div className="space-y-3">

      {rows.map((row, index) => {

        const raw = row[valueKey]

        const known =
          isFiniteNumber(raw)

        const pct = known
          ? Math.max(
              4,
              Math.round(
                (raw / max) * 100
              )
            )
          : 0

        const label =
          row[labelKey] || 'Not specified'

        return (
          <div
            key={`${label}-${index}`}
          >

            <div className="flex items-baseline justify-between text-xs mb-1">

              <span className="text-ink/80 truncate pr-2">
                {label}
              </span>

              <span className="font-semibold text-ink shrink-0">
                {formatValue(raw)}
              </span>

            </div>


            <div className="h-1.5 rounded-full bg-panel overflow-hidden">

              {known && (
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${pct}%`,
                    backgroundColor:
                      CHART_COLORS.blue,
                  }}
                />
              )}

            </div>

          </div>
        )
      })}

    </div>
  )
}


/* -------------------------------------------------------
   Main component
------------------------------------------------------- */

export default function DashboardPortfolioInsights({
  totalProjects,
  activeProjects,
  completedProjects,
  delayedProjects,

  // ML-4
  delayedProjectsAvailable = false,
  delayedProjectsReason = null,

  avgPhysicalProgress,
  byState,
  byWorkType,
}) {

  /* -----------------------------------------------------
     State data

     This comes directly from the real backend aggregation:
       state
       total_sanctioned_amount
       total_expenditure
  ----------------------------------------------------- */

  const stateRows = topN(
    (byState || []).filter(
      row =>
        row &&
        row.state &&
        isFiniteNumber(
          row.total_expenditure
        )
    ),
    'total_expenditure'
  )


  /* -----------------------------------------------------
     Work-type data

     IMPORTANT:
     The current real database returns:

       Not specified → 56,323

     That means work_type is unavailable in the
     imported portfolio. Do NOT display "Not specified"
     as if it were a meaningful work category.
  ----------------------------------------------------- */

  const rawWorkTypeRows =
    (byWorkType || []).filter(
      row =>
        row &&
        row.work_type &&
        isFiniteNumber(row.count)
    )

  const hasUsableWorkTypeData =
    rawWorkTypeRows.length > 0 &&
    rawWorkTypeRows.some(
      row =>
        row.work_type.trim().toLowerCase() !==
        'not specified'
    )

  const workTypeRows =
    hasUsableWorkTypeData
      ? topN(
          rawWorkTypeRows.filter(
            row =>
              row.work_type
                .trim()
                .toLowerCase() !==
              'not specified'
          ),
          'count'
        )
      : []


  return (
    <div className="grid lg:grid-cols-5 gap-4">


      {/* =================================================
          PORTFOLIO STATUS
      ================================================= */}

      <div className="card p-4 lg:col-span-2">

        <Section
          title="Portfolio Status"
          subtitle="Execution status across the full portfolio"
        />


        <div className="space-y-4">

          {/* Active */}

          <ShareBar
            label="Active"
            value={activeProjects}
            total={totalProjects}
            color={CHART_COLORS.blue}
          />


          {/* Completed */}

          <ShareBar
            label="Completed"
            value={completedProjects}
            total={totalProjects}
            color={CHART_COLORS.green}
          />


          {/* ------------------------------------------------
              ML-4

              expected_completion is unavailable in the
              real imported dataset, therefore delayed
              projects cannot currently be calculated.
          ------------------------------------------------ */}

          <ShareBar
            label="Delayed"
            value={delayedProjects}
            total={totalProjects}
            color={CHART_COLORS.amber}
            unavailable={
              !delayedProjectsAvailable
            }
            unavailableReason={
              delayedProjectsReason ||
              'Expected completion data unavailable'
            }
          />

        </div>


        {/* =================================================
            AVERAGE PHYSICAL PROGRESS
        ================================================= */}

        <div className="mt-4 pt-3 border-t border-line">

          <div className="text-xs text-muted mb-1">
            Average physical progress
          </div>


          {isFiniteNumber(
            avgPhysicalProgress
          ) ? (

            <div className="w-full">

              <div className="h-2 bg-panel rounded-full overflow-hidden">

                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(
                        0,
                        Math.round(
                          avgPhysicalProgress
                        )
                      )
                    )}%`,
                    backgroundColor:
                      CHART_COLORS.navy,
                  }}
                />

              </div>


              <div className="text-xs text-muted mt-1">
                {Math.round(
                  avgPhysicalProgress
                )}%
              </div>

            </div>

          ) : (

            <div className="text-xs text-muted">
              Not reported by the current backend data.
            </div>

          )}

        </div>

      </div>


      {/* =================================================
          PORTFOLIO COMPOSITION
      ================================================= */}

      <div className="card p-4 lg:col-span-3">

        <Section
          title="Portfolio Composition"
          subtitle="Top states and work types by volume"
        />


        <div className="grid sm:grid-cols-2 gap-5">


          {/* =================================================
              TOP STATES
          ================================================= */}

          <div>

            <div className="text-[10.5px] font-semibold text-muted mb-2.5 uppercase tracking-wide">
              Top states by expenditure
            </div>


            {stateRows.length > 0 ? (

              <RankedList
                rows={stateRows}
                labelKey="state"
                valueKey="total_expenditure"
                formatValue={value =>
                  isFiniteNumber(value)
                    ? `₹${(
                        value / 10000000
                      ).toFixed(1)} Cr`
                    : 'Not available'
                }
              />

            ) : (

              <EmptyState
                text="State breakdown not available."
              />

            )}

          </div>


          {/* =================================================
              WORK TYPES
          ================================================= */}

          <div>

            <div className="text-[10.5px] font-semibold text-muted mb-2.5 uppercase tracking-wide">
              Top work types
            </div>


            {workTypeRows.length > 0 ? (

              <RankedList
                rows={workTypeRows}
                labelKey="work_type"
                valueKey="count"
                formatValue={value =>
                  isFiniteNumber(value)
                    ? formatNumber(value)
                    : 'Not available'
                }
              />

            ) : (

              <div className="rounded-lg border border-line bg-panel/40 p-3">

                <div className="text-sm font-medium text-ink">
                  Unavailable
                </div>

                <div className="text-[11px] text-muted mt-1">
                  Work-type data is not available in
                  the current imported portfolio.
                </div>

              </div>

            )}

          </div>

        </div>

      </div>

    </div>
  )
}