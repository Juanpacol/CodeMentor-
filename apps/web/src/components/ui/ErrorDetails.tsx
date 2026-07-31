interface ErrorDetailsProps {
  code?: string | null
  details?: Record<string, unknown> | null
}

/** Etiquetas para las claves que produce el backend. Sin esto el docente lee
 * `providers` y `last_error`, que son nombres pensados para el código. */
const LABELS: Record<string, string> = {
  task: 'Tarea',
  providers: 'Proveedores de IA intentados',
  attempts: 'Intentos',
  last_error: 'Último error del modelo',
  exception: 'Excepción',
  error: 'Error',
}

function renderValue(value: unknown) {
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-5">
        {value.map((entry, i) => (
          <li key={i} className="break-words">
            {String(entry)}
          </li>
        ))}
      </ul>
    )
  }
  if (value !== null && typeof value === 'object') {
    return <pre className="overflow-x-auto">{JSON.stringify(value, null, 2)}</pre>
  }
  return <span className="break-words">{String(value)}</span>
}

/** El "por qué" detrás de un mensaje de error, plegado.
 *
 * Mismo idioma que la tabla "Ver datos" de `ChartCard`: el texto amable queda a
 * la vista y el detalle técnico vive un clic más abajo. Existe porque tres
 * causas muy distintas —clave de API vencida, cuota diaria agotada, el modelo
 * devolviendo JSON inválido— se leían con la misma frase genérica, y el detalle
 * que las distingue solo estaba en los logs del servidor, donde el docente no
 * puede entrar. `lib/print.ts` lo despliega solo al imprimir.
 */
export function ErrorDetails({ code, details }: ErrorDetailsProps) {
  const entries = Object.entries(details ?? {}).filter(
    ([, value]) => value !== null && value !== undefined && value !== '',
  )
  if (!code && entries.length === 0) return null

  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs text-ink-secondary hover:text-ink">
        Ver detalle{code ? ` · ${code}` : ''}
      </summary>
      <dl className="mt-2 flex flex-col gap-2 rounded-btn bg-canvas p-3 text-xs text-ink-secondary">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt className="font-medium text-ink">{LABELS[key] ?? key}</dt>
            <dd className="mt-0.5">{renderValue(value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}
