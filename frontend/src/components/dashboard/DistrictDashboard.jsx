import React from 'react'
import { Link } from 'react-router-dom'
import { Banknote, CheckCircle2, ClipboardCheck, FolderKanban, ShieldAlert, TrendingUp, Activity } from 'lucide-react'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import KpiCard from '../ui/KpiCard'
import EmptyState from '../ui/EmptyState'
import { Disclaimer } from '../UI'
import ScopeBanner from '../layout/ScopeBanner'
import {
  DataNotes, DataTable, Percent, ProjectRow, RiskCell, SectionCard, UNAVAILABLE,
  TableControls, TablePager, projectHref, useTableControls,
} from './ScopedDashboardUI'
import { RISK_COLORS } from './dashboardColors'

/**
 * District Authority cockpit.
 *
 * The question this screen answers: "which projects in my district need
 * attention right now?"
 *
 * This is the most operational of the three. Ordering is district
 * overview -> high-priority queue -> risk signals -> why flagged ->
 * evidence -> follow-up, and the review queue is the centre of gravity
 * rather than an afterthought.
 *
 * On review actions: this dashboard surfaces the queue and routes into
 * the EXISTING Project Details / Risk Fusion / WHY FLAGGED screens for
 * investigation. It does not invent "mark reviewed" or "record
 * verification" controls, because the current backend has no review-state
 * model to persist them -- a button that silently forgets what an officer
 * recorded would be worse than no button. Wiring real review actions is
 * listed as a known gap in the delivery report.
 */
export default function DistrictDashboard({ data }) {
  const kpis = data.kpis || {}
  const queue = data.attention_projects || []
  const controls = useTableControls(data.scoped_projects || [], { pageSize: 10 })

  // Group the queue by tier so the highest-severity work reads first.
  const grouped = React.useMemo(() => {
    const buckets = { CRITICAL: [], HIGH: [] }
    queue.forEach(project => {
      const level = String(project.risk_level || '').toUpperCase()
      if (buckets[level]) buckets[level].push(project)
    })
    return buckets
  }, [queue])

  const categoryRisk = (data.by_work_category || []).slice(0, 8).map(entry => ({
    name: entry.label,
    projects: entry.count,
  }))

  const riskCounts = Object.entries(data.risk_level_counts || {}).map(([level, count]) => ({
    name: level,
    value: count,
    fill: RISK_COLORS[level] || RISK_COLORS[String(level).toLowerCase()] || '#1D63A8',
  }))

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">District Operations Overview</h1>
        <p className="text-[13px] text-muted mt-0.5">
          Works in your assigned district, prioritised by what needs attention now.
        </p>
      </header>

      <ScopeBanner scope={data.scope} />

      {/* ---- District overview ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <KpiCard label="Total Projects" value={formatNumber(kpis.total_projects)} icon={FolderKanban} tone="navy" />
        <KpiCard label="Ongoing" value={formatNumber(kpis.active_projects)} icon={Activity} tone="amber" />
        <KpiCard label="Completed" value={formatNumber(kpis.completed_projects)} icon={CheckCircle2} tone="green" />
        <KpiCard label="High-Risk Projects" value={formatNumber(kpis.high_risk_projects)} icon={ShieldAlert} tone="red" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
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
        <KpiCard label="Pending Review" value={formatNumber(kpis.projects_requiring_attention)} icon={ClipboardCheck} tone="red" />
      </div>

      {/* ---- High-priority review queue: the centre of this cockpit ---- */}
      <SectionCard
        id="review-queue"
        title="High-Priority Review Queue"
        subtitle="Ordered by the platform's Risk Fusion score -- the identical score every other role sees for the same project. These are review priorities, not findings."
      >
        {queue.length === 0 ? (
          <div className="px-4 pb-4">
            <EmptyState text="No projects in your district are currently flagged for review." />
          </div>
        ) : (
          <div className="px-4 pb-4 space-y-4">
            {['CRITICAL', 'HIGH'].map(tier => (
              grouped[tier].length > 0 && (
                <div key={tier}>
                  <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted mb-2">
                    {tier === 'CRITICAL' ? 'Critical risk' : 'High risk'} ({grouped[tier].length})
                  </h3>
                  <div className="grid md:grid-cols-2 gap-3">
                    {grouped[tier].map(project => (
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
                          <dt className="text-muted">Constituency</dt>
                          <dd className="text-ink truncate">{project.constituency || '—'}</dd>
                          <dt className="text-muted">Status</dt>
                          <dd className="text-ink">{project.status || '—'}</dd>
                          <dt className="text-muted">Financial progress</dt>
                          <dd className="text-ink"><Percent value={project.utilization_percent} /></dd>
                          <dt className="text-muted">Review status</dt>
                          {/* No review-state model exists in the backend yet,
                              so this is stated honestly rather than faked. */}
                          <dd className="text-muted">Not tracked</dd>
                        </dl>

                        {(project.top_risk_signal || project.triggered_component) && (
                          <p className="mt-2 text-[12px] text-muted">
                            <span className="font-medium text-ink">Top reason: </span>
                            {project.top_risk_signal || project.triggered_component}
                          </p>
                        )}

                        {/* Investigation flow reuses the existing screens:
                            Project Details carries Risk Fusion, WHY FLAGGED
                            and the evidence panels. No parallel
                            investigation system is introduced here. */}
                        <Link to={projectHref(project.project_id)} className="mt-2 inline-block text-xs font-semibold text-navy hover:underline">
                          Investigate — Risk Fusion &amp; Why Flagged →
                        </Link>
                      </article>
                    ))}
                  </div>
                </div>
              )
            ))}
          </div>
        )}
      </SectionCard>

      {/* ---- Risk signals ---- */}
      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Risk Distribution</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Projects by risk tier in your district</p>
          {riskCounts.length === 0 ? <EmptyState text="No risk scores are available for your district." /> : (
            <ResponsiveContainer width="100%" height={240}>
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

        <div className="card p-4">
          <h2 className="text-[13.5px] font-semibold text-ink">Works by Category</h2>
          <p className="text-xs text-muted mt-0.5 mb-2">Where the district's works are concentrated</p>
          {categoryRisk.length === 0 ? <EmptyState text="No category data is available." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={categoryRisk} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE2E8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
                <Tooltip />
                <Bar dataKey="projects" fill="#0B2E4F" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ---- Full district monitoring table ---- */}
      <SectionCard
        id="projects"
        title="District Project Monitoring"
        subtitle="Every work in your assigned district."
      >
        <TableControls
          controls={controls}
          placeholder="Search by Work ID, name, MP, constituency or category…"
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
          columns={['Project ID', 'Project', 'MP / Constituency', 'Category', 'Sanctioned', 'Expenditure', 'Financial Progress', 'Physical Progress', 'Risk', 'Status', 'Action']}
          empty={data.empty_state_message || 'No projects are currently available for your assigned district.'}
        >
          {controls.pageRows.map(project => (
            <ProjectRow
              key={project.project_id}
              project={project}
              columns={['id', 'name', 'constituency', 'category', 'sanctioned', 'expenditure', 'progress', 'physical', 'risk', 'status', 'action']}
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