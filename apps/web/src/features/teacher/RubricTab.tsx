import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { EXERCISE_TYPE_LABELS } from '../../components/exercises/registry'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorDetails } from '../../components/ui/ErrorDetails'
import { Input, Label, Textarea } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pushToast } from '../../components/ui/toastStore'
import { useDraftState } from '../../hooks/useDraftState'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type ExerciseType = components['schemas']['ExerciseType']
type TopicLevel = components['schemas']['TopicLevel']

/** Debe coincidir con `MAX_ITEMS_PER_RUN` en modules/rubrics/service.py — el
 * backend rechaza con 409 más allá de esto, así que avisamos antes de enviar. */
const MAX_ITEMS = 15

const RUN_TERMINAL = ['done', 'partial', 'failed', 'cancelled']

const RUN_STATUS_LABEL: Record<string, string> = {
  pending: 'En cola',
  running: 'Generando…',
  done: 'Completada',
  partial: 'Completada parcialmente',
  failed: 'Falló',
  cancelled: 'Cancelada',
}

const RUN_STATUS_TINT: Record<string, 'neutral' | 'sky' | 'mint' | 'yellow' | 'rose'> = {
  pending: 'neutral',
  running: 'sky',
  done: 'mint',
  partial: 'yellow',
  failed: 'rose',
  // Neutral y no `rose`: cancelar es una decisión del docente, no un incidente.
  cancelled: 'neutral',
}

const ITEM_STATUS_LABEL: Record<string, string> = {
  pending: 'En espera',
  acquiring: 'Buscando material…',
  writing_guide: 'Redactando guía…',
  writing_exercises: 'Creando ejercicios…',
  done: 'Listo',
  failed: 'Falló',
  cancelled: 'Cancelado',
}

const ITEM_STATUS_TINT: Record<string, 'neutral' | 'sky' | 'lavender' | 'mint' | 'rose'> = {
  pending: 'neutral',
  acquiring: 'sky',
  writing_guide: 'lavender',
  writing_exercises: 'lavender',
  done: 'mint',
  failed: 'rose',
  cancelled: 'neutral',
}

const SUGGESTED_TYPES: ExerciseType[] = ['multiple_choice', 'true_false', 'find_error']

/** "Ciclos anidados" → { topic_name, level }. El nivel se puede fijar por línea
 * con un sufijo `| intermedio`; sin sufijo hereda el nivel por defecto elegido
 * arriba. Un textarea y no una tabla de filas porque el docente casi siempre
 * pega un temario que ya tiene escrito en otro lado. */
function parseTopics(raw: string, fallbackLevel: TopicLevel) {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, level] = line.split('|').map((part) => part.trim())
      const parsedLevel = ['basico', 'intermedio', 'avanzado'].includes(level ?? '')
        ? (level as TopicLevel)
        : fallbackLevel
      return { topic_name: name, level: parsedLevel, extra_urls: [] }
    })
    .filter((item) => item.topic_name.length >= 2)
}

