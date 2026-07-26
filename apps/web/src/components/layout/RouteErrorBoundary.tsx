import { isRouteErrorResponse, useNavigate, useRouteError } from 'react-router'

import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'

/**
 * `createBrowserRouter` ya envuelve cada rama en un boundary interno que
 * renderiza el `errorElement` más cercano ante un error de render o de
 * loader/action — no hace falta un class component con `componentDidCatch`
 * propio, RR ya lo resuelve por nosotros (ver router.tsx).
 */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()
  const status = isRouteErrorResponse(error) ? error.status : undefined

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <EmptyState
        emoji="⚠️"
        title={status ? `Error ${status}` : 'Algo salió mal'}
        description="Ocurrió un error inesperado. Intenta recargar la página; si el problema persiste, avísale a tu docente o al equipo de soporte."
        action={<Button onClick={() => navigate('/')}>Volver al inicio</Button>}
      />
    </div>
  )
}
