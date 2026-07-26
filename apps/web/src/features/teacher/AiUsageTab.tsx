import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { BarList, type BarListItem } from '../../components/ui/BarList'
import { Callout } from '../../components/ui/Callout'
import { Card } from '../../components/ui/Card'
import { ChartCard } from '../../components/ui/ChartCard'
import { EmptyState } from '../../components/ui/EmptyState'
import { PillTabs } from '../../components/ui/Tabs'
import { Spinner } from '../../components/ui/Spinner'
import { Stat } from '../../components/ui/Stat'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type AiUsageRowOut = components['schemas']['AiUsageRowOut']

const GROUP_BY_OPTIONS = [
  { value: 'task', label: 'Por tarea' },
  { value: 'model', label: 'Por modelo' },
  { value: 'day', label: 'Por día' },
] as const

function toBarListItems(rows: AiUsageRowOut[], maxCost: number): BarListItem[] {
  return rows.map((row) => ({
    key: row.key,
    label: row.key,
    value: row.cost_usd,
    max: maxCost || 1,
    valueLabel: `US$ ${row.cost_usd.toFixed(4)}`,
    hint: <span>{row.interactions} interacciones</span>,
  }))
}

export function AiUsageTab() {
  const [groupBy, setGroupBy] = useState<'task' | 'model' | 'day'>('task')

  const { data, isLoading } = useQuery({
    queryKey: qk.observability.aiUsage(groupBy),
    queryFn: () =>
      unwrap(apiClient.GET('/observability/ai/usage', { params: { query: { group_by: groupBy } } })),
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="size-6" />
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        emoji="🤖"
        title="Aún no hay uso de IA registrado"
        description="Cuando el grupo empiece a usar el tutor u otros agentes, aquí verás el costo estimado."
      />
    )
  }

  const totalInteractions = data.items.reduce((sum, r) => sum + r.interactions, 0)
  const totalTokens = data.items.reduce((sum, r) => sum + r.prompt_tokens + r.completion_tokens, 0)
  const totalCacheHits = data.items.reduce((sum, r) => sum + r.cache_hits, 0)
  const cacheRate = totalInteractions === 0 ? 0 : (totalCacheHits / totalInteractions) * 100
  const maxCost = Math.max(0, ...data.items.map((r) => r.cost_usd))

  return (
    <div className="flex flex-col gap-6">
      {data.budget.level !== 'ok' && (
        <Callout tone={data.budget.level === 'critical' ? 'error' : 'warning'}>
          Costo estimado del mes: US$ {data.budget.month_to_date_usd.toFixed(2)} de US${' '}
          {data.budget.monthly_limit_usd.toFixed(2)} ({data.budget.pct_used.toFixed(0)}%). Es un
          estimado de atribución relativa entre agentes, no una factura real.
        </Callout>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <Stat label="Interacciones" value={totalInteractions} />
        </Card>
        <Card>
          <Stat label="Tokens" value={totalTokens.toLocaleString('es-CO')} />
        </Card>
        <Card>
          <Stat
            label="Costo estimado (mes)"
            value={`US$ ${data.budget.month_to_date_usd.toFixed(2)}`}
          />
        </Card>
        <Card>
          <Stat label="% desde caché" value={`${cacheRate.toFixed(0)}%`} />
        </Card>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">Costo estimado</h3>
          <PillTabs
            value={groupBy}
            onChange={(v) => setGroupBy(v as 'task' | 'model' | 'day')}
            tabs={[...GROUP_BY_OPTIONS]}
          />
        </div>
        <ChartCard
          title="Distribución de costo"
          tableHeaders={['Clave', 'Interacciones', 'Tokens', 'Costo (US$)', 'Caché', 'Bloqueadas']}
          tableRows={data.items.map((row) => [
            row.key,
            row.interactions,
            row.prompt_tokens + row.completion_tokens,
            row.cost_usd.toFixed(4),
            row.cache_hits,
            row.blocked,
          ])}
        >
          <BarList items={toBarListItems(data.items, maxCost)} />
        </ChartCard>
      </div>
    </div>
  )
}
