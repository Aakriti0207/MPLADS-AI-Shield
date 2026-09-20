import React, { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, BadgeIndianRupee, CheckCircle2, Clock, FolderKanban, Landmark, MapPinned, Wallet } from 'lucide-react'
import PublicLayout from '../components/public/PublicLayout'
import SearchBox from '../components/public/SearchBox'
import StatCard from '../components/public/StatCard'
import StatusBars from '../components/public/StatusBars'
import UtilisationBar from '../components/public/UtilisationBar'
import LifecycleSteps from '../components/public/LifecycleSteps'
import ProjectCard from '../components/public/ProjectCard'
import DataFreshness from '../components/public/DataFreshness'
import { PublicError, SectionHeading } from '../components/public/PublicStates'
import { LoadingRegion, ProjectCardSkeleton, Skeleton, StatCardSkeleton } from '../components/public/Skeleton'
import usePublicQuery from '../lib/usePublicQuery'
import { fetchExplorerProjects, fetchExplorerSummary } from '../features/public/api'
import { formatCount, formatInr, formatPercent, showInr } from '../lib/publicFormat'
import { PORTAL_PATHS, locationPath } from '../lib/publicTheme'

// Purely decorative rotation for the state-tile grid -- gives the row a
// touch of variety without any of these colours carrying meaning.
const STATE_ACCENT = ['border-t-info', 'border-t-teal', 'border-t-indigo', 'border-t-good']

/**
 * Public landing page.
 *
 * Answers, in order: what is MPLADS, how much money / how many projects,
 * where, what status -- then hands the citizen to search, map or
 * statistics. Every number comes from the public explorer API; when a
 * value is unavailable the card says so instead of showing 0.
 *
 * Only two requests are made on load (an aggregate summary and one
 * short page of recent projects) -- no project-level bulk fetch.
 */
