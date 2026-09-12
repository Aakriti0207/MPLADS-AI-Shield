import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { BarChart3, BellRing, FileText, FolderKanban, LayoutDashboard, LogIn, Map, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { appRoutes } from '../../app/routes'
import { useAuth } from '../../context/AuthContext'

const NAV_ICONS = {
  Dashboard: LayoutDashboard,
  Projects: FolderKanban,
  'Upload & Analyze': UploadCloud,
  Alerts: BellRing,
  Analytics: BarChart3,
  'Map View': Map,
  Reports: FileText,
}

// Nav entries are derived from the centralized route config (app/routes.jsx)
// rather than a separate hardcoded list, so the sidebar can't drift out of
// sync with the routes it links to.
const navEntries = appRoutes.filter(r => r.nav).map(r => ({ label: r.nav, path: r.path }))

/**
 * Application sidebar: brand mark, primary navigation (active state derived
 * from the current route), advisory note, and sign-out. Persistent on
 * desktop; slides in as an overlay on smaller screens via `open`/`onClose`.
 */
export default function Sidebar({ open, onClose }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleSignOut() {
    onClose?.()
    logout()
    navigate('/login')
  }

  return (
    <>
      <aside
        id="app-sidebar"
        aria-label="Main navigation"
        className={`fixed z-40 inset-y-0 left-0 w-64 bg-navy text-white p-5 transform transition-transform md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between mb-8">
          <NavLink to="/" className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-white/10 flex items-center justify-center"><ShieldCheck size={22} aria-hidden="true" /></div>
            <div><div className="font-bold leading-tight">MPLADS Insight</div><div className="text-[10px] text-blue-200">Monitoring & Risk Intelligence</div></div>
          </NavLink>
          <button onClick={onClose} className="md:hidden" aria-label="Close navigation menu"><X aria-hidden="true" /></button>
        </div>

        <div className="eyebrow !text-blue-200 mb-3">Workspace</div>
        <nav aria-label="Primary" className="space-y-1">
          {navEntries.map(({ label, path }) => {
            const Icon = NAV_ICONS[label]
            return (
              <NavLink
                key={path}
                to={path}
                onClick={onClose}
                className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${isActive ? 'bg-white text-navy font-semibold' : 'text-blue-100 hover:bg-white/10'}`}
              >
                {Icon && <Icon size={18} aria-hidden="true" />}
                {label}
              </NavLink>
            )
          })}
        </nav>

        <div className="mt-8 rounded-2xl bg-white/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={16} aria-hidden="true" /> AI Advisory Layer</div>
          <p className="text-xs text-blue-100 mt-2 leading-5">Risk signals are advisory and support—not replace—authorized government review.</p>
        </div>

        <button
          type="button"
          onClick={handleSignOut}
          className="absolute bottom-5 left-5 right-5 btn bg-white/10 hover:bg-white/20 text-white"
        ><LogIn size={16} aria-hidden="true" /> Sign out</button>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={onClose} aria-hidden="true" />}
    </>
  )
}
