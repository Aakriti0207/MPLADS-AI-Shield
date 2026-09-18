import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2, ShieldAlert } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ROUTE_PERMISSIONS } from '../lib/roles'

/**
 * Guards the authenticated app routes (dashboard/projects/alerts/etc).
 *
 * Two independent checks, in order:
 *
 *   1. Authentication -- 'checking' shows a spinner, 'unauthenticated'
 *      redirects to /login carrying `state={{ from: location }}` so
 *      Login.jsx can return the user to where they were headed. This is
 *      unchanged from before.
 *
 *   2. Authorization -- if the route requires a permission this account
 *      does not hold (per the backend's own permission list, delivered
 *      by GET /auth/me), the route is refused. Direct URL entry is
 *      therefore blocked, not merely hidden from the sidebar.
 *
 * The refusal renders a message rather than silently redirecting,
 * because an officer who types /upload deserves to be told they lack
 * the permission rather than being bounced somewhere with no reason.
 *
 * This is a usability layer, NOT the security boundary. Every protected
 * endpoint re-authorizes server-side, so bypassing this component in a
 * browser console gains the caller nothing but a 401/403 from the API.
 */
export default function ProtectedRoute({ children, permission }) {
  const { status, isDemo, can } = useAuth()
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

  // An explicit `permission` prop wins; otherwise fall back to the
  // central route/permission map, so a newly added route cannot
  // accidentally ship ungated.
  const required = permission ?? ROUTE_PERMISSIONS[location.pathname]

  if (required && !can(required)) {
    return <PermissionDenied />
  }

  return children
}

function PermissionDenied() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="card max-w-md w-full p-6 text-center">
        <div className="flex justify-center mb-3">
          <div className="h-10 w-10 rounded-full bg-panel flex items-center justify-center">
            <ShieldAlert size={18} className="text-muted" aria-hidden="true" />
          </div>
        </div>
        <h1 className="text-[15px] font-semibold text-ink">Access not permitted</h1>
        <p className="text-[13px] text-muted mt-1.5">
          You don&apos;t have permission to access this resource.
        </p>
        <p className="text-[12px] text-muted mt-3">
          If you believe this is incorrect, contact the Ministry administrator to
          review the jurisdiction assigned to your account.
        </p>
      </div>
    </div>
  )
}