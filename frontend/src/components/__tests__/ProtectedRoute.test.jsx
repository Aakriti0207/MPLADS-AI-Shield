import React from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProtectedRoute from '../ProtectedRoute'
import { AuthProvider } from '../../context/AuthContext'
import { setAuthToken } from '../../lib/authToken'

// Minimal stand-ins for the real pages/Login -- these tests only care
// about ProtectedRoute's own behavior (loading/redirect/render), not
// about what any particular protected page renders.
function ProtectedProbe() {
  return <div data-testid="protected-content">secret dashboard</div>
}

function LoginProbe() {
  const location = useLocation()
  return (
    <div>
      <div data-testid="login-page">login page</div>
      <div data-testid="redirect-from">{location.state?.from?.pathname || 'none'}</div>
    </div>
  )
}

function renderAtPath(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <ProtectedProbe />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
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

describe('ProtectedRoute', () => {
  it('shows a loading state (not the protected content) while the session check is in flight', async () => {
    // Never resolves during this test -- keeps AuthContext in 'checking'.
    setAuthToken('some-token')
    global.fetch = vi.fn(() => new Promise(() => {}))

    renderAtPath('/dashboard')

    expect(screen.getByText(/checking your session/i)).toBeTruthy()
    expect(screen.queryByTestId('protected-content')).toBeNull()
    expect(screen.queryByTestId('login-page')).toBeNull()
  })

  it('with no token, redirects an unauthenticated visitor to /login', async () => {
    renderAtPath('/dashboard')

    await waitFor(() => expect(screen.queryByTestId('login-page')).not.toBeNull())
    expect(screen.queryByTestId('protected-content')).toBeNull()
  })

  it('with a valid stored token, renders the protected content (no redirect)', async () => {
    setAuthToken('valid-token')
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, email: 'user@example.gov.in', role: 'Administrator', is_active: true, created_at: '2026-01-01T00:00:00Z' }),
    }))

    renderAtPath('/dashboard')

    await waitFor(() => expect(screen.queryByTestId('protected-content')).not.toBeNull())
    expect(screen.queryByTestId('login-page')).toBeNull()
  })

  it('with an invalid/expired token, redirects to /login instead of rendering protected content', async () => {
    setAuthToken('expired-token')
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Could not validate credentials' }),
    }))

    renderAtPath('/dashboard')

    await waitFor(() => expect(screen.queryByTestId('login-page')).not.toBeNull())
    expect(screen.queryByTestId('protected-content')).toBeNull()
  })

  it('preserves the originally requested path so Login can send the user back after signing in', async () => {
    renderAtPath('/dashboard')

    await waitFor(() => expect(screen.queryByTestId('login-page')).not.toBeNull())
    expect(screen.getByTestId('redirect-from').textContent).toBe('/dashboard')
  })
})