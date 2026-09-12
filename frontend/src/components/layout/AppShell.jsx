import React, { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { matchAppRoute } from '../../app/routes'

const DEFAULT_DESCRIPTION = 'Public-sector project monitoring workspace'

/**
 * Reusable application shell: persistent sidebar on desktop, a mobile
 * overlay sidebar toggled from the topbar, and the current page rendered
 * via <Outlet/>. Page title is derived from the centralized route config
 * so individual pages don't need to know about the shell.
 */
export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const current = matchAppRoute(location.pathname)
  const title = current?.title || 'MPLADS Insight'

  return (
    <div className="min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="md:ml-64">
        <Topbar
          title={title}
          description={DEFAULT_DESCRIPTION}
          onOpenSidebar={() => setSidebarOpen(true)}
        />
        <Outlet />
      </main>
    </div>
  )
}
