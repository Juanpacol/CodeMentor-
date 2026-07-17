import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

export type TintColor = 'peach' | 'rose' | 'mint' | 'lavender' | 'sky' | 'yellow' | 'purple' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tint?: TintColor
}

const tints: Record<TintColor, string> = {
  peach: 'bg-tint-peach text-tint-peach-fg',
  rose: 'bg-tint-rose text-tint-rose-fg',
  mint: 'bg-tint-mint text-tint-mint-fg',
  lavender: 'bg-tint-lavender text-tint-lavender-fg',
  sky: 'bg-tint-sky text-tint-sky-fg',
  yellow: 'bg-tint-yellow text-tint-yellow-fg',
  purple: 'bg-primary text-white',
  neutral: 'bg-overlay text-ink-secondary',
}

export function Badge({ tint = 'neutral', className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold',
        tints[tint],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  )
}
