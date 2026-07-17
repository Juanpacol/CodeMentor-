import { cn } from '../../lib/cn'
import type { ExerciseRendererProps } from './types'

interface TrueFalseAnswer {
  value: boolean
}

export function TrueFalseRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<TrueFalseAnswer>) {
  const statement = String(content.statement ?? '')

  return (
    <div>
      <p className="mb-5 text-base text-ink">{statement}</p>
      <div className="grid grid-cols-2 gap-3">
        {[true, false].map((option) => (
          <button
            key={String(option)}
            type="button"
            disabled={disabled}
            onClick={() => onChange({ value: option })}
            className={cn(
              'rounded-card border px-6 py-4 text-base font-medium transition-colors duration-150',
              value?.value === option
                ? 'border-primary bg-primary/10 text-ink'
                : 'border-hairline-strong text-ink-secondary hover:border-hairline-strong hover:bg-hover',
              disabled && 'opacity-60',
            )}
          >
            {option ? 'Verdadero' : 'Falso'}
          </button>
        ))}
      </div>
    </div>
  )
}
