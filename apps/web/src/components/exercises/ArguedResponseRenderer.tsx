import { Callout } from '../ui/Callout'
import { Textarea } from '../ui/Input'
import type { ExerciseRendererProps } from './types'

interface ArguedResponseAnswer {
  text: string
}

export function ArguedResponseRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<ArguedResponseAnswer>) {
  const prompt = String(content.prompt ?? '')
  const text = value?.text ?? ''

  return (
    <div>
      <p className="mb-4 text-base text-ink">{prompt}</p>
      <Textarea
        disabled={disabled}
        value={text}
        onChange={(e) => onChange({ text: e.target.value })}
        rows={6}
        placeholder="Escribe tu respuesta..."
      />
      <p className="mt-1.5 text-right text-xs text-ink-muted">{text.length} caracteres</p>
      <Callout tone="info" className="mt-3">
        Esta respuesta la revisa y califica tu docente — no recibe una calificación automática.
      </Callout>
    </div>
  )
}
