import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/ui/Button'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { useAuth } from '../../hooks/useAuth'

export function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<'student' | 'teacher'>('student')
  const [studentCode, setStudentCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await unwrap(
        apiClient.POST('/auth/register', {
          body: {
            email,
            password,
            full_name: fullName,
            role,
            student_code: studentCode || undefined,
          },
        }),
      )
      const user = await login(email, password)
      navigate(user.role === 'student' ? '/app' : '/app/docente', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo crear la cuenta')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout title="Crea tu cuenta" subtitle="Usa tu correo institucional o tu código de estudiante">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="full_name">Nombre completo</Label>
          <Input id="full_name" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
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
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <div>
          <Label htmlFor="role">Soy</Label>
          <Select id="role" value={role} onChange={(e) => setRole(e.target.value as 'student' | 'teacher')}>
            <option value="student">Estudiante</option>
            <option value="teacher">Docente</option>
          </Select>
        </div>
        {role === 'student' && (
          <div>
            <Label htmlFor="student_code">Código de estudiante (si tu correo no es institucional)</Label>
            <Input id="student_code" value={studentCode} onChange={(e) => setStudentCode(e.target.value)} />
          </div>
        )}
        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={loading} className="mt-2 w-full">
          {loading ? 'Creando cuenta...' : 'Crear cuenta gratis'}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm text-ink-secondary">
        ¿Ya tienes cuenta?{' '}
        <Link to="/login" className="text-primary hover:text-primary-hover">
          Inicia sesión
        </Link>
      </p>
    </AuthLayout>
  )
}
