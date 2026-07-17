import type { ReactNode } from 'react'

interface EmptyStateProps {
  emoji?: string
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ emoji = '🗂️', title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-hairline-strong py-16 text-center">
      <span className="text-4xl" aria-hidden="true">
        {emoji}
      </span>
      <p className="text-base font-medium text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-secondary">{description}</p>}
      {action}
    </div>
  )
}
