import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, setUnauthorizedHandler, API_BASE } from '../api'
import { clearAuthToken, setAuthToken } from '../authToken'

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
  setUnauthorizedHandler(null)
})

afterEach(() => {
  localStorage.clear()
  setUnauthorizedHandler(null)
})

describe('apiFetch', () => {
  it('attaches Authorization: Bearer <token> when a token is stored', async () => {
    setAuthToken('my-jwt-123')
    global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))

    await apiFetch('/projects')

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const [url, options] = global.fetch.mock.calls[0]
    expect(url).toBe(`${API_BASE}/projects`)
    expect(options.headers.Authorization).toBe('Bearer my-jwt-123')
  })

  it('sends no Authorization header when no token is stored', async () => {
    clearAuthToken()
    global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))

    await apiFetch('/dashboard/stats')

    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBeUndefined()
  })

  it('preserves caller-supplied options (method, body, other headers) alongside the auth header', async () => {
    setAuthToken('my-jwt-123')
    global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))

    await apiFetch('/projects?skip=0&limit=50', {
      method: 'GET',
      headers: { 'X-Test': 'yes' },
    })

    const [url, options] = global.fetch.mock.calls[0]
    expect(url).toBe(`${API_BASE}/projects?skip=0&limit=50`)
    expect(options.method).toBe('GET')
    expect(options.headers['X-Test']).toBe('yes')
    expect(options.headers.Authorization).toBe('Bearer my-jwt-123')
  })

  it('calls the registered unauthorized handler on a 401 response', async () => {
    setAuthToken('expired-jwt')
    global.fetch = vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Could not validate credentials' }) }))

    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    const res = await apiFetch('/alerts')

    expect(handler).toHaveBeenCalledTimes(1)
    // The response is still returned to the caller -- apiFetch doesn't
    // swallow it, in case a page wants to show its own error state too.
    expect(res.status).toBe(401)
  })

  it('does not call the unauthorized handler on a successful response', async () => {
    setAuthToken('valid-jwt')
    global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ([]) }))

    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await apiFetch('/alerts')

    expect(handler).not.toHaveBeenCalled()
  })

  it('does nothing special on a 401 if no unauthorized handler is registered (no crash)', async () => {
    setAuthToken('expired-jwt')
    global.fetch = vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) }))

    await expect(apiFetch('/projects')).resolves.toMatchObject({ status: 401 })
  })
})