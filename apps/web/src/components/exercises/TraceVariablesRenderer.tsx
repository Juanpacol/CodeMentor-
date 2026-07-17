import { Button } from '../ui/Button'
import type { ExerciseRendererProps } from './types'

interface TraceVariablesAnswer {
  trace: Array<Record<string, unknown>>
}

interface StepRow {
  variable: string
  value: string
}

/** Convierte el texto tal como lo escribe el estudiante a un tipo más
 * preciso cuando es posible (números, booleanos) — el grader compara los
 * pasos por igualdad estructural, así que "5" (string) no coincidiría con
 * 5 (número) si no se intenta esta conversión. */
function coerceValue(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

function stepToRows(step: Record<string, unknown> | undefined): StepRow[] {
  if (!step) return [{ variable: '', value: '' }]
  const entries = Object.entries(step)
  return entries.length > 0
    ? entries.map(([variable, value]) => ({ variable, value: String(value) }))
    : [{ variable: '', value: '' }]
}

export function TraceVariablesRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<TraceVariablesAnswer>) {
  const statement = String(content.statement ?? '')
  const code = String(content.code ?? '')
  const steps = value?.trace ?? [{}]

  function updateStep(stepIndex: number, rows: StepRow[]) {
    const nextSteps = steps.map((step, i) => {
      if (i !== stepIndex) return step
      const next: Record<string, unknown> = {}
      for (const row of rows) {
        if (row.variable.trim()) next[row.variable.trim()] = coerceValue(row.value)
      }
      return next
    })
    onChange({ trace: nextSteps })
  }

  return (
    <div>
      <p className="mb-3 text-base text-ink">{statement}</p>
      {code && (
        <pre className="mb-4 whitespace-pre-wrap rounded-card border border-hairline-strong bg-canvas p-4 font-mono text-sm text-ink-secondary">
          {code}
        </pre>
      )}
      <div className="flex flex-col gap-3">
        {steps.map((step, stepIndex) => {
          const rows = stepToRows(step)
          return (
            <div key={stepIndex} className="rounded-card border border-hairline p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-secondary">
                Paso {stepIndex + 1}
              </p>
              <div className="flex flex-col gap-2">
                {rows.map((row, rowIndex) => (
                  <div key={rowIndex} className="flex gap-2">
                    <input
                      disabled={disabled}
                      placeholder="variable"
                      value={row.variable}
                      onChange={(e) => {
                        const next = [...rows]
                        next[rowIndex] = { ...row, variable: e.target.value }
                        updateStep(stepIndex, next)
                      }}
                      className="w-1/2 rounded border border-hairline-strong bg-canvas px-2 py-1 font-mono text-sm text-ink focus:border-primary focus:outline-none"
                    />
                    <input
                      disabled={disabled}
                      placeholder="valor"
                      value={row.value}
                      onChange={(e) => {
                        const next = [...rows]
                        next[rowIndex] = { ...row, value: e.target.value }
                        updateStep(stepIndex, next)
                      }}
                      className="w-1/2 rounded border border-hairline-strong bg-canvas px-2 py-1 font-mono text-sm text-ink focus:border-primary focus:outline-none"
                    />
                  </div>
                ))}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={disabled}
                className="mt-2"
                onClick={() => updateStep(stepIndex, [...rows, { variable: '', value: '' }])}
              >
                + variable
              </Button>
            </div>
          )
        })}
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={disabled}
        className="mt-3"
        onClick={() => onChange({ trace: [...steps, {}] })}
      >
        + paso
      </Button>
    </div>
  )
}
