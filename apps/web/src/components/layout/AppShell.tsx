import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
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
  { to: '/app/docente/actividad', label: 'Actividad y errores' },
  { to: '/app/admin/periodos', label: 'Periodos académicos' },
]

function SidebarContent({ nav, onNavigate }: { nav: NavItem[]; onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  return (
    <>
      <div className="mb-6 px-2">
        <span className="font-mono text-lg font-semibold text-ink">CodeMentor</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
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
    </>
  )
}

export function AppShell() {
  const { user } = useAuth()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const isTeacher = user?.role === 'teacher' || user?.role === 'admin'
  const nav = isTeacher ? teacherNav : studentNav

  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-hairline bg-surface p-4 md:flex">
        <SidebarContent nav={nav} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-hairline bg-surface px-4 py-3 md:hidden">
          <span className="font-mono text-lg font-semibold text-ink">CodeMentor</span>
          <button
            aria-label="Abrir menú"
            aria-expanded={mobileNavOpen}
            onClick={() => setMobileNavOpen(true)}
            className="rounded-btn p-2 text-ink hover:bg-hover"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M3 5h14M3 10h14M3 15h14"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <Outlet />
        </main>
      </div>

      <AnimatePresence>
        {mobileNavOpen && (
          <motion.div
            className="fixed inset-0 z-50 bg-black/60 md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setMobileNavOpen(false)}
            role="presentation"
          >
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
              onClick={(e) => e.stopPropagation()}
              className="flex h-full w-64 max-w-[80vw] flex-col border-r border-hairline bg-surface p-4"
            >
              <SidebarContent nav={nav} onNavigate={() => setMobileNavOpen(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
