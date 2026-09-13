import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

/**
 * Guards the authenticated app routes (dashboard/projects/alerts/etc).
 *
 * Reads `status` from the existing AuthContext (Phase 4) -- 'checking'
 * while the startup session check is in flight, then 'authenticated'
 * or 'unauthenticated'. Renders nothing route-specific itself; it just
 * decides whether to show a loading state, redirect to /login, or
 * render `children` (the actual protected page/layout).
 *
 * The redirect passes `state={{ from: location }}`, which Login.jsx
 * (Phase 3) already reads via `location.state?.from?.pathname` to
 * send the user back to the page they originally asked for.
 */
export default function ProtectedRoute({ children }) {
  const { status, isDemo } = useAuth()
  const location = useLocation()

  if (status === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center gap-2 text-muted">
        <Loader2 className="animate-spin" size={20} />
        <span className="text-sm">Checking your session…</span>
      </div>
    )
  }

  if (status === 'unauthenticated' && !isDemo) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return children
}