import React, { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Check, ChevronRight, Circle, Copy, MapPin } from 'lucide-react'
import PublicLayout from '../../components/public/PublicLayout'
import StatusPill from '../../components/public/StatusPill'
import UtilisationBar from '../../components/public/UtilisationBar'
import DataFreshness from '../../components/public/DataFreshness'
import { PublicError } from '../../components/public/PublicStates'
import { LoadingRegion, Skeleton } from '../../components/public/Skeleton'
import usePublicQuery from '../../lib/usePublicQuery'
import { fetchExplorerProject, fetchPublicMeta } from '../../features/public/api'
import { cleanAgency, formatDateLong, formatInrExact, formatPercent, showInr, titleCase, NOT_AVAILABLE } from '../../lib/publicFormat'
import { PORTAL_PATHS, locationPath, projectsLink } from '../../lib/publicTheme'

function Tile({ label, children }) {
  return (
    <div className="rounded-lg bg-panel border border-line p-4">
      <dt className="text-[12.5px] text-muted font-medium">{label}</dt>
      <dd className="mt-1 text-[18px] font-bold text-navy leading-snug">{children}</dd>
    </div>
  )
}

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return (
    <div className="grid sm:grid-cols-[170px_1fr] gap-x-4 gap-y-0.5 py-3 border-b border-line last:border-0">
      <dt className="text-[13.5px] text-muted">{label}</dt>
      <dd className="text-[15px] text-ink font-medium break-words">{children}</dd>
    </div>
  )
}

/** Only dates that actually exist in the record -- no empty placeholder steps. */
function buildTimeline(project) {
  const events = [
    ['Recommended', project.recommendedDate],
    ['Sanctioned', project.sanctionDate],
    ['First payment recorded', project.firstExpenditureDate],
    project.lastExpenditureDate && project.lastExpenditureDate !== project.firstExpenditureDate
      ? ['Latest payment recorded', project.lastExpenditureDate] : null,
    ['Completed', project.completionDate],
  ].filter(item => item && item[1])
  return events.sort((a, b) => new Date(a[1]) - new Date(b[1]))
}

function StageTracker({ project }) {
  const stages = [
    ['Recommended', Boolean(project.recommendedDate)],
    ['Sanctioned', Boolean(project.sanctionDate || project.sanctioned !== null)],
    ['Payments recorded', project.expenditure !== null && project.expenditure > 0],
    ['Completed', project.status === 'Completed' || Boolean(project.completionDate)],
  ]
  return (
    <ol className="grid grid-cols-2 gap-3">
      {stages.map(([label, reached]) => (
        <li key={label} className={`rounded-lg border p-3 ${reached ? 'border-good bg-good-bg' : 'border-line bg-white'}`}>
          <span className="flex items-center gap-1.5 text-[13.5px] font-semibold" style={{ color: reached ? '#14683f' : '#3f4b55' }}>
            {reached ? <Check size={15} aria-hidden="true" /> : <Circle size={15} aria-hidden="true" />}
            {label}
          </span>
          <span className="block text-[12.5px] mt-0.5" style={{ color: reached ? '#14683f' : '#55636e' }}>
            {reached ? 'Recorded' : 'Not recorded'}
          </span>
        </li>
      ))}
    </ol>
  )
}

