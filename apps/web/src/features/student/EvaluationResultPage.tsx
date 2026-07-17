import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { Link, useParams } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, unwrap } from '../../lib/api/client'
import { useAuth } from '../../hooks/useAuth'
import { qk } from '../../lib/api/queries'

export function EvaluationResultPage() {
  const { evaluationId } = useParams<{ evaluationId: string }>()
  const { user } = useAuth()

  const { data: take } = useQuery({
    queryKey: qk.evaluation.take(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/take', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId),
  })

  const { data: result, isLoading } = useQuery({
    queryKey: qk.evaluation.result(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/result', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId),
  })

  const { data: ranking } = useQuery({
    queryKey: qk.evaluation.ranking(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/ranking', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId) && Boolean(take?.evaluation.is_ranked),
  })

  if (isLoading || !result) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="size-6" />
      </div>
    )
  }

  const percent = result.total_score !== null ? Math.round((result.total_score / result.max_score) * 100) : null

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to={take ? `/app/grupos/${take.evaluation.group_id}` : '/app'}
        className="mb-4 inline-block text-sm text-ink-secondary hover:text-ink"
      >
        ← Volver al grupo
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-ink">
        Resultado — {take?.evaluation.title ?? 'Evaluación'}
      </h1>

      <Card className="mb-6 flex items-center gap-6">
        <motion.div
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20 }}
          className="flex size-24 shrink-0 items-center justify-center rounded-full border-4 border-primary text-xl font-bold text-ink"
        >
          {percent !== null ? `${percent}%` : '—'}
        </motion.div>
        <div>
          <p className="text-sm text-ink-secondary">
            Estado:{' '}
            <Badge tint={result.status === 'expired' ? 'rose' : 'mint'}>
              {result.status === 'submitted'
                ? 'Enviada'
                : result.status === 'expired'
                  ? 'Expirada'
                  : 'En progreso'}
            </Badge>
          </p>
          {result.total_score !== null && (
            <p className="mt-1 text-sm text-ink-secondary">
              Puntaje: {result.total_score.toFixed(2)} / {result.max_score}
            </p>
          )}
        </div>
      </Card>

      <div className="mb-6 flex flex-col gap-2">
        {result.answers.map((answer, i) => (
          <div
            key={answer.evaluation_exercise_id}
            className="flex items-center justify-between rounded-card border border-hairline bg-raised px-4 py-3"
          >
            <span className="text-sm text-ink">Pregunta {i + 1}</span>
            {answer.needs_manual_review ? (
              <Badge tint="sky">Pendiente de revisión</Badge>
            ) : (
              <Badge tint={answer.correct ? 'mint' : 'rose'}>
                {Math.round((answer.manual_score ?? answer.score) * 100)}%
              </Badge>
            )}
          </div>
        ))}
      </div>

      {take?.evaluation.is_ranked && ranking && ranking.length > 0 && (
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-ink">Tabla de posiciones</h2>
          <ol className="flex flex-col gap-1.5">
            {ranking.map((entry, i) => (
              <li
                key={entry.student_id}
                className={`flex items-center justify-between rounded-btn px-3 py-1.5 text-sm ${
                  entry.student_id === user?.id ? 'bg-primary/10 text-ink' : 'text-ink-secondary'
                }`}
              >
                <span>
                  {i + 1}. {entry.student_id === user?.id ? 'Tú' : `Estudiante #${i + 1}`}
                </span>
                <span className="font-medium">{entry.total_score.toFixed(2)}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}