export function RubricTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  // `error` no se persiste: es la consecuencia de un envío concreto, y
  // resucitarlo al volver a la pestaña señalaría un fallo que ya no existe.
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Un temario son varios minutos de escritura. Ver otra pestaña y volver no
  // puede costarlos — de ahí el borrador por grupo (ver `useDraftState`).
  const key = `rubrica:${groupId}`
  const [openRunId, setOpenRunId] = useDraftState<string | null>(`${key}:openRunId`, null)
  const [name, setName] = useDraftState(`${key}:name`, '')
  const [folderName, setFolderName] = useDraftState(`${key}:folderName`, '')
  const [languageId, setLanguageId] = useDraftState(`${key}:languageId`, '')
  const [templateId, setTemplateId] = useDraftState(`${key}:templateId`, '')
  const [defaultLevel, setDefaultLevel] = useDraftState<TopicLevel>(`${key}:level`, 'basico')
  const [topicsRaw, setTopicsRaw] = useDraftState(`${key}:topicsRaw`, '')
  const [acquireContent, setAcquireContent] = useDraftState(`${key}:acquireContent`, true)
  const [exerciseTypes, setExerciseTypes] = useDraftState<ExerciseType[]>(
    `${key}:exerciseTypes`,
    SUGGESTED_TYPES,
  )

  const { data: languages } = useQuery({
    queryKey: qk.languages,
    queryFn: () => unwrap(apiClient.GET('/languages')),
  })

  const { data: templates } = useQuery({
    queryKey: qk.guides.templates,
    queryFn: () => unwrap(apiClient.GET('/guide-templates')),
  })

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: qk.rubrics.runs(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/rubric-runs', {
          params: { path: { group_id: groupId } },
        }),
      ),
    // Mientras haya una corrida viva, la lista también se refresca: es la que
    // muestra el estado final cuando el docente cierra el detalle.
    refetchInterval: (query) =>
      query.state.data?.some((run) => !RUN_TERMINAL.includes(run.status)) ? 5000 : false,
  })

  const activeRunId = openRunId ?? runs?.find((run) => !RUN_TERMINAL.includes(run.status))?.id ?? null

  const { data: detail } = useQuery({
    queryKey: qk.rubrics.run(activeRunId ?? ''),
    enabled: Boolean(activeRunId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/rubric-runs/{run_id}', {
          params: { path: { run_id: activeRunId as string } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.data && RUN_TERMINAL.includes(query.state.data.run.status) ? false : 3000,
  })

  const parsedTopics = parseTopics(topicsRaw, defaultLevel)

  // Sube el PDF/Word de la rúbrica institucional y prellena el textarea de
  // temas con lo que la IA extrajo — el docente lo sigue editando con el
  // mismo control antes de "Generar contenido", el resto del flujo no cambia.
  const extractTopics = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return unwrap(
        apiClient.POST('/rubric-runs/extract-topics', {
          // openapi-fetch pasa un FormData tal cual — mismo workaround que
          // MaterialsTab.tsx para la subida de material RAG.
          body: formData as unknown as { file: string },
        }),
      )
    },
    onSuccess: (result) => {
      const extractedText = result.items
        .map((item) => `${item.topic_name} | ${item.level}`)
        .join('\n')
      setTopicsRaw((current) => (current ? `${current}\n${extractedText}` : extractedText))
      setError(null)
      pushToast(
        `${result.items.length} tema${result.items.length === 1 ? '' : 's'} extraído${result.items.length === 1 ? '' : 's'}, revísalos antes de generar`,
        'success',
      )
      if (fileInputRef.current) fileInputRef.current.value = ''
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo leer el documento'),
  })

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) extractTopics.mutate(file)
  }

  const createRun = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/groups/{group_id}/rubric-runs', {
          params: { path: { group_id: groupId } },
          body: {
            name,
            language_id: languageId,
            template_id: templateId,
            folder_name: folderName,
            items: parsedTopics,
            exercise_types: exerciseTypes,
            acquire_content: acquireContent,
          },
        }),
      ),
    onSuccess: (run) => {
      pushToast('Rúbrica en marcha: el contenido aparecerá como borrador', 'success')
      setError(null)
      setOpenRunId(run.id)
      setTopicsRaw('')
      void queryClient.invalidateQueries({ queryKey: qk.rubrics.runs(groupId) })
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo iniciar la rúbrica'),
  })

  const cancelRun = useMutation({
    mutationFn: (runId: string) =>
      unwrap(
        apiClient.POST('/rubric-runs/{run_id}/cancel', {
          params: { path: { run_id: runId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Cancelando… se detiene en unos segundos', 'default')
      void queryClient.invalidateQueries({ queryKey: qk.rubrics.runs(groupId) })
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo cancelar la corrida'),
  })

  const toggleType = (type: ExerciseType) =>
    setExerciseTypes((current) =>
      current.includes(type) ? current.filter((t) => t !== type) : [...current, type],
    )

  const tooManyTopics = parsedTopics.length > MAX_ITEMS
  const canSubmit =
    Boolean(name && folderName && languageId && templateId) &&
    parsedTopics.length > 0 &&
    !tooManyTopics &&
    exerciseTypes.length > 0 &&
    !createRun.isPending

  return (
    <div className="flex flex-col gap-6">
      <Callout tone="ai">
        Escribe los temas que quieres y la plataforma crea el temario, busca material de
        referencia, redacta una guía por tema y genera ejercicios para cada una. Todo queda
        como <strong>borrador</strong>: nada se publica hasta que tú lo revises.
      </Callout>

      {error && <Callout tone="error">{error}</Callout>}

      <section className="flex flex-col gap-4 rounded-card border border-hairline bg-raised p-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rubric-name">Nombre de la rúbrica</Label>
            <Input
              id="rubric-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Temario primer periodo"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rubric-folder">Carpeta de guías</Label>
            <Input
              id="rubric-folder"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="Guías 10-A"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rubric-language">Lenguaje</Label>
            <Select
              id="rubric-language"
              value={languageId}
              onChange={(e) => setLanguageId(e.target.value)}
            >
              <option value="">Selecciona…</option>
              {languages?.map((language) => (
                <option key={language.id} value={language.id}>
                  {language.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rubric-template">Plantilla de guía</Label>
            <Select
              id="rubric-template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
            >
              <option value="">Selecciona…</option>
              {templates?.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} · v{template.version}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="rubric-topics">Temas, uno por línea</Label>
            <div className="flex items-center gap-2">
              {extractTopics.isPending && <Spinner className="size-4" />}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={extractTopics.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                Subir documento (.pdf, .docx)
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                className="hidden"
                disabled={extractTopics.isPending}
                onChange={handleFileSelected}
              />
            </div>
          </div>
          <p className="text-sm text-muted">
            Sube la rúbrica institucional en PDF o Word y la plataforma propone los temas que
            trae, para que solo tengas que revisarlos y ajustarlos abajo.
          </p>
          <Textarea
            id="rubric-topics"
            rows={7}
            value={topicsRaw}
            onChange={(e) => setTopicsRaw(e.target.value)}
            placeholder={'Estructuras condicionales\nCiclos mientras | intermedio\nArreglos unidimensionales'}
          />
          <p className="text-sm text-muted">
            Agrega <code>| intermedio</code> o <code>| avanzado</code> al final de una línea
            para fijarle el nivel. {parsedTopics.length} tema
            {parsedTopics.length === 1 ? '' : 's'} detectado
            {parsedTopics.length === 1 ? '' : 's'}.
          </p>
          {tooManyTopics && (
            <Callout tone="warning">
              Máximo {MAX_ITEMS} temas por corrida: cada tema son varias llamadas al modelo y
              el cupo diario gratuito no alcanza para más. Divide el temario en dos rúbricas.
            </Callout>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="rubric-level">Nivel por defecto</Label>
          <Select
            id="rubric-level"
            value={defaultLevel}
            onChange={(e) => setDefaultLevel(e.target.value as TopicLevel)}
            className="sm:max-w-xs"
          >
            <option value="basico">Básico</option>
            <option value="intermedio">Intermedio</option>
            <option value="avanzado">Avanzado</option>
          </Select>
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">Tipos de ejercicio por guía</legend>
          <div className="flex flex-wrap gap-3">
            {(Object.keys(EXERCISE_TYPE_LABELS) as ExerciseType[]).map((type) => (
              <label key={type} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={exerciseTypes.includes(type)}
                  onChange={() => toggleType(type)}
                />
                {EXERCISE_TYPE_LABELS[type]}
              </label>
            ))}
          </div>
          {exerciseTypes.length > 4 && (
            <Callout tone="warning">
              Máximo 4 tipos por guía: son 4 llamadas al modelo por cada tema.
            </Callout>
          )}
        </fieldset>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={acquireContent}
            onChange={(e) => setAcquireContent(e.target.checked)}
          />
          Buscar material de referencia en Wikipedia y Wikibooks
        </label>

        <div>
          <Button
            onClick={() => createRun.mutate()}
            disabled={!canSubmit || exerciseTypes.length > 4}
          >
            {createRun.isPending ? 'Iniciando…' : 'Generar contenido'}
          </Button>
        </div>
      </section>

      {detail && (
        <section className="flex flex-col gap-3 rounded-card border border-hairline bg-raised p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h3 className="font-medium">{detail.run.name}</h3>
              <Badge tint={RUN_STATUS_TINT[detail.run.status] ?? 'neutral'}>
                {RUN_STATUS_LABEL[detail.run.status] ?? detail.run.status}
              </Badge>
            </div>
            {!RUN_TERMINAL.includes(detail.run.status) && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => cancelRun.mutate(detail.run.id)}
                disabled={cancelRun.isPending}
              >
                Cancelar
              </Button>
            )}
          </div>

          {detail.run.error_message && (
            <Callout tone="warning">{detail.run.error_message}</Callout>
          )}

          <ol className="flex flex-col gap-2">
            {detail.items.map((item) => (
              <li
                key={item.id}
                className="rounded-card border border-hairline px-3 py-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{item.topic_name}</span>
                  <span className="flex items-center gap-2 text-sm text-muted">
                    {item.status === 'done' && (
                      <>
                        <span>{item.sources_ingested} fuentes</span>
                        <span>·</span>
                        <span>{item.exercises_created} ejercicios</span>
                      </>
                    )}
                    {item.error_message && item.status === 'failed' && (
                      <span className="text-sm">{item.error_message}</span>
                    )}
                    <Badge tint={ITEM_STATUS_TINT[item.status] ?? 'neutral'}>
                      {ITEM_STATUS_LABEL[item.status] ?? item.status}
                    </Badge>
                  </span>
                </div>
                {item.status === 'failed' && (
                  <ErrorDetails code={item.error_code} details={item.error_details} />
                )}
              </li>
            ))}
          </ol>

          {RUN_TERMINAL.includes(detail.run.status) && (
            <p className="text-sm text-muted">
              Las guías están en la pestaña <strong>Guías</strong> y los ejercicios en el banco,
              ambos como borrador — revísalos y publícalos desde ahí.
            </p>
          )}
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h3 className="font-medium">Corridas anteriores</h3>
        {loadingRuns && <Spinner className="size-6" />}
        {!loadingRuns && runs?.length === 0 && (
          <EmptyState
            emoji="🧭"
            title="Todavía no has generado ningún temario"
            description="Llena la rúbrica de arriba y la plataforma se encarga del resto."
          />
        )}
        {runs?.map((run) => (
          <button
            key={run.id}
            type="button"
            onClick={() => setOpenRunId(run.id)}
            className="flex items-center justify-between gap-2 rounded-card border border-hairline bg-raised px-4 py-3 text-left"
          >
            <span>{run.name}</span>
            <Badge tint={RUN_STATUS_TINT[run.status] ?? 'neutral'}>
              {RUN_STATUS_LABEL[run.status] ?? run.status}
            </Badge>
          </button>
        ))}
      </section>
    </div>
  )
}
