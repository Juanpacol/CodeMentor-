import { Navigate, Outlet, useLocation } from 'react-router-dom'

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

export function RequireRole({ roles }: { roles: Array<'student' | 'teacher' | 'admin'> }) {
  const { user } = useAuth()

  if (!user) return null
  const allowed = roles.includes(user.role) || user.role === 'admin'
  if (!allowed) return <Navigate to="/app" replace />

  return <Outlet />
}
