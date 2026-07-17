import type { ReactNode } from 'react'

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-hairline-strong bg-overlay px-1.5 py-0.5 font-mono text-xs text-ink-secondary">
      {children}
    </kbd>
  )
}
