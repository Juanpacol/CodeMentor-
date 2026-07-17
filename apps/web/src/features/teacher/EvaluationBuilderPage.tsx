import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { EXERCISE_TYPE_LABELS } from '../../components/exercises/registry'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Tag } from '../../components/ui/Tag'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

export function EvaluationBuilderPage() {
  const navigate = useNavigate()
  const [groupId, setGroupId] = useState('')
  const [title, setTitle] = useState('')
  const [mode, setMode] = useState<'fixed' | 'cumulative'>('cumulative')
  const [upToTopicId, setUpToTopicId] = useState('')
  const [durationMinutes, setDurationMinutes] = useState('')
  const [isRanked, setIsRanked] = useState(false)
  const [selectedExercises, setSelectedExercises] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const { data: groups } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })

  const { data: topics } = useQuery({
    queryKey: qk.topics(),
    queryFn: () => unwrap(apiClient.GET('/topics')),
  })

  const { data: exercises } = useQuery({
    queryKey: qk.exercises(),
    queryFn: () => unwrap(apiClient.GET('/exercises')),
  })

  const publishedExercises = (exercises ?? []).filter((e) => e.status === 'published')

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/evaluations', {
          body: {
            group_id: groupId,
            title,
            mode,
            up_to_topic_id: mode === 'fixed' ? upToTopicId : null,
            duration_minutes: durationMinutes ? Number(durationMinutes) : null,
            is_ranked: isRanked,
            exercise_ids: selectedExercises,
          },
        }),
      ),
    onSuccess: (evaluation) => navigate(`/app/docente/evaluaciones/${evaluation.id}`),
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo crear la evaluación'),
  })

  function toggleExercise(id: string) {
    setSelectedExercises((prev) => (prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate()
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold text-ink">Nueva evaluación</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <Card>
          <div className="flex flex-col gap-4">
            <div>
              <Label htmlFor="title">Título</Label>
              <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>

            <div>
              <Label htmlFor="group">Grupo</Label>
              <Select id="group" required value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                <option value="">Selecciona un grupo</option>
                {groups?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="mode">Alcance</Label>
              <Select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as 'fixed' | 'cumulative')}
              >
                <option value="cumulative">Acumulativo (todo lo habilitado hasta hoy)</option>
                <option value="fixed">Fijo (hasta un tema específico)</option>
              </Select>
            </div>

            {mode === 'fixed' && (
              <div>
                <Label htmlFor="up_to_topic">Hasta el tema</Label>
                <Select
                  id="up_to_topic"
                  required
                  value={upToTopicId}
                  onChange={(e) => setUpToTopicId(e.target.value)}
                >
                  <option value="">Selecciona un tema</option>
                  {topics?.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </Select>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="duration">Duración (minutos, opcional)</Label>
                <Input
                  id="duration"
                  type="number"
                  min={1}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(e.target.value)}
                />
              </div>
              <div className="flex items-end pb-2.5">
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={isRanked}
                    onChange={(e) => setIsRanked(e.target.checked)}
                  />
                  Con tabla de posiciones
                </label>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-ink">
            Ejercicios ({selectedExercises.length} seleccionados)
          </h2>
          <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
            {publishedExercises.map((exercise) => (
              <label
                key={exercise.id}
                className="flex cursor-pointer items-center gap-3 rounded-btn border border-hairline-strong px-3 py-2 hover:bg-hover"
              >
                <input
                  type="checkbox"
                  checked={selectedExercises.includes(exercise.id)}
                  onChange={() => toggleExercise(exercise.id)}
                />
                <span className="flex-1 text-sm text-ink">{exercise.title}</span>
                <Tag>{EXERCISE_TYPE_LABELS[exercise.type]}</Tag>
              </label>
            ))}
          </div>
        </Card>

        <FieldError>{error}</FieldError>

        <Button
          type="submit"
          disabled={create.isPending || selectedExercises.length === 0 || !groupId}
        >
          {create.isPending ? 'Creando...' : 'Crear evaluación'}
        </Button>
      </form>
    </div>
  )
}
