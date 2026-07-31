import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { EXERCISE_TYPE_LABELS, type ExerciseType } from '../../components/exercises/registry'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { Tag } from '../../components/ui/Tag'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'
import { ExerciseContentForm } from './ExerciseContentForm'

type Exercise = components['schemas']['ExerciseOut']

interface ExerciseVariant {
  title: string
  content: Record<string, unknown>
}

export function EvaluationBuilderPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [groupId, setGroupId] = useState('')
  const [title, setTitle] = useState('')
  const [mode, setMode] = useState<'fixed' | 'cumulative'>('cumulative')
  const [upToTopicId, setUpToTopicId] = useState('')
  const [durationMinutes, setDurationMinutes] = useState('')
  const [isRanked, setIsRanked] = useState(false)
  const [weightPercent, setWeightPercent] = useState('')
  const [selectedExercises, setSelectedExercises] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  // Variantes por IA (ítem 21): se piden a partir de un ejercicio ya
  // publicado, se revisan/editan acá mismo, y solo las aceptadas se crean de
  // verdad (vía POST /exercises) y quedan seleccionadas para la evaluación.
  const [variantSourceId, setVariantSourceId] = useState<string | null>(null)
  const [variants, setVariants] = useState<ExerciseVariant[]>([])
  const [editingVariantIndex, setEditingVariantIndex] = useState<number | null>(null)

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

  const { data: groupEvaluations } = useQuery({
    queryKey: qk.groupEvaluations(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/evaluations', { params: { path: { group_id: groupId } } }),
      ),
    enabled: Boolean(groupId),
  })

  const publishedExercises = (exercises ?? []).filter((e) => e.status === 'published')

  // Suma de lo que YA pesa el grupo más lo que se está por crear — aviso, no
  // bloqueo: un docente puede estar a mitad de armar el periodo y todavía no
  // haber cargado todas las evaluaciones.
  const existingWeightSum = (groupEvaluations ?? []).reduce(
    (sum, e) => sum + (e.weight_percent ?? 0),
    0,
  )
  const newWeight = weightPercent ? Number(weightPercent) : 0
  const totalWeightAfterCreate = existingWeightSum + newWeight

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
            weight_percent: weightPercent ? Number(weightPercent) : null,
            exercise_ids: selectedExercises,
          },
        }),
      ),
    onSuccess: (evaluation) => navigate(`/app/docente/evaluaciones/${evaluation.id}`),
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo crear la evaluación'),
  })

  const generateVariants = useMutation({
    mutationFn: (exerciseId: string) =>
      unwrap(
        apiClient.POST('/ai/exercises/{exercise_id}/variants', {
          params: { path: { exercise_id: exerciseId } },
          body: { count: 3 },
        }),
      ),
    onSuccess: (result, exerciseId) => {
      setVariantSourceId(exerciseId)
      setVariants(result)
      if (result.length === 0) {
        pushToast('La IA no pudo generar variantes esta vez', 'error')
      }
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudieron generar variantes'),
  })

  const acceptVariant = useMutation({
    mutationFn: ({ variant, source }: { variant: ExerciseVariant; source: Exercise }) =>
      unwrap(
        apiClient.POST('/exercises', {
          body: {
            language_id: source.language_id,
            title: variant.title,
            type: source.type,
            content: variant.content,
            status: 'published',
          },
        }),
      ),
    onSuccess: (created, { variant }) => {
      setSelectedExercises((prev) => [...prev, created.id])
      setVariants((prev) => prev.filter((v) => v !== variant))
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
      pushToast('Variante aceptada y seleccionada', 'success')
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo aceptar la variante'),
  })

  function discardVariant(variant: ExerciseVariant) {
    setVariants((prev) => prev.filter((v) => v !== variant))
  }

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
              <div>
                <Label htmlFor="weight">Porcentaje de la nota (opcional)</Label>
                <Input
                  id="weight"
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={weightPercent}
                  onChange={(e) => setWeightPercent(e.target.value)}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={isRanked}
                onChange={(e) => setIsRanked(e.target.checked)}
              />
              Con tabla de posiciones
            </label>
            {groupId && totalWeightAfterCreate > 0 && totalWeightAfterCreate !== 100 && (
              <Callout tone="warning">
                Las evaluaciones de este grupo suman {totalWeightAfterCreate}% de la nota
                {totalWeightAfterCreate > 100 ? ', ya pasaste el 100%' : ' — todavía no llegan a 100%'}
                .
              </Callout>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-ink">
            Ejercicios ({selectedExercises.length} seleccionados)
          </h2>
          <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
            {publishedExercises.map((exercise) => (
              <div
                key={exercise.id}
                className="flex items-center gap-3 rounded-btn border border-hairline-strong px-3 py-2 hover:bg-hover"
              >
                <label className="flex flex-1 cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedExercises.includes(exercise.id)}
                    onChange={() => toggleExercise(exercise.id)}
                  />
                  <span className="flex-1 text-sm text-ink">{exercise.title}</span>
                  <Tag>{EXERCISE_TYPE_LABELS[exercise.type]}</Tag>
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={generateVariants.isPending}
                  onClick={() => generateVariants.mutate(exercise.id)}
                >
                  {generateVariants.isPending && generateVariants.variables === exercise.id ? (
                    <Spinner className="size-4" />
                  ) : (
                    'Pedir variantes'
                  )}
                </Button>
              </div>
            ))}
          </div>
        </Card>

        {variants.length > 0 && (
          <Card>
            <h2 className="mb-1 text-sm font-semibold text-ink">Variantes generadas</h2>
            <p className="mb-3 text-xs text-ink-secondary">
              Revísalas antes de aceptar — solo las que aceptes se crean y se suman a la
              evaluación.
            </p>
            <div className="flex flex-col gap-2">
              {variants.map((variant, index) => {
                const source = (exercises ?? []).find((e) => e.id === variantSourceId)
                return (
                  <div
                    key={index}
                    className="flex flex-col gap-2 rounded-btn border border-hairline-strong px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-1 text-sm text-ink">{variant.title}</span>
                      {source && <Tag>{EXERCISE_TYPE_LABELS[source.type]}</Tag>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={!source || acceptVariant.isPending}
                        onClick={() => source && acceptVariant.mutate({ variant, source })}
                      >
                        {acceptVariant.isPending && acceptVariant.variables?.variant === variant
                          ? 'Aceptando…'
                          : 'Aceptar'}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => setEditingVariantIndex(index)}
                      >
                        Editar
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => discardVariant(variant)}
                      >
                        Descartar
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>
        )}

        <FieldError>{error}</FieldError>

        <Button
          type="submit"
          disabled={create.isPending || selectedExercises.length === 0 || !groupId}
        >
          {create.isPending ? 'Creando...' : 'Crear evaluación'}
        </Button>
      </form>

      <Dialog
        open={editingVariantIndex !== null}
        onClose={() => setEditingVariantIndex(null)}
        title="Editar variante"
      >
        {editingVariantIndex !== null &&
          variants[editingVariantIndex] &&
          (() => {
            const source = (exercises ?? []).find((e) => e.id === variantSourceId)
            const variant = variants[editingVariantIndex]
            if (!source) return null
            return (
              <div className="flex flex-col gap-4">
                <div>
                  <Label htmlFor="variant-title">Título</Label>
                  <Input
                    id="variant-title"
                    value={variant.title}
                    onChange={(e) => {
                      const next = [...variants]
                      next[editingVariantIndex] = { ...variant, title: e.target.value }
                      setVariants(next)
                    }}
                  />
                </div>
                <ExerciseContentForm
                  type={source.type as ExerciseType}
                  value={variant.content}
                  onChange={(content) => {
                    const next = [...variants]
                    next[editingVariantIndex] = { ...variant, content }
                    setVariants(next)
                  }}
                />
                <Button type="button" onClick={() => setEditingVariantIndex(null)}>
                  Listo
                </Button>
              </div>
            )
          })()}
      </Dialog>
    </div>
  )
}
