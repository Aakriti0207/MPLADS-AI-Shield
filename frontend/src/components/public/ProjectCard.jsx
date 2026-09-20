import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, MapPin } from 'lucide-react'
import StatusPill from './StatusPill'
import UtilisationBar from './UtilisationBar'
import { NOT_AVAILABLE, formatInr, titleCase } from '../../lib/publicFormat'
import { publicProjectPath, statusStyle } from '../../lib/publicTheme'

export function locationText(project) {
  const parts = [titleCase(project.district), project.state].filter(Boolean)
  return parts.length ? parts.join(', ') : 'Location not recorded'
}

/**
 * Public project card. Shows ONLY citizen-facing facts: name, place,
 * category, status, sanctioned amount, expenditure, funds used, id.
 */
export default function ProjectCard({ project }) {
  const href = publicProjectPath(project.id)
  const title = project.title || 'Project description not recorded'
  const hasSpend = project.expenditure !== null
  // Same colour the status pill uses, applied as a thin edge so a card's
  // stage reads at a glance even before the eye reaches the pill text.
  const edge = statusStyle(project.status || 'Not specified').bar

  return (
    <article
      className="pub-card p-5 flex flex-col h-full border-l-[3px] hover:shadow-soft hover:-translate-y-0.5 transition"
      style={{ borderLeftColor: edge }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={project.status} />
        {project.category && (
          <span className="text-[12.5px] font-medium text-muted bg-panel border border-line rounded-full px-2.5 py-1">
            {project.category}
          </span>
        )}
      </div>

      <h3 className="mt-3 text-[16px] font-semibold text-ink leading-snug line-clamp-3">
        <Link to={href} className="hover:text-blue hover:underline">{title}</Link>
      </h3>

      <p className="mt-2 text-[13.5px] text-muted flex items-start gap-1.5">
        <MapPin size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>{locationText(project)}</span>
      </p>

      <dl className="grid grid-cols-2 gap-3 mt-4">
        <div>
          <dt className="text-[12px] text-muted">Sanctioned</dt>
          <dd className="text-[16px] font-bold text-ink">{formatInr(project.sanctioned) ?? NOT_AVAILABLE}</dd>
        </div>
        <div>
          <dt className="text-[12px] text-muted">Spent so far</dt>
          <dd className="text-[16px] font-bold text-ink">{hasSpend ? formatInr(project.expenditure) : 'Not recorded'}</dd>
        </div>
      </dl>

      <div className="mt-4">
        {project.utilisationPercent !== null
          ? <UtilisationBar percent={project.utilisationPercent} compact label="of sanctioned amount spent" />
          : <p className="text-[12.5px] text-muted">Funds-used percentage not available for this project.</p>}
      </div>

      <div className="mt-auto pt-4 flex items-center justify-between gap-3">
        <span className="text-[11.5px] text-muted font-mono break-all" title="Project ID">{project.id}</span>
        <Link
          to={href}
          className="shrink-0 inline-flex items-center gap-1 text-[14px] font-semibold text-blue hover:underline"
          aria-label={`View details: ${title}`}
        >
          View details <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </article>
  )
}