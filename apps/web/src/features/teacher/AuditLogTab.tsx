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

export function AuditLogTab() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: qk.observability.audit({ action, page }),
    queryFn: () =>
      unwrap(
        apiClient.GET('/observability/audit', {
          params: {
            query: { action: action || undefined, page, page_size: PAGE_SIZE },
          },
        }),
      ),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="flex flex-col gap-4">
      <Input
        placeholder="Filtrar por acción (ej. role_changed)..."
        value={action}
        onChange={(e) => {
          setAction(e.target.value)
          setPage(1)
        }}
        className="max-w-sm"
      />

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      )}

      {!isLoading && data && data.items.length === 0 && (
        <EmptyState emoji="🗂️" title="Sin actividad registrada todavía" />
      )}

      {!isLoading && data && data.items.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.items.map((item) => (
            <div key={item.id} className="rounded-card border border-hairline bg-raised p-4">
              <div className="mb-1 flex items-center gap-2">
                <Badge tint="lavender">{item.action}</Badge>
                <span className="text-xs text-ink-secondary">
                  {item.target_type} · {item.target_id}
                </span>
                <span className="ml-auto text-xs text-ink-secondary">
                  {new Date(item.created_at).toLocaleString('es-CO')}
                </span>
              </div>
              {Object.keys(item.details).length > 0 && (
                <pre className="mt-2 overflow-auto rounded-btn bg-canvas p-2 text-xs text-ink-secondary">
                  {JSON.stringify(item.details, null, 2)}
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
