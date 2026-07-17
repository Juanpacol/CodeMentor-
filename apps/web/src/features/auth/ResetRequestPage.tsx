import { useState } from 'react'
import { Link } from 'react-router-dom'

import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Input, Label } from '../../components/ui/Input'
import { apiClient, unwrap } from '../../lib/api/client'

export function ResetRequestPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await unwrap(apiClient.POST('/auth/password-reset/request', { body: { email } }))
    } finally {
      setLoading(false)
      // La API siempre responde igual (nunca revela si el correo existe).
      setSent(true)
    }
  }

  return (
    <AuthLayout title="Recuperar contraseña">
      {sent ? (
        <Callout tone="success">
          Si el correo existe en nuestro sistema, recibirás instrucciones para restablecer tu
          contraseña.
        </Callout>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="email">Correo</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={loading} className="mt-2 w-full">
            {loading ? 'Enviando...' : 'Enviar instrucciones'}
          </Button>
        </form>
      )}
      <p className="mt-5 text-center text-sm">
        <Link to="/login" className="text-ink-secondary hover:text-ink">
          Volver a iniciar sesión
        </Link>
      </p>
    </AuthLayout>
  )
}
