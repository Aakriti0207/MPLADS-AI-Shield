import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { BarChart3, BellRing, ClipboardCheck, FileText, FolderKanban, LayoutDashboard, LogOut, Map, Building2, ShieldAlert, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { NAV_BY_ROLE, ROLE, ROLE_VIEW_LABEL, scopeDescriptor } from '../../lib/roles'

const NAV_ICONS = {
  Dashboard: LayoutDashboard,
  Overview: LayoutDashboard,
  Projects: FolderKanban,
  'My Projects': FolderKanban,
  'State Projects': FolderKanban,
  'District Projects': FolderKanban,
  'District Monitoring': Building2,
  'AI Shield': ShieldAlert,
  'Upload & Analyze': UploadCloud,
  Alerts: BellRing,
  'Priority Alerts': BellRing,
  'Review Queue': ClipboardCheck,
  Analytics: BarChart3,
  'Map View': Map,
  Reports: FileText,
}

/**
 * Institutional sidebar: brand mark, role-scoped navigation, and the
 * signed-in officer's identity, role and jurisdiction.
 *
 * Navigation is built from two backend-supplied facts: the resolved
 * role (which decides the menu and its labels -- an MP's "My Projects"
 * and a State officer's "State Projects" are the same scoped route) and
 * the permission list (which decides whether each entry appears at
 * all). Nothing here is inferred from the role string locally.
 *
 * Hiding a nav entry is convenience, not authorization. ProtectedRoute
 * blocks direct URL entry, and the API refuses regardless.
 */
export default function Sidebar({ open, onClose }) {
  const {
    logout, user, isDemo, demoRole, enterDemo,
    role, roleLabel, displayName, scope, can,
  } = useAuth()
  const navigate = useNavigate()

  const entries = (NAV_BY_ROLE[role] || NAV_BY_ROLE[ROLE.UNSCOPED]).filter(
    entry => can(entry.permission),
  )

  const descriptor = scopeDescriptor(scope)

  function handleSignOut() {
    onClose?.()
    logout()
    navigate('/login')
  }

  function handleDemoRoleChange(event) {
    const nextRole = event.target.value
    if (enterDemo(nextRole)) navigate('/dashboard')
  }

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

        {/* Role header -- who is signed in, acting as what, over where.
            Placed above the nav so the jurisdiction is read before any
            figure on the page is. */}
        <div className="px-4 py-3 shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
          <div className="text-[12.5px] font-semibold truncate" title={displayName}>{displayName}</div>
          <div className="text-[11px] text-white/70 leading-4">{roleLabel || ROLE_VIEW_LABEL[role]}</div>
          {descriptor && (
            <div className="text-[11px] text-white/55 leading-4 truncate" title={descriptor}>{descriptor}</div>
          )}
          {role !== ROLE.UNSCOPED && !descriptor && scope?.type === 'none' && (
            <div className="text-[11px] text-white/55 leading-4">No jurisdiction assigned</div>
          )}
        </div>

        <nav aria-label="Primary" className="flex-1 overflow-y-auto py-3">
          {entries.map(({ label, path }) => {
            const Icon = NAV_ICONS[label]
            return (
              <NavLink
                key={`${path}-${label}`}
                to={path}
                onClick={onClose}
                end={!path.includes('#')}
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
          <div className="text-[11px] text-white/55 mb-2 truncate" title={user?.email}>{user?.email}</div>
          {isDemo && (
            <label className="block mb-2">
              <span className="sr-only">Switch demo role</span>
              <select
                value={demoRole || ''}
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