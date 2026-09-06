/**
 * Minimal auth-token storage helper.
 *
 * Phase 3 scope: just get/set/clear around localStorage, under a single
 * key, so later phases (AuthContext, an Authorization-header interceptor,
 * logout) can all read/write the same place without re-inventing token
 * storage or scattering the storage key across files.
 *
 * Deliberately does NOT decode/validate the token, attach it to requests,
 * or manage any React state -- that belongs to later phases (Phase 5's
 * centralized auth system).
 */

const TOKEN_KEY = 'mplads_access_token'

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY)
}