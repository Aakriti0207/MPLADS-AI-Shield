import React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import AuthenticatedShell, { DEFAULT_SHELL_DESCRIPTION } from './AuthenticatedShell'
import { matchAppRoute } from '../../app/routes'

/**
 * Reusable application shell: persistent sidebar on desktop, a mobile
 * overlay sidebar toggled from the topbar, and the current page rendered
 * via <Outlet/>. Page title is derived from the centralized route config
 * so individual pages don't need to know about the shell.
 *
 * The actual sidebar/topbar markup lives in AuthenticatedShell (see that
 * file) so Projects.jsx can reuse it for authenticated visitors at the
 * public-reachable /projects route without duplicating this layout.
 */
export default function AppShell() {
  const location = useLocation()
  const current = matchAppRoute(location.pathname)
  const title = current?.title || 'MPLADS Insight'

  return (
    <AuthenticatedShell title={title} description={DEFAULT_SHELL_DESCRIPTION}>
      <Outlet />
    </AuthenticatedShell>
  )
}