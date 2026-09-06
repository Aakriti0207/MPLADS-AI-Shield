import React, { createContext, useContext, useEffect, useState } from 'react'
import { clearAuthToken, getAuthToken, setAuthToken } from '../lib/authToken'

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
 */

const API_BASE = 'http://127.0.0.1:8000'

const AuthContext = createContext(null)

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
  // 'checking' | 'authenticated' | 'unauthenticated'
  const [status, setStatus] = useState('checking')

  // On app startup: if a token is stored, verify it against the backend
  // before trusting it. Always resolves to a definite status -- never
  // leaves the app stuck on 'checking'.
  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
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
    setUser(null)
    setStatus('unauthenticated')
  }

  const value = {
    user,
    status,
    isAuthenticated: status === 'authenticated',
    isChecking: status === 'checking',
    login,
    logout,
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