import React, { createContext, useContext, useEffect, useState } from 'react'
import { clearAuthToken, getAuthToken, setAuthToken } from '../lib/authToken'
import { API_BASE, setUnauthorizedHandler } from '../lib/api'
import { clearDemoRole, getDemoRole, isDemoModeEnabled, setDemoRole } from '../lib/demoSession'
import { ROLE, ROLE_VIEW_LABEL, fallbackPermissions, normalizeRole } from '../lib/roles'

/**
 * Global authentication state.
 *
 * No existing state-management library (Context, Redux, Zustand, ...) was
 * found in this project (see package.json) -- this is a lightweight
 * Context + useState implementation, matching the project's existing
 * "plain React, no extra state library" architecture.
 *
 * `user` always comes from the backend (GET /auth/me), never fabricated
 * on the frontend -- the JWT itself is never decoded/trusted client-side
 * for this purpose.
 *
 * RBAC
 * ----
 * /auth/me now also returns the RESOLVED role identity: `role_key`, the
 * jurisdiction (`scope`) the backend will enforce, and the `permissions`
 * that role holds. Those are exposed here as `role`, `scope` and `can()`,
 * and every role-aware decision in the UI reads them rather than
 * re-deriving anything from the role string.
 *
 * The consequence worth stating plainly: the UI cannot grant itself a
 * capability. If the backend did not list a permission, `can()` is
 * false, the nav entry is absent and the route redirects -- and if all
 * of that were bypassed anyway, the API would still refuse.
 */

const AuthContext = createContext(null)

// Demo mode stores a short persona key in sessionStorage; map it onto
// the canonical role keys so a demo preview renders the same dashboard a
// real account of that role would. Demo sessions get no real data
// scoping -- they have no backend account and fall back to the public
// endpoints, which is why the demo badge stays visible throughout.
const DEMO_ROLE_KEYS = {
  ministry: 'MINISTRY',
  state: 'STATE_NODAL',
  district: 'DISTRICT_AUTHORITY',
  mp: 'MP',
}

/** Thrown by login() so callers (Login.jsx) can branch on the HTTP
 * status the same way they did with the raw fetch in Phase 3.
 * status === null means the request never got a response (network /
 * backend-unreachable), not a rejection from the server. */
class AuthRequestError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'AuthRequestError'
    this.status = status
  }
}

/** GET /auth/me with the given token. Resolves with the safe user
 * profile, or throws an Error with `.status` set to the HTTP status
 * (e.g. 401) if the token was rejected, or `.status === null` if the
 * request couldn't reach the server at all. */
