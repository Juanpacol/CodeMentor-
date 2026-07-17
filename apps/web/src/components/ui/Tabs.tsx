import { cn } from '../../lib/cn'

interface Tab {
  value: string
  label: string
}

interface TabsProps {
  tabs: Tab[]
  value: string
  onChange: (value: string) => void
  className?: string
}

/** Tabs segmentadas estilo Notion: subrayado de 2px, sin fondo pill. */
export function Tabs({ tabs, value, onChange, className }: TabsProps) {
  return (
    <div role="tablist" className={cn('flex gap-6 border-b border-hairline', className)}>
      {tabs.map((tab) => {
        const active = tab.value === value
        return (
          <button
            key={tab.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cn(
              'relative -mb-px border-b-2 px-1 pb-3 text-sm font-medium transition-colors duration-150',
              active
                ? 'border-ink text-ink'
                : 'border-transparent text-ink-secondary hover:text-ink',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

interface PillTabsProps {
  tabs: Tab[]
  value: string
  onChange: (value: string) => void
  className?: string
}

/** Pill-tabs para filtros (p. ej. filtro por lenguaje en práctica, RF-27). */
export function PillTabs({ tabs, value, onChange, className }: PillTabsProps) {
  return (
    <div role="tablist" className={cn('flex flex-wrap gap-2', className)}>
      {tabs.map((tab) => {
        const active = tab.value === value
        return (
          <button
            key={tab.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cn(
              'rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors duration-150',
              active
                ? 'border-ink bg-ink text-canvas'
                : 'border-hairline text-ink-secondary hover:border-hairline-strong hover:text-ink',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
