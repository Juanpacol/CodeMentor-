import { useQuery } from '@tanstack/react-query'

import { BarList, type BarListItem } from '../../components/ui/BarList'
import { ChartCard } from '../../components/ui/ChartCard'
import { cn } from '../../lib/cn'
import { EmptyState } from '../../components/ui/EmptyState'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type GradebookOut = components['schemas']['GradebookOut']

// Clases literales (no una plantilla `bg-ordinal-${n}`): el escáner de
// Tailwind necesita ver el nombre completo de la utilidad en el código
// fuente para generarla — una concatenación en runtime no la encontraría.
const ORDINAL_DOT_CLASSES = ['bg-ordinal-1', 'bg-ordinal-2', 'bg-ordinal-3', 'bg-ordinal-4'] as const

/** Banda ordinal de 4 pasos, relativa a las notas de ESTA evaluación (no a
 * una escala absoluta): el API no expone el puntaje máximo posible de una
 * evaluación, así que "alto"/"bajo" se calcula contra el rango real
 * observado en esa columna, no contra un ideal fijo. El número de la celda
 * se queda en su color de texto normal (--color-ink-secondary) sin importar
 * el paso — el color-como-magnitud vive solo en el punto decorativo de al
 * lado, así que nunca hay que garantizar contraste de texto sobre 4 fondos
 * distintos. */
function ordinalStep(score: number, min: number, max: number): number {
  if (max === min) return 2
  const t = (score - min) / (max - min)
  if (t >= 0.75) return 3
  if (t >= 0.5) return 2
  if (t >= 0.25) return 1
  return 0
}

function evaluationMeans(data: GradebookOut): BarListItem[] {
  const items = data.evaluations.map((evaluation) => {
    const scores = data.students
      .flatMap((s) => s.scores)
      .filter((score) => score.evaluation_id === evaluation.id)
      .map((score) => score.total_score)
    const mean = scores.length === 0 ? null : scores.reduce((a, b) => a + b, 0) / scores.length
    return { id: evaluation.id, title: evaluation.title, mean }
  })
  const max = Math.max(0, ...items.map((i) => i.mean ?? 0))
  return items.map((i) => ({
    key: i.id,
    label: i.title,
    value: i.mean,
    max: max || 1,
    valueLabel: i.mean !== null ? i.mean.toFixed(2) : '—',
  }))
}

export function GradebookTab({ groupId }: { groupId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.reports.gradebook(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/gradebook', { params: { path: { group_id: groupId } } }),
      ),
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="size-6" />
      </div>
    )
  }

  if (!data || data.evaluations.length === 0 || data.students.length === 0) {
    return (
      <EmptyState
        emoji="📊"
        title="Aún no hay evaluaciones calificadas"
        description="Cuando el grupo tenga evaluaciones y estudiantes inscritos, aquí verás sus notas."
      />
    )
  }

  const meanItems = evaluationMeans(data)

  // Rango real de notas por evaluación (columna), para las bandas ordinales
  // de las celdas — ver ordinalStep().
  const rangeByEvaluation = new Map(
    data.evaluations.map((evaluation) => {
      const scores = data.students
        .flatMap((s) => s.scores)
        .filter((score) => score.evaluation_id === evaluation.id)
        .map((score) => score.total_score)
      return [evaluation.id, { min: Math.min(...scores), max: Math.max(...scores) }] as const
    }),
  )

  return (
    <div className="flex flex-col gap-6">
      <ChartCard
        title="Media por evaluación"
        tableHeaders={['Evaluación', 'Media']}
        tableRows={meanItems.map((item) => [item.label, item.valueLabel])}
      >
        <BarList items={meanItems} />
      </ChartCard>

      <div>
        <div className="mb-2 flex items-center gap-2 text-xs text-ink-secondary">
          <span>Nota relativa a la evaluación:</span>
          <span className="flex items-center gap-1">
            <span aria-hidden="true" className={cn('size-2 rounded-full', ORDINAL_DOT_CLASSES[0])} />
            bajo
          </span>
          <span className="flex items-center gap-1">
            <span aria-hidden="true" className={cn('size-2 rounded-full', ORDINAL_DOT_CLASSES[3])} />
            alto
          </span>
        </div>
        <div className="overflow-x-auto rounded-card border border-hairline">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Libro de calificaciones: una fila por estudiante, una columna por evaluación
            </caption>
            <thead>
              <tr className="border-b border-hairline bg-raised">
                <th scope="col" className="sticky left-0 bg-raised px-4 py-3 text-left font-semibold text-ink">
                  Estudiante
                </th>
                {data.evaluations.map((evaluation) => (
                  <th
                    key={evaluation.id}
                    scope="col"
                    className="px-4 py-3 text-left font-semibold text-ink"
                    title={evaluation.title}
                  >
                    {evaluation.title}
                  </th>
                ))}
                <th scope="col" className="px-4 py-3 text-left font-semibold text-ink">
                  Promedio
                </th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((student) => {
                const scoreByEvaluation = new Map(
                  student.scores.map((score) => [score.evaluation_id, score.total_score]),
                )
                return (
                  <tr key={student.student_id} className="border-b border-hairline last:border-0">
                    <th
                      scope="row"
                      className="sticky left-0 bg-canvas px-4 py-3 text-left font-normal text-ink"
                    >
                      {student.full_name}
                    </th>
                    {data.evaluations.map((evaluation) => {
                      const score = scoreByEvaluation.get(evaluation.id)
                      const range = rangeByEvaluation.get(evaluation.id)
                      const step =
                        score !== undefined && range ? ordinalStep(score, range.min, range.max) : null
                      return (
                        <td key={evaluation.id} className="px-4 py-3 text-ink-secondary">
                          {score !== undefined ? (
                            <span className="inline-flex items-center gap-1.5">
                              {score.toFixed(2)}
                              {step !== null && (
                                <span
                                  aria-hidden="true"
                                  className={cn('inline-block size-2 rounded-full', ORDINAL_DOT_CLASSES[step])}
                                />
                              )}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      )
                    })}
                    <td className="px-4 py-3 font-medium text-ink">
                      {student.avg_evaluation_score !== null
                        ? student.avg_evaluation_score.toFixed(2)
                        : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
