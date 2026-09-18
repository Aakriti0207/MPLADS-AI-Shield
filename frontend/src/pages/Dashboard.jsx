import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
} from 'lucide-react'

import { toNumber } from '../lib/formatters'
import { ROLE } from '../lib/roles'
import { useAuth } from '../context/AuthContext'

import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import EmptyState from '../components/ui/EmptyState'
import PageContainer from '../components/layout/PageContainer'

import DashboardKpiGrid from '../components/dashboard/DashboardKpiGrid'
import DashboardFinancialOverview from '../components/dashboard/DashboardFinancialOverview'
import DashboardRiskOverview from '../components/dashboard/DashboardRiskOverview'
import DashboardPortfolioInsights from '../components/dashboard/DashboardPortfolioInsights'
import DashboardQuickAccess from '../components/dashboard/DashboardQuickAccess'
import ScopedDashboard from '../components/dashboard/ScopedDashboard'

import { RiskBadge } from '../components/UI'

import {
  fetchPublicOverview,
  fetchRoleDashboard,
} from '../features/dashboard/api'


/* ============================================================
   MAIN DASHBOARD
   ============================================================ */

export default function Dashboard() {
  /*
   * `role` is the canonical role key resolved by the BACKEND and passed
   * through AuthContext -- not a local guess from the role string. An
   * unrecognised role resolves to UNSCOPED, which lands on the scoped
   * dashboard's "no jurisdiction assigned" state rather than falling
   * through to the national view.
   */
  const { role } = useAuth()


  /*
   * Ministry/Admin gets the national command-center dashboard.
   * State Nodal, District Authority and MP each get their own scoped
   * cockpit, chosen by the backend's `dashboard` key.
   */
  if (role !== ROLE.MINISTRY) {
    return (
      <PageContainer>
        <ScopedDashboard role={role} />
      </PageContainer>
    )
  }


  return <MinistryDashboard />
}


/* ============================================================
   MINISTRY DASHBOARD
   ============================================================ */

