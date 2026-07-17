import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { EXERCISE_TYPE_LABELS } from '../../components/exercises/registry'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

export function ApprovalsInboxPage() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: qk.ai.pendingApprovals,
    queryFn: () => unwrap(apiClient.GET('/ai/pending-approvals')),
  })

  const publish = useMutation({
    mutationFn: (exerciseId: string) =>
      unwrap(
        apiClient.PATCH('/exercises/{exercise_id}', {
          params: { path: { exercise_id: exerciseId } },
          body: { status: 'published' },
        }),
      ),
    onSuccess: () => {
      pushToast('Ejercicio publicado', 'success')
      void queryClient.invalidateQueries({ queryKey: qk.ai.pendingApprovals })
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
    },
  })

  const isEmpty =
    !isLoading && data && data.exercises.length === 0 && data.grading_suggestions.length === 0

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">Bandeja de aprobaciones</h1>

      {isEmpty && <EmptyState emoji="📬" title="No hay nada pendiente de aprobación" />}

      {data && data.exercises.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-3 text-sm font-semibold text-ink">Ejercicios generados por IA</h2>
          <div className="flex flex-col gap-2">
            {data.exercises.map((exercise) => (
              <Card key={exercise.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-ink">{exercise.title}</span>
                  <Badge tint="lavender">{EXERCISE_TYPE_LABELS[exercise.type]}</Badge>
                </div>
                <Button
                  size="sm"
                  disabled={publish.isPending}
                  onClick={() => publish.mutate(exercise.id)}
                >
                  Publicar
                </Button>
              </Card>
            ))}
          </div>
        </div>
      )}

      {data && data.grading_suggestions.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-semibold text-ink">Sugerencias de calificación</h2>
          <div className="flex flex-col gap-2">
            {data.grading_suggestions.map((suggestion) => (
              <Link key={suggestion.answer_id} to={`/app/docente/evaluaciones/${suggestion.evaluation_id}`}>
                <Card interactive className="flex items-center justify-between">
                  <span className="text-ink">{suggestion.exercise_title}</span>
                  <Badge tint="lavender">
                    IA: {Math.round(suggestion.ai_suggested_score * 100)}%
                  </Badge>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
