import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Textarea } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { Tabs } from '../../components/ui/Tabs'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

function ManualReviewRow({ evaluationId, answerId, exerciseTitle, answer }: {
  evaluationId: string
  answerId: string
  exerciseTitle: string
  answer: Record<string, unknown>
}) {
  const queryClient = useQueryClient()
  const [rubric, setRubric] = useState('')
  const [score, setScore] = useState('')
  const [suggestion, setSuggestion] = useState<{ score: number | null; justification: string | null } | null>(
    null,
  )
  const [aiUnavailable, setAiUnavailable] = useState(false)

  const suggest = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/ai/grading/suggest', {
          body: { evaluation_id: evaluationId, answer_id: answerId, rubric },
        }),
      ),
    onSuccess: (data) => {
      setAiUnavailable(false)
      setSuggestion({ score: data.ai_suggested_score, justification: data.ai_suggested_justification })
      if (data.ai_suggested_score !== null) setScore(String(Math.round(data.ai_suggested_score * 100)))
    },
    onError: (err) => {
      if (isAiUnavailable(err)) setAiUnavailable(true)
    },
  })

  const confirm = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/evaluations/{evaluation_id}/manual-review/{answer_id}', {
          params: { path: { evaluation_id: evaluationId, answer_id: answerId } },
          body: { score: Number(score) / 100 },
        }),
      ),
    onSuccess: () => {
      pushToast('Calificación registrada', 'success')
      void queryClient.invalidateQueries({ queryKey: qk.evaluation.manualReview(evaluationId) })
    },
  })

  return (
    <Card>
      <h3 className="font-medium text-ink">{exerciseTitle}</h3>
      <p className="mt-2 whitespace-pre-wrap rounded-btn bg-canvas p-3 text-sm text-ink-secondary">
        {String(answer.text ?? JSON.stringify(answer))}
      </p>

      <div className="mt-4 flex flex-col gap-2">
        <Textarea
          placeholder="Rúbrica para la sugerencia de IA (opcional)"
          value={rubric}
          onChange={(e) => setRubric(e.target.value)}
          rows={2}
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={!rubric.trim() || suggest.isPending}
          onClick={() => suggest.mutate()}
        >
          {suggest.isPending ? 'Consultando...' : '✨ Sugerir con IA'}
        </Button>
      </div>

      {aiUnavailable && (
        <Callout tone="ai" className="mt-3">
          El asistente de IA no está disponible en este momento.
        </Callout>
      )}
      {suggestion && (
        <Callout tone="ai" className="mt-3">
          <p className="font-medium">
            Sugerencia: {suggestion.score !== null ? `${Math.round(suggestion.score * 100)}%` : '—'}
          </p>
          <p className="mt-1">{suggestion.justification}</p>
        </Callout>
      )}

      <div className="mt-4 flex items-end gap-2 border-t border-hairline pt-4">
        <div className="flex-1">
          <Input
            type="number"
            min={0}
            max={100}
            placeholder="Nota (0-100)"
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
        </div>
        <Button disabled={!score || confirm.isPending} onClick={() => confirm.mutate()}>
          Confirmar nota
        </Button>
      </div>
    </Card>
  )
}

export function EvaluationManagePage() {
  const { evaluationId } = useParams<{ evaluationId: string }>()
  const [tab, setTab] = useState('respuestas')

  const { data: answers, isLoading: loadingAnswers } = useQuery({
    queryKey: qk.evaluation.answers(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/answers', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId) && tab === 'respuestas',
  })

  const { data: manualReview, isLoading: loadingReview } = useQuery({
    queryKey: qk.evaluation.manualReview(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/evaluations/{evaluation_id}/manual-review', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId) && tab === 'revision',
  })

  const { data: alerts, isLoading: loadingAlerts } = useQuery({
    queryKey: qk.evaluation.integrityAlerts(evaluationId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/ai/evaluations/{evaluation_id}/integrity-alerts', {
          params: { path: { evaluation_id: evaluationId! } },
        }),
      ),
    enabled: Boolean(evaluationId) && tab === 'integridad',
  })

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">Gestión de evaluación</h1>

      <Tabs
        className="mb-6"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'respuestas', label: 'Respuestas' },
          { value: 'revision', label: 'Revisión manual' },
          { value: 'integridad', label: 'Integridad' },
        ]}
      />

      {tab === 'respuestas' && (
        <>
          {loadingAnswers && <Spinner className="size-6" />}
          {!loadingAnswers && answers?.length === 0 && (
            <EmptyState emoji="📭" title="Todavía no hay respuestas" />
          )}
          <div className="flex flex-col gap-2">
            {answers?.map((answer) => (
              <div
                key={answer.answer_id}
                className="flex items-center justify-between rounded-card border border-hairline bg-raised px-4 py-3"
              >
                <span className="text-sm text-ink-secondary">
                  Estudiante {answer.student_id.slice(0, 8)}
                </span>
                <div className="flex items-center gap-2">
                  {answer.ai_suggested_score !== null && (
                    <Badge tint="lavender">IA: {Math.round(answer.ai_suggested_score * 100)}%</Badge>
                  )}
                  <Badge tint={answer.correct ? 'mint' : answer.needs_manual_review ? 'sky' : 'rose'}>
                    {answer.needs_manual_review
                      ? 'Pendiente'
                      : `${Math.round((answer.manual_score ?? answer.score) * 100)}%`}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'revision' && (
        <>
          {loadingReview && <Spinner className="size-6" />}
          {!loadingReview && manualReview?.length === 0 && (
            <EmptyState emoji="✅" title="No hay respuestas pendientes de revisión" />
          )}
          <div className="flex flex-col gap-4">
            {manualReview?.map((item) => (
              <ManualReviewRow
                key={item.answer_id}
                evaluationId={evaluationId!}
                answerId={item.answer_id}
                exerciseTitle={item.exercise_title}
                answer={item.answer}
              />
            ))}
          </div>
        </>
      )}

      {tab === 'integridad' && (
        <>
          {loadingAlerts && <Spinner className="size-6" />}
          {!loadingAlerts && alerts?.length === 0 && (
            <EmptyState emoji="🛡️" title="Sin alertas de integridad" />
          )}
          <div className="flex flex-col gap-2">
            {alerts?.map((alert) => (
              <Callout key={alert.id} tone={alert.suspicious ? 'warning' : 'info'}>
                <p className="font-medium">{alert.suspicious ? 'Posible alerta' : 'Sin hallazgos'}</p>
                <p className="mt-1">{alert.reasoning}</p>
                <p className="mt-2 text-xs opacity-70">
                  Esto es informativo — nunca aplica una sanción automáticamente.
                </p>
              </Callout>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
