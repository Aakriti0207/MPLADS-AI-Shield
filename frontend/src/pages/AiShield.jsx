import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis
} from 'recharts'
import { useAuth } from '../context/AuthContext'
import { ROLE, normalizeRole, ROLE_VIEW_LABEL } from '../lib/roles'
import {
  fetchProjects,
  fetchDemoProjects,
  fetchProjectRisk,
  fetchDemoProjectRisk
} from '../features/projects/api'
import { fetchRoleDashboard } from '../features/dashboard/api'
import { toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { FALLBACK_COMPONENT_LABELS, buildRiskModel } from '../lib/riskModel'
import { Disclaimer, RiskBadge, Stat } from '../components/UI'
import ChartCard from '../components/ui/ChartCard'
import EmptyState from '../components/ui/EmptyState'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import PageContainer from '../components/layout/PageContainer'
import Methodology from '../components/ai/Methodology'

// Bounded sample used ONLY for the peer-relative scatter on the national
// view (no dedicated aggregate endpoint exists for it). Every point is a
// real project; the subtitle says outright that it is a sample.
const SAMPLE_LIMIT = 300

// How many of the highest-priority projects have their Risk Fusion
// breakdown fetched to build the anomaly-category graph and fill the
// "Top Reason" column. One request each, all real /risk responses.
const QUEUE_RISK_LIMIT = 12

const shortLabel = label =>
  String(label || '')
    .replace(/ \(Isolation Forest\)/, '')
    .replace(/ Risk$/, '')

const componentLabel = name =>
  shortLabel(FALLBACK_COMPONENT_LABELS[name] || String(name || '').replace(/_/g, ' '))

const titleCase = s =>
  s ? String(s).charAt(0).toUpperCase() + String(s).slice(1).toLowerCase() : null

const tooltipStyle = {
  fontSize: 12,
  borderRadius: 6,
  border: `1px solid ${CHART_COLORS.line}`
}

/** Horizontal bar chart of "how many projects triggered each component". */
function AnomalyBars({ data }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} layout="vertical" margin={{ left: 24, right: 24 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={CHART_COLORS.line} />
        <XAxis
          type="number"
          allowDecimals={false}
          tick={{ fontSize: 11, fill: CHART_COLORS.muted }}
          axisLine={{ stroke: CHART_COLORS.line }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={130}
          tick={{ fontSize: 11.5, fill: CHART_COLORS.ink }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={v => [`${v} project(s)`, 'Triggered']} />
        <Bar dataKey="value" fill={CHART_COLORS.blue} radius={[0, 4, 4, 0]} barSize={16}>
          <LabelList dataKey="value" position="right" style={{ fontSize: 11, fill: CHART_COLORS.ink, fontWeight: 600 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Sanction (Rs Cr) vs expenditure ratio, High/Critical highlighted. */
function PeerScatter({ data }) {
  const isHigh = d => d.risk === 'High' || d.risk === 'Critical'
  return (
    <ResponsiveContainer>
      <ScatterChart margin={{ left: -10, right: 12, top: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.line} />
        <XAxis
          type="number"
          dataKey="x"
          name="Sanction (₹ Cr)"
          tick={{ fontSize: 10.5, fill: CHART_COLORS.muted }}
          axisLine={{ stroke: CHART_COLORS.line }}
          tickLine={false}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="Expenditure ratio"
          tick={{ fontSize: 10.5, fill: CHART_COLORS.muted }}
          axisLine={false}
          tickLine={false}
        />
        <ZAxis range={[24, 24]} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={tooltipStyle} />
        <Scatter data={data.filter(d => !isHigh(d))} fill="#9fb6cc" fillOpacity={0.6} />
        <Scatter data={data.filter(isHigh)} fill={CHART_COLORS.red} fillOpacity={0.85} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

export default function AiShield() {
  const { user, isDemo } = useAuth()
  const role = normalizeRole(user)

  if (role !== ROLE.MINISTRY) {
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
 * aggregation as the Dashboard page (fetchRoleDashboard).
 *
 * Anomaly Categories is built from real /risk responses for the
 * highest-priority projects (which Risk Fusion components triggered), and
 * the same responses fill the queue's "Top Reason" column. The
 * peer-relative scatter uses a disclosed, bounded real-project sample.
 */
function MinistryAiShield({ isDemo }) {
  const [overview, setOverview] = useState(null)
  const [sample, setSample] = useState([])
  const [queueModels, setQueueModels] = useState({})
  const [queueLoading, setQueueLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError(null)

    const overviewRequest = fetchRoleDashboard()

    const sampleRequest = isDemo
      ? fetchDemoProjects({ skip: 0, limit: SAMPLE_LIMIT })
      : fetchProjects({ skip: 0, limit: SAMPLE_LIMIT })

    Promise.all([overviewRequest, sampleRequest.catch(() => [])])
      .then(([data, projects]) => {
        if (!cancelled) {
          setOverview(data)
          setSample(projects)
        }
      })
      .catch(err => {
        if (!cancelled) setError(err.message || 'Failed to reach the API')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isDemo])

  // Fetch the Risk Fusion breakdown for the top of the priority queue.
  // Non-blocking: the page renders first, the graph and reasons fill in.
  useEffect(() => {
    const queue = (overview?.priority_projects || []).slice(0, QUEUE_RISK_LIMIT)

    if (!queue.length) {
      setQueueModels({})
      return undefined
    }

    let cancelled = false
    const fetchRisk = isDemo ? fetchDemoProjectRisk : fetchProjectRisk

    setQueueLoading(true)

    Promise.allSettled(
      queue.map(p => fetchRisk(p.id).then(risk => [p.id, buildRiskModel(risk)]))
    )
      .then(results => {
        if (cancelled) return
        const map = {}
        results.forEach(r => {
          if (r.status === 'fulfilled' && r.value[1]) map[r.value[0]] = r.value[1]
        })
        setQueueModels(map)
      })
      .finally(() => {
        if (!cancelled) setQueueLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [overview, isDemo])

  const modelCount = Object.keys(queueModels).length

  const categoryData = useMemo(() => {
    const counts = {}
    Object.values(queueModels).forEach(model => {
      model.triggered.forEach(c => {
        counts[c.name] = {
          name: componentLabel(c.name),
          value: (counts[c.name]?.value || 0) + 1
        }
      })
    })
    return Object.values(counts).sort((a, b) => b.value - a.value)
  }, [queueModels])

  const scatterData = useMemo(
    () =>
      sample
        .filter(r => r.sanctioned && r.expenditure !== null)
        .map(r => ({
          x: Number((r.sanctioned / 10000000).toFixed(2)),
          y: Math.min(2, Number((r.expenditure / r.sanctioned).toFixed(2))),
          risk: r.risk,
          id: r.id
        })),
    [sample]
  )

  if (loading) {
    return <LoadingState text="Loading AI Shield intelligence…" />
  }

  if (error) {
    return <ErrorState title="Could not load AI Shield data" message={error} />
  }

  const stats = overview?.stats
  const riskCounts = stats?.risk_level_counts || {}
  const hasRiskCounts = Object.keys(riskCounts).length > 0
  const highPlusCritical = (riskCounts.HIGH || 0) + (riskCounts.CRITICAL || 0)
  const totalAnalyzed = toNumber(stats?.total_projects)
  const priorityQueue = overview?.priority_projects || []

  const topReason = p =>
    queueModels[p.id]?.triggered[0]?.reasons?.[0] || p.raw?.risk_reason_1 || ''

  return (
    <>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">
          AI Shield Command Center
        </h1>
        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
          National AI risk & monitoring overview, built from real per-project
          risk data.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Stat
          label="Total Analyzed"
          value={totalAnalyzed !== null ? totalAnalyzed.toLocaleString() : 'Not available'}
          tone="navy"
        />
        <Stat
          label="Low Risk"
          value={hasRiskCounts ? (riskCounts.LOW || 0).toLocaleString() : 'Not available'}
          tone="green"
        />
        <Stat
          label="Medium Risk"
          value={hasRiskCounts ? (riskCounts.MEDIUM || 0).toLocaleString() : 'Not available'}
          tone="amber"
        />
        <Stat
          label="High + Critical"
          value={hasRiskCounts ? highPlusCritical.toLocaleString() : 'Not available'}
          tone="red"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <ChartCard
          title="Anomaly Categories"
          subtitle={
            modelCount
              ? `Risk components triggered across the ${modelCount} highest-priority projects`
              : 'Risk components triggered across the highest-priority projects'
          }
          height={260}
        >
          {categoryData.length ? (
            <AnomalyBars data={categoryData} />
          ) : queueLoading ? (
            <div className="h-full flex items-center justify-center text-sm text-muted">
              Loading anomaly signals…
            </div>
          ) : (
            <EmptyState text="No triggered risk components were returned for the highest-priority projects." />
          )}
        </ChartCard>

        <ChartCard
          title="Peer-Relative Analysis"
          subtitle={`Sanction amount (₹ Cr) vs. expenditure ratio — sample of ${sample.length.toLocaleString()} real projects`}
          height={260}
        >
          {scatterData.length ? (
            <PeerScatter data={scatterData} />
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
            Real projects with stored medium, high, or critical advisory signals
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                {['Work ID', 'State', 'Risk Score', 'Risk', 'Progress', 'Top Reason', ''].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {priorityQueue.map(p => (
                <tr key={p.id}>
                  <td className="font-mono font-semibold text-navy whitespace-nowrap">{p.id}</td>
                  <td className="whitespace-nowrap">{p.state || '—'}</td>
                  <td className="font-semibold text-ink">
                    {p.riskScore !== null && p.riskScore !== undefined ? p.riskScore : '—'}
                  </td>
                  <td>
                    <RiskBadge risk={p.risk} />
                  </td>
                  <td>{p.financialProgress !== null ? `${p.financialProgress}%` : '—'}</td>
                  <td
                    className="text-xs text-muted max-w-[260px] truncate"
                    title={topReason(p)}
                  >
                    {topReason(p) || (queueLoading ? 'Loading…' : '—')}
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
              No High, Medium or Critical risk projects were returned by the
              backend for the current scope.
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
 * State / District / MP: scoped view. Reads the backend's ScopedProjectRow
 * contract (snake_case: project_id, sanctioned_amount, risk_score,
 * risk_level, triggered_component, top_risk_signal) straight from
 * scoped_projects -- never re-derives "your data" from a national page.
 * When the backend hasn't authorized a scope for this account yet, every
 * section shows an explicit unavailable state rather than a guess.
 */
function ScopedAiShield({ role, isDemo }) {
  const [rows, setRows] = useState([])
  const [attention, setAttention] = useState([])
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
        setRows(data.scope_available ? data.scoped_projects || [] : [])
        setAttention(data.scope_available ? data.attention_projects || [] : [])
      })
      .catch(err => {
        if (!cancelled) setError(err.message || 'Failed to reach the API')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isDemo])

  const categoryData = useMemo(() => {
    const counts = {}
    rows.forEach(r => {
      if (!r.triggered_component) return
      counts[r.triggered_component] = {
        name: componentLabel(r.triggered_component),
        value: (counts[r.triggered_component]?.value || 0) + 1
      }
    })
    return Object.values(counts).sort((a, b) => b.value - a.value)
  }, [rows])

  const scatterData = useMemo(
    () =>
      rows
        .filter(r => toNumber(r.sanctioned_amount) && toNumber(r.expenditure) !== null)
        .map(r => ({
          x: Number((toNumber(r.sanctioned_amount) / 10000000).toFixed(2)),
          y: Math.min(2, Number((toNumber(r.expenditure) / toNumber(r.sanctioned_amount)).toFixed(2))),
          risk: titleCase(r.risk_level),
          id: r.project_id
        })),
    [rows]
  )

  if (loading) {
    return <LoadingState text="Loading AI Shield intelligence…" />
  }

  if (error) {
    return <ErrorState title="Could not load AI Shield data" message={error} />
  }

  const highRisk = rows
    .filter(r => ['HIGH', 'CRITICAL'].includes(String(r.risk_level || '').toUpperCase()))
    .sort((a, b) => (toNumber(b.risk_score) || 0) - (toNumber(a.risk_score) || 0))

  const scopedQueue = highRisk.length ? highRisk : attention

  const scopeWord =
    role === ROLE.MP ? 'Constituency' : role === ROLE.STATE_NODAL ? 'State' : 'District'

  return (
    <>
      <div className="mb-5">
        <h1 className="text-[19px] font-semibold text-ink">
          AI Shield — {ROLE_VIEW_LABEL[role] || 'Scoped view'}
        </h1>

        <p className="text-[13px] text-muted mt-0.5 max-w-2xl">
          {scopeAvailable
            ? `Scoped to your account's authorized ${scopeWord.toLowerCase()} records, as returned by the backend.`
            : `${scopeWord}-scoped AI intelligence is not available for this account.`}
        </p>
      </div>

      {!scopeAvailable ? (
        <div className="card p-10 text-center text-sm text-muted mb-4">
          {scopeWord}-scoped AI intelligence is not available for this account.
          This view stays intact so it can be connected to a real scope once
          the backend provides one.
        </div>
      ) : (
        <>
          <div className="grid lg:grid-cols-2 gap-4 mb-4">
            <ChartCard
              title="Anomaly Categories"
              subtitle="Main triggered risk component per project, within your scope"
              height={240}
            >
              {categoryData.length ? (
                <AnomalyBars data={categoryData} />
              ) : (
                <EmptyState text="Category-level anomaly data is not available for your scope." />
              )}
            </ChartCard>

            <ChartCard
              title="Peer-Relative Analysis"
              subtitle="Sanction amount (₹ Cr) vs. expenditure ratio — projects in your scope"
              height={240}
            >
              {scatterData.length ? (
                <PeerScatter data={scatterData} />
              ) : (
                <EmptyState text="Peer-relative data is not available for your scope." />
              )}
            </ChartCard>
          </div>

          <div className="card overflow-hidden mb-4">
            <div className="px-4 pt-4 pb-1">
              <h3 className="text-[13.5px] font-semibold text-ink">
                Priority Review Queue
              </h3>
              <p className="text-xs text-muted mt-0.5">
                Highest-risk projects in your authorized scope
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {['Work ID', 'Location', 'Risk Score', 'Risk', 'Top Reason', ''].map(h => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {scopedQueue.slice(0, 12).map(p => (
                    <tr key={p.project_id}>
                      <td className="font-mono font-semibold text-navy whitespace-nowrap">
                        {p.project_id}
                      </td>
                      <td className="whitespace-nowrap">
                        {p.district || '—'}, {p.state || '—'}
                      </td>
                      <td className="font-semibold text-ink">
                        {p.risk_score !== null && p.risk_score !== undefined ? p.risk_score : '—'}
                      </td>
                      <td>
                        <RiskBadge risk={titleCase(p.risk_level)} />
                      </td>
                      <td
                        className="text-xs text-muted max-w-[220px] truncate"
                        title={p.top_risk_signal || ''}
                      >
                        {p.top_risk_signal || (p.triggered_component ? componentLabel(p.triggered_component) : '—')}
                      </td>
                      <td>
                        <Link
                          to={`/projects/${encodeURIComponent(p.project_id)}`}
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
                  No High or Critical risk projects in your current scope.
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