export default function Home() {
  const navigate = useNavigate()
  const summary = usePublicQuery(opts => fetchExplorerSummary({}, opts), [])
  const recent = usePublicQuery(opts => fetchExplorerProjects({ sort: 'recent', pageSize: 6, detailed: true }, opts), [])

  const data = summary.data
  const ongoing = useMemo(
    () => data?.statusDistribution.find(row => row.status === 'Ongoing')?.count ?? null,
    [data]
  )
  const topStates = useMemo(
    () => (data?.byState || []).filter(row => row.name && row.name !== 'Not specified').slice(0, 8),
    [data]
  )

  return (
    <PublicLayout>
      {/* ------------------------------------------------ hero */}
      <section aria-labelledby="hero-title" className="pub-card p-6 md:p-12 border-t-4 border-t-blue">
        <div className="pub-eyebrow">MPLADS Public Transparency Portal</div>
        <h1 id="hero-title" className="mt-2 text-[30px] md:text-[44px] font-bold text-navy leading-[1.15] max-w-[860px]">
          Explore MPLADS Development Projects Across India
        </h1>
        <p className="mt-4 text-[16.5px] md:text-[18px] text-muted max-w-[720px]">
          Track sanctioned projects, expenditure, progress and completed works through publicly available MPLADS data.
        </p>

        <div className="mt-7 max-w-[860px]"><SearchBox /></div>

        <div className="mt-5 flex flex-wrap gap-3">
          <Link to={PORTAL_PATHS.projects} className="pub-btn-primary">Explore Projects <ArrowRight size={16} aria-hidden="true" /></Link>
          <Link to={PORTAL_PATHS.map} className="pub-btn-secondary"><MapPinned size={16} aria-hidden="true" /> Explore Map</Link>
        </div>
      </section>

      {/* ------------------------------------------------ headline numbers */}
      <section aria-labelledby="overview-title" className="mt-10">
        <SectionHeading id="overview-title" title="MPLADS at a glance" description="National totals from the public MPLADS records." />
        {summary.error ? (
          <PublicError onRetry={summary.retry} />
        ) : !data ? (
          <LoadingRegion label="Loading national statistics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[0, 1, 2, 3, 4].map(i => <StatCardSkeleton key={i} />)}
          </LoadingRegion>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <StatCard icon={FolderKanban} label="Total projects" value={formatCount(data.kpis.totalProjects)}
                description="Projects recorded in the public MPLADS dataset" tone="teal" />
              <StatCard icon={BadgeIndianRupee} label="Total sanctioned" value={formatInr(data.kpis.totalSanctioned)}
                description="Amount approved for these works" tone="blue" />
              <StatCard icon={Wallet} label="Total expenditure" value={formatInr(data.kpis.totalExpenditure)}
                description="Amount recorded as spent so far" tone="indigo" />
              <StatCard icon={CheckCircle2} label="Completed projects" value={formatCount(data.kpis.completedProjects)}
                description={data.kpis.completionRatePercent !== null ? `${formatPercent(data.kpis.completionRatePercent)} of all recorded projects` : 'Works with a completion record'} tone="green" />
              <StatCard icon={Clock} label="Ongoing projects" value={formatCount(ongoing)}
                description="Works recorded as under way" tone="amber" />
            </div>
            <DataFreshness meta={data.meta} className="mt-4" />
          </>
        )}
      </section>

      {/* ------------------------------------------------ status + funds */}
      {data && (
        <section className="mt-10 grid gap-5 lg:grid-cols-2" aria-label="Project status and fund utilization">
          <div className="pub-card p-6 border-t-[3px] border-t-info">
            <h2 className="text-[20px] font-bold text-navy">Project status</h2>
            <p className="text-[14px] text-muted mt-1 mb-5">How many projects are at each stage.</p>
            <StatusBars rows={data.statusDistribution} />
          </div>

          <div className="pub-card p-6 border-t-[3px] border-t-teal">
            <h2 className="text-[20px] font-bold text-navy">Fund utilization</h2>
            <p className="text-[14px] text-muted mt-1 mb-5">How much of the sanctioned money has been recorded as spent.</p>
            {data.utilisation.percent === null ? (
              <p className="text-[14px] text-muted">Fund utilization cannot be calculated from the current records.</p>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-4 mb-5">
                  <div>
                    <dt className="text-[13px] text-muted">Sanctioned</dt>
                    <dd className="text-[24px] font-bold text-navy">{showInr(data.utilisation.sanctioned)}</dd>
                  </div>
                  <div>
                    <dt className="text-[13px] text-muted">Expenditure</dt>
                    <dd className="text-[24px] font-bold text-navy">{showInr(data.utilisation.expenditureOnThose)}</dd>
                  </div>
                </dl>
                <UtilisationBar percent={data.utilisation.percent} label="utilized" />
                <p className="text-[13px] text-muted mt-4 leading-relaxed">
                  Utilization represents expenditure recorded against the sanctioned amount, across the{' '}
                  {formatCount(data.utilisation.projectsWithSanction)} projects that have a sanctioned amount recorded.
                  {data.utilisation.projectsWithExpenditureRecord < data.utilisation.totalProjects && (
                    <> Expenditure is recorded for {formatCount(data.utilisation.projectsWithExpenditureRecord)} of {formatCount(data.utilisation.totalProjects)} projects.</>
                  )}
                  {data.kpis.totalExpenditure - data.utilisation.expenditureOnThose > 0 && (
                    <> Total expenditure above also includes {formatInr(data.kpis.totalExpenditure - data.utilisation.expenditureOnThose)} spent on works with no sanctioned amount recorded.</>
                  )}
                </p>
              </>
            )}
          </div>
        </section>
      )}

      {/* ------------------------------------------------ how funds are used */}
      <section className="mt-12 rounded-2xl bg-teal-bg/60 p-5 md:p-8" aria-labelledby="how-title">
        <SectionHeading id="how-title" title="How MPLADS funds are used"
          description="A project moves through these stages. The numbers on this portal come from the records kept at each stage." />
        <LifecycleSteps />
      </section>

      {/* ------------------------------------------------ by location */}
      <section className="mt-12" aria-labelledby="loc-title">
        <SectionHeading id="loc-title" title="Explore projects by location"
          description="Choose a state to see its districts and projects."
          action={<Link to={PORTAL_PATHS.locations} className="text-[14.5px] font-semibold text-blue hover:underline inline-flex items-center gap-1">All states <ArrowRight size={15} aria-hidden="true" /></Link>} />
        {!data ? (
          summary.error ? null : (
            <LoadingRegion label="Loading states" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-28" />)}
            </LoadingRegion>
          )
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {topStates.map((row, index) => (
              <li key={row.name}>
                <Link
                  to={locationPath(row.name)}
                  className={`pub-card p-5 block h-full border-t-[3px] pub-card-hover ${STATE_ACCENT[index % STATE_ACCENT.length]}`}
                >
                  <div className="text-[16px] font-semibold text-navy">{row.name}</div>
                  <div className="text-[24px] font-bold text-ink mt-1">{formatCount(row.projectCount)}</div>
                  <div className="text-[13px] text-muted">projects &middot; {showInr(row.sanctioned)} sanctioned</div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ------------------------------------------------ recent projects */}
      <section className="mt-12" aria-labelledby="recent-title">
        <SectionHeading id="recent-title" title="Recently updated projects"
          description="Projects with the most recent activity in the records that have a description and a sanctioned amount."
          action={<Link to={PORTAL_PATHS.projects} className="pub-btn-secondary">View all projects</Link>} />
        {recent.error ? (
          <PublicError compact onRetry={recent.retry} />
        ) : !recent.data ? (
          <LoadingRegion label="Loading recent projects" className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map(i => <ProjectCardSkeleton key={i} />)}
          </LoadingRegion>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {recent.data.items.map(project => <li key={project.id}><ProjectCard project={project} /></li>)}
          </ul>
        )}
      </section>

      {/* ------------------------------------------------ about teaser */}
      <section className="mt-12 pub-card p-6 md:p-8 border-t-[3px] border-t-indigo flex flex-col md:flex-row md:items-center justify-between gap-5" aria-labelledby="about-teaser">
        <div>
          <h2 id="about-teaser" className="text-[20px] font-bold text-navy flex items-center gap-2">
            <Landmark size={20} aria-hidden="true" /> New to MPLADS?
          </h2>
          <p className="mt-1.5 text-[14.5px] text-muted max-w-[640px]">
            Learn what the Members of Parliament Local Area Development Scheme is, how a project moves from
            recommendation to completion, and what this portal shows.
          </p>
        </div>
        <button type="button" className="pub-btn-primary shrink-0" onClick={() => navigate(PORTAL_PATHS.about)}>About MPLADS</button>
      </section>
    </PublicLayout>
  )
}