import { useNavigate } from 'react-router'

import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'

export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <EmptyState
        emoji="🧭"
        title="Página no encontrada"
        description="La dirección a la que intentas entrar no existe o ya no está disponible."
        action={<Button onClick={() => navigate('/')}>Volver al inicio</Button>}
      />
    </div>
  )
}
