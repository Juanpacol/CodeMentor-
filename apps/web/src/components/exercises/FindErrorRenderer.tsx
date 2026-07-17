import { cn } from '../../lib/cn'
import type { ExerciseRendererProps } from './types'

interface FindErrorAnswer {
  line: number
  kind?: string
}

const ERROR_KINDS = [
  { value: 'sintaxis', label: 'Error de sintaxis' },
  { value: 'logica', label: 'Error de lógica' },
  { value: 'tipos', label: 'Error de tipos' },
]

export function FindErrorRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<FindErrorAnswer>) {
  const statement = String(content.statement ?? '')
  const code = String(content.code ?? '')
  const lines = code.split('\n')

  return (
    <div>
      <p className="mb-4 text-base text-ink">{statement}</p>
      <div className="overflow-hidden rounded-card border border-hairline-strong">
        {lines.map((line, i) => {
          const lineNumber = i + 1
          const selected = value?.line === lineNumber
          return (
            <button
              key={i}
              type="button"
              disabled={disabled}
              onClick={() => onChange({ ...value, line: lineNumber } as FindErrorAnswer)}
              className={cn(
                'flex w-full gap-4 px-4 py-1.5 text-left font-mono text-sm transition-colors duration-100',
                selected ? 'bg-primary/15 text-ink' : 'text-ink-secondary hover:bg-hover',
              )}
            >
              <span className="w-6 shrink-0 text-right text-ink-muted">{lineNumber}</span>
              <span className="whitespace-pre">{line}</span>
            </button>
          )
        })}
      </div>
      <div className="mt-4">
        <p className="mb-1.5 text-sm font-medium text-ink-secondary">Tipo de error (opcional)</p>
        <div className="flex flex-wrap gap-2">
          {ERROR_KINDS.map((kind) => (
            <button
              key={kind.value}
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange({ ...(value ?? { line: 0 }), kind: kind.value } as FindErrorAnswer)
              }
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150',
                value?.kind === kind.value
                  ? 'border-primary bg-primary/10 text-ink'
                  : 'border-hairline-strong text-ink-secondary hover:bg-hover',
              )}
            >
              {kind.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
