import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge, type TintColor } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Label } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

const PAGE_SIZE = 25

/** Los dos códigos que de verdad se buscan acá: 500 es un bug nuestro, 503 una
 * dependencia caída (proveedor de IA, sandbox). Como atajo y no como único
 * camino — el campo de código sigue aceptando cualquier valor. */
const QUICK_CODES = ['500', '503']

/** 503 no es lo mismo que 500: uno es una dependencia caída (se reintenta solo)
 * y el otro un bug que hay que arreglar. Pintarlos igual escondía esa diferencia. */
const CODE_TINT: Record<string, TintColor> = { '503': 'yellow' }

export function ErrorLogTab() {
  const [statusCode, setStatusCode] = useState('')
  const [path, setPath] = useState('')
  const [page, setPage] = useState(1)

  const parsedStatusCode = statusCode ? Number(statusCode) : undefined
  const hasFilters = Boolean(path || statusCode)

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
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label htmlFor="err-path">Ruta (opcional)</Label>
          <Input
            id="err-path"
            placeholder="p. ej. rubric-runs"
            value={path}
            onChange={(e) => {
              setPath(e.target.value)
              setPage(1)
            }}
            className="max-w-xs"
          />
        </div>
        <div>
          <Label htmlFor="err-code">Código (opcional)</Label>
          <Input
            id="err-code"
            placeholder="p. ej. 500"
            value={statusCode}
            onChange={(e) => {
              setStatusCode(e.target.value)
              setPage(1)
            }}
            className="max-w-[10rem]"
          />
        </div>
        {QUICK_CODES.map((code) => (
          <Button
            key={code}
            variant="secondary"
            size="sm"
            onClick={() => {
              setStatusCode(statusCode === code ? '' : code)
              setPage(1)
            }}
          >
            {statusCode === code ? `✓ ${code}` : code}
          </Button>
        ))}
        {hasFilters && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setPath('')
              setStatusCode('')
              setPage(1)
            }}
          >
            Limpiar filtros
          </Button>
        )}
      </div>

      {/* Sin esto los dos campos de arriba se leían como un buscador obligatorio
        * y la lista —que ya viene cargada— parecía vacía a la espera de una
        * búsqueda. Decir cuántos hay y en qué orden es lo que faltaba. */}
      {!isLoading && data && (
        <p className="text-xs text-ink-secondary">
          {data.total === 0
            ? 'No hay errores registrados.'
            : `${data.total} error${data.total === 1 ? '' : 'es'} ${
                hasFilters ? 'con este filtro' : 'registrados'
              }, del más reciente al más antiguo.`}
        </p>
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      )}

      {/* Un filtro que no casa NO es "buena señal": decirle eso al docente lo
        * manda a concluir que no hubo errores cuando solo escribió mal la ruta. */}
      {!isLoading && data && data.items.length === 0 && (
        hasFilters ? (
          <EmptyState
            emoji="🔍"
            title="Ningún error coincide con el filtro"
            description="Limpia los filtros para ver todos los errores registrados."
          />
        ) : (
          <EmptyState emoji="✅" title="Sin errores registrados" description="Buena señal." />
        )
      )}

      {!isLoading && data && data.items.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.items.map((item) => (
            <div
              key={item.id}
              className="rounded-card border border-hairline bg-raised p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <Badge tint={CODE_TINT[String(item.status_code)] ?? 'rose'}>
                  {item.status_code}
                </Badge>
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
