import { cn } from '../../lib/cn'
import type { ExerciseRendererProps } from './types'

interface MultipleChoiceAnswer {
  selected_index: number
}

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

export function MultipleChoiceRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<MultipleChoiceAnswer>) {
  const statement = String(content.statement ?? '')
  const options = Array.isArray(content.options) ? (content.options as string[]) : []

  return (
    <div>
      <p className="mb-5 text-base text-ink">{statement}</p>
      <div className="flex flex-col gap-2">
        {options.map((option, index) => (
          <button
            key={index}
            type="button"
            disabled={disabled}
            onClick={() => onChange({ selected_index: index })}
            className={cn(
              'flex items-center gap-3 rounded-card border px-4 py-3 text-left text-sm transition-colors duration-150',
              value?.selected_index === index
                ? 'border-primary bg-primary/10 text-ink'
                : 'border-hairline-strong text-ink-secondary hover:bg-hover',
              disabled && 'opacity-60',
            )}
          >
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-overlay text-xs font-semibold text-ink-secondary">
              {LETTERS[index] ?? index + 1}
            </span>
            {option}
          </button>
        ))}
      </div>
    </div>
  )
}
