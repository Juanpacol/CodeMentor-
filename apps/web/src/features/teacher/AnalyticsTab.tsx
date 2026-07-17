import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { EmptyState } from '../../components/ui/EmptyState'
import { apiClient, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

export function AnalyticsTab({ groupId }: { groupId: string }) {
  const [summary, setSummary] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)

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

  const { data: lagging, isLoading } = useQuery({
    queryKey: qk.progress.lagging(groupId),
    queryFn: () =>
      unwrap(apiClient.GET('/groups/{group_id}/progress/lagging', { params: { path: { group_id: groupId } } })),
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
        {!isLoading && lagging?.length === 0 && (
          <EmptyState emoji="🎉" title="Nadie está rezagado por ahora" />
        )}
        <div className="flex flex-col gap-2">
          {lagging?.map((student) => (
            <div
              key={student.student_id}
              className="flex items-center justify-between rounded-card border border-hairline bg-raised px-4 py-3"
            >
              <span className="text-sm text-ink">{student.full_name}</span>
              <span className="text-xs text-ink-secondary">{student.reason}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
