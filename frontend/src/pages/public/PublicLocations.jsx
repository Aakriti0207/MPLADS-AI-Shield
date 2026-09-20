import React, { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, Search } from 'lucide-react'
import PublicLayout from '../../components/public/PublicLayout'
import StatCard from '../../components/public/StatCard'
import StatusBars from '../../components/public/StatusBars'
import UtilisationBar from '../../components/public/UtilisationBar'
import ProjectCard from '../../components/public/ProjectCard'
import DataFreshness from '../../components/public/DataFreshness'
import { PageHeading, PublicEmpty, PublicError, SectionHeading } from '../../components/public/PublicStates'
import { LoadingRegion, ProjectCardSkeleton, Skeleton, StatCardSkeleton } from '../../components/public/Skeleton'
import usePublicQuery from '../../lib/usePublicQuery'
import { fetchExplorerProjects, fetchExplorerSummary } from '../../features/public/api'
import { formatCount, formatInr, formatPercent, showInr, titleCase } from '../../lib/publicFormat'
import { PORTAL_PATHS, locationPath, projectsLink } from '../../lib/publicTheme'

function AreaList({ rows, getLink, label }) {
  const [find, setFind] = useState('')
  const shown = rows.filter(r => (titleCase(r.name) || '').toLowerCase().includes(find.trim().toLowerCase()))
  return (
    <>
      <div className="relative max-w-[420px] mb-4">
        <label htmlFor="find-area" className="sr-only">Find a {label}</label>
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
        <input id="find-area" type="search" className="pub-input pl-9" placeholder={`Find a ${label}`} value={find} onChange={e => setFind(e.target.value)} />
      </div>
      {shown.length === 0 ? <PublicEmpty title={`No ${label} found`} suggestions={['Check the spelling', 'Clear the search']} /> : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map(r => (
            <li key={r.name}>
              <Link to={getLink(r)} className="pub-card p-4 block h-full hover:border-blue hover:shadow-soft transition">
                <div className="text-[16px] font-semibold text-navy">{titleCase(r.name)}</div>
                <div className="mt-1 text-[22px] font-bold text-ink">{formatCount(r.projectCount)} <span className="text-[13px] font-normal text-muted">projects</span></div>
                <div className="text-[13px] text-muted mt-0.5">{showInr(r.sanctioned)} sanctioned &middot; {showInr(r.expenditure)} spent</div>
                <div className="text-[13px] text-muted">{formatCount(r.completedProjects)} completed &middot; {formatCount(r.ongoingProjects)} ongoing</div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

/**
 * India -> State -> District drill-down. Every level shows the same
 * plain summary (projects, sanctioned, spent, completed, ongoing) and a
 * clear next step.
 */
export default function PublicLocations() {
  const { state, district } = useParams()
  const summary = usePublicQuery(opts => fetchExplorerSummary({ state, district }, opts), [state, district])
  const preview = usePublicQuery(
    opts => (district ? fetchExplorerProjects({ state, district, sort: 'recent', pageSize: 6 }, opts) : Promise.resolve(null)),
    [state, district]
  )
  const d = summary.data
  const level = district ? 'district' : state ? 'state' : 'india'
  const placeName = district ? titleCase(district) : state || 'India'
  const ongoing = useMemo(() => d?.statusDistribution.find(r => r.status === 'Ongoing')?.count ?? null, [d])

  const crumbs = [
    { label: 'India', to: PORTAL_PATHS.locations, current: level === 'india' },
    ...(state ? [{ label: state, to: locationPath(state), current: level === 'state' }] : []),
    ...(district ? [{ label: titleCase(district), to: locationPath(state, district), current: true }] : []),
  ]

  return (
    <PublicLayout>
      <nav aria-label="Breadcrumb" className="text-[13.5px] text-muted flex items-center flex-wrap gap-1 mb-4">
        {crumbs.map((c, i) => (
          <React.Fragment key={c.label}>
            {i > 0 && <ChevronRight size={14} aria-hidden="true" />}
            {c.current ? <span aria-current="page" className="text-ink font-medium">{c.label}</span> : <Link to={c.to} className="hover:underline">{c.label}</Link>}
          </React.Fragment>
        ))}
      </nav>

      <PageHeading eyebrow={level === 'india' ? 'Explore by location' : level === 'state' ? 'State' : 'District'} title={placeName}
        description={level === 'india' ? 'Choose a state or union territory to see its districts and projects.' : level === 'state' ? 'Overview of projects in this state, with a breakdown by district.' : `Projects in ${placeName}, ${state}.`} />

      {summary.error ? (
        summary.error.status === 404
          ? <PublicEmpty title="We couldn't find that area" suggestions={['Choose a state from the list', 'Check the spelling']} action={<Link className="pub-btn-primary mt-5" to={PORTAL_PATHS.locations}>Browse all states</Link>} />
          : <PublicError onRetry={summary.retry} />
      ) : !d ? (
        <LoadingRegion label="Loading area summary" className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{[0, 1, 2, 3, 4].map(i => <StatCardSkeleton key={i} />)}</div>
          <Skeleton className="h-64" />
        </LoadingRegion>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="Projects" value={formatCount(d.kpis.totalProjects)} description="Recorded in this area" />
            <StatCard label="Sanctioned" value={formatInr(d.kpis.totalSanctioned)} description="Amount approved" />
            <StatCard label="Expenditure" value={formatInr(d.kpis.totalExpenditure)} description="Amount recorded as spent" />
            <StatCard label="Completed" value={formatCount(d.kpis.completedProjects)} description="Works with a completion record" />
            <StatCard label="Ongoing" value={formatCount(ongoing)} description="Works recorded as under way" />
          </div>

          <div className="grid gap-5 lg:grid-cols-2 mt-6">
            <section className="pub-card p-6" aria-labelledby="loc-status">
              <h2 id="loc-status" className="text-[19px] font-bold text-navy mb-4">Project status</h2>
              <StatusBars rows={d.statusDistribution} />
            </section>
            <section className="pub-card p-6" aria-labelledby="loc-util">
              <h2 id="loc-util" className="text-[19px] font-bold text-navy mb-4">Fund utilization</h2>
              {d.utilisation.percent === null
                ? <p className="text-[14px] text-muted">Fund utilization cannot be calculated for this area from the current records.</p>
                : <UtilisationBar percent={d.utilisation.percent} label="utilized" />}
              <p className="text-[13px] text-muted mt-4">Utilization represents expenditure recorded against the sanctioned amount.</p>
              {level !== 'india' && (
                <Link className="pub-btn-primary mt-5" to={projectsLink({ state, district })}>
                  View all {formatCount(d.kpis.totalProjects)} projects
                </Link>
              )}
            </section>
          </div>

          {level === 'india' && (
            <section className="mt-10" aria-labelledby="states-h">
              <SectionHeading id="states-h" title="States and union territories" />
              <AreaList rows={d.byState.filter(r => r.name !== 'Not specified')} label="state" getLink={r => locationPath(r.name)} />
            </section>
          )}
          {level === 'state' && (
            <section className="mt-10" aria-labelledby="dist-h">
              <SectionHeading id="dist-h" title={`Districts in ${state}`} description="Select a district to see its projects." />
              <AreaList rows={d.byDistrict.filter(r => r.name !== 'Not specified')} label="district" getLink={r => locationPath(state, r.name)} />
            </section>
          )}
          {level === 'district' && (
            <section className="mt-10" aria-labelledby="dp-h">
              <SectionHeading id="dp-h" title="Recent projects" action={<Link className="pub-btn-secondary" to={projectsLink({ state, district })}>See all</Link>} />
              {preview.error ? <PublicError compact onRetry={preview.retry} /> : !preview.data ? (
                <LoadingRegion label="Loading projects" className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map(i => <ProjectCardSkeleton key={i} />)}</LoadingRegion>
              ) : (
                <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{preview.data.items.map(p => <li key={p.id}><ProjectCard project={p} /></li>)}</ul>
              )}
            </section>
          )}
          <DataFreshness meta={d.meta} className="mt-10" />
        </>
      )}
    </PublicLayout>
  )
}