import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { appRoutes, matchAppRoute } from '../../app/routes'

export default function Breadcrumbs() {
  const location = useLocation()
  const current = matchAppRoute(location.pathname)
  if (!current) return null

  const parent = current.parent ? appRoutes.find(r => r.path === current.parent) : null
  const trail = [parent, current].filter(Boolean)
  if (trail.length < 2) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[11px] text-muted mb-0.5">
      {trail.map((r, i) => {
        const isLast = i === trail.length - 1
        return (
          <span key={r.path} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={11} aria-hidden="true" />}
            {isLast
              ? <span aria-current="page">{r.title}</span>
              : <Link to={r.path} className="hover:text-ink">{r.title}</Link>}
          </span>
        )
      })}
    </nav>
  )
}