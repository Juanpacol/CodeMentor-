import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EvaluationBuilderPage } from './EvaluationBuilderPage'

const EXERCISE = {
  id: 'ex-1',
  institution_id: 'inst-1',
  language_id: 'lang-1',
  title: 'Condicionales básicos',
  type: 'true_false',
  content: { statement: 'x', answer: true },
  origin: 'teacher',
  status: 'published',
  version: 1,
}

type Call = { url: string; method: string; body: string }

/** Mismo patrón que RubricTab.test.tsx/GuidesTab.test.tsx: enruta por URL,
 * gana la clave más larga. */
function stubApi(routes: Record<string, unknown>, calls?: Call[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request
      const url = typeof input === 'string' ? input : request.url
      if (calls && typeof input !== 'string') {
        calls.push({
          url,
          method: request.method,
          body: request.method === 'GET' ? '' : await request.clone().text(),
        })
      }
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
      <MemoryRouter>
        <EvaluationBuilderPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EvaluationBuilderPage — variantes por IA', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('pedir variantes las muestra para revisión, sin crearlas todavía', async () => {
    const calls: Call[] = []
    stubApi(
      {
        'groups/mine': [],
        topics: [],
        exercises: [EXERCISE],
        'ai/exercises/ex-1/variants': [
          { title: 'Condicionales — variante 1', content: { statement: 'y', answer: false } },
        ],
      },
      calls,
    )
    renderPage()

    await screen.findByText('Condicionales básicos')
    await userEvent.click(screen.getByRole('button', { name: 'Pedir variantes' }))

    await screen.findByText('Condicionales — variante 1')
    expect(screen.getByRole('button', { name: 'Aceptar' })).toBeInTheDocument()
    // Todavía no se creó nada: ni POST a /exercises.
    const persistedSomething = calls.some(
      (c) => c.method === 'POST' && c.url.includes('/exercises') && !c.url.includes('variants'),
    )
    expect(persistedSomething).toBe(false)
  })

  it('aceptar una variante la crea y la deja seleccionada', async () => {
    const calls: Call[] = []
    stubApi(
      {
        'groups/mine': [],
        topics: [],
        exercises: [EXERCISE],
        'ai/exercises/ex-1/variants': [
          { title: 'Condicionales — variante 1', content: { statement: 'y', answer: false } },
        ],
      },
      calls,
    )
    renderPage()

    await screen.findByText('Condicionales básicos')
    await userEvent.click(screen.getByRole('button', { name: 'Pedir variantes' }))
    await screen.findByText('Condicionales — variante 1')

    await userEvent.click(screen.getByRole('button', { name: 'Aceptar' }))

    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.method === 'POST' && c.url.endsWith('/exercises') && c.body.includes('variante 1'),
        ),
      ).toBe(true),
    )
    // La variante aceptada desaparece de la lista de revisión.
    await waitFor(() =>
      expect(screen.queryByText('Condicionales — variante 1')).not.toBeInTheDocument(),
    )
  })
})
