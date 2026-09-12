import React from 'react'
import { Link } from 'react-router-dom'
import { BarChart3, BellRing, ChevronRight, FileText, FolderKanban, MapPinned } from 'lucide-react'

const SHORTCUTS = [
  { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/alerts', label: 'Alerts', icon: BellRing },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/map', label: 'Map view', icon: MapPinned },
  { to: '/reports', label: 'Reports', icon: FileText },
]

/**
 * Restrained navigation shortcuts to related workspaces. Deliberately
 * link-only -- this is not a second sidebar and carries no fetched data.
 */
export default function DashboardQuickAccess() {
  return (
    <div className="card p-5">
      <div className="font-bold text-lg mb-3">Quick access</div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {SHORTCUTS.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-2.5 rounded-xl border border-slate-200 px-3.5 py-3 text-sm font-semibold text-slate-700 hover:border-navy hover:text-navy transition"
          >
            <Icon size={17} className="shrink-0 text-navy" />
            <span className="truncate">{label}</span>
            <ChevronRight size={14} className="ml-auto text-slate-300 shrink-0" />
          </Link>
        ))}
      </div>
    </div>
  )
}
