import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis
} from 'recharts'
import { useAuth } from '../context/AuthContext'
import { normalizeRole, ROLE_VIEW_LABEL } from '../lib/roles'
import {
  fetchProjects,
  fetchDemoProjects
} from '../features/projects/api'
import { fetchRoleDashboard } from '../features/dashboard/api'
import { toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { Disclaimer, RiskBadge, Stat } from '../components/UI'
import ChartCard from '../components/ui/ChartCard'
import EmptyState from '../components/ui/EmptyState'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import PageContainer from '../components/layout/PageContainer'
import Methodology from '../components/ai/Methodology'

// Bounded sample used ONLY for the two ministry-level charts below
// (category breakdown, peer-relative scatter), for which no dedicated
// backend aggregate endpoint exists yet -- same disclosed-sample pattern
// ScopedDashboard.jsx already uses elsewhere in this app. Every value
// plotted is real; the subtitle says outright that it's a sample, not a
// full-portfolio aggregate, rather than presenting it as one.
const SAMPLE_LIMIT = 300

// Real per-project risk sub-scores (see lib/normalizers.js -- financial_
// risk_score, payment_risk_score, execution_risk_score, peer_anomaly_
// score, duplicate_risk_score all come straight from the /risk endpoint)
// used here to build a genuine "anomaly categories" breakdown, instead
// of a fabricated one -- each bucket below is a real count of projects
// whose real sub-score for that category exceeds a review threshold.
const CATEGORY_FIELDS = [
  ['Financial', 'financial_risk_score'],
  ['Payment', 'payment_risk_score'],
  ['Execution', 'execution_risk_score'],
  ['Peer anomaly', 'peer_anomaly_score'],
  ['Duplicate similarity', 'duplicate_risk_score'],
]

const REVIEW_THRESHOLD = 50

export default function AiShield() {
  const { user, isDemo } = useAuth()
  const role = normalizeRole(user?.role)

  if (role !== 'ministry') {
    return (
      <PageContainer>
        <ScopedAiShield role={role} isDemo={isDemo} />
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <MinistryAiShield isDemo={isDemo} />
    </PageContainer>
  )
}

/**
 * Ministry / Admin: national view. Real risk_level_counts and
 * priority_projects come from the same authoritative dashboard
 * aggregation as the Dashboard page (fetchRoleDashboard) -- this screen
 * does not run its own competing aggregation for those numbers. Only
 * the category-breakdown and scatter charts fall back to a disclosed,
 * bounded real-project sample, because no dedicated aggregate endpoint
 * for per-category anomaly counts exists yet.
 */
function MinistryAiShield({ isDemo }) {
  const [overview, setOverview] = useState(null)
  const [sample, setSample] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError(null)

    // fetchRoleDashboard() automatically selects:
    //   Ministry -> /dashboard/role-overview
    //   Demo     -> /demo/dashboard/role-overview
    //
    // Both endpoints expose the same dashboard/Risk Fusion intelligence.
    const overviewRequest = fetchRoleDashboard()

    // Use the matching project universe for each mode:
    //   Ministry -> authenticated /projects
    //   Demo     -> anonymous /demo/projects
    const sampleRequest = isDemo
      ? fetchDemoProjects({ skip: 0, limit: SAMPLE_LIMIT })
      : fetchProjects({ skip: 0, limit: SAMPLE_LIMIT })

    Promise.all([
      overviewRequest,
      sampleRequest.catch(() => [])
    ])
      .then(([data, projects]) => {
        if (!cancelled) {
          setOverview(data)
          setSample(projects)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to reach the API')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isDemo])

  const categoryData = useMemo(
    () =>
      CATEGORY_FIELDS.map(([label, key]) => ({
        name: label,
        value: sample.filter(
          r =>
            toNumber(r.raw?.[key]) !== null &&
            toNumber(r.raw[key]) >= REVIEW_THRESHOLD
        ).length,
      })),
    [sample]
  )

  const scatterData = useMemo(
    () =>
      sample
        .filter(r => r.sanctioned && r.expenditure !== null)
        .map(r => ({
          x: Number((r.sanctioned / 10000000).toFixed(2)),
          y: Math.min(
            2,
            Number((r.expenditure / r.sanctioned).toFixed(2))
          ),
          risk: r.risk,
          id: r.id
        })),
    [sample]
  )

  if (loading) {
    return <LoadingState text="Loading AI Shield intelligence…" />
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load AI Shield data"
        message={error}
      />
    )
  }

  const stats = overview?.stats
  const riskCounts = stats?.risk_level_counts || {}
  const hasRiskCounts = Object.keys(riskCounts).length > 0
  const highPlusCritical =
    (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0)
  const totalAnalyzed = toNumber(stats?.total_projects)
  const priorityQueue = overview?.priority_projects || []

  return (
    <>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">
          AI Shield Command Center
        </h1>
        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
          National AI risk & monitoring overview, built from real
          per-project risk data.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Stat
          label="Total Analyzed"
          value={
            totalAnalyzed !== null
              ? totalAnalyzed.toLocaleString()
              : 'Not available'
          }
          tone="navy"
        />

        <Stat
          label="Low Risk"
          value={
            hasRiskCounts
              ? (riskCounts.LOW || 0).toLocaleString()
              : 'Not available'
          }
          tone="green"
        />

        <Stat
          label="Medium Risk"
          value={
            hasRiskCounts
              ? (riskCounts.MEDIUM || 0).toLocaleString()
              : 'Not available'
          }
          tone="amber"
        />

        <Stat
          label="High + Critical"
          value={
            hasRiskCounts
              ? highPlusCritical.toLocaleString()
              : 'Not available'
          }
          tone="red"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <ChartCard
          title="Anomaly Categories"
          subtitle={`Sample of ${sample.length.toLocaleString()} loaded projects with a real sub-score ≥ ${REVIEW_THRESHOLD}, by category`}
          height={260}
        >
          {sample.length ? (
            <ResponsiveContainer>
              <BarChart
                data={categoryData}
                layout="vertical"
                margin={{ left: 24 }}
              >
                <CartesianGrid
                  horizontal={false}
                  strokeDasharray="3 3"
                  stroke={CHART_COLORS.line}
                />

                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{
                    fontSize: 11,
                    fill: CHART_COLORS.muted
                  }}
                  axisLine={{
                    stroke: CHART_COLORS.line
                  }}
                  tickLine={false}
                />

                <YAxis
                  type="category"
                  dataKey="name"
                  width={110}
                  tick={{
                    fontSize: 11.5,
                    fill: CHART_COLORS.ink
                  }}
                  axisLine={false}
                  tickLine={false}
                />

                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 6,
                    border: `1px solid ${CHART_COLORS.line}`
                  }}
                />

                <Bar
                  dataKey="value"
                  fill={CHART_COLORS.blue}
                  radius={[0, 4, 4, 0]}
                  barSize={16}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="Category-level anomaly data is not available for the current dataset." />
          )}
        </ChartCard>

        <ChartCard
          title="Peer-Relative Analysis"
          subtitle="Sanction amount (₹ Cr) vs. expenditure ratio — real project sample"
          height={260}
        >
          {scatterData.length ? (
            <ResponsiveContainer>
              <ScatterChart
                margin={{ left: -10, right: 12, top: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={CHART_COLORS.line}
                />

                <XAxis
                  type="number"
                  dataKey="x"
                  name="Sanction (₹ Cr)"
                  tick={{
                    fontSize: 10.5,
                    fill: CHART_COLORS.muted
                  }}
                  axisLine={{
                    stroke: CHART_COLORS.line
                  }}
                  tickLine={false}
                />

                <YAxis
                  type="number"
                  dataKey="y"
                  name="Expenditure ratio"
                  tick={{
                    fontSize: 10.5,
                    fill: CHART_COLORS.muted
                  }}
                  axisLine={false}
                  tickLine={false}
                />

                <ZAxis range={[24, 24]} />

                <Tooltip
                  cursor={{
                    strokeDasharray: '3 3'
                  }}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 6,
                    border: `1px solid ${CHART_COLORS.line}`
                  }}
                />

                <Scatter
                  data={scatterData.filter(
                    d =>
                      d.risk !== 'High' &&
                      d.risk !== 'Critical'
                  )}
                  fill="#9fb6cc"
                  fillOpacity={0.6}
                />

                <Scatter
                  data={scatterData.filter(
                    d =>
                      d.risk === 'High' ||
                      d.risk === 'Critical'
                  )}
                  fill={CHART_COLORS.red}
                  fillOpacity={0.85}
                />
              </ScatterChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="Peer-relative data is not available for the current dataset." />
          )}
        </ChartCard>
      </div>

      <div className="card overflow-hidden mb-4">
        <div className="px-4 pt-4 pb-1">
          <h3 className="text-[13.5px] font-semibold text-ink">
            Priority Review Queue
          </h3>

          <p className="text-xs text-muted mt-0.5">
            Real projects with stored medium, high, or critical advisory
            signals
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
                  'Top Reason',
                  ''
                ].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {priorityQueue.map(p => (
                <tr key={p.id}>
                  <td className="font-mono font-semibold text-navy whitespace-nowrap">
                    {p.id}
                  </td>

                  <td className="whitespace-nowrap">
                    {p.state || '—'}
                  </td>

                  <td className="font-semibold text-ink">
                    {p.riskScore !== null &&
                    p.riskScore !== undefined
                      ? p.riskScore
                      : '—'}
                  </td>

                  <td>
                    <RiskBadge risk={p.risk} />
                  </td>

                  <td>
                    {p.financialProgress !== null
                      ? `${p.financialProgress}%`
                      : '—'}
                  </td>

                  <td className="text-xs text-muted max-w-[260px] truncate" title={p.raw?.risk_reason_1 || ''}>
                    {p.raw?.risk_reason_1 || '—'}
                  </td>

                  <td>
                    <Link
                      to={`/projects/${encodeURIComponent(p.id)}`}
                      className="text-xs font-semibold text-navy whitespace-nowrap"
                    >
                      View Risk Breakdown →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {priorityQueue.length === 0 && (
            <div className="p-8 text-center text-sm text-muted">
              No High, Medium or Critical risk projects were returned
              by the backend for the current scope.
            </div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <Methodology compact />
      </div>

      <Disclaimer />
    </>
  )
}

/**
 * State / District / MP: scoped view. Uses the SAME real
 * scope_available / scoped_projects contract as ScopedDashboard.jsx --
 * never re-derives "your state's data" by filtering a page of national
 * projects client-side. When the backend hasn't authorized a scope for
 * this account yet, every scoped section shows an explicit unavailable
 * state rather than a guess.
 */
function ScopedAiShield({ role, isDemo }) {
  const [rows, setRows] = useState([])
  const [priorityQueue, setPriorityQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scopeAvailable, setScopeAvailable] = useState(false)

  useEffect(() => {
    if (isDemo) {
      setScopeAvailable(false)
      setLoading(false)
      return undefined
    }

    let cancelled = false

    setLoading(true)
    setError(null)

    fetchRoleDashboard()
      .then(data => {
        if (cancelled) return

        setScopeAvailable(Boolean(data.scope_available))

        setRows(
          data.scope_available
            ? (data.scoped_projects || [])
            : []
        )

        setPriorityQueue(
          data.scope_available
            ? (data.priority_projects || [])
            : []
        )
      })
      .catch(err => {
        if (!cancelled) {
          setError(
            err.message || 'Failed to reach the API'
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isDemo])

  // Unlike the ministry sample (which comes straight from fetchProjects
  // and is run through normalizeProject, so raw sub-scores live under
  // `.raw`), `scoped_projects` here follows the SAME already-flat field
  // convention ScopedDashboard.jsx relies on for r.sanctioned/r.risk/etc.
  // -- so sub-scores are read directly off each row, not under `.raw`.
  const categoryData = useMemo(
    () =>
      CATEGORY_FIELDS.map(([label, key]) => ({
        name: label,
        value: rows.filter(
          r =>
            toNumber(r[key]) !== null &&
            toNumber(r[key]) >= REVIEW_THRESHOLD
        ).length,
      })),
    [rows]
  )

  if (loading) {
    return <LoadingState text="Loading AI Shield intelligence…" />
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load AI Shield data"
        message={error}
      />
    )
  }

  const scopedQueue = priorityQueue.length
    ? priorityQueue
    : rows.filter(
        r =>
          r.risk === 'High' ||
          r.risk === 'Critical'
      )

  return (
    <>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">
          AI Shield — {ROLE_VIEW_LABEL[role]}
        </h1>

        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
          {scopeAvailable
            ? `Scoped to your account's authorized ${
                role === 'mp'
                  ? 'constituency'
                  : role
              } records, as returned by the backend.`
            : `${
                role === 'mp'
                  ? 'Constituency'
                  : role === 'state'
                    ? 'State'
                    : 'District'
              }-scoped AI intelligence is not available for this account.`}
        </p>
      </div>

      {!scopeAvailable ? (
        <div className="card p-10 text-center text-sm text-muted mb-4">
          {role === 'mp'
            ? 'Constituency'
            : role === 'state'
              ? 'State'
              : 'District'}-scoped AI intelligence is not available for this
          account. This view stays intact so it can be connected to a real
          scope once the backend provides one.
        </div>
      ) : (
        <>
          <div className="card mb-4">
            <div className="px-4 pt-4 pb-1">
              <h3 className="text-[13.5px] font-semibold text-ink">
                Anomaly Categories
              </h3>

              <p className="text-xs text-muted mt-0.5">
                Real sub-score ≥ {REVIEW_THRESHOLD}, within your scope
              </p>
            </div>

            <div className="p-4" style={{ height: 220 }}>
              {rows.length ? (
                <ResponsiveContainer>
                  <BarChart
                    data={categoryData}
                    layout="vertical"
                    margin={{ left: 24 }}
                  >
                    <CartesianGrid
                      horizontal={false}
                      strokeDasharray="3 3"
                      stroke={CHART_COLORS.line}
                    />

                    <XAxis
                      type="number"
                      allowDecimals={false}
                      tick={{
                        fontSize: 11,
                        fill: CHART_COLORS.muted
                      }}
                      axisLine={{
                        stroke: CHART_COLORS.line
                      }}
                      tickLine={false}
                    />

                    <YAxis
                      type="category"
                      dataKey="name"
                      width={110}
                      tick={{
                        fontSize: 11.5,
                        fill: CHART_COLORS.ink
                      }}
                      axisLine={false}
                      tickLine={false}
                    />

                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 6,
                        border: `1px solid ${CHART_COLORS.line}`
                      }}
                    />

                    <Bar
                      dataKey="value"
                      fill={CHART_COLORS.blue}
                      radius={[0, 4, 4, 0]}
                      barSize={16}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState text="Category-level anomaly data is not available for your scope." />
              )}
            </div>
          </div>

          <div className="card overflow-hidden mb-4">
            <div className="px-4 pt-4 pb-1">
              <h3 className="text-[13.5px] font-semibold text-ink">
                Priority Review Queue
              </h3>

              <p className="text-xs text-muted mt-0.5">
                Real High/Critical risk projects, in your authorized
                scope
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {[
                      'Work ID',
                      'Location',
                      'Risk Score',
                      'Risk',
                      'Top Reason',
                      ''
                    ].map(h => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {scopedQueue.slice(0, 12).map(p => (
                    <tr key={p.id}>
                      <td className="font-mono font-semibold text-navy whitespace-nowrap">
                        {p.id}
                      </td>

                      <td className="whitespace-nowrap">
                        {p.district || '—'}, {p.state || '—'}
                      </td>

                      <td className="font-semibold text-ink">
                        {p.riskScore !== null &&
                        p.riskScore !== undefined
                          ? p.riskScore
                          : '—'}
                      </td>

                      <td>
                        <RiskBadge risk={p.risk} />
                      </td>

                      <td className="text-xs text-muted max-w-[220px] truncate" title={p.raw?.risk_reason_1 || ''}>
                        {p.raw?.risk_reason_1 || '—'}
                      </td>

                      <td>
                        <Link
                          to={`/projects/${encodeURIComponent(p.id)}`}
                          className="text-xs font-semibold text-navy whitespace-nowrap"
                        >
                          View Risk Breakdown →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {scopedQueue.length === 0 && (
                <div className="p-8 text-center text-sm text-muted">
                  No High or Critical risk projects in your current
                  scope.
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <div className="mb-4">
        <Methodology compact />
      </div>

      <Disclaimer />
    </>
  )
}