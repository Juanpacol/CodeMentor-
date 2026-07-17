import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/ui/Button'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { ApiError } from '../../lib/api/client'
import { useAuth } from '../../hooks/useAuth'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await login(email, password)
      const from = (location.state as { from?: Location })?.from?.pathname
      const fallback = user.role === 'student' ? '/app' : '/app/docente'
      navigate(from ?? fallback, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

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
      <div className="mt-5 flex justify-between text-sm">
        <Link to="/recuperar" className="text-ink-secondary hover:text-ink">
          ¿Olvidaste tu contraseña?
        </Link>
        <Link to="/registro" className="text-primary hover:text-primary-hover">
          Crear cuenta
        </Link>
      </div>
    </AuthLayout>
  )
}
