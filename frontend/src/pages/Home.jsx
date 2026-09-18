import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Eye, Info } from 'lucide-react'
import { fetchPublicOverview } from '../features/dashboard/api'
import { fetchPublicDistricts, fetchPublicInsights } from '../features/public/api'
import { formatCurrency, formatNumber, toNumber } from '../lib/formatters'
import { CHART_COLORS } from '../lib/theme'
import { Disclaimer } from '../components/UI'
import EmptyState from '../components/ui/EmptyState'
import IndiaStateGrid from '../components/home/IndiaStateGrid'
import PublicTrends from '../components/home/PublicTrends'
import StateDistrictInsights from '../components/home/StateDistrictInsights'
import PublicNavbar from '../components/layout/PublicNavbar'

/**
 * Public Overview (Phase 5 overhaul).
 *
 * Anonymous-only surface. Everything rendered here comes from the
 * `/public/*` routes via the dedicated public data contract
 * (features/public/api.js + lib/publicNormalizers.js):
 *
 *   GET /public/insights            KPIs, real trends, state + district
 *                                   insights, categories, status
 *   GET /public/insights/districts  State -> District drilldown
 *   GET /public/overview            recently monitored public projects
 *
 * Deliberately absent (Phase 5 requirement): risk score, risk level,
 * Risk Fusion output, financial/payment/timeline anomaly scores,
 * duplicate score, isolation-forest score, AI reasoning / why-risky
 * text, alerts, investigation or review state, and internal
 * administrative notes. The former "Requiring Review" KPI -- which was
 * derived from `risk_level_counts` on `/public/overview` -- has been
 * removed along with the backend field that fed it.
 *
 * Where the source dataset genuinely lacks data (e.g. projects with no
 * expenditure date), the page says so via the coverage notes rather than
 * showing an invented figure.
 */
