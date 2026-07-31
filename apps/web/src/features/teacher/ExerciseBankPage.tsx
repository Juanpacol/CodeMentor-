import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { EXERCISE_TYPE_LABELS, type ExerciseType } from '../../components/exercises/registry'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Callout } from '../../components/ui/Callout'
import { Dialog } from '../../components/ui/Dialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Tag } from '../../components/ui/Tag'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'
import { ExerciseContentForm } from './ExerciseContentForm'

const EXERCISE_TYPES = Object.keys(EXERCISE_TYPE_LABELS) as ExerciseType[]

type Exercise = components['schemas']['ExerciseOut']

/** Crear, editar y duplicar son el mismo formulario con distinto punto de
 * partida y distinto verbo al guardar; tenerlos como tres diálogos separados
 * habría triplicado el `ExerciseContentForm` de 8 tipos. */
type Mode = { kind: 'create' } | { kind: 'edit'; exercise: Exercise } | { kind: 'duplicate'; exercise: Exercise }

const MODE_TITLE: Record<Mode['kind'], string> = {
  create: 'Crear ejercicio',
  edit: 'Editar ejercicio',
  duplicate: 'Duplicar ejercicio',
}

function ExerciseDialog({ mode, onClose }: { mode: Mode | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const source = mode && mode.kind !== 'create' ? mode.exercise : null

  const [languageId, setLanguageId] = useState('')
  const [title, setTitle] = useState('')
  const [type, setType] = useState<ExerciseType>('true_false')
  const [content, setContent] = useState<Record<string, unknown>>({})
  const [status, setStatus] = useState<'draft' | 'published'>('published')
  const [error, setError] = useState<string | null>(null)

  // Reinicia el formulario cada vez que cambia el ejercicio de partida. La
  // `key` del componente en el padre garantiza que esto corra al abrir.
  const [seeded, setSeeded] = useState(false)
  if (mode && !seeded) {
    setSeeded(true)
    setLanguageId(source?.language_id ?? '')
    // "Copia de X" y no "X": dos ejercicios con el mismo título en la lista son
    // indistinguibles justo cuando acabas de duplicar y quieres editar uno.
    setTitle(source ? (mode.kind === 'duplicate' ? `Copia de ${source.title}` : source.title) : '')
    setType((source?.type as ExerciseType) ?? 'true_false')
    setContent((source?.content as Record<string, unknown>) ?? {})
    setStatus((source?.status as 'draft' | 'published') ?? 'published')
    setError(null)
  }

  const { data: languages } = useQuery({
    queryKey: qk.languages,
    queryFn: () => unwrap(apiClient.GET('/languages')),
  })

  const save = useMutation({
    mutationFn: () => {
      // El PATCH no acepta `language_id` ni `type`: cambiar el tipo invalidaría
      // el `content` entero, así que para eso se duplica y se crea de nuevo.
      if (mode?.kind === 'edit') {
        return unwrap(
          apiClient.PATCH('/exercises/{exercise_id}', {
            params: { path: { exercise_id: mode.exercise.id } },
            body: { title, content, status },
          }),
        )
      }
      return unwrap(
        apiClient.POST('/exercises', {
          body: { language_id: languageId, title, type, content, status },
        }),
      )
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
      pushToast(mode?.kind === 'edit' ? 'Ejercicio actualizado' : 'Ejercicio creado', 'success')
      onClose()
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo guardar el ejercicio'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    save.mutate()
  }

  return (
    <Dialog open={mode !== null} onClose={onClose} title={mode ? MODE_TITLE[mode.kind] : ''}>
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
              disabled={mode?.kind === 'edit'}
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
              disabled={mode?.kind === 'edit'}
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
        {mode?.kind === 'edit' && (
          <p className="text-xs text-ink-secondary">
            El lenguaje y el tipo no se pueden cambiar: el contenido depende del tipo. Si
            necesitas otro, duplica el ejercicio.
          </p>
        )}

        <ExerciseContentForm type={type} value={content} onChange={setContent} />

        <div>
          <Label htmlFor="ex-status">Estado</Label>
          <Select id="ex-status" value={status} onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}>
            <option value="published">Publicado (visible para estudiantes)</option>
            <option value="draft">Borrador</option>
          </Select>
        </div>

        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={save.isPending} className="w-full">
          {save.isPending ? 'Guardando...' : 'Guardar ejercicio'}
        </Button>
      </form>
    </Dialog>
  )
}

/** Ítem 5 (dashboard docente): historial de versiones + restaurar — solo se
 * genera una fila cuando se edita un ejercicio ya publicado. */
function ExerciseHistoryDialog({
  exerciseId,
  onClose,
}: {
  exerciseId: string | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  const { data: versions, isLoading } = useQuery({
    queryKey: qk.exerciseVersions(exerciseId ?? ''),
    queryFn: () =>
      unwrap(
        apiClient.GET('/exercises/{exercise_id}/versions', {
          params: { path: { exercise_id: exerciseId! } },
        }),
      ),
    enabled: Boolean(exerciseId),
  })

  const restore = useMutation({
    mutationFn: (versionId: string) =>
      unwrap(
        apiClient.POST('/exercises/{exercise_id}/versions/{version_id}/restore', {
          params: { path: { exercise_id: exerciseId!, version_id: versionId } },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.exercises() })
      void queryClient.invalidateQueries({ queryKey: qk.exerciseVersions(exerciseId ?? '') })
      pushToast('Versión restaurada', 'success')
      onClose()
    },
  })

  return (
    <Dialog open={exerciseId !== null} onClose={onClose} title="Historial de versiones">
      {isLoading && <p className="text-sm text-ink-secondary">Cargando...</p>}
      {!isLoading && versions?.length === 0 && (
        <p className="text-sm text-ink-secondary">
          Sin versiones anteriores — este ejercicio no se ha editado desde que se publicó.
        </p>
      )}
      <div className="flex flex-col gap-2">
        {versions?.map((version) => (
          <Card key={version.id} className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-ink">
                v{version.version} — {version.title}
              </p>
              <p className="text-xs text-ink-secondary">
                {new Date(version.created_at).toLocaleString('es-CO')}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={restore.isPending}
              onClick={() => restore.mutate(version.id)}
            >
              Restaurar
            </Button>
          </Card>
        ))}
      </div>
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
  const [mode, setMode] = useState<Mode | null>(null)
  // Fuerza el remontaje del diálogo por cada apertura, que es lo que reinicia
  // el formulario con el ejercicio de partida correcto.
  const [dialogKey, setDialogKey] = useState(0)
  const [aiOpen, setAiOpen] = useState(false)
  const [historyExerciseId, setHistoryExerciseId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const openDialog = (next: Mode) => {
    setDialogKey((k) => k + 1)
    setMode(next)
  }

  const { data: exercises, isLoading } = useQuery({
    queryKey: qk.exercises(),
    queryFn: () => unwrap(apiClient.GET('/exercises')),
  })

  // Filtrado en cliente: el banco es de decenas de ejercicios, no de miles, y
  // la lista ya viene entera — hacerlo en el servidor añadiría un round-trip
  // por cada tecla sin ganar nada.
  const filtered = exercises?.filter(
    (exercise) =>
      exercise.title.toLowerCase().includes(search.trim().toLowerCase()) &&
      (!typeFilter || exercise.type === typeFilter) &&
      (!statusFilter || exercise.status === statusFilter),
  )
  const hasFilters = Boolean(search || typeFilter || statusFilter)

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink">Banco de ejercicios</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setAiOpen(true)}>
            ✨ Generar con IA
          </Button>
          <Button onClick={() => openDialog({ kind: 'create' })}>Crear ejercicio</Button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <Label htmlFor="ex-search">Buscar por título</Label>
          <Input
            id="ex-search"
            placeholder="p. ej. ciclos"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>
        <div>
          <Label htmlFor="ex-filter-type">Tipo</Label>
          <Select id="ex-filter-type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">Todos</option>
            {EXERCISE_TYPES.map((t) => (
              <option key={t} value={t}>
                {EXERCISE_TYPE_LABELS[t]}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="ex-filter-status">Estado</Label>
          <Select
            id="ex-filter-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="published">Publicado</option>
            <option value="draft">Borrador</option>
          </Select>
        </div>
      </div>

      {!isLoading && filtered && filtered.length === 0 && (
        <EmptyState
          emoji={hasFilters ? '🔍' : '🧩'}
          title={hasFilters ? 'Ningún ejercicio coincide' : 'El banco está vacío'}
          description={
            hasFilters
              ? 'Prueba con otro título, tipo o estado.'
              : 'Crea uno a mano o genera un borrador con IA.'
          }
        />
      )}

      {!isLoading && filtered && filtered.length > 0 && (
        <div className="flex flex-col gap-2">
          {filtered.map((exercise) => (
            <Card key={exercise.id} className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{exercise.title}</span>
                <Tag>{EXERCISE_TYPE_LABELS[exercise.type]}</Tag>
                {exercise.origin === 'ai' && <Badge tint="lavender">IA</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <Badge tint={exercise.status === 'published' ? 'mint' : 'yellow'}>
                  {exercise.status === 'published' ? 'Publicado' : 'Borrador'}
                </Badge>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => openDialog({ kind: 'edit', exercise })}
                >
                  Editar
                </Button>
                {/* "Copiar y pegar" un ejercicio sin inventar un formato de
                  * intercambio: se abre el formulario ya lleno. */}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => openDialog({ kind: 'duplicate', exercise })}
                >
                  Duplicar
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setHistoryExerciseId(exercise.id)}
                >
                  Historial
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <ExerciseDialog key={dialogKey} mode={mode} onClose={() => setMode(null)} />
      <GenerateWithAiDialog open={aiOpen} onClose={() => setAiOpen(false)} />
      <ExerciseHistoryDialog
        exerciseId={historyExerciseId}
        onClose={() => setHistoryExerciseId(null)}
      />
    </div>
  )
}
