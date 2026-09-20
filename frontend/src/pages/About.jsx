import React from 'react'
import { Link } from 'react-router-dom'
import PublicLayout from '../components/public/PublicLayout'
import LifecycleSteps from '../components/public/LifecycleSteps'
import DataFreshness from '../components/public/DataFreshness'
import { PageHeading, SectionHeading } from '../components/public/PublicStates'
import usePublicQuery from '../lib/usePublicQuery'
import { fetchExplorerSummary } from '../features/public/api'
import { formatCount } from '../lib/publicFormat'
import { PORTAL_PATHS } from '../lib/publicTheme'

export default function About() {
  const summary = usePublicQuery(opts => fetchExplorerSummary({}, opts), [])
  const d = summary.data

  return (
    <PublicLayout width="max-w-[900px]">
      <PageHeading eyebrow="About MPLADS" title="What is MPLADS?" />

      <section className="pub-card p-6 md:p-8" aria-labelledby="what">
        <h2 id="what" className="text-[20px] font-bold text-navy">The scheme in one paragraph</h2>
        <p className="mt-2 text-[15.5px] text-ink leading-relaxed">
          The Members of Parliament Local Area Development Scheme (MPLADS) lets Members of Parliament
          recommend development works for their constituencies or areas &ndash; such as roads, school
          buildings, community halls or water facilities. Approved works are carried out by an
          implementing agency and paid for from scheme funds.
        </p>
      </section>

      <section className="mt-10" aria-labelledby="how">
        <SectionHeading id="how" title="How a project moves forward" />
        <LifecycleSteps />
      </section>

      <section className="pub-card p-6 md:p-8 mt-10" aria-labelledby="shown">
        <h2 id="shown" className="text-[20px] font-bold text-navy">What this portal shows</h2>
        <ul className="mt-3 space-y-2 text-[15px] text-ink list-disc pl-5">
          <li>Each project&rsquo;s description, place, work category and status.</li>
          <li>The amount sanctioned and the expenditure recorded against it.</li>
          <li>Dates that appear in the records, such as sanction and completion.</li>
          <li>Totals by state and district, so you can compare areas.</li>
        </ul>
        <h3 className="text-[16px] font-bold text-navy mt-6">What the numbers mean</h3>
        <ul className="mt-2 space-y-2 text-[15px] text-ink list-disc pl-5">
          <li><strong>Sanctioned</strong> is the amount approved for a work.</li>
          <li><strong>Expenditure</strong> is the amount recorded as spent so far.</li>
          <li><strong>Utilization</strong> is expenditure recorded against the sanctioned amount.</li>
        </ul>
      </section>

      <section className="pub-card p-6 md:p-8 mt-6" aria-labelledby="limits">
        <h2 id="limits" className="text-[20px] font-bold text-navy">Please keep in mind</h2>
        <ul className="mt-3 space-y-2 text-[15px] text-ink list-disc pl-5">
          <li>Figures reflect what the source records contain. A blank means &ldquo;not recorded&rdquo;, not zero.</li>
          <li>Physical progress (percentage of work finished) is not part of the public data.</li>
          {d && d.utilisation.projectsWithExpenditureRecord < d.utilisation.totalProjects && (
            <li>Expenditure is recorded for {formatCount(d.utilisation.projectsWithExpenditureRecord)} of {formatCount(d.utilisation.totalProjects)} projects, so spending totals may look low.</li>
          )}
          <li>This is a public transparency view, not an official Government of India portal.</li>
        </ul>
        <DataFreshness meta={d?.meta} className="mt-5" />
      </section>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link to={PORTAL_PATHS.projects} className="pub-btn-primary">Explore projects</Link>
        <Link to={PORTAL_PATHS.statistics} className="pub-btn-secondary">See statistics</Link>
      </div>
    </PublicLayout>
  )
}