function MinistryDashboard() {

  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)


  /* ------------------------------------------------------------
     Load dashboard

     Priority:
       1. Authenticated Ministry endpoint
          /dashboard/role-overview

       2. If authentication is unavailable (for example
          Demo Mode), fall back to:
          /public/overview

     This keeps the dashboard usable in prototype/demo mode
     without pretending that public data contains Ministry-only
     risk information.
  ------------------------------------------------------------ */

  const loadDashboard = async () => {

    setLoading(true)
    setError(null)

    try {

      let data

      try {

        /*
         * First attempt the real authenticated Ministry
         * dashboard.
         */
        data = await fetchRoleDashboard()

      } catch (roleError) {

        /*
         * Demo Mode may not have a backend JWT.
         *
         * In that case /dashboard/role-overview returns 401.
         *
         * Fall back to the public overview instead of
         * rendering a completely broken dashboard.
         */
        const status =
          roleError?.status ||
          roleError?.statusCode ||
          roleError?.response?.status

        const message =
          String(
            roleError?.message || ''
          ).toLowerCase()

        const isUnauthorized =
          status === 401 ||
          message.includes('401') ||
          message.includes('unauthorized')

        if (!isUnauthorized) {
          throw roleError
        }


        /*
         * Public overview does not require Ministry
         * authentication.
         */
        const publicStats =
          await fetchPublicOverview()

        data = {
          stats: publicStats,

          /*
           * Public data is intentionally NOT treated as
           * Ministry-scoped data.
           */
          scope_available: false,

          /*
           * No Ministry-only risk data in public fallback.
           */
          by_state_risk: null,

          priority_projects: [],
        }
      }


      setOverview(data)

    } catch (err) {

      setError(
        err?.message ||
        'Failed to reach the dashboard API'
      )

    } finally {

      setLoading(false)

    }
  }


  useEffect(() => {

    let cancelled = false


    const load = async () => {

      setLoading(true)
      setError(null)

      try {

        let data

        try {

          /*
           * Preferred source:
           * authenticated Ministry dashboard.
           */
          data = await fetchRoleDashboard()

        } catch (roleError) {

          const status =
            roleError?.status ||
            roleError?.statusCode ||
            roleError?.response?.status

          const message =
            String(
              roleError?.message || ''
            ).toLowerCase()

          const isUnauthorized =
            status === 401 ||
            message.includes('401') ||
            message.includes('unauthorized')


          if (!isUnauthorized) {
            throw roleError
          }


          /*
           * Demo / unauthenticated fallback.
           */
          const publicStats =
            await fetchPublicOverview()

          data = {
            stats: publicStats,
            scope_available: false,
            by_state_risk: null,
            priority_projects: [],
          }

        }


        if (!cancelled) {
          setOverview(data)
        }

      } catch (err) {

        if (!cancelled) {

          setError(
            err?.message ||
            'Failed to reach the dashboard API'
          )

        }

      } finally {

        if (!cancelled) {
          setLoading(false)
        }

      }

    }


    load()


    return () => {
      cancelled = true
    }

  }, [])


  /* ============================================================
     LOADING
     ============================================================ */

  if (loading) {

    return (
      <PageContainer>
        <LoadingState text="Loading dashboard…" />
      </PageContainer>
    )

  }


  /* ============================================================
     ERROR
     ============================================================ */

  if (error) {

    return (
      <PageContainer>

        <ErrorState
          title="Could not load dashboard statistics"
          message={error}
          onRetry={loadDashboard}
        />

      </PageContainer>
    )

  }


  /* ============================================================
     RESPONSE VALIDATION
     ============================================================ */

  const stats =
    overview?.stats


  if (!stats) {

    return (
      <PageContainer>

        <ErrorState
          title="Dashboard data unavailable"
          message="The backend did not return dashboard statistics."
          onRetry={loadDashboard}
        />

      </PageContainer>
    )

  }


  /* ============================================================
     CORE STATISTICS
     ============================================================ */

  const totalProjects =
    toNumber(
      stats.total_projects
    )


  const totalSanctioned =
    toNumber(
      stats.total_sanctioned_amount
    )


  const totalExpenditure =
    toNumber(
      stats.total_expenditure
    )


  const avgFinancialProgress =
    toNumber(
      stats.average_financial_progress
    )


  const avgPhysicalProgress =
    toNumber(
      stats.average_physical_progress
    )


  const activeProjects =
    toNumber(
      stats.active_projects
    )


  const completedProjects =
    toNumber(
      stats.completed_projects
    )


  /* ============================================================
     ML-4 — DELAYED PROJECTS

     NULL means unavailable.

     NEVER convert null into zero.
     ============================================================ */

  const delayedProjects =
    stats.delayed_projects === null ||
    stats.delayed_projects === undefined
      ? null
      : toNumber(
          stats.delayed_projects
        )


  const delayedProjectsAvailable =
    stats.delayed_projects_available === true


  const delayedProjectsReason =
    stats.delayed_projects_reason ||
    'Expected completion data unavailable'


  /* ============================================================
     FINANCIAL UTILIZATION
     ============================================================ */

  const utilizationPct =
    totalSanctioned !== null &&
    totalSanctioned > 0 &&
    totalExpenditure !== null
      ? Math.round(
          (
            totalExpenditure /
            totalSanctioned
          ) * 100
        )
      : null


  /* ============================================================
     RISK COUNTS
     ============================================================ */

  const riskCounts =
    stats.risk_level_counts || {}


  const hasRiskCounts =
    Object.keys(
      riskCounts
    ).length > 0


  const high =
    toNumber(
      riskCounts.HIGH
    )


  const medium =
    toNumber(
      riskCounts.MEDIUM
    )


  const critical =
    toNumber(
      riskCounts.CRITICAL
    )


  const highPlusCritical =
    (high || 0) +
    (critical || 0)


  const reviewQueue =
    hasRiskCounts
      ? (high || 0) +
        (medium || 0) +
        (critical || 0)
      : null


  /* ============================================================
     KPI CARDS
     ============================================================ */

  const kpiItems = [

    {
      key: 'critical',
      label: 'Critical',
      value: critical,
      format: 'number',
      hint: 'Stored critical signals',
      icon: AlertTriangle,
      tone: 'red',
    },

    {
      key: 'high',
      label: 'High',
      value: high,
      format: 'number',
      hint: 'Stored high-risk signals',
      icon: ShieldAlert,
      tone: 'amber',
    },

    {
      key: 'medium',
      label: 'Medium',
      value: medium,
      format: 'number',
      hint: 'Stored medium-risk signals',
      icon: Info,
      tone: 'navy',
    },

    {
      key: 'reviewQueue',
      label: 'Review Queue',
      value: reviewQueue,
      format: 'number',
      hint: 'Medium + High + Critical',
      icon: CheckCircle2,
      tone: 'blue',
    },

  ]


  /* ============================================================
     RENDER
     ============================================================ */

  return (

    <PageContainer>

      {/* ========================================================
          PAGE HEADER
      ======================================================== */}

      <div className="mb-5">

        <h1 className="text-[19px] font-semibold text-ink">
          National AI Command Center
        </h1>

        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
          Monitor project health, anomalies and review
          priorities across MPLADS.
        </p>

      </div>


      {/* ========================================================
          RISK KPI GRID
      ======================================================== */}

      <div className="mb-4">

        <DashboardKpiGrid
          items={kpiItems}
        />

      </div>


      {/* ========================================================
          FINANCIAL + RISK OVERVIEW
      ======================================================== */}

      <div className="grid lg:grid-cols-3 gap-4 mb-4">

        <div className="lg:col-span-2">

          <DashboardFinancialOverview
            totalSanctioned={
              totalSanctioned
            }

            totalExpenditure={
              totalExpenditure
            }

            utilizationPct={
              utilizationPct
            }

            avgFinancialProgress={
              avgFinancialProgress
            }
          />

        </div>


        <DashboardRiskOverview
          riskCounts={
            riskCounts
          }

          hasRiskCounts={
            hasRiskCounts
          }

          highPlusCritical={
            highPlusCritical
          }
        />

      </div>


      {/* ========================================================
          PORTFOLIO STATUS + COMPOSITION
      ======================================================== */}

      <div className="mb-4">

        <DashboardPortfolioInsights
          totalProjects={
            totalProjects
          }

          activeProjects={
            activeProjects
          }

          completedProjects={
            completedProjects
          }

          delayedProjects={
            delayedProjects
          }

          delayedProjectsAvailable={
            delayedProjectsAvailable
          }

          delayedProjectsReason={
            delayedProjectsReason
          }

          avgPhysicalProgress={
            avgPhysicalProgress
          }

          byState={
            stats.by_state
          }

          byWorkType={
            stats.by_work_type
          }

        />

      </div>


      {/* ========================================================
          STATE-WISE RISK OVERVIEW

          Available only when authenticated Ministry data
          is returned.
      ======================================================== */}

      <div className="mb-4">

        <StateRiskOverview
          rows={
            overview.by_state_risk
          }

          authenticatedScope={
            overview.scope_available === true
          }

        />

      </div>


      {/* ========================================================
          PRIORITIZED REVIEW
      ======================================================== */}

      <div className="card p-4 mb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">

        <div>

          <div className="font-semibold text-[13.5px] text-ink">
            Prioritized Review
          </div>

          <p className="text-[12.5px] text-muted mt-1 max-w-2xl">

            {hasRiskCounts ? (

              <>
                There are{' '}

                <b className="text-ink">
                  {highPlusCritical.toLocaleString()}
                </b>{' '}

                High or Critical risk projects across
                the portfolio. Use the Risk filter on the
                Projects page to review them individually
                with full detail and evidence.
              </>

            ) : (

              'Risk-level counts are not available from the current backend data. Open Projects to review individual project risk detail.'

            )}

          </p>

        </div>


        <Link
          to="/projects"
          className="btn-primary shrink-0"
        >
          Review projects
        </Link>

      </div>


      {/* ========================================================
          PRIORITY REVIEW QUEUE

          Only rendered when authenticated backend provides
          priority projects.
      ======================================================== */}

      {overview.priority_projects?.length > 0 && (

        <div className="card overflow-hidden mb-4">

          <div className="px-4 pt-4 pb-3">

            <h3 className="text-[13.5px] font-semibold text-ink">
              Priority Review Queue
            </h3>

            <p className="text-xs text-muted mt-0.5">
              Real projects with stored medium, high,
              or critical advisory signals
            </p>

          </div>


          <div className="overflow-x-auto">

            <table className="data-table">

              <thead>

                <tr>

                  {[
                    'Work ID',
                    'State',
                    'Risk Score',
                    'Risk',
                    'Progress',
                    '',
                  ].map(label => (

                    <th key={label}>
                      {label}
                    </th>

                  ))}

                </tr>

              </thead>


              <tbody>

                {overview.priority_projects.map(
                  project => {

                    const projectId =
                      project.project_id ??
                      project.id ??
                      '—'


                    const state =
                      project.state ??
                      '—'


                    const riskScoreRaw =
                      project.risk_score ??
                      project.riskScore


                    const riskScore =
                      riskScoreRaw === null ||
                      riskScoreRaw === undefined
                        ? null
                        : toNumber(
                            riskScoreRaw
                          )


                    const risk =
                      project.risk_level ??
                      project.riskLevel ??
                      project.risk ??
                      '—'


                    const progressRaw =
                      project.financial_progress ??
                      project.financialProgress


                    const progress =
                      progressRaw === null ||
                      progressRaw === undefined
                        ? null
                        : toNumber(
                            progressRaw
                          )


                    return (

                      <tr
                        key={projectId}
                      >

                        <td className="font-mono font-semibold text-navy whitespace-nowrap">
                          {projectId}
                        </td>


                        <td>
                          {state}
                        </td>


                        <td>
                          {riskScore !== null
                            ? riskScore
                            : '—'}
                        </td>


                        <td>

                          <RiskBadge
                            risk={risk}
                          />

                        </td>


                        <td>
                          {progress !== null
                            ? `${progress}%`
                            : '—'}
                        </td>


                        <td>

                          <Link
                            to={`/projects/${encodeURIComponent(
                              projectId
                            )}`}
                            className="text-xs font-semibold text-navy"
                          >
                            Review →
                          </Link>

                        </td>

                      </tr>

                    )

                  }
                )}

              </tbody>

            </table>

          </div>

        </div>

      )}


      {/* ========================================================
          QUICK ACCESS
      ======================================================== */}

      <div className="mb-4">

        <DashboardQuickAccess />

      </div>


      {/* ========================================================
          AI DISCLAIMER
      ======================================================== */}

      <div className="text-xs text-muted flex items-center gap-1.5">

        <CheckCircle2 size={13} />

        AI outputs shown on this dashboard are advisory
        risk-prioritization signals for authorized human
        review. An anomaly does not, by itself, establish
        fraud or wrongdoing.

      </div>

    </PageContainer>
  )
}