export default function PublicProjectDetail() {
  const { id } = useParams()
  const project = usePublicQuery(opts => fetchExplorerProject(id, opts), [id])
  const meta = usePublicQuery(opts => fetchPublicMeta(opts), [])
  const [copied, setCopied] = useState(false)
  const p = project.data
  const timeline = useMemo(() => (p ? buildTimeline(p) : []), [p])

  async function copyId() {
    try {
      await navigator.clipboard.writeText(p.id)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch { /* clipboard unavailable: the ID is visible and selectable */ }
  }

  if (project.error) {
    const notFound = project.error.status === 404
    return (
      <PublicLayout>
        {notFound ? (
          <div className="pub-card p-10 text-center">
            <h1 className="text-[22px] font-bold text-navy">We couldn't find that project</h1>
            <p className="mt-2 text-[15px] text-muted">The project ID may be incorrect, or the project is not in the public records.</p>
            <Link to={PORTAL_PATHS.projects} className="pub-btn-primary mt-6">Search projects</Link>
          </div>
        ) : (
          <PublicError onRetry={project.retry} />
        )}
      </PublicLayout>
    )
  }

  if (!p) {
    return (
      <PublicLayout>
        <LoadingRegion label="Loading project details">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-10 w-3/4 mt-4" />
          <Skeleton className="h-4 w-1/3 mt-3" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 mt-8">
            {[0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24" />)}
          </div>
          <div className="grid gap-5 lg:grid-cols-2 mt-6"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
        </LoadingRegion>
      </PublicLayout>
    )
  }

  const place = [titleCase(p.district), p.state].filter(Boolean).join(', ')
  const title = p.title || 'Project description not recorded'
  const overspent = p.utilisationPercent !== null && p.utilisationPercent > 100

  return (
    <PublicLayout width="max-w-[1100px]">
      <nav aria-label="Breadcrumb" className="text-[13.5px] text-muted flex items-center flex-wrap gap-1 mb-4">
        <Link to={PORTAL_PATHS.home} className="hover:underline">Home</Link><ChevronRight size={14} aria-hidden="true" />
        <Link to={PORTAL_PATHS.projects} className="hover:underline">Projects</Link><ChevronRight size={14} aria-hidden="true" />
        <span aria-current="page" className="text-ink font-medium">Project details</span>
      </nav>

      {/* ---------------- header */}
      <header>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <StatusPill status={p.status} size="lg" />
          {p.category && <span className="text-[13.5px] font-medium text-muted bg-white border border-line rounded-full px-3 py-1.5">{p.category}</span>}
        </div>
        <h1 className="text-[24px] md:text-[32px] font-bold text-navy leading-tight">{title}</h1>
        <p className="mt-2 text-[15.5px] text-muted flex items-center gap-1.5">
          <MapPin size={17} aria-hidden="true" /> {place || 'Location not recorded'}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[13.5px] text-muted">
          <span>Project ID:</span>
          <code className="font-mono text-ink bg-white border border-line rounded px-2 py-0.5 select-all">{p.id}</code>
          <button type="button" onClick={copyId} className="inline-flex items-center gap-1 text-blue font-semibold px-2 min-h-[32px]">
            <Copy size={14} aria-hidden="true" /> {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </header>

      {/* ---------------- at a glance */}
      <section className="mt-8" aria-labelledby="glance">
        <h2 id="glance" className="text-[20px] font-bold text-navy mb-3">At a glance</h2>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Tile label="Sanctioned">{showInr(p.sanctioned)}</Tile>
          <Tile label="Spent">{p.expenditure !== null ? showInr(p.expenditure) : 'Not recorded'}</Tile>
          <Tile label="Utilization">{p.utilisationPercent !== null ? formatPercent(p.utilisationPercent, p.utilisationPercent < 10 && p.utilisationPercent > 0 ? 1 : 0) : NOT_AVAILABLE}</Tile>
          <Tile label="Status">{p.status || 'Not specified'}</Tile>
          <Tile label="Location">{place || NOT_AVAILABLE}</Tile>
        </dl>
      </section>

      <div className="grid gap-5 lg:grid-cols-2 mt-8">
        {/* ---------------- overview */}
        <section className="pub-card p-6" aria-labelledby="overview">
          <h2 id="overview" className="text-[20px] font-bold text-navy mb-2">Project overview</h2>
          <dl>
            <Row label="What is the work?">{p.description}</Row>
            <Row label="Work category">{p.category}</Row>
            <Row label="State">{p.state}</Row>
            <Row label="District">{titleCase(p.district)}</Row>
            <Row label="Constituency">{titleCase(p.constituency)}</Row>
            <Row label="Recommended by">{p.mpName}</Row>
            <Row label="Implementing agency">{cleanAgency(p.agency)}</Row>
            <Row label="Sanction date">{formatDateLong(p.sanctionDate)}</Row>
            <Row label="Current status">{p.status || 'Not specified'}</Row>
          </dl>
        </section>

        {/* ---------------- financial progress */}
        <section className="pub-card p-6" aria-labelledby="financial">
          <h2 id="financial" className="text-[20px] font-bold text-navy mb-2">Financial progress</h2>
          <dl className="grid grid-cols-2 gap-4 my-4">
            <div>
              <dt className="text-[13px] text-muted">Sanctioned amount</dt>
              <dd className="text-[22px] font-bold text-navy">{showInr(p.sanctioned)}</dd>
              {p.sanctioned !== null && <dd className="text-[12.5px] text-muted">{formatInrExact(p.sanctioned)}</dd>}
            </div>
            <div>
              <dt className="text-[13px] text-muted">Expenditure recorded</dt>
              <dd className="text-[22px] font-bold text-navy">{p.expenditure !== null ? showInr(p.expenditure) : 'Not recorded'}</dd>
              {p.expenditure !== null && <dd className="text-[12.5px] text-muted">{formatInrExact(p.expenditure)}</dd>}
            </div>
          </dl>
          {p.utilisationPercent !== null ? (
            <UtilisationBar percent={p.utilisationPercent} label="utilized" />
          ) : (
            <p className="text-[14px] text-muted">
              {p.expenditure === null
                ? 'No expenditure has been recorded for this project in the public records.'
                : 'Utilization cannot be calculated because no sanctioned amount is recorded.'}
            </p>
          )}
          {overspent && (
            <p className="mt-3 text-[13.5px] text-ink bg-warn-bg rounded-lg px-3 py-2">
              The recorded expenditure is higher than the recorded sanctioned amount.
            </p>
          )}
          <p className="text-[12.5px] text-muted mt-4">Utilization represents expenditure recorded against the sanctioned amount.</p>
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-2 mt-5">
        {/* ---------------- project progress */}
        <section className="pub-card p-6" aria-labelledby="progress">
          <h2 id="progress" className="text-[20px] font-bold text-navy mb-2">Project progress</h2>
          <p className="text-[13.5px] text-muted mb-4">
            Stages that appear in the public records for this project. Physical progress (percentage of work
            finished) is not part of the public data, so it is not shown.
          </p>
          <StageTracker project={p} />
        </section>

        {/* ---------------- timeline */}
        <section className="pub-card p-6" aria-labelledby="timeline">
          <h2 id="timeline" className="text-[20px] font-bold text-navy mb-2">Timeline</h2>
          {timeline.length === 0 ? (
            <p className="text-[14px] text-muted">No dates are recorded for this project.</p>
          ) : (
            <ol className="relative border-l-2 border-line ml-2 mt-4 space-y-5">
              {timeline.map(([label, date]) => (
                <li key={label} className="pl-5 relative">
                  <span className="absolute -left-[7px] top-1.5 w-3 h-3 rounded-full bg-blue ring-4 ring-white" aria-hidden="true" />
                  <div className="text-[15px] font-semibold text-ink">{label}</div>
                  <div className="text-[14px] text-muted">{formatDateLong(date)}</div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {/* ---------------- related */}
      <section className="mt-8 pub-card p-6" aria-labelledby="related">
        <h2 id="related" className="text-[18px] font-bold text-navy mb-3">Explore related information</h2>
        <div className="flex flex-wrap gap-3">
          {p.state && p.district && (
            <Link className="pub-btn-secondary" to={projectsLink({ state: p.state, district: p.district })}>
              More projects in {titleCase(p.district)}
            </Link>
          )}
          {p.state && <Link className="pub-btn-secondary" to={locationPath(p.state)}>{p.state} overview</Link>}
          {p.state && <Link className="pub-btn-secondary" to={projectsLink({ state: p.state, category: p.category })}>Similar work in {p.state}</Link>}
          <Link className="pub-btn-secondary" to={PORTAL_PATHS.projects}>Search all projects</Link>
        </div>
      </section>

      <DataFreshness meta={meta.data} className="mt-8" />
    </PublicLayout>
  )
}