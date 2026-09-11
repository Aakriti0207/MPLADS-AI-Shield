/**
 * Centralized, authenticated fetch wrapper.
 *
 * Phase 5 scope. Reuses the token storage already built in Phase 3
 * (lib/authToken.js) rather than introducing a second place that
 * reads/writes the JWT -- this module never touches localStorage
 * directly. Every call automatically attaches
 * `Authorization: Bearer <token>` when a token is present, so pages
 * calling protected endpoints don't build that header themselves.
 *
 * On a 401 response (token missing/invalid/expired), this module
 * notifies whoever has registered as the "unauthorized handler". In
 * practice, AuthContext registers its own `logout()` here (see the
 * effect added to AuthContext.jsx), so an expired token clears auth
 * state through the exact same path a manual "Sign out" click does --
 * no separate/duplicate state-clearing logic. This module deliberately
 * does NOT import AuthContext or call React hooks directly, to avoid a
 * circular dependency between the fetch layer and the auth layer.
 */

import { getAuthToken } from './authToken'

export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

let unauthorizedHandler = null

/**
 * Register a callback to run whenever any apiFetch() call gets a 401.
 * Called once by AuthContext on mount. Pass `null` to unregister.
 */
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn
}

/**
 * fetch() wrapper for authenticated backend calls.
 *
 * - `path` is the route only (e.g. '/projects'), not the full URL.
 * - Attaches `Authorization: Bearer <token>` automatically when a
 *   token is stored; sends no Authorization header otherwise.
 * - On a 401 response, invokes the registered unauthorized handler
 *   (if any) in addition to still returning the response, so callers
 *   can also show their own inline error state if they want to.
 * - Everything else (method, body, query string, response shape) is
 *   entirely up to the caller, exactly like a normal fetch() call.
 */
export async function apiFetch(path, options = {}) {
  const token = getAuthToken()
  const headers = { ...(options.headers || {}) }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401 && unauthorizedHandler) {
    unauthorizedHandler()
  }

  return res
}