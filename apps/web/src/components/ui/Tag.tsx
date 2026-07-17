import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'
import type { TintColor } from './Badge'

interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  tint?: TintColor
}

const tints: Record<TintColor, string> = {
  peach: 'bg-tint-peach text-tint-peach-fg',
  rose: 'bg-tint-rose text-tint-rose-fg',
  mint: 'bg-tint-mint text-tint-mint-fg',
  lavender: 'bg-tint-lavender text-tint-lavender-fg',
  sky: 'bg-tint-sky text-tint-sky-fg',
  yellow: 'bg-tint-yellow text-tint-yellow-fg',
  purple: 'bg-tint-lavender text-tint-lavender-fg',
  neutral: 'bg-overlay text-ink-secondary',
}

/** Igual que Badge pero con esquinas casi rectas (4px) — usado para
 * etiquetas de metadatos (tipo de ejercicio, nivel) en vez de estados. */
export function Tag({ tint = 'neutral', className, children, ...rest }: TagProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold',
        tints[tint],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  )
}
