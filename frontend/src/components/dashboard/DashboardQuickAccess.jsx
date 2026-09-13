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

export default function DashboardQuickAccess() {
  return (
    <div className="card p-4">
      <div className="font-semibold text-[13.5px] text-ink mb-3">Quick access</div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
        {SHORTCUTS.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-2 rounded-md border border-line px-3 py-2.5 text-[12.5px] font-medium text-ink hover:border-navy hover:text-navy transition"
          >
            <Icon size={15} className="shrink-0 text-navy" />
            <span className="truncate">{label}</span>
            <ChevronRight size={13} className="ml-auto text-muted shrink-0" />
          </Link>
        ))}
      </div>
    </div>
  )
}