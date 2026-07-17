import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { apiClient, unwrap } from '../lib/api/client'
import type { components } from '../lib/api/schema'
import { clearTokens, getAccessToken, setTokens } from '../lib/api/tokens'

type UserOut = components['schemas']['UserOut']

type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

interface AuthContextValue {
  user: UserOut | null
  status: AuthStatus
  login: (email: string, password: string) => Promise<UserOut>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  const loadUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      setStatus('anonymous')
      return
    }
    try {
      const me = await unwrap(apiClient.GET('/users/me'))
      setUser(me)
      setStatus('authenticated')
    } catch {
      clearTokens()
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  useEffect(() => {
    void loadUser()
  }, [loadUser])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await unwrap(
      apiClient.POST('/auth/login', { body: { email, password } }),
    )
    setTokens(tokens.access_token, tokens.refresh_token)
    const me = await unwrap(apiClient.GET('/users/me'))
    setUser(me)
    setStatus('authenticated')
    return me
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(
    () => ({ user, status, login, logout, refreshUser: loadUser }),
    [user, status, login, logout, loadUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
