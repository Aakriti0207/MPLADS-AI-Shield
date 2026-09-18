import React from 'react'
import { Banknote, CheckCircle2, FolderKanban, ShieldAlert, TrendingUp, Activity } from 'lucide-react'
import { BarChart, Bar, CartesianGrid, Cell, PieChart, Pie, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import KpiCard from '../ui/KpiCard'
import EmptyState from '../ui/EmptyState'
import { Disclaimer } from '../UI'
import ScopeBanner from '../layout/ScopeBanner'
import {
  DataNotes, DataTable, Percent, ProjectRow, RiskCell, SectionCard,
  TableControls, TablePager, projectHref, useTableControls,
} from './ScopedDashboardUI'
import { CHART_COLORS, RISK_COLORS } from './dashboardColors'
import { Link } from 'react-router-dom'

/**
 * Member of Parliament cockpit.
 *
 * The question this screen answers: "how are the works recommended under
 * my constituency progressing?"
 *
 * Deliberate ordering (project visibility -> progress -> financial
 * utilisation -> risk signals -> alerts -> details): an MP is an
 * oversight persona, not an investigator. The ML internals are NOT the
 * first thing on screen. The full Risk Fusion / WHY FLAGGED breakdown
 * stays one click away on the existing Project Details page, using the
 * same engine and the same score every other role sees.
 *
 * Nothing on this page calls a project fraudulent. Risk is framed as a
 * review-priority signal, which is what it actually is.
 */
export default function MpDashboard({ data }) {
  const kpis = data.kpis || {}
  const controls = useTableControls(data.scoped_projects || [], { pageSize: 10 })

  const statusData = (data.status_distribution || []).map((entry, index) => ({
    name: entry.status,
    value: entry.count,
    fill: CHART_COLORS[index % CHART_COLORS.length],
  }))

  const categoryData = (data.by_work_category || []).slice(0, 8).map(entry => ({
    name: entry.label,
    projects: entry.count,
  }))

  const financial = [
    { name: 'Sanctioned', value: Number(kpis.total_sanctioned || 0) },
    { name: 'Expenditure', value: Number(kpis.total_expenditure || 0) },
  ]

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">Constituency Overview</h1>
        <p className="text-[13px] text-muted mt-0.5">
          Works recommended under your constituency, their progress and their
          financial utilisation.
        </p>
      </header>

      <ScopeBanner scope={data.scope} />

      {/* ---- Headline figures ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <KpiCard label="Total Projects" value={formatNumber(kpis.total_projects)} icon={FolderKanban} tone="navy" />
        <KpiCard label="Active Projects" value={formatNumber(kpis.active_projects)} icon={Activity} tone="amber" />
        <KpiCard label="Completed Projects" value={formatNumber(kpis.completed_projects)} icon={CheckCircle2} tone="green" />
        <KpiCard label="Requiring Attention" value={formatNumber(kpis.projects_requiring_attention)} icon={ShieldAlert} tone="red" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <KpiCard label="Total Sanctioned" value={formatCurrency(kpis.total_sanctioned)} icon={Banknote} tone="navy" />
        <KpiCard label="Total Expenditure" value={formatCurrency(kpis.total_expenditure)} icon={TrendingUp} tone="blue" />
        <KpiCard
          label="Utilisation"
          value={kpis.utilization_percent === null || kpis.utilization_percent === undefined
            ? 'Data unavailable'
            : `${Number(kpis.utilization_percent).toFixed(1)}%`}
          icon={TrendingUp}
          tone="blue"
        />
      </div>

      {/* ---- Constituency project overview ---- */}
      <div className="grid lg:grid-cols-3 gap-4 mb-4">
        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Project Status</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Completed vs ongoing works</p>
          {statusData.length === 0 ? <EmptyState text="No status data available for your constituency." /> : (
            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
                  {statusData.map(entry => <Cell key={entry.name} fill={entry.fill} />)}
                </Pie>
                <Tooltip formatter={value => formatNumber(value)} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Financial Utilisation</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Sanctioned against expenditure</p>
          <ResponsiveContainer width="100%" height={210}>
            <BarChart data={financial}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DCE2E8" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={value => formatCurrency(value)} width={70} />
              <Tooltip formatter={value => formatCurrency(value)} />
              <Bar dataKey="value" fill="#1D63A8" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Work Categories</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Projects by category</p>
          {categoryData.length === 0 ? <EmptyState text="No category data available." /> : (
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={categoryData} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE2E8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={110} />
                <Tooltip />
                <Bar dataKey="projects" fill="#0B2E4F" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ---- Projects requiring attention ---- */}
      <SectionCard
        id="attention"
        title="Projects Requiring Attention"
        subtitle="Flagged for review by the platform's risk analysis. These are prioritisation signals for authorised review, not findings of wrongdoing."
      >
        {(data.attention_projects || []).length === 0 ? (
          <div className="px-4 pb-4">
            <EmptyState text="No projects in your constituency are currently flagged for review." />
          </div>
        ) : (
          <div className="px-4 pb-4 grid md:grid-cols-2 gap-3">
            {(data.attention_projects || []).slice(0, 6).map(project => (
              <article key={project.project_id} className="border border-line rounded-md p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link to={projectHref(project.project_id)} className="font-mono text-[12px] font-semibold text-navy hover:underline">
                      {project.project_id}
                    </Link>
                    <p className="text-[13px] text-ink mt-0.5 truncate" title={project.work_description || ''}>
                      {project.work_description || project.work_category || 'Untitled work'}
                    </p>
                  </div>
                  <RiskCell score={project.risk_score} level={project.risk_level} />
                </div>

                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[12px]">
                  <dt className="text-muted">Location</dt>
                  <dd className="text-ink truncate">{project.district || '—'}</dd>
                  <dt className="text-muted">Status</dt>
                  <dd className="text-ink">{project.status || '—'}</dd>
                  <dt className="text-muted">Financial progress</dt>
                  <dd className="text-ink"><Percent value={project.utilization_percent} /></dd>
                  <dt className="text-muted">Physical progress</dt>
                  <dd className="text-muted">Data unavailable</dd>
                </dl>

                {(project.top_risk_signal || project.triggered_component) && (
                  <p className="mt-2 text-[12px] text-muted">
                    <span className="font-medium text-ink">Top signal: </span>
                    {project.top_risk_signal || project.triggered_component}
                  </p>
                )}

                <Link to={projectHref(project.project_id)} className="mt-2 inline-block text-xs font-semibold text-navy hover:underline">
                  View Details →
                </Link>
              </article>
            ))}
          </div>
        )}
      </SectionCard>

      {/* ---- Full project table ---- */}
      <SectionCard
        id="projects"
        title="My Projects"
        subtitle="Every work recommended under your constituency."
      >
        <TableControls
          controls={controls}
          placeholder="Search by Work ID, name, district or category…"
          sortOptions={[
            { value: 'risk_score', label: 'Risk score' },
            { value: 'sanctioned_amount', label: 'Sanctioned amount' },
            { value: 'expenditure', label: 'Expenditure' },
            { value: 'utilization_percent', label: 'Utilisation' },
            { value: 'status', label: 'Status' },
            { value: 'project_id', label: 'Work ID' },
          ]}
        />
        <DataTable
          columns={['Project ID', 'Project Name', 'District', 'Work Category', 'Sanctioned', 'Expenditure', 'Utilisation', 'Progress', 'Risk', 'Status', 'Action']}
          empty={data.empty_state_message || 'No projects are currently available for your constituency.'}
        >
          {controls.pageRows.map(project => (
            <ProjectRow
              key={project.project_id}
              project={project}
              columns={['id', 'name', 'district', 'category', 'sanctioned', 'expenditure', 'utilization', 'progress', 'risk', 'status', 'action']}
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