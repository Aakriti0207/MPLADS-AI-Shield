import React from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from '../AuthContext'
import { getAuthToken, setAuthToken } from '../../lib/authToken'

// Small probe component that renders the context's current state as text,
// and exposes login/logout via clickable buttons -- lets these tests
// exercise the real provider through React, not by calling internals directly.
function Probe() {
  const { user, status, isAuthenticated, login, logout } = useAuth()
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="authed">{String(isAuthenticated)}</div>
      <div data-testid="user-email">{user ? user.email : 'none'}</div>
      <button onClick={() => login('test@example.gov.in', 'SecurePass123').catch(e => {
        document.getElementById('login-error').textContent = `${e.status}`
      })}>
        do-login
      </button>
      <div id="login-error" data-testid="login-error"></div>
      <button onClick={logout}>do-logout</button>
    </div>
  )
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('AuthProvider session restore on startup', () => {
  it('with no stored token, resolves straight to unauthenticated (never stuck checking)', async () => {
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))
    expect(screen.getByTestId('authed').textContent).toBe('false')
  })

  it('with a valid stored token, calls GET /auth/me and restores the user', async () => {
    setAuthToken('valid-token-123')
    global.fetch = vi.fn(async (url, opts) => {
      expect(url).toContain('/auth/me')
      expect(opts.headers.Authorization).toBe('Bearer valid-token-123')
      return {
        ok: true,
        status: 200,
        json: async () => ({ id: 1, email: 'restored@example.gov.in', role: 'Administrator', is_active: true, created_at: '2026-01-01T00:00:00Z' }),
      }
    })

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))
    expect(screen.getByTestId('user-email').textContent).toBe('restored@example.gov.in')
    expect(global.fetch).toHaveBeenCalledTimes(1)
  })

  it('with an invalid/expired stored token (401 from /auth/me), clears the token and logs out', async () => {
    setAuthToken('expired-token-456')
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Could not validate credentials' }),
    }))

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))
    expect(screen.getByTestId('user-email').textContent).toBe('none')
    expect(getAuthToken()).toBeNull()
  })

  it('when the backend is unreachable (network failure), does not clear the token but is unauthenticated for this session', async () => {
    setAuthToken('token-while-backend-down')
    global.fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))
    // Token intentionally left in storage -- see AuthContext.jsx comment.
    expect(getAuthToken()).toBe('token-while-backend-down')
  })
})

describe('login()', () => {
  it('on success: stores the token, fetches /auth/me, and becomes authenticated', async () => {
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/login')) {
        return { ok: true, status: 200, json: async () => ({ access_token: 'brand-new-token', token_type: 'bearer' }) }
      }
      if (url.endsWith('/auth/me')) {
        return { ok: true, status: 200, json: async () => ({ id: 2, email: 'test@example.gov.in', role: 'District Authority', is_active: true, created_at: '2026-01-01T00:00:00Z' }) }
      }
      throw new Error('unexpected url ' + url)
    })

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))

    await act(async () => {
      screen.getByText('do-login').click()
    })

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))
    expect(screen.getByTestId('user-email').textContent).toBe('test@example.gov.in')
    expect(getAuthToken()).toBe('brand-new-token')
  })

  it('on 401, throws with status 401, stores no token, and stays unauthenticated', async () => {
    global.fetch = vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Incorrect email or password.' }) }))

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))

    await act(async () => {
      screen.getByText('do-login').click()
    })

    await waitFor(() => expect(screen.getByTestId('login-error').textContent).toBe('401'))
    expect(screen.getByTestId('status').textContent).toBe('unauthenticated')
    expect(getAuthToken()).toBeNull()
  })
})

describe('logout()', () => {
  it('clears the token, clears the user, and sets status to unauthenticated', async () => {
    setAuthToken('some-token')
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ id: 3, email: 'logout.test@example.gov.in', role: 'Administrator', is_active: true, created_at: '2026-01-01T00:00:00Z' }),
    }))

    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))

    await act(async () => {
      screen.getByText('do-logout').click()
    })

    expect(screen.getByTestId('status').textContent).toBe('unauthenticated')
    expect(screen.getByTestId('user-email').textContent).toBe('none')
    expect(getAuthToken()).toBeNull()
  })
})