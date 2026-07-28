import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Dialog } from '../../components/ui/Dialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorDetails } from '../../components/ui/ErrorDetails'
import { Input, Textarea } from '../../components/ui/Input'
import { Markdown } from '../../components/ui/Markdown'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pushToast } from '../../components/ui/toastStore'
import { useDraftState } from '../../hooks/useDraftState'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { parseTemplateText } from './parseTemplateText'

type Section = { heading: string; instructions: string }

const STATUS_LABEL: Record<string, string> = {
  generating: 'Generando…',
  draft: 'Borrador · IA',
  published: 'Publicada',
  archived: 'Archivada',
  failed: 'Falló',
  cancelled: 'Cancelada',
}

const STATUS_TINT: Record<string, 'neutral' | 'lavender' | 'mint' | 'rose'> = {
  generating: 'neutral',
  draft: 'lavender',
  published: 'mint',
  archived: 'neutral',
  failed: 'rose',
  // Neutral y no `rose`: cancelar es una decisión, no un fallo.
  cancelled: 'neutral',
}

const EMPTY_SECTION: Section = { heading: '', instructions: '' }

/** Cada sección es una llamada al modelo por guía, así que el tope acota el
 * costo. 15 y no 10 porque los formatos institucionales reales rondan las 6-8 y
 * el margen evita que importar uno completo se corte a la mitad. */
const MAX_SECTIONS = 15