/* ============================================================
   STATE-WISE RISK OVERVIEW
   ============================================================ */

function StateRiskOverview({
  rows,
  authenticatedScope = false,
}) {

  /*
   * No authenticated Ministry data.
   *
   * Do NOT manufacture state risk levels from project
   * counts. That would be an invented AI classification.
   */

  if (!authenticatedScope) {

    return (

      <div className="card p-4">

        <div className="font-semibold text-[13.5px] text-ink">
          State-wise Risk Overview
        </div>

        <p className="text-xs text-muted mt-0.5 mb-3">
          States with the highest stored review indicators
        </p>

        <EmptyState
          text="State risk data is available only from the authenticated Ministry dashboard."
        />

      </div>

    )
  }


  const normalizedRows =
    (rows || [])
      .map(row => {

        const medium =
          toNumber(row.medium) || 0

        const high =
          toNumber(row.high) || 0

        const critical =
          toNumber(row.critical) || 0

        return {

          ...row,

          medium,
          high,
          critical,

          review:
            medium +
            high +
            critical,

        }

      })


  const ranked =
    normalizedRows
      .filter(
        row =>
          row.state &&
          row.review > 0
      )
      .sort(
        (a, b) =>
          b.review -
          a.review
      )
      .slice(0, 8)


  const max =
    ranked[0]?.review || 1


  return (

    <div className="card p-4">

      <div className="font-semibold text-[13.5px] text-ink">
        State-wise Risk Overview
      </div>

      <p className="text-xs text-muted mt-0.5 mb-3">
        States with the highest stored review indicators
      </p>


      {ranked.length ? (

        <div className="space-y-2.5">

          {ranked.map(row => (

            <div
              key={row.state}
            >

              <div className="flex items-baseline justify-between text-xs mb-1">

                <span className="text-ink truncate pr-2">
                  {row.state}
                </span>

                <span className="font-semibold text-ink">
                  {row.review.toLocaleString()}
                </span>

              </div>


              <div className="h-1.5 rounded-full bg-panel overflow-hidden">

                <div
                  className="h-full rounded-full bg-warn"
                  style={{
                    width: `${Math.max(
                      4,
                      Math.round(
                        (row.review / max) * 100
                      )
                    )}%`,
                  }}
                />

              </div>

            </div>

          ))}

        </div>

      ) : (

        <EmptyState
          text="State risk data not available."
        />

      )}

    </div>

  )
}