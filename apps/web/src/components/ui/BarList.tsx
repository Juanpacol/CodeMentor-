import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface BarListItem {
  key: string
  label: string
  /** 0..max, o `null` para "sin datos" — no renderiza barra, solo "—". */
  value: number | null
  /** Techo de `value` para el ancho de la barra. Por defecto 1 (ratios tipo accuracy). */
  max?: number
  /** Texto a la derecha del label; por defecto un porcentaje de `value/max`. */
  valueLabel?: ReactNode
  /** Contenido extra a la derecha (conteo, Badge, etc.). */
  hint?: ReactNode
}

/** Lista de barras horizontales de una sola serie (siempre `--color-chart-1`
 * — con una sola serie no hace falta leyenda, el título de la sección ya la
 * nombra). Generaliza el `MasteryBar` que antes vivía solo en ProgressPage.
 * Accesibilidad: el label y el valor son texto plano normal (ya legible por
 * un lector de pantalla sin necesitar más); la barra en sí es puramente
 * decorativa (`aria-hidden`) porque el texto ya transmite el valor — no le
 * pongas `role="img"` al contenedor, eso ocultaría el texto real de cada
 * fila detrás de un resumen, que es peor que dejarlo como texto nativo. */
export function BarList({ items, className }: { items: BarListItem[]; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {items.map((item) => {
        const max = item.max ?? 1
        const pct = item.value === null ? null : Math.max(0, Math.min(1, item.value / max)) * 100
        const defaultValueLabel = item.value === null ? '—' : `${Math.round(pct!)}%`

        return (
          <div key={item.key}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-ink">{item.label}</span>
              <span className="flex items-center gap-2 text-ink-secondary">
                <span>{item.valueLabel ?? defaultValueLabel}</span>
                {item.hint}
              </span>
            </div>
            {pct !== null && (
              <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-overlay">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                  className="h-full rounded-full bg-chart-1"
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
