import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/ui/Button'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'

export function ResetConfirmPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await unwrap(
        apiClient.POST('/auth/password-reset/confirm', {
          body: { token, new_password: password },
        }),
      )
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo restablecer la contraseña')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout title="Nueva contraseña">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="password">Contraseña nueva</Label>
          <Input
            id="password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={loading} className="mt-2 w-full">
          {loading ? 'Guardando...' : 'Restablecer contraseña'}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm">
        <Link to="/login" className="text-ink-secondary hover:text-ink">
          Volver a iniciar sesión
        </Link>
      </p>
    </AuthLayout>
  )
}
