import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Dialog } from '../../components/ui/Dialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

export function MaterialsTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [topicId, setTopicId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: curriculum } = useQuery({
    queryKey: qk.curriculum(groupId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId } } }),
      ),
  })
  const topics = curriculum?.map((entry) => entry.topic) ?? []

  const { data: documents, isLoading } = useQuery({
    queryKey: qk.ragDocuments(),
    queryFn: () => unwrap(apiClient.GET('/ai/rag/documents', { params: { query: {} } })),
  })

  const upload = useMutation({
    mutationFn: ({ file, title, topicId }: { file: File; title: string; topicId: string }) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title)
      if (topicId) formData.append('topic_id', topicId)
      return unwrap(
        apiClient.POST('/ai/rag/documents', {
          // openapi-fetch pasa un FormData tal cual (no lo serializa a JSON)
          // solo si ya es una instancia de FormData — mismo workaround que
          // MembersTab.tsx para la subida de CSV.
          body: formData as unknown as { file: string; title: string },
        }),
      )
    },
    onSuccess: () => {
      setError(null)
      setDialogOpen(false)
      setTitle('')
      setTopicId('')
      pushToast('Material cargado', 'success')
      void queryClient.invalidateQueries({ queryKey: qk.ragDocuments() })
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.detail : 'No se pudo cargar el archivo'),
  })

  const remove = useMutation({
    mutationFn: (documentId: string) =>
      unwrap(
        apiClient.DELETE('/ai/rag/documents/{document_id}', {
          params: { path: { document_id: documentId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Material eliminado', 'success')
      void queryClient.invalidateQueries({ queryKey: qk.ragDocuments() })
    },
  })

  function handleSubmit() {
    const file = fileInputRef.current?.files?.[0]
    if (!file || !title.trim()) {
      setError('Selecciona un archivo y escribe un título')
      return
    }
    upload.mutate({ file, title, topicId })
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-ink-secondary">
          Material de referencia (.md/.txt) que el Tutor de IA usa para fundamentar sus pistas.
        </p>
        <Button onClick={() => setDialogOpen(true)}>Cargar material</Button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      )}

      {!isLoading && documents && documents.length === 0 && (
        <EmptyState emoji="📚" title="Aún no hay material cargado" />
      )}

      {!isLoading && documents && documents.length > 0 && (
        <div className="flex flex-col gap-2">
          {documents.map((doc) => {
            const topicName = topics.find((t) => t.id === doc.topic_id)?.name
            return (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-card border border-hairline bg-raised px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{doc.title}</p>
                  <p className="text-xs text-ink-secondary">
                    {topicName ?? 'General'} · {doc.chunk_count} fragmento(s) ·{' '}
                    {new Date(doc.created_at).toLocaleDateString('es-CO')}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(doc.id)}
                >
                  Eliminar
                </Button>
              </div>
            )
          })}
        </div>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Cargar material">
        <div className="flex flex-col gap-4">
          {error && <Callout tone="error">{error}</Callout>}
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary">Título</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary">
              Tema (opcional)
            </label>
            <Select value={topicId} onChange={(e) => setTopicId(e.target.value)}>
              <option value="">General (sin tema)</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-secondary">
              Archivo (.md o .txt)
            </label>
            <input ref={fileInputRef} type="file" accept=".md,.txt" className="text-sm text-ink" />
          </div>
          <Button disabled={upload.isPending} onClick={handleSubmit}>
            {upload.isPending ? 'Cargando...' : 'Cargar'}
          </Button>
        </div>
      </Dialog>
    </div>
  )
}
