import React from 'react'
import { NavLink } from 'react-router-dom'
import { BellRing, Menu } from 'lucide-react'
import Breadcrumbs from './Breadcrumbs'

/**
 * Application topbar: mobile nav toggle, breadcrumbs + page title/context,
 * and a right-side utility area. Visual-shell only -- the alerts entry
 * point links to the real Alerts page, but no notification logic lives here.
 */
export default function Topbar({ title, description, onOpenSidebar }) {
  return (
    <header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-200">
      <div className="h-16 px-4 md:px-8 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button
            className="md:hidden shrink-0"
            onClick={onOpenSidebar}
            aria-label="Open navigation menu"
            aria-controls="app-sidebar"
          ><Menu aria-hidden="true" /></button>
          <div className="min-w-0">
            <Breadcrumbs />
            <div className="font-bold truncate">{title}</div>
            {description && <div className="text-xs text-slate-500 truncate">{description}</div>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <NavLink
            to="/alerts"
            className="h-9 w-9 rounded-xl border border-slate-200 flex items-center justify-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-navy"
            aria-label="View alerts"
          ><BellRing size={17} aria-hidden="true" /></NavLink>
        </div>
      </div>
    </header>
  )
}
