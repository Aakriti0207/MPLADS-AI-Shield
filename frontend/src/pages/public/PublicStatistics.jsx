import React, { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BadgeIndianRupee, CheckCircle2, FolderKanban, Wallet } from 'lucide-react'
import PublicLayout from '../../components/public/PublicLayout'
import PublicChartCard, { ChartTable } from '../../components/public/PublicChartCard'
import StatCard from '../../components/public/StatCard'
import StatusBars from '../../components/public/StatusBars'
import DataFreshness from '../../components/public/DataFreshness'
import { PageHeading, PublicError } from '../../components/public/PublicStates'
import { ChartSkeleton, LoadingRegion, StatCardSkeleton } from '../../components/public/Skeleton'
import usePublicQuery from '../../lib/usePublicQuery'
import { fetchExplorerSummary } from '../../features/public/api'
import { formatCount, formatInr, formatPercent, showInr } from '../../lib/publicFormat'

const BLUE = '#1d63a8'
const NAVY = '#0b2e4f'
const CR = 1e7

function BarsByCount({ data, nameKey, height }) {
  return (
    <div style={{ height }} role="img" aria-label="Bar chart. The same numbers are in the table below.">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="#e3e8ed" />
          <XAxis type="number" tick={{ fontSize: 12, fill: '#3f4b55' }} tickFormatter={v => formatCount(v)} />
          <YAxis type="category" dataKey={nameKey} width={150} tick={{ fontSize: 12, fill: '#16232e' }} interval={0} />
          <Tooltip formatter={value => [formatCount(value), 'Projects']} />
          <Bar dataKey="count" name="Projects" fill={BLUE} radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#16232e', formatter: v => formatCount(v) }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function PublicStatistics() {
  const summary = usePublicQuery(opts => fetchExplorerSummary({}, opts), [])
  const d = summary.data

  const states = useMemo(() => (d?.byState || []).filter(r => r.name !== 'Not specified').slice(0, 15), [d])
  const categories = useMemo(() => (d?.byCategory || []).filter(r => r.category !== 'Not specified'), [d])
  const money = useMemo(() => categories.map(c => ({
    category: c.category,
    sanctioned: (c.sanctioned || 0) / CR,
    expenditure: (c.expenditure || 0) / CR,
  })), [categories])

  return (
    <PublicLayout>
      <PageHeading eyebrow="Statistics" title="MPLADS in numbers"
        description="Simple charts built from the public records. Each one has a plain-language summary and a table of the same figures." />

      {summary.error ? <PublicError onRetry={summary.retry} /> : !d ? (
        <LoadingRegion label="Loading statistics" className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map(i => <StatCardSkeleton key={i} />)}</div>
          <div className="grid gap-5 lg:grid-cols-2"><ChartSkeleton /><ChartSkeleton /></div>
        </LoadingRegion>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={FolderKanban} label="Total projects" value={formatCount(d.kpis.totalProjects)} description="Recorded in the public dataset" />
            <StatCard icon={CheckCircle2} label="Completion rate" value={formatPercent(d.kpis.completionRatePercent, 1)} description="Share of projects with a completion record" />
            <StatCard icon={BadgeIndianRupee} label="Total sanctioned" value={formatInr(d.kpis.totalSanctioned)} description="Amount approved" />
            <StatCard icon={Wallet} label="Total expenditure" value={formatInr(d.kpis.totalExpenditure)} description="Amount recorded as spent" />
          </div>

          <div className="grid gap-5 lg:grid-cols-2 mt-6">
            <PublicChartCard title="Projects by status" description="How many projects are at each stage."
              summary={`${formatCount(d.kpis.completedProjects)} of ${formatCount(d.kpis.totalProjects)} projects are completed.`}
              table={<ChartTable caption="Projects by status" columns={['Status', 'Projects']} rows={d.statusDistribution.map(r => [r.status, formatCount(r.count)])} />}>
              <StatusBars rows={d.statusDistribution} />
            </PublicChartCard>

            <PublicChartCard title="Projects by work category" description="The kind of work being carried out."
              summary={categories[0] ? `${categories[0].category} is the largest category, with ${formatCount(categories[0].count)} projects.` : null}
              table={<ChartTable caption="Projects by work category" columns={['Category', 'Projects']} rows={categories.map(r => [r.category, formatCount(r.count)])} />}>
              <BarsByCount data={categories} nameKey="category" height={Math.max(260, categories.length * 34)} />
            </PublicChartCard>
          </div>

          <div className="mt-5">
            <PublicChartCard title="Projects by state" description="The 15 states and union territories with the most recorded projects."
              summary={states[0] ? `${states[0].name} has the most projects (${formatCount(states[0].projectCount)}).` : null}
              table={<ChartTable caption="Projects by state" columns={['State', 'Projects', 'Sanctioned', 'Expenditure']} rows={(d.byState || []).map(r => [r.name, formatCount(r.projectCount), showInr(r.sanctioned), showInr(r.expenditure)])} />}>
              <BarsByCount data={states.map(s => ({ name: s.name, count: s.projectCount }))} nameKey="name" height={Math.max(300, states.length * 32)} />
            </PublicChartCard>
          </div>

          <div className="mt-5">
            <PublicChartCard title="Sanctioned vs expenditure, by work category" description="Amount approved compared with amount recorded as spent, in ₹ crore."
              summary={d.utilisation.percent !== null ? `Overall, ${formatPercent(d.utilisation.percent, 1)} of the sanctioned amount is recorded as spent.` : null}
              table={<ChartTable caption="Sanctioned and expenditure by category" columns={['Category', 'Sanctioned', 'Expenditure']} rows={categories.map(r => [r.category, showInr(r.sanctioned), showInr(r.expenditure)])} />}>
              <div style={{ height: 340 }} role="img" aria-label="Grouped bar chart of sanctioned amount and expenditure by category. The same numbers are in the table below.">
                <ResponsiveContainer>
                  <BarChart data={money} margin={{ top: 8, right: 16, left: 40, bottom: 90 }}>
                    <CartesianGrid vertical={false} stroke="#e3e8ed" />
                    <XAxis dataKey="category" interval={0} angle={-35} textAnchor="end" height={110} tick={{ fontSize: 11, fill: '#16232e' }} />
                    <YAxis tick={{ fontSize: 12, fill: '#3f4b55' }} tickFormatter={v => `₹${v.toLocaleString('en-IN')}`} />
                    <Tooltip formatter={(v, name) => [`₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })} Cr`, name]} />
                    <Legend verticalAlign="top" formatter={v => <span style={{ color: '#16232e' }}>{v}</span>} />
                    <Bar dataKey="sanctioned" name="Sanctioned (₹ Cr)" fill={NAVY} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="expenditure" name="Expenditure (₹ Cr)" fill="#8fb4d9" stroke={BLUE} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </PublicChartCard>
          </div>

          <p className="mt-5 text-[13px] text-muted max-w-[760px]">
            Expenditure is recorded for {formatCount(d.utilisation.projectsWithExpenditureRecord)} of {formatCount(d.utilisation.totalProjects)} projects,
            so spending totals reflect only what the records contain.
          </p>
          <DataFreshness meta={d.meta} className="mt-6" />
        </>
      )}
    </PublicLayout>
  )
}