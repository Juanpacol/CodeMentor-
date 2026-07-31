import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/ui/Button'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { ApiError } from '../../lib/api/client'
import { useAuth } from '../../hooks/useAuth'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
          }) => void
          renderButton: (parent: HTMLElement, options: { width?: number }) => void
        }
      }
    }
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export function LoginPage() {
  const { login, loginWithGoogle } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const googleButtonRef = useRef<HTMLDivElement>(null)

  function goToRoleHome(user: { role: string }) {
    const from = (location.state as { from?: Location })?.from?.pathname
    const fallback = user.role === 'student' ? '/app' : '/app/docente'
    navigate(from ?? fallback, { replace: true })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await login(email, password)
      goToRoleHome(user)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleButtonRef.current) return

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = () => {
      if (!window.google || !googleButtonRef.current) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => {
          setError(null)
          loginWithGoogle(response.credential)
            .then(goToRoleHome)
            .catch((err: unknown) => {
              setError(err instanceof ApiError ? err.detail : 'No se pudo iniciar sesión con Google')
            })
        },
      })
      window.google.accounts.id.renderButton(googleButtonRef.current, { width: 320 })
    }
    document.body.appendChild(script)
    return () => {
      document.body.removeChild(script)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <AuthLayout title="Inicia sesión" subtitle="Continúa donde lo dejaste">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="email">Correo</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>
        <div>
          <Label htmlFor="password">Contraseña</Label>
          <Input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={loading} className="mt-2 w-full">
          {loading ? 'Ingresando...' : 'Iniciar sesión'}
        </Button>
      </form>
      {GOOGLE_CLIENT_ID && (
        <div className="mt-4 flex justify-center">
          <div ref={googleButtonRef} />
        </div>
      )}
      <div className="mt-5 flex justify-between text-sm">
        <Link to="/recuperar" className="text-ink-secondary hover:text-ink">
          ¿Olvidaste tu contraseña?
        </Link>
        <Link to="/registro" className="text-primary-ink hover:text-primary-hover">
          Crear cuenta
        </Link>
      </div>
    </AuthLayout>
  )
}
