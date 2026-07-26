import { Navigate, Outlet, useLocation } from 'react-router'

import { Spinner } from '../ui/Spinner'
import { useAuth } from '../../hooks/useAuth'

export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Spinner className="size-6" />
      </div>
    )
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}

// Dashboard propio de cada rol — usado para redirigir cuando alguien entra a
// una URL de un rol que no es el suyo. Antes esto era siempre '/app', que
// para un docente no es una ruta válida (su dashboard es '/app/docente') y
// terminaba en la pantalla en blanco del catch-all.
const HOME_BY_ROLE: Record<'student' | 'teacher' | 'admin', string> = {
  student: '/app',
  teacher: '/app/docente',
  admin: '/app/docente',
}

export function RequireRole({ roles }: { roles: Array<'student' | 'teacher' | 'admin'> }) {
  const { user } = useAuth()

  if (!user) return null
  const allowed = roles.includes(user.role) || user.role === 'admin'
  if (!allowed) return <Navigate to={HOME_BY_ROLE[user.role]} replace />

  return <Outlet />
}
