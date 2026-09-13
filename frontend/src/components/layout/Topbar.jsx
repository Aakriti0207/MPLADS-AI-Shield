import React from 'react'
import { NavLink } from 'react-router-dom'
import { BellRing, Menu } from 'lucide-react'
import Breadcrumbs from './Breadcrumbs'

/**
 * Application topbar: mobile nav toggle, breadcrumbs + page title/context,
 * and a right-side utility area. Visual-shell only -- the alerts entry
 * point links to the real Alerts page, but no notification logic lives here.
 */
export default function Topbar({ title, description, onOpenSidebar, isDemo }) {
  return (
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-line">
      <div className="h-14 px-4 md:px-6 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button
            className="md:hidden shrink-0"
            onClick={onOpenSidebar}
            aria-label="Open navigation menu"
            aria-controls="app-sidebar"
          ><Menu size={18} aria-hidden="true" /></button>
          <div className="min-w-0">
            <Breadcrumbs />
            <div className="font-semibold text-[14px] text-ink truncate">{title}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isDemo && <span className="rounded border border-warn/30 bg-warn-bg px-2 py-1 text-[10px] font-semibold tracking-wide text-warn">DEMO MODE</span>}
          <NavLink
            to="/alerts"
            className="h-8 w-8 rounded-md border border-line flex items-center justify-center text-muted hover:text-ink hover:bg-panel focus-visible:outline focus-visible:outline-2 focus-visible:outline-navy"
            aria-label="View alerts"
          ><BellRing size={15} aria-hidden="true" /></NavLink>
        </div>
      </div>
    </header>
  )
}