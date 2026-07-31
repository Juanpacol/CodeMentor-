import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { BarList, type BarListItem } from '../../components/ui/BarList'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { EmptyState } from '../../components/ui/EmptyState'
import { PillTabs } from '../../components/ui/Tabs'
import { apiClient, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type LaggingStudentOut = components['schemas']['LaggingStudentOut']

/** Peor primero: un docente revisando rezagados quiere ver primero a quien
 * más necesita atención, no un orden alfabético/de llegada. */
function toBarListItems(students: LaggingStudentOut[]): BarListItem[] {
  return [...students]
    .sort((a, b) => (a.accuracy ?? -1) - (b.accuracy ?? -1))
    .map((s) => ({
      key: s.student_id,
      label: s.full_name,
      value: s.accuracy,
      hint: (
        <>
          <span>{s.reason}</span>
          {s.days_since_last_activity !== null && (
            <Badge tint="rose">{s.days_since_last_activity}d sin actividad</Badge>
          )}
        </>
      ),
    }))
}

export function AnalyticsTab({ groupId }: { groupId: string }) {
  const [summary, setSummary] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [topicId, setTopicId] = useState<string>('all')

  const generateSummary = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/ai/groups/{group_id}/analytics/summary', {
          params: { path: { group_id: groupId } },
        }),
      ),
    onSuccess: (data) => {
      setUnavailable(false)
      setSummary(data.summary)
    },
    onError: (err) => {
      if (isAiUnavailable(err)) setUnavailable(true)
    },
  })

  const { data: curriculum } = useQuery({
    queryKey: qk.curriculum(groupId),
    queryFn: () =>
      unwrap(apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId } } })),
  })

  const { data: lagging, isLoading } = useQuery({
    queryKey: [...qk.progress.lagging(groupId), topicId],
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/progress/lagging', {
          params: {
            path: { group_id: groupId },
            query: { topic_id: topicId === 'all' ? undefined : topicId },
          },
        }),
      ),
    // "Tiempo real" vía polling (ítem 1) — mismo patrón que ReportsTab, sin
    // WebSockets/SSE nuevos en el stack.
    refetchInterval: 15_000,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button
          variant="secondary"
          disabled={generateSummary.isPending}
          onClick={() => generateSummary.mutate()}
        >
          {generateSummary.isPending ? 'Generando...' : '✨ Generar resumen del grupo'}
        </Button>

        {unavailable && (
          <Callout tone="ai" className="mt-3">
            El asistente de IA no está disponible en este momento.
          </Callout>
        )}
        {summary && (
          <Callout tone="ai" className="mt-3">
            {summary}
          </Callout>
        )}
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink">Estudiantes rezagados</h3>
        {curriculum && curriculum.length > 0 && (
          <PillTabs
            className="mb-3"
            value={topicId}
            onChange={setTopicId}
            tabs={[
              { value: 'all', label: 'Todos los temas' },
              ...curriculum.map((c) => ({ value: c.topic.id, label: c.topic.name })),
            ]}
          />
        )}
        {!isLoading && lagging?.length === 0 && (
          <EmptyState emoji="🎉" title="Nadie está rezagado por ahora" />
        )}
        {lagging && lagging.length > 0 && <BarList items={toBarListItems(lagging)} />}
      </div>
    </div>
  )
}
