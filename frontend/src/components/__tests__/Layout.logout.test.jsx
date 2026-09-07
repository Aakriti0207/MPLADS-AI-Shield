import React from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Layout from '../Layout'
import ProtectedRoute from '../ProtectedRoute'
import { AuthProvider } from '../../context/AuthContext'
import { getAuthToken, setAuthToken } from '../../lib/authToken'

// Phase 6 Part 1: exercise the real "Sign out" button inside Layout
// (not just AuthContext.logout() in isolation) while sitting on a
// protected page, and confirm the whole path -- click -> context
// clears -> redirect -> route re-guarded -- actually works together.
function DashboardProbe() {
  return <div data-testid="dashboard-content">dashboard content</div>
}

function LoginProbe() {
  return <div data-testid="login-page">login page</div>
}

function renderApp() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<DashboardProbe />} />
          </Route>
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

describe('Logout via Layout "Sign out" while on a protected page', () => {
  it('clears the token, clears the session, and redirects to /login', async () => {
    setAuthToken('a-valid-session-token')
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, email: 'user@example.gov.in', role: 'Administrator', is_active: true, created_at: '2026-01-01T00:00:00Z' }),
    }))

    renderApp()

    // Confirm we actually landed on the protected page first (not
    // already redirected, not stuck loading).
    await waitFor(() => expect(screen.queryByTestId('dashboard-content')).not.toBeNull())
    expect(getAuthToken()).toBe('a-valid-session-token')

    await act(async () => {
      screen.getByText(/sign out/i).click()
    })

    // Redirected to /login, protected content gone, token cleared.
    await waitFor(() => expect(screen.queryByTestId('login-page')).not.toBeNull())
    expect(screen.queryByTestId('dashboard-content')).toBeNull()
    expect(getAuthToken()).toBeNull()
  })
})