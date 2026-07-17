import createClient from 'openapi-fetch'

import type { paths } from './schema'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './tokens'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

/** Evita carreras de refresh: si dos peticiones reciben 401 a la vez, solo
 * la primera dispara `/auth/refresh` — la API rota ambos tokens en cada
 * refresh, así que dos refresh concurrentes invalidarían el par del otro. */
let refreshPromise: Promise<boolean> | null = null

async function refreshTokens(): Promise<boolean> {
  const refresh_token = getRefreshToken()
  if (!refresh_token) return false

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token }),
        })
        if (!res.ok) return false
        const body = (await res.json()) as { access_token: string; refresh_token: string }
        setTokens(body.access_token, body.refresh_token)
        return true
      } catch {
        return false
      } finally {
        refreshPromise = null
      }
    })()
  }
  return refreshPromise
}

export const apiClient = createClient<paths>({ baseUrl: API_URL })

const RETRY_HEADER = 'x-logica-retried'

apiClient.use({
  onRequest({ request }) {
    const token = getAccessToken()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
  async onResponse({ request, response }) {
    if (response.status !== 401 || request.headers.has(RETRY_HEADER)) {
      return response
    }

    const refreshed = await refreshTokens()
    if (!refreshed) {
      clearTokens()
      return response
    }

    const retryRequest = new Request(request, {
      headers: new Headers(request.headers),
    })
    retryRequest.headers.set(RETRY_HEADER, '1')
    retryRequest.headers.set('Authorization', `Bearer ${getAccessToken()}`)
    return fetch(retryRequest)
  },
})

/** Extrae el `detail` en español que la API ya devuelve en cada error de
 * dominio ({"detail": "..."}) y lo empaqueta como ApiError tipado. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; response: Response; error?: unknown }>,
): Promise<T> {
  const { data, response, error } = await promise
  if (response.ok && data !== undefined) return data
  const detail =
    error && typeof error === 'object' && 'detail' in error
      ? String((error as { detail: unknown }).detail)
      : `Error inesperado (${response.status})`
  throw new ApiError(response.status, detail)
}

export function isAiUnavailable(err: unknown): err is ApiError {
  return err instanceof ApiError && err.status === 503
}
