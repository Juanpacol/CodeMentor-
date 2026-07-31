import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

/** Exactamente uno de los cuatro, nunca varios: es el mismo invariante que el
 * `CheckConstraint` de la tabla, expresado como un solo selector para que la UI
 * no permita construir un estado que el backend rechaza. */
type Target = 'topic' | 'exercise' | 'evaluation' | 'guide'

const TARGET_LABELS: Record<Target, string> = {
  topic: 'Un tema completo',
  exercise: 'Un ejercicio suelto',
  evaluation: 'Un examen',
  guide: 'Un taller (guía)',
}

export function AssignmentsTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [target, setTarget] = useState<Target>('topic')
  const [targetId, setTargetId] = useState('')
  const [dueAt, setDueAt] = useState('')

  const { data: assignments, isLoading } = useQuery({
    queryKey: qk.assignments.forGroup(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/assignments', {
          params: { path: { group_id: groupId } },
        }),
      ),
  })

  const { data: curriculum } = useQuery({
    queryKey: qk.curriculum(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId } } }),
      ),
  })
  const topics = curriculum?.map((entry) => entry.topic) ?? []

  const { data: exercises } = useQuery({
    queryKey: qk.exercises(),
    queryFn: () => unwrap(apiClient.GET('/exercises')),
  })

  const { data: evaluations } = useQuery({
    queryKey: qk.groupEvaluations(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/evaluations', { params: { path: { group_id: groupId } } }),
      ),
  })

  const { data: guides } = useQuery({
    queryKey: qk.guides.published(groupId),
    queryFn: () =>
      unwrap(apiClient.GET('/groups/{group_id}/guides', { params: { path: { group_id: groupId } } })),
  })

  const invalidate = () =>
    void queryClient.invalidateQueries({ queryKey: qk.assignments.forGroup(groupId) })

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/groups/{group_id}/assignments', {
          params: { path: { group_id: groupId } },
          body: {
            title,
            topic_id: target === 'topic' ? targetId : null,
            exercise_id: target === 'exercise' ? targetId : null,
            evaluation_id: target === 'evaluation' ? targetId : null,
            guide_id: target === 'guide' ? targetId : null,
            // `datetime-local` no lleva zona; se interpreta como hora local del
            // docente, que es lo que él quiso decir con "hasta el viernes".
            due_at: dueAt ? new Date(dueAt).toISOString() : null,
          },
        }),
      ),
    onSuccess: () => {
      setError(null)
      setTitle('')
      setTargetId('')
      setDueAt('')
      pushToast('Asignación creada', 'success')
      invalidate()
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo crear la asignación'),
  })

  const remove = useMutation({
    mutationFn: (assignmentId: string) =>
      unwrap(
        apiClient.DELETE('/assignments/{assignment_id}', {
          params: { path: { assignment_id: assignmentId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Asignación eliminada', 'default')
      invalidate()
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo eliminar la asignación'),
  })

  const canSubmit = title.trim() !== '' && targetId !== '' && !create.isPending

  const nameFor = (assignment: {
    topic_id: string | null
    exercise_id: string | null
    evaluation_id: string | null
    guide_id: string | null
  }) => {
    if (assignment.topic_id) {
      return topics.find((t) => t.id === assignment.topic_id)?.name ?? 'Tema'
    }
    if (assignment.exercise_id) {
      return exercises?.find((e) => e.id === assignment.exercise_id)?.title ?? 'Ejercicio'
    }
    if (assignment.evaluation_id) {
      return evaluations?.find((e) => e.id === assignment.evaluation_id)?.title ?? 'Examen'
    }
    return guides?.find((g) => g.id === assignment.guide_id)?.title ?? 'Taller'
  }

  const targetKindLabel = (assignment: {
    topic_id: string | null
    exercise_id: string | null
    evaluation_id: string | null
    guide_id: string | null
  }) => {
    if (assignment.topic_id) return 'Tema'
    if (assignment.exercise_id) return 'Ejercicio'
    if (assignment.evaluation_id) return 'Examen'
    return 'Taller'
  }

  return (
    <div className="flex flex-col gap-6">
      <Callout tone="info">
        Lo que asignes acá le aparece al estudiante en su panel como pendiente, ordenado por
        fecha de entrega. Se marca como cumplido solo cuando resuelve bien los ejercicios.
      </Callout>

      {error && <Callout tone="error">{error}</Callout>}

      <section className="flex flex-col gap-4 rounded-card border border-hairline bg-raised p-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="as-title">Nombre de la asignación</Label>
            <Input
              id="as-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Taller de ciclos"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="as-due">Fecha de entrega (opcional)</Label>
            <Input
              id="as-due"
              type="datetime-local"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="as-target">Asignar</Label>
            <Select
              id="as-target"
              value={target}
              onChange={(e) => {
                setTarget(e.target.value as Target)
                setTargetId('')
              }}
            >
              {(Object.keys(TARGET_LABELS) as Target[]).map((t) => (
                <option key={t} value={t}>
                  {TARGET_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="as-target-id">
              {target === 'topic' && 'Tema'}
              {target === 'exercise' && 'Ejercicio'}
              {target === 'evaluation' && 'Examen'}
              {target === 'guide' && 'Taller'}
            </Label>
            <Select
              id="as-target-id"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
            >
              <option value="">Selecciona…</option>
              {target === 'topic' &&
                topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              {target === 'exercise' &&
                exercises?.map((exercise) => (
                  <option key={exercise.id} value={exercise.id}>
                    {exercise.title}
                  </option>
                ))}
              {target === 'evaluation' &&
                evaluations?.map((evaluation) => (
                  <option key={evaluation.id} value={evaluation.id}>
                    {evaluation.title}
                  </option>
                ))}
              {target === 'guide' &&
                guides?.map((guide) => (
                  <option key={guide.id} value={guide.id}>
                    {guide.title}
                  </option>
                ))}
            </Select>
          </div>
        </div>

        <div>
          <Button disabled={!canSubmit} onClick={() => create.mutate()}>
            {create.isPending ? 'Asignando…' : 'Asignar'}
          </Button>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="font-medium">Asignaciones de este grupo</h3>
        {isLoading && <Spinner className="size-6" />}
        {!isLoading && assignments?.length === 0 && (
          <EmptyState
            emoji="📋"
            title="Todavía no has asignado nada"
            description="Asigna un tema o un ejercicio y aparecerá en el panel de tus estudiantes."
          />
        )}
        {assignments?.map((assignment) => (
          <div
            key={assignment.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-hairline bg-raised px-4 py-3"
          >
            <div>
              <p className="font-medium text-ink">{assignment.title}</p>
              <p className="text-xs text-ink-secondary">
                {targetKindLabel(assignment)}: {nameFor(assignment)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tint={assignment.due_at ? 'sky' : 'neutral'}>
                {assignment.due_at
                  ? new Date(assignment.due_at).toLocaleString('es-CO')
                  : 'Sin fecha'}
              </Badge>
              <Button
                variant="secondary"
                size="sm"
                disabled={remove.isPending}
                onClick={() => remove.mutate(assignment.id)}
              >
                Eliminar
              </Button>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
