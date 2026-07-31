import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'
import { AuthProvider } from '../../hooks/useAuth'
import { clearTokens, setTokens } from '../../lib/api/tokens'

function stubApi(role: 'teacher' | 'student') {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (url.includes('/users/me')) {
        return new Response(JSON.stringify({ id: '1', full_name: 'Ana', role }), { status: 200 })
      }
      return new Response(JSON.stringify([]), { status: 200 })
    }),
  )
}

function renderShell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      {
        element: <AppShell />,
        children: [
          { path: '/app', element: <div>Mis grupos (estudiante)</div> },
          { path: '/app/docente', element: <div>Grupos (docente)</div> },
        ],
      },
    ],
    { initialEntries: ['/app/docente'] },
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('AppShell — vista previa como estudiante', () => {
  beforeEach(() => {
    clearTokens()
    setTokens('valid-access', 'valid-refresh')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('un estudiante no ve el botón de vista previa', async () => {
    stubApi('student')
    renderShell()

    await waitFor(() => expect(screen.getByText('Ana')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Ver como estudiante' })).not.toBeInTheDocument()
  })

  it('un docente puede activar la vista de estudiante y el menú/banner cambian', async () => {
    stubApi('teacher')
    renderShell()

    await waitFor(() => expect(screen.getByText('Ana')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Banco de ejercicios' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Ver como estudiante' }))

    expect(screen.getByText('Estás viendo la plataforma como estudiante.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Mi progreso' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Banco de ejercicios' })).not.toBeInTheDocument()

    // Aparece dos veces: en el banner y en el botón del sidebar que cambió de
    // texto al activar la vista de estudiante.
    const backButtons = screen.getAllByRole('button', { name: 'Volver a vista docente' })
    await userEvent.click(backButtons[0])

    expect(
      screen.queryByText('Estás viendo la plataforma como estudiante.'),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Banco de ejercicios' })).toBeInTheDocument()
  })
})