export function GuidesTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  const [folderDialog, setFolderDialog] = useState(false)
  const [templateDialog, setTemplateDialog] = useState(false)
  const [generateDialog, setGenerateDialog] = useState(false)
  const [openGuideId, setOpenGuideId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [folderName, setFolderName] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState('')

  // Solo el formulario de plantilla se persiste: es el largo (varias secciones
  // redactadas a mano) y el que dolía perder al cambiar de pestaña. Ver
  // `useDraftState`.
  const key = `guias:${groupId}`
  const [templateName, setTemplateName] = useDraftState(`${key}:templateName`, '')
  const [templateTone, setTemplateTone] = useDraftState(`${key}:templateTone`, 'cercano')
  const [templateLevel, setTemplateLevel] = useDraftState(`${key}:templateLevel`, 'basico')
  const [sections, setSections] = useDraftState<Section[]>(`${key}:sections`, [
    { ...EMPTY_SECTION },
  ])
  // No se persiste como borrador: es material de paso, y una vez convertido en
  // secciones dejarlo ahí solo invita a importarlo dos veces.
  const [pasted, setPasted] = useState('')
  const [genTemplateId, setGenTemplateId] = useState('')
  const [genTopicId, setGenTopicId] = useState('')

  const { data: folders, isLoading: loadingFolders } = useQuery({
    queryKey: qk.guides.folders(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/guide-folders', {
          params: { path: { group_id: groupId } },
        }),
      ),
  })

  const { data: templates } = useQuery({
    queryKey: qk.guides.templates,
    queryFn: () => unwrap(apiClient.GET('/guide-templates')),
  })

  const { data: curriculum } = useQuery({
    queryKey: qk.curriculum(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId } } }),
      ),
  })
  const topics = curriculum?.map((entry) => entry.topic) ?? []

  const activeFolderId = selectedFolderId || folders?.[0]?.id || ''

  const { data: guides } = useQuery({
    queryKey: qk.guides.inFolder(activeFolderId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/guide-folders/{folder_id}/guides', {
          params: { path: { folder_id: activeFolderId } },
        }),
      ),
    enabled: Boolean(activeFolderId),
    // Mientras alguna guía se esté generando, sondear: la fila ES el job (no hay
    // tabla de jobs), así que su `status` es el progreso.
    refetchInterval: (query) =>
      query.state.data?.some((g) => g.status === 'generating') ? 3000 : false,
  })

  const invalidateGuides = () => {
    void queryClient.invalidateQueries({ queryKey: qk.guides.inFolder(activeFolderId) })
    void queryClient.invalidateQueries({ queryKey: qk.ai.pendingApprovals })
  }

  const onError = (fallback: string) => (err: unknown) =>
    setError(err instanceof ApiError ? err.detail : fallback)

  // Mismas reglas que `GuideSectionSpec` en el backend: título no vacío e
  // instrucciones de 10 caracteres para arriba, en TODAS las secciones.
  const templateCanSubmit =
    templateName.trim() !== '' &&
    sections.length > 0 &&
    sections.every((s) => s.heading.trim() !== '' && s.instructions.trim().length >= 10)

  const createFolder = useMutation({
    mutationFn: (name: string) =>
      unwrap(
        apiClient.POST('/groups/{group_id}/guide-folders', {
          params: { path: { group_id: groupId } },
          body: { name },
        }),
      ),
    onSuccess: () => {
      setError(null)
      setFolderDialog(false)
      setFolderName('')
      pushToast('Carpeta creada', 'success')
      void queryClient.invalidateQueries({ queryKey: qk.guides.folders(groupId) })
    },
    onError: onError('No se pudo crear la carpeta'),
  })

  const saveTemplate = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/guide-templates', {
          body: {
            name: templateName,
            sections,
            tone: templateTone,
            target_level: templateLevel as 'basico' | 'intermedio' | 'avanzado',
          },
        }),
      ),
    onSuccess: (template) => {
      setError(null)
      setTemplateDialog(false)
      setSections([{ ...EMPTY_SECTION }])
      setTemplateName('')
      pushToast(`Plantilla guardada (versión ${template.version})`, 'success')
      void queryClient.invalidateQueries({ queryKey: qk.guides.templates })
    },
    onError: onError('No se pudo guardar la plantilla'),
  })

  const generate = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/ai/guides/generate', {
          body: {
            folder_id: activeFolderId,
            template_id: genTemplateId,
            topic_id: genTopicId,
          },
        }),
      ),
    onSuccess: () => {
      setError(null)
      setGenerateDialog(false)
      pushToast('Generando la guía… aparecerá como borrador al terminar', 'success')
      invalidateGuides()
    },
    onError: onError('No se pudo generar la guía'),
  })

  const autoGenerate = useMutation({
    mutationFn: ({ folderId, templateId }: { folderId: string; templateId: string }) =>
      unwrap(
        apiClient.PATCH('/guide-folders/{folder_id}', {
          params: { path: { folder_id: folderId } },
          // null apaga la autogeneración (semántica de asignación).
          body: { auto_generate_template_id: templateId || null },
        }),
      ),
    onSuccess: (folder) => {
      pushToast(
        folder.auto_generate_template_id
          ? 'Autogeneración activada para esta carpeta'
          : 'Autogeneración desactivada',
        'success',
      )
      void queryClient.invalidateQueries({ queryKey: qk.guides.folders(groupId) })
    },
    onError: onError('No se pudo cambiar la autogeneración'),
  })

  const publish = useMutation({
    mutationFn: (guideId: string) =>
      unwrap(
        apiClient.POST('/guides/{guide_id}/publish', {
          params: { path: { guide_id: guideId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Guía publicada', 'success')
      invalidateGuides()
    },
    onError: onError('No se pudo publicar la guía'),
  })

  const cancelGuide = useMutation({
    mutationFn: (guideId: string) =>
      unwrap(
        apiClient.POST('/guides/{guide_id}/cancel', {
          params: { path: { guide_id: guideId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Generación cancelada', 'default')
      invalidateGuides()
    },
    onError: onError('No se pudo cancelar la guía'),
  })

  const archive = useMutation({
    mutationFn: (guideId: string) =>
      unwrap(
        apiClient.POST('/guides/{guide_id}/archive', {
          params: { path: { guide_id: guideId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Guía archivada', 'success')
      setOpenGuideId(null)
      invalidateGuides()
    },
    onError: onError('No se pudo archivar la guía'),
  })

  const activeFolder = folders?.find((f) => f.id === activeFolderId)
  const openGuide = guides?.find((g) => g.id === openGuideId)

  return (
    <div>
      {error && (
        <Callout tone="error" className="mb-4">
          {error}
        </Callout>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-secondary">
          Guías de clase redactadas por IA a partir de tus temas y tu material de apoyo. Siempre
          llegan como borrador: tú decides qué se publica.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setTemplateDialog(true)}>
            Nueva plantilla
          </Button>
          <Button variant="secondary" onClick={() => setFolderDialog(true)}>
            Nueva carpeta
          </Button>
          <Button disabled={!activeFolderId || !templates?.length} onClick={() => setGenerateDialog(true)}>
            Generar guía
          </Button>
        </div>
      </div>

      {loadingFolders && (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      )}

      {!loadingFolders && folders && folders.length === 0 && (
        <EmptyState
          emoji="📓"
          title="Aún no hay carpetas de guías"
          description="Crea una carpeta y una plantilla para empezar a generar guías de este grupo."
        />
      )}

      {!loadingFolders && folders && folders.length > 0 && (
        <>
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <div className="min-w-48">
              <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="folder">
                Carpeta
              </label>
              <Select
                id="folder"
                value={activeFolderId}
                onChange={(e) => setSelectedFolderId(e.target.value)}
              >
                {folders.map((folder) => (
                  <option key={folder.id} value={folder.id}>
                    {folder.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="min-w-56">
              <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="auto">
                Autogenerar al habilitar un tema
              </label>
              <Select
                id="auto"
                value={activeFolder?.auto_generate_template_id ?? ''}
                disabled={autoGenerate.isPending}
                onChange={(e) =>
                  autoGenerate.mutate({ folderId: activeFolderId, templateId: e.target.value })
                }
              >
                <option value="">Desactivada</option>
                {templates?.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} (v{template.version})
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {guides && guides.length === 0 && (
            <EmptyState emoji="✨" title="Esta carpeta todavía no tiene guías" />
          )}

          <div className="flex flex-col gap-2">
            {guides?.map((guide) => (
              <button
                key={guide.id}
                type="button"
                onClick={() => setOpenGuideId(guide.id)}
                className="flex items-center justify-between gap-3 rounded-card border border-hairline bg-raised px-4 py-3 text-left hover:border-primary"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{guide.title}</p>
                  <p className="text-xs text-ink-secondary">
                    {new Date(guide.created_at).toLocaleDateString('es-CO')}
                    {guide.sources?.length ? ` · ${guide.sources.length} fuente(s)` : ''}
                  </p>
                </div>
                <Badge tint={STATUS_TINT[guide.status]}>{STATUS_LABEL[guide.status]}</Badge>
              </button>
            ))}
          </div>
        </>
      )}

      <Dialog open={folderDialog} onClose={() => setFolderDialog(false)} title="Nueva carpeta">
        <div className="flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="fname">
              Nombre
            </label>
            <Input id="fname" value={folderName} onChange={(e) => setFolderName(e.target.value)} />
          </div>
          <Button
            disabled={createFolder.isPending || !folderName.trim()}
            onClick={() => createFolder.mutate(folderName.trim())}
          >
            {createFolder.isPending ? 'Creando…' : 'Crear'}
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={templateDialog}
        onClose={() => setTemplateDialog(false)}
        title="Plantilla de guía"
      >
        <div className="flex flex-col gap-4">
          <Callout tone="info">
            Guardar con un nombre que ya existe crea una versión nueva; la anterior se conserva para
            que las guías viejas sigan siendo explicables.
          </Callout>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="tname">
              Nombre
            </label>
            <Input
              id="tname"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="tone">
                Tono
              </label>
              <Input id="tone" value={templateTone} onChange={(e) => setTemplateTone(e.target.value)} />
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="level">
                Nivel
              </label>
              <Select
                id="level"
                value={templateLevel}
                onChange={(e) => setTemplateLevel(e.target.value)}
              >
                <option value="basico">Básico</option>
                <option value="intermedio">Intermedio</option>
                <option value="avanzado">Avanzado</option>
              </Select>
            </div>
          </div>

          {/* El docente casi siempre ya tiene el formato escrito en Word o en
            * un documento compartido: llenarlo sección por sección era volver a
            * teclear algo que ya existe. Lo pegado se parsea a filas editables
            * —no se guarda directo— para que revise antes. */}
          <details className="rounded-card border border-hairline p-3">
            <summary className="cursor-pointer text-xs font-medium text-ink-secondary">
              Pegar un formato que ya tienes, o subirlo
            </summary>
            <div className="mt-3 flex flex-col gap-2">
              <Textarea
                aria-label="Formato de guía para importar"
                rows={6}
                placeholder={'## Introducción\nContextualiza el tema…\n\n## Objetivos\nUn objetivo general…'}
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
              />
              <p className="text-xs text-muted">
                Reconoce títulos markdown (<code>##</code>) y, si no hay, toma la primera línea
                de cada bloque separado por una línea en blanco.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={parseTemplateText(pasted).length === 0}
                  onClick={() => {
                    setSections(parseTemplateText(pasted).slice(0, MAX_SECTIONS))
                    setPasted('')
                  }}
                >
                  Convertir en secciones
                </Button>
                {/* Se lee en el navegador con `file.text()`: es texto plano y no
                  * necesita endpoint de subida, a diferencia del material RAG. */}
                <label className="cursor-pointer text-sm text-ink-secondary underline hover:text-ink">
                  Subir .md o .txt
                  <input
                    type="file"
                    accept=".md,.txt"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file) return
                      setPasted(await file.text())
                      e.target.value = ''
                    }}
                  />
                </label>
              </div>
            </div>
          </details>

          <div className="flex flex-col gap-3">
            <p className="text-xs font-medium text-ink-secondary">
              Secciones (una llamada a la IA por sección)
            </p>
            {sections.map((section, index) => (
              <div key={index} className="rounded-card border border-hairline p-3">
                <Input
                  aria-label={`Título de la sección ${index + 1}`}
                  placeholder="Título (p. ej. Objetivos)"
                  value={section.heading}
                  onChange={(e) =>
                    setSections((prev) =>
                      prev.map((s, i) => (i === index ? { ...s, heading: e.target.value } : s)),
                    )
                  }
                />
                <Textarea
                  aria-label={`Instrucciones de la sección ${index + 1}`}
                  className="mt-2"
                  rows={2}
                  placeholder="Qué debe contener (mínimo 10 caracteres)"
                  value={section.instructions}
                  onChange={(e) =>
                    setSections((prev) =>
                      prev.map((s, i) => (i === index ? { ...s, instructions: e.target.value } : s)),
                    )
                  }
                />
                {section.heading.trim() !== '' && section.instructions.trim().length < 10 && (
                  <p className="mt-1 text-xs text-error">
                    El backend exige al menos 10 caracteres de instrucciones.
                  </p>
                )}
                {sections.length > 1 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-2"
                    onClick={() => setSections((prev) => prev.filter((_, i) => i !== index))}
                  >
                    Quitar
                  </Button>
                )}
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              disabled={sections.length >= MAX_SECTIONS}
              onClick={() => setSections((prev) => [...prev, { ...EMPTY_SECTION }])}
            >
              Añadir sección
            </Button>
          </div>

          {/* Antes el botón dejaba enviar una plantilla que el backend rechaza,
            * y el 422 llegaba sin decir cuál sección estaba mal. */}
          <Button
            disabled={saveTemplate.isPending || !templateCanSubmit}
            onClick={() => saveTemplate.mutate()}
          >
            {saveTemplate.isPending ? 'Guardando…' : 'Guardar plantilla'}
          </Button>
        </div>
      </Dialog>

      <Dialog open={generateDialog} onClose={() => setGenerateDialog(false)} title="Generar guía">
        <div className="flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="gtpl">
              Plantilla
            </label>
            <Select id="gtpl" value={genTemplateId} onChange={(e) => setGenTemplateId(e.target.value)}>
              <option value="">Selecciona una plantilla</option>
              {templates?.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} (v{template.version})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary" htmlFor="gtopic">
              Tema
            </label>
            <Select id="gtopic" value={genTopicId} onChange={(e) => setGenTopicId(e.target.value)}>
              <option value="">Selecciona un tema</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.name}
                </option>
              ))}
            </Select>
          </div>
          <Button
            disabled={generate.isPending || !genTemplateId || !genTopicId}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? 'Enviando…' : 'Generar'}
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={Boolean(openGuide)}
        onClose={() => setOpenGuideId(null)}
        title={openGuide?.title ?? 'Guía'}
      >
        {openGuide && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Badge tint={STATUS_TINT[openGuide.status]}>{STATUS_LABEL[openGuide.status]}</Badge>
              {openGuide.origin === 'ai' && <Badge tint="lavender">Generada por IA</Badge>}
            </div>

            {openGuide.status === 'failed' && (
              <div>
                <Callout tone="error">{openGuide.error_message ?? 'La generación falló.'}</Callout>
                <ErrorDetails code={openGuide.error_code} details={openGuide.error_details} />
              </div>
            )}

            {openGuide.status === 'generating' && (
              <div className="flex flex-wrap items-center gap-3">
                <span className="flex items-center gap-2 text-sm text-ink-secondary">
                  <Spinner className="size-4" /> Redactando las secciones…
                </span>
                {/* Sin esto, una guía cuya generación se atasca no tiene salida:
                  * `Archivar` la rechaza justamente en `generating`. */}
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={cancelGuide.isPending}
                  onClick={() => cancelGuide.mutate(openGuide.id)}
                >
                  {cancelGuide.isPending ? 'Cancelando…' : 'Cancelar generación'}
                </Button>
              </div>
            )}

            {openGuide.sources && openGuide.sources.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-ink-secondary">
                  Material del curso en que se basó
                </p>
                <ul className="list-disc pl-5 text-xs text-ink-secondary">
                  {openGuide.sources.map((source) => (
                    <li key={source}>{source}</li>
                  ))}
                </ul>
              </div>
            )}

            {openGuide.content_md && (
              <div className="max-h-96 overflow-y-auto rounded-card border border-hairline p-4">
                <Markdown md={openGuide.content_md} />
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {openGuide.status === 'draft' && (
                <Button disabled={publish.isPending} onClick={() => publish.mutate(openGuide.id)}>
                  Publicar
                </Button>
              )}
              {openGuide.status !== 'generating' && openGuide.status !== 'archived' && (
                <Button
                  variant="secondary"
                  disabled={archive.isPending}
                  onClick={() => archive.mutate(openGuide.id)}
                >
                  Archivar
                </Button>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  )
}
