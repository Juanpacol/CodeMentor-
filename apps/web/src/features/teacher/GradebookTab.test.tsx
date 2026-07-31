import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { GradebookTab } from './GradebookTab'

const GRADEBOOK_RESPONSE = {
  evaluations: [
    { id: 'eval-1', title: 'Quiz 1', mode: 'cumulative', is_ranked: false, weight_percent: null },
    { id: 'eval-2', title: 'Quiz 2', mode: 'cumulative', is_ranked: false, weight_percent: null },
  ],
  students: [
    {
      student_id: 'student-1',
      full_name: 'Estudiante A',
      scores: [
        { evaluation_id: 'eval-1', total_score: 1 },
        { evaluation_id: 'eval-2', total_score: 0.5 },
      ],
      evaluations_submitted: 2,
      avg_evaluation_score: 0.75,
      weighted_average: null,
    },
    {
      student_id: 'student-2',
      full_name: 'Estudiante B',
      scores: [{ evaluation_id: 'eval-1', total_score: 1 }],
      evaluations_submitted: 1,
      avg_evaluation_score: 1,
      weighted_average: null,
    },
  ],
}

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <GradebookTab groupId="group-1" />
    </QueryClientProvider>,
  )
}

describe('GradebookTab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders students as rows and evaluations as columns, with an average column', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(GRADEBOOK_RESPONSE), { status: 200 })),
    )

    renderTab()

    await waitFor(() => expect(screen.getByText('Estudiante A')).toBeInTheDocument())

    // Los títulos de evaluación y los puntajes también aparecen en el
    // gráfico "Media por evaluación" (ChartCard) de arriba — se acota la
    // consulta a la tabla real (identificada por su <caption> sr-only) para
    // no confundir ambas superficies.
    const gradebookTable = screen.getByRole('table', { name: /libro de calificaciones/i })
    expect(within(gradebookTable).getByText('Quiz 1')).toBeInTheDocument()
    expect(within(gradebookTable).getByText('Quiz 2')).toBeInTheDocument()
    expect(within(gradebookTable).getByText('Estudiante B')).toBeInTheDocument()

    // "1.00" aparece 3 veces dentro de la tabla: Quiz 1 de Estudiante A,
    // Quiz 1 de Estudiante B y el promedio de Estudiante B (que solo
    // presentó esa evaluación).
    expect(within(gradebookTable).getAllByText('1.00')).toHaveLength(3)
    expect(within(gradebookTable).getByText('0.50')).toBeInTheDocument()
    expect(within(gradebookTable).getByText('0.75')).toBeInTheDocument()

    // Estudiante B no presentó Quiz 2 -> guion
    expect(within(gradebookTable).getAllByText('—').length).toBeGreaterThan(0)
  })

  it('muestra el porcentaje, la nota acumulada y avisa si la suma no da 100%', async () => {
    const weighted = {
      evaluations: [
        { id: 'eval-1', title: 'Quiz 1', mode: 'cumulative', is_ranked: false, weight_percent: 30 },
        { id: 'eval-2', title: 'Quiz 2', mode: 'cumulative', is_ranked: false, weight_percent: 50 },
      ],
      students: [
        {
          student_id: 'student-1',
          full_name: 'Estudiante A',
          scores: [
            { evaluation_id: 'eval-1', total_score: 1 },
            { evaluation_id: 'eval-2', total_score: 1 },
          ],
          evaluations_submitted: 2,
          avg_evaluation_score: 1,
          weighted_average: 80,
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(weighted), { status: 200 })),
    )

    renderTab()

    await waitFor(() => expect(screen.getByText('Estudiante A')).toBeInTheDocument())

    // Suma 30% + 50% = 80%, no 100% -> aviso.
    expect(screen.getByText(/suman 80%/)).toBeInTheDocument()

    const gradebookTable = screen.getByRole('table', { name: /libro de calificaciones/i })
    expect(within(gradebookTable).getByText('(30%)')).toBeInTheDocument()
    expect(within(gradebookTable).getByText('(50%)')).toBeInTheDocument()
    expect(within(gradebookTable).getByText('80.0%')).toBeInTheDocument()
  })

  it('shows an empty state when there are no evaluations yet', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ evaluations: [], students: [] }), { status: 200 }),
      ),
    )

    renderTab()

    await waitFor(() =>
      expect(screen.getByText('Aún no hay evaluaciones calificadas')).toBeInTheDocument(),
    )
  })
})
