import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

const PAGE_SIZE = 25

export function ErrorLogTab() {
  const [statusCode, setStatusCode] = useState('')
  const [path, setPath] = useState('')
  const [page, setPage] = useState(1)

  const parsedStatusCode = statusCode ? Number(statusCode) : undefined

  const { data, isLoading } = useQuery({
    queryKey: qk.observability.errors({ statusCode: parsedStatusCode, path, page }),
    queryFn: () =>
      unwrap(
        apiClient.GET('/observability/errors', {
          params: {
            query: {
              status_code: parsedStatusCode,
              path: path || undefined,
              page,
              page_size: PAGE_SIZE,
            },
          },
        }),
      ),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Filtrar por ruta..."
          value={path}
          onChange={(e) => {
            setPath(e.target.value)
            setPage(1)
          }}
          className="max-w-xs"
        />
        <Input
          placeholder="Código (ej. 500)"
          value={statusCode}
          onChange={(e) => {
            setStatusCode(e.target.value)
            setPage(1)
          }}
          className="max-w-[10rem]"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      )}

      {!isLoading && data && data.items.length === 0 && (
        <EmptyState emoji="✅" title="Sin errores registrados" description="Buena señal." />
      )}

      {!isLoading && data && data.items.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.items.map((item) => (
            <div
              key={item.id}
              className="rounded-card border border-hairline bg-raised p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <Badge tint="rose">{item.status_code}</Badge>
                <span className="font-mono text-xs text-ink-secondary">
                  {item.method} {item.path}
                </span>
                <span className="ml-auto text-xs text-ink-secondary">
                  {new Date(item.created_at).toLocaleString('es-CO')}
                </span>
              </div>
              <p className="text-sm text-ink">
                <span className="font-medium">{item.exception_type}:</span> {item.message}
              </p>
              {item.stacktrace && (
                <pre className="mt-2 max-h-40 overflow-auto rounded-btn bg-canvas p-2 text-xs text-ink-secondary">
                  {item.stacktrace}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Anterior
          </Button>
          <span className="text-xs text-ink-secondary">
            Página {page} de {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </Button>
        </div>
      )}
    </div>
  )
}
