import React from 'react'
import { Link } from 'react-router-dom'
import { Banknote, Building2, CheckCircle2, FolderKanban, ShieldAlert, TrendingUp, Activity } from 'lucide-react'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import KpiCard from '../ui/KpiCard'
import EmptyState from '../ui/EmptyState'
import { Disclaimer } from '../UI'
import ScopeBanner from '../layout/ScopeBanner'
import {
  DataNotes, DataTable, Percent, ProjectRow, SectionCard, UNAVAILABLE,
  TableControls, TablePager, useTableControls,
} from './ScopedDashboardUI'
import { RISK_COLORS } from './dashboardColors'

/**
 * State Nodal Authority cockpit.
 *
 * The question this screen answers: "how is MPLADS performing across my
 * state?"
 *
 * Ordering is state overview -> district comparison -> risk hotspots ->
 * exception projects -> drill-down, because a state officer's job is
 * allocating attention between districts rather than working a single
 * project queue.
 *
 * On district ranking: the comparison table sorts by REAL metrics the
 * officer chooses (high-risk count, utilisation, project volume). There
 * is deliberately no composite "district score" -- no such metric exists
 * in the source data, and inventing one would dress a guess up as a
 * finding. Where a district has no scored projects, average risk reads
 * "Data unavailable" rather than 0.
 *
 * Clicking a district drills into the projects WITHIN this state only;
 * the backend would refuse anything else regardless.
 */
