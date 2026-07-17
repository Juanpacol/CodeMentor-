import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../../components/ui/EmptyState'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

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

  return (
    <div className="overflow-x-auto rounded-card border border-hairline">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-hairline bg-raised">
            <th className="sticky left-0 bg-raised px-4 py-3 text-left font-semibold text-ink">
              Estudiante
            </th>
            {data.evaluations.map((evaluation) => (
              <th
                key={evaluation.id}
                className="px-4 py-3 text-left font-semibold text-ink"
                title={evaluation.title}
              >
                {evaluation.title}
              </th>
            ))}
            <th className="px-4 py-3 text-left font-semibold text-ink">Promedio</th>
          </tr>
        </thead>
        <tbody>
          {data.students.map((student) => {
            const scoreByEvaluation = new Map(
              student.scores.map((score) => [score.evaluation_id, score.total_score]),
            )
            return (
              <tr key={student.student_id} className="border-b border-hairline last:border-0">
                <td className="sticky left-0 bg-canvas px-4 py-3 text-ink">
                  {student.full_name}
                </td>
                {data.evaluations.map((evaluation) => {
                  const score = scoreByEvaluation.get(evaluation.id)
                  return (
                    <td key={evaluation.id} className="px-4 py-3 text-ink-secondary">
                      {score !== undefined ? score.toFixed(2) : '—'}
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
  )
}
