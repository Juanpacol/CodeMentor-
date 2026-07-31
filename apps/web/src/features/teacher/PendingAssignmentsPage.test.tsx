import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PendingAssignmentsPage } from './PendingAssignmentsPage'

const GROUP = { id: 'group-1', name: '10-A', invite_code: 'ABC123' }

function stubApi(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const match = Object.keys(routes)
        .filter((key) => url.includes(key))
        .sort((a, b) => b.length - a.length)[0]
      return new Response(JSON.stringify(match ? routes[match] : []), { status: 200 })
    }),
  )
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <PendingAssignmentsPage />
    </QueryClientProvider>,
  )
}

describe('PendingAssignmentsPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('pide elegir un grupo antes de mostrar el formulario de asignación', async () => {
    stubApi({ 'groups/mine': [GROUP] })
    renderPage()

    await screen.findByText('Elige un grupo')
    expect(screen.queryByText('Asignar')).not.toBeInTheDocument()
  })

  it('al elegir un grupo, muestra el formulario de asignaciones de ese grupo', async () => {
    stubApi({
      'groups/mine': [GROUP],
      'group-1/assignments': [],
      curriculum: [],
      exercises: [],
      'group-1/evaluations': [],
      'group-1/guides': [],
    })
    renderPage()

    await screen.findByText('10-A')
    await userEvent.selectOptions(screen.getByLabelText('Grupo'), 'group-1')

    expect(await screen.findByRole('button', { name: /Asignar/ })).toBeInTheDocument()
  })
})
