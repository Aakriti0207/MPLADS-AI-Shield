import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { appRoutes, matchAppRoute } from '../../app/routes'

/**
 * Reads the current route from centralized route config and renders a
 * short breadcrumb trail (parent listing -> current page), where a parent
 * is configured (e.g. Projects -> Project Intelligence).
 */
export default function Breadcrumbs() {
  const location = useLocation()
  const current = matchAppRoute(location.pathname)
  if (!current) return null

  const parent = current.parent ? appRoutes.find(r => r.path === current.parent) : null
  const trail = [parent, current].filter(Boolean)
  if (trail.length < 2) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-slate-400 mb-0.5">
      {trail.map((r, i) => {
        const isLast = i === trail.length - 1
        return (
          <span key={r.path} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={12} aria-hidden="true" />}
            {isLast
              ? <span aria-current="page" className="text-slate-500">{r.title}</span>
              : <Link to={r.path} className="hover:text-slate-600">{r.title}</Link>}
          </span>
        )
      })}
    </nav>
  )
}
