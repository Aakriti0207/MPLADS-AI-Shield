import React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import AuthenticatedShell, { DEFAULT_SHELL_DESCRIPTION } from './AuthenticatedShell'
import { matchAppRoute } from '../../app/routes'
import { pageTitleFor } from '../../lib/roles'
import { useAuth } from '../../context/AuthContext'

/**
 * Reusable application shell: persistent sidebar on desktop, a mobile
 * overlay sidebar toggled from the topbar, and the current page rendered
 * via <Outlet/>. Page title is derived from the centralized route config
 * so individual pages don't need to know about the shell. Titles are
 * role-aware (see lib/roles.js's PAGE_TITLE_BY_ROLE).
 *
 * The actual sidebar/topbar markup lives in AuthenticatedShell (see that
 * file) so Projects.jsx can reuse it for authenticated visitors at the
 * public-reachable /projects route without duplicating this layout.
 */
export default function AppShell() {
  const location = useLocation()
  const { role } = useAuth()
  const current = matchAppRoute(location.pathname)

  // The page is shared; only its heading is role-aware. An MP's
  // "AI Shield -- My Constituency" and a District Authority's
  // "AI Shield -- District Monitoring" are the SAME component reading
  // the SAME risk engine over differently-scoped records. The title is
  // the scope statement, never a hint that the analysis differs.
  const title = pageTitleFor(location.pathname, role, current?.title || 'MPLADS Insight')

  return (
    <AuthenticatedShell title={title} description={DEFAULT_SHELL_DESCRIPTION}>
      <Outlet />
    </AuthenticatedShell>
  )
}