import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { BarChart3, BellRing, FileText, FolderKanban, LayoutDashboard, LogOut, Map, ShieldAlert, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { appRoutes } from '../../app/routes'
import { useAuth } from '../../context/AuthContext'
import { NAV_BY_ROLE, ROLE_VIEW_LABEL, normalizeRole } from '../../lib/roles'

const NAV_ICONS = {
  Dashboard: LayoutDashboard,
  Projects: FolderKanban,
  'AI Shield': ShieldAlert,
  'Upload & Analyze': UploadCloud,
  Alerts: BellRing,
  Analytics: BarChart3,
  'Map View': Map,
  Reports: FileText,
}

/**
 * Institutional sidebar: brand mark, role-scoped navigation (which items
 * appear is driven by the REAL user.role returned from GET /auth/me --
 * see lib/roles.js), and the signed-in user + real role label + sign-out.
 */
export default function Sidebar({ open, onClose }) {
  const { logout, user, isDemo, demoRole, enterDemo } = useAuth()
  const navigate = useNavigate()

  const role = normalizeRole(user?.role)
  const allowedNav = NAV_BY_ROLE[role] || NAV_BY_ROLE.ministry
  const navEntries = appRoutes.filter(r => r.nav && allowedNav.includes(r.nav)).map(r => ({ label: r.nav, path: r.path }))

  function handleSignOut() {
    onClose?.()
    logout()
    navigate('/login')
  }

  function handleDemoRoleChange(event) {
    const nextRole = event.target.value
    if (enterDemo(nextRole)) navigate('/dashboard')
  }

  const identity = user?.full_name || user?.name || user?.email || 'Authorized user'

  return (
    <>
      <aside
        id="app-sidebar"
        aria-label="Main navigation"
        className={`fixed z-40 inset-y-0 left-0 w-[220px] bg-navy text-white flex flex-col transform transition-transform md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between gap-2.5 px-4 h-14 shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
          <NavLink to="/" className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}>
              <ShieldCheck size={15} aria-hidden="true" />
            </div>
            <div className="text-[12.5px] font-bold leading-tight truncate">MPLADS<br />AI SHIELD</div>
          </NavLink>
          <button onClick={onClose} className="md:hidden shrink-0" aria-label="Close navigation menu"><X size={18} aria-hidden="true" /></button>
        </div>

        <nav aria-label="Primary" className="flex-1 overflow-y-auto py-3">
          {navEntries.map(({ label, path }) => {
            const Icon = NAV_ICONS[label]
            return (
              <NavLink
                key={path}
                to={path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-medium border-l-[3px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-white ${
                    isActive
                      ? 'text-white'
                      : 'text-white/60 border-l-transparent hover:bg-white/10 hover:text-white/90'
                  }`
                }
                style={({ isActive }) =>
                  isActive
                    ? { backgroundColor: 'rgba(255,255,255,0.10)', borderLeftColor: '#6FA8DC' }
                    : undefined
                }
              >
                {Icon && <Icon size={15} aria-hidden="true" />}
                {label}
              </NavLink>
            )
          })}
        </nav>

        <div className="px-4 py-3 mx-3 mb-3 rounded-md" style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}>
          <div className="flex items-center gap-1.5 text-xs font-semibold"><ShieldCheck size={13} aria-hidden="true" /> AI Advisory Layer</div>
          <p className="text-[11px] text-white/65 mt-1.5 leading-4">Risk signals are advisory and support -- not replace -- authorized government review.</p>
        </div>

        <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.12)' }}>
          <div className="text-[10px] uppercase tracking-wide text-white/45">Signed in as</div>
          <div className="text-[12.5px] font-semibold truncate" title={identity}>{identity}</div>
          <div className="text-[11px] text-white/55 mb-2">{user?.role || ROLE_VIEW_LABEL[role]}</div>
          {isDemo && (
            <label className="block mb-2">
              <span className="sr-only">Switch demo role</span>
              <select
                value={demoRole || role}
                onChange={handleDemoRoleChange}
                className="w-full rounded border border-white/20 bg-white/10 px-2 py-1 text-[11px] text-white outline-none"
              >
                <option className="text-ink" value="ministry">Ministry / Admin</option>
                <option className="text-ink" value="state">State Nodal Authority</option>
                <option className="text-ink" value="district">District Authority</option>
                <option className="text-ink" value="mp">Member of Parliament</option>
              </select>
            </label>
          )}
          <button type="button" onClick={handleSignOut} className="flex items-center gap-1.5 text-xs text-white/70 hover:text-white">
            <LogOut size={13} aria-hidden="true" /> Sign out
          </button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={onClose} aria-hidden="true" />}
    </>
  )
}