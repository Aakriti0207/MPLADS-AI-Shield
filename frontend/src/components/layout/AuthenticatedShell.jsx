import React, { useState } from 'react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useAuth } from '../../context/AuthContext'

export const DEFAULT_SHELL_DESCRIPTION = 'Public-sector project monitoring workspace'

/**
 * Shared authenticated-shell chrome: persistent sidebar on desktop, a
 * mobile overlay sidebar toggled from the topbar, and whatever page
 * content is passed as `children`.
 *
 * Originally this markup lived only inside AppShell.jsx (rendered via
 * <Outlet/> for every route in app/routes.jsx behind ProtectedRoute).
 * Phase 4 pulled it out into its own component so Projects.jsx -- which
 * now has to render for BOTH anonymous and authenticated visitors at the
 * same /projects URL, and therefore can't live inside the
 * ProtectedRoute-wrapped route tree -- can reuse the exact same
 * sidebar/topbar chrome for authenticated visitors instead of
 * duplicating it. AppShell.jsx below is unchanged in behavior; it just
 * delegates to this component now.
 */
export default function AuthenticatedShell({ title, description = DEFAULT_SHELL_DESCRIPTION, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { isDemo } = useAuth()

  return (
    <div className="min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="md:ml-[220px]">
        <Topbar
          title={title}
          description={description}
          isDemo={isDemo}
          onOpenSidebar={() => setSidebarOpen(true)}
        />
        {children}
      </main>
    </div>
  )
}