import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RequireAuth, RequireRole } from './RequireAuth'
import { clearTokens, setTokens } from '../../lib/api/tokens'
import { AuthProvider } from '../../hooks/useAuth'

function renderWithRouter(initialPath: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <div>Pantalla de login</div> },
      { path: '/app', element: <div>Área de estudiante</div> },
      {
        element: <RequireAuth />,
        children: [
          { path: '/privado', element: <div>Contenido privado</div> },
          {
            element: <RequireRole roles={['teacher']} />,
            children: [{ path: '/solo-docente', element: <div>Panel docente</div> }],
          },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  )
  return render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
}

describe('RequireAuth', () => {
  beforeEach(() => {
    clearTokens()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('redirects to /login when there is no session', async () => {
    renderWithRouter('/privado')
    await waitFor(() => expect(screen.getByText('Pantalla de login')).toBeInTheDocument())
  })

  it('renders the protected content once authenticated', async () => {
    setTokens('valid-access', 'valid-refresh')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ id: '1', role: 'student' }), { status: 200 }),
      ),
    )

    renderWithRouter('/privado')
    await waitFor(() => expect(screen.getByText('Contenido privado')).toBeInTheDocument())
  })
})

describe('RequireRole', () => {
  beforeEach(() => {
    clearTokens()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('redirects a student away from a teacher-only route', async () => {
    setTokens('valid-access', 'valid-refresh')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ id: '1', role: 'student' }), { status: 200 }),
      ),
    )

    renderWithRouter('/solo-docente')
    await waitFor(() => expect(screen.getByText('Área de estudiante')).toBeInTheDocument())
  })

  it('lets a teacher through a teacher-only route', async () => {
    setTokens('valid-access', 'valid-refresh')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ id: '1', role: 'teacher' }), { status: 200 }),
      ),
    )

    renderWithRouter('/solo-docente')
    await waitFor(() => expect(screen.getByText('Panel docente')).toBeInTheDocument())
  })
})