export default function Home() {
  const navigate = useNavigate()

  const [insights, setInsights] = useState(null)
  const [insightsError, setInsightsError] = useState(null)

  const [overview, setOverview] = useState(null)
  const [overviewError, setOverviewError] = useState(null)

  const [selectedState, setSelectedState] = useState(null)
  const [districts, setDistricts] = useState([])
  const [districtsLoading, setDistrictsLoading] = useState(false)
  const [districtsError, setDistrictsError] = useState(null)

  useEffect(() => {
    let cancelled = false

    fetchPublicInsights()
      .then(data => { if (!cancelled) setInsights(data) })
      .catch(err => {
        if (!cancelled) setInsightsError(err.message || 'Failed to reach the API')
      })

    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false

    fetchPublicOverview()
      .then(data => { if (!cancelled) setOverview(data) })
      .catch(err => {
        if (!cancelled) setOverviewError(err.message || 'Failed to reach the API')
      })

    return () => { cancelled = true }
  }, [])

  // State -> District drilldown. Fetching only the district table keeps
  // the national payload from being recomputed on every state click.
  useEffect(() => {
    if (!selectedState) {
      setDistricts([])
      setDistrictsError(null)
      setDistrictsLoading(false)
      return undefined
    }

    let cancelled = false
    setDistrictsLoading(true)
    setDistrictsError(null)

    fetchPublicDistricts(selectedState)
      .then(data => { if (!cancelled) setDistricts(data.districts) })
      .catch(err => {
        if (!cancelled) setDistrictsError(err.message || 'Failed to reach the API')
      })
      .finally(() => { if (!cancelled) setDistrictsLoading(false) })

    return () => { cancelled = true }
  }, [selectedState])

  const live = !!insights
  const loadingLive = !insights && !insightsError
  const kpiData = insights?.kpis ?? null

  const kpis = [
    [
      'Total Projects',
      formatNumber(kpiData?.totalProjects),
      'All recorded MPLADS works',
    ],
    [
      'Sanctioned Amount',
      formatCurrency(kpiData?.totalSanctioned),
      'Cumulative sanction',
    ],
    [
      'Expenditure',
      formatCurrency(kpiData?.totalExpenditure),
      kpiData?.utilisationPercent !== null && kpiData?.utilisationPercent !== undefined
        ? `${Math.round(kpiData.utilisationPercent)}% of sanctioned amount`
        : 'Cumulative expenditure',
    ],
    [
      'Completed Works',
      formatNumber(kpiData?.completedProjects),
      kpiData?.completionRatePercent !== null && kpiData?.completionRatePercent !== undefined
        ? `${Math.round(kpiData.completionRatePercent)}% of total`
        : '',
    ],
    [
      'Active Works',
      formatNumber(kpiData?.activeWorks),
      'Sanctioned or ongoing',
    ],
  ]

  const statusColors = {
    Ongoing: CHART_COLORS.blue,
    Active: CHART_COLORS.blue,
    Sanctioned: CHART_COLORS.navy,
    Completed: CHART_COLORS.green,
    Recommended: CHART_COLORS.amber,
    'Not specified': CHART_COLORS.muted,
  }

  const statusData = useMemo(() => (insights?.statusDistribution || [])
    .map(item => ({
      name: item.status,
      value: toNumber(item.count) || 0,
      color: statusColors[item.status] || CHART_COLORS.muted,
    }))
    .filter(d => d.value > 0), [insights])

  const recentProjects = overview?.recent_projects || []
  const coverageNotes = insights?.dataCoverage?.notes || []

  // The trend charts always show the national series. Selecting a state
  // drills the state/district panel only, so the label stays "Nationwide"
  // rather than implying the charts were re-scoped.
  const scopeLabel = 'Nationwide'

  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />

      <div className="max-w-[1200px] mx-auto px-5 py-6">
        <h1 className="text-[21px] font-semibold text-ink">MPLADS Project Monitoring</h1>
        <p className="text-[13px] text-muted mt-1.5 max-w-[640px]">
          Transparent public reporting of MPLADS works, sanctioned amounts, expenditure and completion across states and districts.
        </p>
        {loadingLive && <p className="text-xs text-muted mt-2">Loading national portfolio figures…</p>}
        {insightsError && <p className="text-xs mt-2" style={{ color: CHART_COLORS.red }}>Could not load public figures: {insightsError}</p>}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          {kpis.map(([label, value, hint]) => (
            <div className="card p-4" key={label}>
              <div className="text-xs text-muted">{label}</div>
              <div className="text-[20px] font-semibold mt-1.5 text-ink">{value}</div>
              {hint && <div className="text-[11px] text-muted mt-1.5">{hint}</div>}
            </div>
          ))}
        </div>

        {live && (
          <p className="text-[11px] text-muted mt-2">
            Covering {formatNumber(kpiData?.statesCovered)} states and {formatNumber(kpiData?.districtsCovered)} districts.
            {kpiData?.statusNotSpecified
              ? ` ${formatNumber(kpiData.statusNotSpecified)} works have no recorded lifecycle status and are counted in neither completed nor active.`
              : ''}
          </p>
        )}

        <div className="mt-4">
          <PublicTrends trends={insights?.trends} scopeLabel={scopeLabel} />
        </div>

        <div className="grid lg:grid-cols-5 gap-4 mt-4">
          <div className="card p-4 lg:col-span-3">
            <h3 className="text-[13.5px] font-semibold text-ink">State-wise MPLADS Monitoring</h3>
            <p className="text-xs text-muted mt-0.5 mb-3">
              {live
                ? 'By cumulative expenditure — select a state to drill into its districts'
                : 'State-wise data is not available.'}
            </p>
            <IndiaStateGrid
              data={insights?.byState ?? null}
              selected={selectedState}
              onSelect={setSelectedState}
              lockedMessage="State-wise figures are not available from the current source."
            />
          </div>
          <div className="card p-4 lg:col-span-2">
            <h3 className="text-[13.5px] font-semibold text-ink">Project Status Distribution</h3>
            <p className="text-xs text-muted mt-0.5">{live ? 'National lifecycle distribution' : 'Status data is not available.'}</p>
            {statusData.length ? (
              <div style={{ height: 230 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={2}>
                      {statusData.map(d => <Cell key={d.name} fill={d.color} />)}
                    </Pie>
                    <Legend verticalAlign="bottom" height={44} iconSize={9} wrapperStyle={{ fontSize: 11 }} />
                    <Tooltip formatter={v => Number(v).toLocaleString()} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="py-10">
                <EmptyState text="Status breakdown not available." />
              </div>
            )}
          </div>
        </div>

        <div className="mt-4">
          <StateDistrictInsights
            states={insights?.byState || []}
            selectedState={selectedState}
            onSelectState={setSelectedState}
            districts={districts}
            districtsLoading={districtsLoading}
            districtsError={districtsError}
          />
        </div>

        <div className="card mt-4 overflow-hidden">
          <div className="px-4 pt-4 pb-3">
            <h3 className="text-[13.5px] font-semibold text-ink">Recently Monitored Projects</h3>
            <p className="text-xs text-muted mt-0.5">
              {overview ? 'Public summaries of recently updated works' : 'Project data is not available.'}
            </p>
            {overviewError && (
              <p className="text-xs mt-1" style={{ color: CHART_COLORS.red }}>
                Could not load public project summaries: {overviewError}
              </p>
            )}
          </div>
          {overview ? (
            !recentProjects.length ? (
              <div className="py-10 px-4"><EmptyState text="No monitored projects found." /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr>{['Work ID', 'Work', 'State', 'District', 'Constituency', 'Status', 'Sanctioned', 'Expenditure', 'Progress'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                  <tbody>
                    {recentProjects.map(p => (
                      <tr
                        key={p.id}
                        className={p.id ? 'hover:bg-panel cursor-pointer' : undefined}
                        onClick={() => p.id && navigate(`/projects/${encodeURIComponent(p.id)}`)}
                      >
                        <td className="font-mono font-semibold whitespace-nowrap">
                          {p.id ? (
                            <Link to={`/projects/${encodeURIComponent(p.id)}`} onClick={e => e.stopPropagation()} className="text-navy hover:underline">{p.id}</Link>
                          ) : '—'}
                        </td>
                        <td className="whitespace-nowrap">{p.workType ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.state ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.district ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.constituency ?? '—'}</td>
                        <td className="whitespace-nowrap">{p.status ?? '—'}</td>
                        <td className="whitespace-nowrap">{formatCurrency(p.sanctioned)}</td>
                        <td className="whitespace-nowrap">{formatCurrency(p.expenditure)}</td>
                        <td className="whitespace-nowrap">{p.financialProgress !== null ? `${Math.round(p.financialProgress)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : (
            <div className="py-10 px-4"><EmptyState text="Public project data is not available." /></div>
          )}
        </div>

        {coverageNotes.length > 0 && (
          <div className="card p-4 mt-4">
            <h3 className="text-[13.5px] font-semibold text-ink flex items-center gap-1.5">
              <Info size={13} /> About this data
            </h3>
            <ul className="mt-2 space-y-1.5">
              {coverageNotes.map(note => (
                <li key={note} className="text-[11.5px] text-muted leading-snug">— {note}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4"><Disclaimer /></div>
      </div>

      <footer className="border-t border-line bg-white mt-10">
        <div className="max-w-[1200px] mx-auto px-5 py-5 text-xs text-muted flex flex-wrap justify-between gap-3">
          <span>© 2026 MPLADS AI Shield -- SIH prototype</span>
          <span className="flex items-center gap-1.5"><Eye size={12} /> Public transparency view -- not an official Government of India portal</span>
        </div>
      </footer>
    </div>
  )
}
