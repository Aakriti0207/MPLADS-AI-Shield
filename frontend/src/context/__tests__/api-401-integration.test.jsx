import React from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from '../AuthContext'
import { apiFetch } from '../../lib/api'
import { getAuthToken, setAuthToken } from '../../lib/authToken'

// Simulates a real protected page: once logged in, it calls a protected
// endpoint through the same apiFetch() every page uses. If that call
// comes back 401, AuthContext should flip to 'unauthenticated' through
// the handler registered in AuthContext.jsx (Phase 5 Part 3) -- not
// through any separate/duplicate logic in this test.
function ProtectedPageProbe() {
  const { status } = useAuth()
  return (
    <div>
      <div data-testid="status">{status}</div>
      <button onClick={() => apiFetch('/projects')}>call-protected-api</button>
    </div>
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

describe('apiFetch 401 -> AuthContext integration', () => {
  it('a 401 from a protected API call clears the real AuthContext session (via the registered logout)', async () => {
    setAuthToken('will-expire-mid-session')
    // First call (AuthContext's own startup /auth/me check) succeeds;
    // the later apiFetch('/projects') call from the page returns 401.
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/me')) {
        return { ok: true, status: 200, json: async () => ({ id: 1, email: 'user@example.gov.in', role: 'Administrator', is_active: true, created_at: '2026-01-01T00:00:00Z' }) }
      }
      return { ok: false, status: 401, json: async () => ({ detail: 'Could not validate credentials' }) }
    })

    render(
      <AuthProvider>
        <ProtectedPageProbe />
      </AuthProvider>
    )

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))

    await act(async () => {
      screen.getByText('call-protected-api').click()
    })

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))
    expect(getAuthToken()).toBeNull()
  })
})