async function fetchCurrentUser(token) {
  let res
  try {
    res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch (err) {
    const networkError = new Error('Could not reach the server.')
    networkError.status = null
    throw networkError
  }

  if (!res.ok) {
    const invalidSession = new Error('Session is invalid or expired.')
    invalidSession.status = res.status
    throw invalidSession
  }

  return res.json()
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [demoRole, setDemoRoleState] = useState(() => getDemoRole())
  // 'checking' | 'authenticated' | 'unauthenticated'
  const [status, setStatus] = useState('checking')

  // On app startup: if a token is stored, verify it against the backend
  // before trusting it. Always resolves to a definite status -- never
  // leaves the app stuck on 'checking'.
  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      const storedDemoRole = getDemoRole()
      if (storedDemoRole) {
        if (!cancelled) {
          setDemoRoleState(storedDemoRole)
          setUser({
            email: 'demo@mplads-ai-shield.local',
            role: storedDemoRole,
            role_key: DEMO_ROLE_KEYS[storedDemoRole] || null,
            is_demo: true,
          })
          setStatus('authenticated')
        }
        return
      }
      const token = getAuthToken()
      if (!token) {
        if (!cancelled) setStatus('unauthenticated')
        return
      }

      try {
        const me = await fetchCurrentUser(token)
        if (cancelled) return
        setUser(me)
        setStatus('authenticated')
      } catch (err) {
        if (cancelled) return
        // A real response from the server (401, etc.) means the token
        // itself is invalid/expired -- clear it. A network failure
        // (status === null, backend unreachable) does NOT prove the
        // token is bad, so it's left in storage in case the backend
        // comes back; the user just isn't treated as logged in for
        // this session load.
        if (err.status !== null) {
          clearAuthToken()
        }
        setUser(null)
        setStatus('unauthenticated')
      }
    }

    restoreSession()
    return () => {
      cancelled = true
    }
  }, [])

  async function login(email, password) {
    let res
    try {
      res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
    } catch (err) {
      throw new AuthRequestError('Could not reach the server.', null)
    }

    if (!res.ok) {
      throw new AuthRequestError('Login failed.', res.status)
    }

    const data = await res.json()
    setAuthToken(data.access_token)

    try {
      const me = await fetchCurrentUser(data.access_token)
      setUser(me)
      setStatus('authenticated')
    } catch (err) {
      // Login succeeded but the immediate follow-up /auth/me failed --
      // don't leave the app claiming a session that isn't verified.
      clearAuthToken()
      setUser(null)
      setStatus('unauthenticated')
      throw new AuthRequestError('Could not verify session after login.', err.status ?? null)
    }
  }

  function logout() {
    clearAuthToken()
    clearDemoRole()
    setDemoRoleState(null)
    setUser(null)
    setStatus('unauthenticated')
  }

  function enterDemo(role) {
    if (!isDemoModeEnabled() || !setDemoRole(role)) return false
    clearAuthToken()
    setDemoRoleState(role)
    setUser({
      email: 'demo@mplads-ai-shield.local',
      role,
      role_key: DEMO_ROLE_KEYS[role] || null,
      is_demo: true,
    })
    setStatus('authenticated')
    return true
  }

  // Phase 5: whenever any authenticated request made through
  // lib/api.js's apiFetch() gets a 401 (token invalid/expired), route
  // it through this exact same logout() -- not a separate/duplicate
  // "clear auth" implementation. ProtectedRoute then reacts to the
  // resulting status change and redirects to /login on its own; no
  // navigation call is made from here.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (!getDemoRole()) logout()
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  // ---------------------------------------------------------------
  // Resolved RBAC identity
  // ---------------------------------------------------------------

  const role = normalizeRole(user)

  const permissions = Array.isArray(user?.permissions) ? user.permissions : []

  const scope = user?.scope || null

  // A demo session has no backend account, and an older backend may not
  // send `permissions` at all. In both cases fall back to the role's
  // known permission set (lib/roles.js mirrors app/rbac.py) rather than
  // denying everything.
  //
  // Failing open here is deliberate and costs nothing: the backend is
  // the authorization boundary and re-checks every request regardless,
  // so a missing field cannot grant real access -- but failing CLOSED
  // would lock a legitimate officer out of the whole application during
  // a rollout where the frontend ships ahead of the backend.
  //
  // Demo sessions additionally never get the write/upload/manage
  // permissions, because those genuinely require a real account.
  const DEMO_EXCLUDED = ['UPLOAD_DATA', 'MANAGE_USERS']

  const effectivePermissions =
    permissions.length > 0
      ? permissions
      : demoRole
        ? fallbackPermissions(role).filter(p => !DEMO_EXCLUDED.includes(p))
        : fallbackPermissions(role)

  function can(permission) {
    if (!permission) return true
    return effectivePermissions.includes(permission)
  }

  const value = {
    user,
    demoRole,
    isDemo: Boolean(demoRole),
    demoModeEnabled: isDemoModeEnabled(),
    status,
    isAuthenticated: status === 'authenticated',
    isChecking: status === 'checking',
    login,
    enterDemo,
    logout,

    // --- RBAC ----------------------------------------------------
    role,
    roleLabel: user?.role_label || ROLE_VIEW_LABEL[role] || user?.role || '',
    rawRole: user?.role || '',
    displayName: user?.full_name || user?.name || user?.email || 'Authorized user',
    dashboard: user?.dashboard || null,
    permissions: effectivePermissions,
    can,
    scope,
    scopeAvailable: user?.scope_available !== false && role !== ROLE.UNSCOPED,
    emptyStateMessage: user?.empty_state_message || null,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}