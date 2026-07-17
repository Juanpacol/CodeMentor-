import { cn } from '../../lib/cn'

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Cargando"
      className={cn(
        'inline-block size-4 animate-spin rounded-full border-2 border-hairline-strong border-t-primary',
        className,
      )}
    />
  )
}
