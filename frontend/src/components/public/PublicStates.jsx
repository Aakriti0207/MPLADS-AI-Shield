import React from 'react'
import { AlertCircle, SearchX } from 'lucide-react'

/** Friendly error. Never shows raw API text, status codes or traces. */
export function PublicError({ message = "We couldn't load project data right now.", onRetry, compact = false }) {
  return (
    <div role="alert" className={`pub-card text-center ${compact ? 'p-6' : 'p-10'}`}>
      <AlertCircle className="mx-auto text-bad" size={26} aria-hidden="true" />
      <p className="mt-3 text-[16px] font-semibold text-ink">{message}</p>
      <p className="mt-1 text-[14px] text-muted">Please check your connection and try again in a moment.</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="pub-btn-primary mt-5">Try Again</button>
      )}
    </div>
  )
}

/** Empty results with concrete next steps -- never a blank box. */
export function PublicEmpty({ title = 'No projects found', suggestions, action }) {
  const tips = suggestions || ['Try another project name', 'Try another district', 'Try another category']
  return (
    <div className="pub-card p-10 text-center">
      <SearchX className="mx-auto text-muted" size={28} aria-hidden="true" />
      <p className="mt-3 text-[17px] font-semibold text-ink">{title}</p>
      <p className="mt-1 text-[14px] text-muted">Try:</p>
      <ul className="mt-1 text-[14px] text-muted space-y-0.5">
        {tips.map(tip => <li key={tip}>{tip}</li>)}
      </ul>
      {action}
    </div>
  )
}

export function PageHeading({ eyebrow, title, description, children }) {
  return (
    <div className="mb-6 md:mb-8">
      {eyebrow && <div className="pub-eyebrow mb-1.5">{eyebrow}</div>}
      <h1 className="text-[26px] md:text-[32px] font-bold text-navy leading-tight">{title}</h1>
      {description && <p className="mt-2 text-[15.5px] text-muted max-w-[720px]">{description}</p>}
      {children}
    </div>
  )
}

export function SectionHeading({ id, title, description, action }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div>
        <h2 id={id} className="text-[21px] md:text-[24px] font-bold text-navy">{title}</h2>
        {description && <p className="mt-1 text-[14.5px] text-muted max-w-[680px]">{description}</p>}
      </div>
      {action}
    </div>
  )
}