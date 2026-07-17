import { NavLink, Outlet } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { useAuth } from '../../hooks/useAuth'
import { Button } from '../ui/Button'

interface NavItem {
  to: string
  label: string
  end?: boolean
}

const studentNav: NavItem[] = [
  { to: '/app', label: 'Mis grupos', end: true },
  { to: '/app/progreso', label: 'Mi progreso' },
]

const teacherNav: NavItem[] = [
  { to: '/app/docente', label: 'Grupos', end: true },
  { to: '/app/docente/ejercicios', label: 'Banco de ejercicios' },
  { to: '/app/docente/evaluaciones/nueva', label: 'Nueva evaluación' },
  { to: '/app/docente/bandeja', label: 'Bandeja de aprobaciones' },
  { to: '/app/admin/periodos', label: 'Periodos académicos' },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const isTeacher = user?.role === 'teacher' || user?.role === 'admin'
  const nav = isTeacher ? teacherNav : studentNav

  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="flex w-60 shrink-0 flex-col border-r border-hairline bg-surface p-4">
        <div className="mb-6 px-2">
          <span className="font-mono text-lg font-semibold text-ink">Lógica&gt;_</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'rounded-btn px-3 py-2 text-sm font-medium transition-colors duration-150',
                  isActive ? 'bg-hover text-ink' : 'text-ink-secondary hover:bg-hover hover:text-ink',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-hairline pt-3">
          <p className="truncate px-2 text-xs text-ink-secondary">{user?.full_name}</p>
          <Button variant="ghost" size="sm" className="mt-2 w-full justify-start" onClick={logout}>
            Cerrar sesión
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
