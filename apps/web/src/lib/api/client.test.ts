import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearTokens, setTokens } from './tokens'

describe('auth refresh middleware', () => {
  beforeEach(() => {
    clearTokens()
    vi.resetModules()
    vi.unstubAllGlobals()
  })

  it('retries the original request once after a successful refresh, using the new token', async () => {
    setTokens('expired-access', 'valid-refresh')

    let loginCalls = 0
    const fetchMock = vi.fn(async (input: Request | string) => {
      const url = typeof input === 'string' ? input : input.url
      if (url.includes('/auth/refresh')) {
        return new Response(
          JSON.stringify({ access_token: 'new-access', refresh_token: 'new-refresh' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      if (url.includes('/users/me')) {
        loginCalls += 1
        const authHeader =
          typeof input === 'string' ? null : input.headers.get('Authorization')
        if (authHeader === 'Bearer expired-access') {
          return new Response(JSON.stringify({ detail: 'No autenticado' }), { status: 401 })
        }
        return new Response(JSON.stringify({ id: '1', role: 'student' }), { status: 200 })
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { apiClient } = await import('./client')
    const result = await apiClient.GET('/users/me')

    expect(result.response.status).toBe(200)
    expect(loginCalls).toBe(2) // 401 original + retry with new token
    const refreshCalls = fetchMock.mock.calls.filter((call) => {
      const [input] = call
      const url = typeof input === 'string' ? input : (input as Request).url
      return url.includes('/auth/refresh')
    })
    expect(refreshCalls).toHaveLength(1)
  })

  it('clears tokens and gives up when refresh itself fails', async () => {
    setTokens('expired-access', 'invalid-refresh')

    const fetchMock = vi.fn(async (input: Request | string) => {
      const url = typeof input === 'string' ? input : input.url
      if (url.includes('/auth/refresh')) {
        return new Response(JSON.stringify({ detail: 'Token inválido' }), { status: 401 })
      }
      return new Response(JSON.stringify({ detail: 'No autenticado' }), { status: 401 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { apiClient } = await import('./client')
    const { getAccessToken } = await import('./tokens')

    const result = await apiClient.GET('/users/me')

    expect(result.response.status).toBe(401)
    expect(getAccessToken()).toBeNull()
  })
})
