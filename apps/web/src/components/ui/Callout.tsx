import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

type Tone = 'info' | 'ai' | 'warning' | 'error' | 'success'

interface CalloutProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone
  icon?: string
}

const tones: Record<Tone, string> = {
  info: 'bg-tint-sky text-tint-sky-fg',
  ai: 'bg-tint-lavender text-tint-lavender-fg',
  warning: 'bg-tint-yellow text-tint-yellow-fg',
  error: 'bg-tint-rose text-tint-rose-fg',
  success: 'bg-tint-mint text-tint-mint-fg',
}

const defaultIcons: Record<Tone, string> = {
  info: 'ℹ️',
  ai: '✨',
  warning: '⚠️',
  error: '⛔',
  success: '✅',
}

/** Bloque estilo "callout" de Notion — usado en particular para las
 * respuestas del Tutor IA (RF-35: siempre visiblemente etiquetadas como IA)
 * y para la degradación amable cuando un endpoint /ai/* responde 503. */
export function Callout({ tone = 'info', icon, className, children, ...rest }: CalloutProps) {
  return (
    <div
      className={cn('flex gap-3 rounded-card p-4 text-sm', tones[tone], className)}
      {...rest}
    >
      <span aria-hidden="true">{icon ?? defaultIcons[tone]}</span>
      <div className="flex-1">{children}</div>
    </div>
  )
}
