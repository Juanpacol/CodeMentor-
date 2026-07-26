import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

interface StatProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  className?: string
}

/** Número héroe + etiqueta, no un gráfico — para KPIs sueltos (puntos,
 * conteos derivados) donde una barra/columna no aportaría nada que el
 * número ya no diga. */
export function Stat({ label, value, hint, className }: StatProps) {
  const labelId = `stat-label-${label.replace(/\s+/g, '-').toLowerCase()}`
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <span id={labelId} className="text-sm text-ink-secondary">
        {label}
      </span>
      <span aria-labelledby={labelId} className="text-3xl font-bold text-ink">
        {value}
      </span>
      {hint && <span className="text-xs text-ink-muted">{hint}</span>}
    </div>
  )
}