export default function StateDashboard({ data }) {
  const kpis = data.kpis || {}
  const districts = data.district_performance || []
  const [districtSort, setDistrictSort] = React.useState('high_risk')
  const [districtQuery, setDistrictQuery] = React.useState('')

  const controls = useTableControls(data.attention_projects || [], { pageSize: 10 })

  const visibleDistricts = React.useMemo(() => {
    const needle = districtQuery.trim().toLowerCase()
    const filtered = needle
      ? districts.filter(d => d.district.toLowerCase().includes(needle))
      : districts
    const copy = [...filtered]
    copy.sort((a, b) => {
      const av = a[districtSort]
      const bv = b[districtSort]
      if (av === bv) return a.district.localeCompare(b.district)
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      return Number(bv) - Number(av)
    })
    return copy
  }, [districts, districtSort, districtQuery])

  const hotspots = visibleDistricts.slice(0, 10).map(d => ({
    name: d.district,
    highRisk: d.high_risk,
  }))

  const riskCounts = Object.entries(data.risk_level_counts || {}).map(([level, count]) => ({
    name: level,
    value: count,
    fill: RISK_COLORS[level] || RISK_COLORS[String(level).toLowerCase()] || '#1D63A8',
  }))

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">State Monitoring Overview</h1>
        <p className="text-[13px] text-muted mt-0.5">
          MPLADS performance across every district in your assigned state.
        </p>
      </header>

      <ScopeBanner scope={data.scope} />

      {/* ---- State overview ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <KpiCard label="Total Projects" value={formatNumber(kpis.total_projects)} icon={FolderKanban} tone="navy" />
        <KpiCard label="Total Sanctioned" value={formatCurrency(kpis.total_sanctioned)} icon={Banknote} tone="navy" />
        <KpiCard label="Total Expenditure" value={formatCurrency(kpis.total_expenditure)} icon={TrendingUp} tone="blue" />
        <KpiCard
          label="Utilisation"
          value={kpis.utilization_percent === null || kpis.utilization_percent === undefined
            ? UNAVAILABLE
            : `${Number(kpis.utilization_percent).toFixed(1)}%`}
          icon={TrendingUp}
          tone="blue"
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <KpiCard label="Ongoing" value={formatNumber(kpis.active_projects)} icon={Activity} tone="amber" />
        <KpiCard label="Completed" value={formatNumber(kpis.completed_projects)} icon={CheckCircle2} tone="green" />
        <KpiCard label="High-Risk Projects" value={formatNumber(kpis.high_risk_projects)} icon={ShieldAlert} tone="red" />
        <KpiCard
          label="Districts Requiring Attention"
          value={kpis.districts_requiring_attention === null || kpis.districts_requiring_attention === undefined
            ? UNAVAILABLE
            : formatNumber(kpis.districts_requiring_attention)}
          hint={kpis.districts_in_scope ? `of ${formatNumber(kpis.districts_in_scope)} districts` : undefined}
          icon={Building2}
          tone="amber"
        />
      </div>

      {/* ---- Risk hotspots ---- */}
      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">District Risk Hotspots</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">
            Districts by count of projects flagged high or critical
          </p>
          {hotspots.length === 0 ? <EmptyState text="No district-level risk data is available for your state." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={hotspots} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE2E8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
                <Tooltip formatter={value => `${formatNumber(value)} projects`} />
                <Bar dataKey="highRisk" fill="#C0392B" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Risk Distribution</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Projects by risk tier across the state</p>
          {riskCounts.length === 0 ? <EmptyState text="No risk scores are available for your state." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={riskCounts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE2E8" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip formatter={value => formatNumber(value)} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {riskCounts.map(entry => <Cell key={entry.name} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ---- District comparison ---- */}
      <SectionCard
        id="districts"
        title="District Performance Comparison"
        subtitle="Real aggregates per district. Sorting is by an actual metric you choose -- this table deliberately has no composite ranking score, because the source data supports none."
      >
        <div className="px-4 pb-3 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="text-[11px] font-medium text-muted mb-1 block">Find district</label>
            <input
              value={districtQuery}
              onChange={e => setDistrictQuery(e.target.value)}
              placeholder="Search districts…"
              className="w-full border border-line rounded-md py-2 px-3 text-[13px] outline-none focus:border-navy"
            />
          </div>
          <div className="w-full sm:w-auto sm:min-w-[190px]">
            <label className="text-[11px] font-medium text-muted mb-1 block">Sort by</label>
            <select
              value={districtSort}
              onChange={e => setDistrictSort(e.target.value)}
              className="w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink"
            >
              <option value="high_risk">High-risk projects</option>
              <option value="projects">Project count</option>
              <option value="sanctioned">Sanctioned amount</option>
              <option value="expenditure">Expenditure</option>
              <option value="utilization_percent">Utilisation</option>
              <option value="completed">Completed</option>
              <option value="average_risk">Average risk</option>
            </select>
          </div>
        </div>

        <DataTable
          columns={['District', 'Projects', 'Sanctioned', 'Expenditure', 'Utilisation', 'Completed', 'Ongoing', 'High Risk', 'Average Risk', '']}
          empty={data.empty_state_message || 'No district data is available for your assigned state.'}
        >
          {visibleDistricts.map(row => (
            <tr key={row.district} className="hover:bg-panel">
              <td className="font-medium whitespace-nowrap">{row.district}</td>
              <td>{formatNumber(row.projects)}</td>
              <td className="whitespace-nowrap">{formatCurrency(row.sanctioned)}</td>
              <td className="whitespace-nowrap">{formatCurrency(row.expenditure)}</td>
              <td className="whitespace-nowrap"><Percent value={row.utilization_percent} /></td>
              <td>{formatNumber(row.completed)}</td>
              <td>{formatNumber(row.ongoing)}</td>
              <td className={row.high_risk > 0 ? 'font-semibold text-ink' : undefined}>{formatNumber(row.high_risk)}</td>
              <td className="whitespace-nowrap">
                {row.average_risk === null || row.average_risk === undefined
                  ? <span className="text-muted text-[12px]">{UNAVAILABLE}</span>
                  : Number(row.average_risk).toFixed(1)}
              </td>
              <td className="whitespace-nowrap">
                {/* Drill-down stays inside the assigned state: the district
                    filter is applied on top of the server-side state scope,
                    and the backend refuses anything outside it. */}
                <Link
                  to={`/projects?district=${encodeURIComponent(row.district)}`}
                  className="text-xs font-semibold text-navy hover:underline"
                >
                  Open →
                </Link>
              </td>
            </tr>
          ))}
        </DataTable>
      </SectionCard>

      {/* ---- Exception projects ---- */}
      <SectionCard
        id="exceptions"
        title="Exception Projects"
        subtitle="Highest-priority works across the state, ordered by the same risk score used everywhere else in the platform."
      >
        <TableControls
          controls={controls}
          placeholder="Search by Work ID, name, district or MP…"
          sortOptions={[
            { value: 'risk_score', label: 'Risk score' },
            { value: 'district', label: 'District' },
            { value: 'sanctioned_amount', label: 'Sanctioned amount' },
            { value: 'utilization_percent', label: 'Utilisation' },
            { value: 'project_id', label: 'Work ID' },
          ]}
        />
        <DataTable
          columns={['Project ID', 'Project Name', 'District', 'Constituency', 'Sanctioned', 'Utilisation', 'Risk', 'Top Signal', 'Action']}
          empty="No projects in your state are currently flagged for review."
        >
          {controls.pageRows.map(project => (
            <ProjectRow
              key={project.project_id}
              project={project}
              columns={['id', 'name', 'district', 'constituency', 'sanctioned', 'utilization', 'risk', 'signal', 'action']}
            />
          ))}
        </DataTable>
        <TablePager controls={controls} />
      </SectionCard>

      <div className="grid lg:grid-cols-2 gap-4">
        <DataNotes notes={data.data_notes} />
        <div><Disclaimer compact /></div>
      </div>
    </div>
  )
}