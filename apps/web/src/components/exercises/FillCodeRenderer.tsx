import type { ExerciseRendererProps } from './types'

interface FillCodeAnswer {
  values: string[]
}

const BLANK_MARKER = '___'

export function FillCodeRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<FillCodeAnswer>) {
  const statement = String(content.statement ?? '')
  const template = String(content.code_template ?? '')
  const parts = template.split(BLANK_MARKER)
  const values = value?.values ?? []

  function setBlank(index: number, next: string) {
    const updated = [...values]
    updated[index] = next
    onChange({ values: updated })
  }

  return (
    <div>
      <p className="mb-4 text-base text-ink">{statement}</p>
      <pre className="whitespace-pre-wrap rounded-card border border-hairline-strong bg-canvas p-4 font-mono text-sm text-ink">
        {parts.map((part, i) => (
          <span key={i}>
            {part}
            {i < parts.length - 1 && (
              <input
                aria-label={`Espacio en blanco ${i + 1}`}
                disabled={disabled}
                value={values[i] ?? ''}
                onChange={(e) => setBlank(i, e.target.value)}
                className="mx-1 inline-block w-24 rounded border border-hairline-strong bg-raised px-1.5 py-0.5 font-mono text-sm text-primary focus:border-primary focus:outline-none disabled:opacity-60"
              />
            )}
          </span>
        ))}
      </pre>
    </div>
  )
}
