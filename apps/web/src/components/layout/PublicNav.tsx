import { Link } from 'react-router'

import { Button } from '../ui/Button'
import { ThemeToggle } from '../ui/ThemeToggle'

export function PublicNav() {
  return (
    <header className="flex items-center justify-between px-6 py-4 md:px-12">
      <Link to="/" className="font-mono text-lg font-semibold text-ink">
        CodeMentor
      </Link>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        {/* inline-flex: un <a> por defecto tiene su propia caja de línea
            (line-height) que no calza con la del <button> que envuelve,
            dejando una zona de "espacio seguro de clic" angosta entre
            controles vecinos — Lighthouse lo marca como target-size
            insuficiente. inline-flex hace que el enlace calce exactamente
            con el tamaño de su botón. */}
        <Link to="/login" className="inline-flex">
          <Button variant="ghost" size="sm">
            Iniciar sesión
          </Button>
        </Link>
        <Link to="/registro" className="inline-flex">
          <Button size="sm">Crear cuenta gratis</Button>
        </Link>
      </div>
    </header>
  )
}
