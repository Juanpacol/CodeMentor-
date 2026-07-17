import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TakeEvaluationPage } from './TakeEvaluationPage'

const TAKE_RESPONSE = {
  evaluation: {
    id: 'eval-1',
    institution_id: 'inst-1',
    group_id: 'group-1',
    teacher_id: 'teacher-1',
    title: 'Quiz de prueba',
    mode: 'fixed',
    up_to_topic_id: null,
    duration_minutes: 20,
    is_ranked: false,
  },
  attempt_id: 'attempt-1',
  started_at: new Date().toISOString(),
  deadline: new Date(Date.now() + 60_000).toISOString(),
  exercises: [
    {
      evaluation_exercise_id: 'ee-1',
      order_index: 0,
      points: 1,
      exercise_id: 'ex-1',
      type: 'true_false',
      title: 'Pregunta 1',
      content: { statement: '¿Es correcto?', answer: true },
    },
  ],
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    [
      { path: '/app/evaluaciones/:evaluationId', element: <TakeEvaluationPage /> },
      { path: '/app/grupos/:groupId', element: <div>Detalle del grupo</div> },
      {
        path: '/app/evaluaciones/:evaluationId/resultado',
        element: <div>Resultado de la evaluación</div>,
      },
    ],
    { initialEntries: ['/app/evaluaciones/eval-1'] },
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('TakeEvaluationPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('opens the exit confirmation dialog and stays on the page when cancelled', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(TAKE_RESPONSE), { status: 200 })),
    )

    renderPage()
    await waitFor(() => expect(screen.getByText('Quiz de prueba')).toBeInTheDocument())

    fireEvent.click(screen.getByText('← Salir'))
    expect(screen.getByText('¿Salir de la evaluación?')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Seguir respondiendo'))
    await waitFor(() =>
      expect(screen.queryByText('¿Salir de la evaluación?')).not.toBeInTheDocument(),
    )
    expect(screen.getByText('Quiz de prueba')).toBeInTheDocument()
  })

  it('navigates to the group when exit is confirmed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(TAKE_RESPONSE), { status: 200 })),
    )

    renderPage()
    await waitFor(() => expect(screen.getByText('Quiz de prueba')).toBeInTheDocument())

    fireEvent.click(screen.getByText('← Salir'))
    fireEvent.click(screen.getByText('Salir sin enviar'))

    await waitFor(() => expect(screen.getByText('Detalle del grupo')).toBeInTheDocument())
  })
})
