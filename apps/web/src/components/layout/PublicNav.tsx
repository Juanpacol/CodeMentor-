import { Link } from 'react-router-dom'

import { Button } from '../ui/Button'

export function PublicNav() {
  return (
    <header className="flex items-center justify-between px-6 py-4 md:px-12">
      <Link to="/" className="font-mono text-lg font-semibold text-ink">
        Lógica&gt;_
      </Link>
      <div className="flex items-center gap-3">
        <Link to="/login">
          <Button variant="ghost" size="sm">
            Iniciar sesión
          </Button>
        </Link>
        <Link to="/registro">
          <Button size="sm">Crear cuenta gratis</Button>
        </Link>
      </div>
    </header>
  )
}
