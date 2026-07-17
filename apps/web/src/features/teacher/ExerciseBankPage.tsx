import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { EXERCISE_TYPE_LABELS, type ExerciseType } from '../../components/exercises/registry'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Callout } from '../../components/ui/Callout'
import { Dialog } from '../../components/ui/Dialog'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Tag } from '../../components/ui/Tag'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { ExerciseContentForm } from './ExerciseContentForm'

const EXERCISE_TYPES = Object.keys(EXERCISE_TYPE_LABELS) as ExerciseType[]

function CreateExerciseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [languageId, setLanguageId] = useState('')
  const [title, setTitle] = useState('')
  const [type, setType] = useState<ExerciseType>('true_false')
  const [content, setContent] = useState<Record<string, unknown>>({})
  const [status, setStatus] = useState<'draft' | 'published'>('published')
  const [error, setError] = useState<string | null>(null)

  const { data: languages } = useQuery({
    queryKey: qk.languages,
    queryFn: () => unwrap(apiClient.GET('/languages')),
  })

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/exercises', {
          body: { language_id: languageId, title, type, content, status },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
      pushToast('Ejercicio creado', 'success')
      setTitle('')
      setContent({})
      onClose()
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo crear el ejercicio'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Crear ejercicio">
      <form onSubmit={handleSubmit} className="flex max-h-[70vh] flex-col gap-4 overflow-y-auto">
        <div>
          <Label htmlFor="ex-title">Título</Label>
          <Input id="ex-title" required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="ex-language">Lenguaje</Label>
            <Select
              id="ex-language"
              required
              value={languageId}
              onChange={(e) => setLanguageId(e.target.value)}
            >
              <option value="">Selecciona</option>
              {languages?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="ex-type">Tipo</Label>
            <Select
              id="ex-type"
              value={type}
              onChange={(e) => {
                setType(e.target.value as ExerciseType)
                setContent({})
              }}
            >
              {EXERCISE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {EXERCISE_TYPE_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <ExerciseContentForm type={type} value={content} onChange={setContent} />

        <div>
          <Label htmlFor="ex-status">Estado</Label>
          <Select id="ex-status" value={status} onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}>
            <option value="published">Publicado (visible para estudiantes)</option>
            <option value="draft">Borrador</option>
          </Select>
        </div>

        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={create.isPending} className="w-full">
          {create.isPending ? 'Creando...' : 'Crear ejercicio'}
        </Button>
      </form>
    </Dialog>
  )
}

function GenerateWithAiDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [groupId, setGroupId] = useState('')
  const [topicId, setTopicId] = useState('')
  const [type, setType] = useState<ExerciseType>('true_false')
  const [unavailable, setUnavailable] = useState(false)

  const { data: groups } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })
  const { data: topics } = useQuery({
    queryKey: qk.topics(),
    queryFn: () => unwrap(apiClient.GET('/topics')),
  })

  const generate = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/ai/exercises/generate', {
          body: { group_id: groupId, topic_id: topicId, exercise_type: type },
        }),
      ),
    onSuccess: () => {
      setUnavailable(false)
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
      void queryClient.invalidateQueries({ queryKey: qk.ai.pendingApprovals })
      pushToast('Ejercicio generado como borrador — revísalo en la bandeja de aprobaciones', 'success')
      onClose()
    },
    onError: (err) => {
      if (isAiUnavailable(err)) setUnavailable(true)
    },
  })

  return (
    <Dialog open={open} onClose={onClose} title="Generar ejercicio con IA">
      <div className="flex flex-col gap-4">
        <div>
          <Label htmlFor="ai-group">Grupo</Label>
          <Select id="ai-group" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
            <option value="">Selecciona</option>
            {groups?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="ai-topic">Tema</Label>
          <Select id="ai-topic" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
            <option value="">Selecciona</option>
            {topics?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="ai-type">Tipo de ejercicio</Label>
          <Select id="ai-type" value={type} onChange={(e) => setType(e.target.value as ExerciseType)}>
            {EXERCISE_TYPES.map((t) => (
              <option key={t} value={t}>
                {EXERCISE_TYPE_LABELS[t]}
              </option>
            ))}
          </Select>
        </div>
        {unavailable && (
          <Callout tone="ai">El asistente de IA no está disponible en este momento.</Callout>
        )}
        <Button disabled={!groupId || !topicId || generate.isPending} onClick={() => generate.mutate()}>
          {generate.isPending ? 'Generando...' : '✨ Generar'}
        </Button>
      </div>
    </Dialog>
  )
}

export function ExerciseBankPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)

  const { data: exercises, isLoading } = useQuery({
    queryKey: qk.exercises(),
    queryFn: () => unwrap(apiClient.GET('/exercises')),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Banco de ejercicios</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setAiOpen(true)}>
            ✨ Generar con IA
          </Button>
          <Button onClick={() => setCreateOpen(true)}>Crear ejercicio</Button>
        </div>
      </div>

      {!isLoading && (
        <div className="flex flex-col gap-2">
          {exercises?.map((exercise) => (
            <Card key={exercise.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-medium text-ink">{exercise.title}</span>
                <Tag>{EXERCISE_TYPE_LABELS[exercise.type]}</Tag>
                {exercise.origin === 'ai' && <Badge tint="lavender">IA</Badge>}
              </div>
              <Badge tint={exercise.status === 'published' ? 'mint' : 'yellow'}>
                {exercise.status === 'published' ? 'Publicado' : 'Borrador'}
              </Badge>
            </Card>
          ))}
        </div>
      )}

      <CreateExerciseDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <GenerateWithAiDialog open={aiOpen} onClose={() => setAiOpen(false)} />
    </div>
  )
}
