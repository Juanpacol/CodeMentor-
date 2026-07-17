import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { exerciseRenderers, EXERCISE_TYPE_LABELS } from '../../components/exercises/registry'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { Tag } from '../../components/ui/Tag'
import { useCountdown } from '../../hooks/useCountdown'
import { useDebouncedCallback } from '../../hooks/useDebouncedCallback'
import { apiClient, unwrap } from '../../lib/api/client'
import { cn } from '../../lib/cn'
import { qk } from '../../lib/api/queries'

function formatSeconds(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function TakeEvaluationPage() {
  const { evaluationId } = useParams<{ evaluationId: string }>()
  const navigate = useNavigate()
  const [answers, setAnswers] = useState<Record<string, Record<string, unknown>>>({})
  const [savedAt, setSavedAt] = useState<Record<string, number>>({})
  const [currentIndex, setCurrentIndex] = useState(0)

  const { data: take, isLoading } = useQuery({
    queryKey: qk.evaluation.take(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/take', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId),
  })

  const submit = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/evaluations/{evaluation_id}/submit', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    onSuccess: () => navigate(`/app/evaluaciones/${evaluationId}/resultado`, { replace: true }),
  })

  const handleExpire = useCallback(() => {
    if (!submit.isPending) submit.mutate()
  }, [submit])

  const { secondsLeft, expired } = useCountdown(take?.deadline ?? null, handleExpire)

  const saveAnswer = useDebouncedCallback(
    (evaluationExerciseId: string, answer: Record<string, unknown>) => {
      void unwrap(
        apiClient.POST('/evaluations/{evaluation_id}/answers', {
          params: { path: { evaluation_id: evaluationId! } },
          body: { evaluation_exercise_id: evaluationExerciseId, answer },
        }),
      ).then(() => setSavedAt((prev) => ({ ...prev, [evaluationExerciseId]: Date.now() })))
    },
    800,
  )

  const exercises = useMemo(
    () => [...(take?.exercises ?? [])].sort((a, b) => a.order_index - b.order_index),
    [take],
  )
  const current = exercises[currentIndex]

  function updateAnswer(evaluationExerciseId: string, value: Record<string, unknown>) {
    setAnswers((prev) => ({ ...prev, [evaluationExerciseId]: value }))
    saveAnswer(evaluationExerciseId, value)
  }

  if (isLoading || !take) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="size-6" />
      </div>
    )
  }

  const justSaved =
    current && savedAt[current.evaluation_exercise_id]
      ? Date.now() - savedAt[current.evaluation_exercise_id] < 3000
      : false

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{take.evaluation.title}</h1>
        {secondsLeft !== null && (
          <span
            className={cn(
              'rounded-full px-3 py-1 text-sm font-semibold tabular-nums',
              secondsLeft <= 120 ? 'bg-tint-rose text-tint-rose-fg' : 'bg-overlay text-ink-secondary',
            )}
          >
            {formatSeconds(secondsLeft)}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[200px_1fr]">
        <div className="flex flex-row gap-2 lg:flex-col">
          {exercises.map((ex, i) => (
            <button
              key={ex.evaluation_exercise_id}
              onClick={() => setCurrentIndex(i)}
              className={cn(
                'rounded-btn border px-3 py-2 text-left text-sm transition-colors duration-150',
                i === currentIndex
                  ? 'border-primary bg-primary/10 text-ink'
                  : 'border-hairline-strong text-ink-secondary hover:bg-hover',
                answers[ex.evaluation_exercise_id] && 'font-medium',
              )}
            >
              Pregunta {i + 1}
            </button>
          ))}
        </div>

        {current && (
          <Card>
            <div className="mb-4 flex items-center gap-2">
              <h2 className="text-lg font-semibold text-ink">{current.title}</h2>
              <Tag>{EXERCISE_TYPE_LABELS[current.type]}</Tag>
              <span className="ml-auto text-xs text-ink-secondary">{current.points} pts</span>
            </div>
            {(() => {
              const Renderer = exerciseRenderers[current.type]
              return (
                <Renderer
                  content={current.content}
                  value={answers[current.evaluation_exercise_id] as never}
                  onChange={(v) =>
                    updateAnswer(current.evaluation_exercise_id, v as Record<string, unknown>)
                  }
                  disabled={expired || submit.isPending}
                />
              )
            })()}
            {justSaved && <p className="mt-3 text-xs text-success">Guardado ✓</p>}

            <div className="mt-6 flex items-center justify-between border-t border-hairline pt-4">
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentIndex === 0}
                  onClick={() => setCurrentIndex((i) => i - 1)}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentIndex === exercises.length - 1}
                  onClick={() => setCurrentIndex((i) => i + 1)}
                >
                  Siguiente
                </Button>
              </div>
              <Button disabled={expired || submit.isPending} onClick={() => submit.mutate()}>
                {submit.isPending ? 'Enviando...' : 'Finalizar evaluación'}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
