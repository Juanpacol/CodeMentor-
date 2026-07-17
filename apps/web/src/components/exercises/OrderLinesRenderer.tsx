import { Reorder } from 'motion/react'

import { cn } from '../../lib/cn'
import type { ExerciseRendererProps } from './types'

interface OrderLinesAnswer {
  order: number[]
}

export function OrderLinesRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<OrderLinesAnswer>) {
  const statement = String(content.statement ?? '')
  const lines = Array.isArray(content.lines) ? (content.lines as string[]) : []
  const order = value?.order ?? lines.map((_, i) => i)

  return (
    <div>
      <p className="mb-4 text-base text-ink">{statement}</p>
      <Reorder.Group
        axis="y"
        values={order}
        onReorder={(next) => onChange({ order: next })}
        className="flex flex-col gap-2"
      >
        {order.map((originalIndex) => (
          <Reorder.Item
            key={originalIndex}
            value={originalIndex}
            drag={!disabled}
            className={cn(
              'cursor-grab rounded-btn border border-hairline-strong bg-raised px-4 py-2.5 font-mono text-sm text-ink active:cursor-grabbing',
              disabled && 'cursor-default opacity-70',
            )}
          >
            {lines[originalIndex]}
          </Reorder.Item>
        ))}
      </Reorder.Group>
      <p className="mt-2 text-xs text-ink-muted">Arrastra las líneas para ordenarlas.</p>
    </div>
  )
}
