import { cn } from '../../lib/cn'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-btn bg-overlay', className)}
      aria-hidden="true"
    />
  )
}
