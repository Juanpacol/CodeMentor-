import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Card } from '../../components/ui/Card'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type AgentName = components['schemas']['AgentName']

const AGENT_INFO: Record<AgentName, { label: string; description: string }> = {
  progressive_hint: {
    label: 'Tutor',
    description: 'Pistas progresivas en la práctica libre — nunca revela la solución completa.',
  },
  exercise_generation: {
    label: 'Generador de ejercicios',
    description: 'Propone ejercicios nuevos como borrador, a la espera de tu aprobación.',
  },
  grading_suggestion: {
    label: 'Asistente de calificación',
    description: 'Sugiere una nota y justificación para respuestas argumentadas — tú confirmas.',
  },
  summarize_group: {
    label: 'Analítica de aprendizaje',
    description: 'Resume el avance del grupo en lenguaje natural bajo pedido.',
  },
  code_integrity: {
    label: 'Integridad de código',
    description: 'Alerta advisory sobre posibles indicios de copia — nunca aplica una sanción.',
  },
}

const AGENT_ORDER: AgentName[] = [
  'progressive_hint',
  'exercise_generation',
  'grading_suggestion',
  'summarize_group',
  'code_integrity',
]

export function AgentsTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()

  const { data: configs } = useQuery({
    queryKey: qk.ai.agentConfig(groupId),
    queryFn: () =>
      unwrap(apiClient.GET('/ai/groups/{group_id}/agents', { params: { path: { group_id: groupId } } })),
  })

  const toggle = useMutation({
    mutationFn: ({ agentName, enabled }: { agentName: AgentName; enabled: boolean }) =>
      unwrap(
        apiClient.PUT('/ai/groups/{group_id}/agents/{agent_name}', {
          params: { path: { group_id: groupId, agent_name: agentName } },
          body: { enabled },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: qk.ai.agentConfig(groupId) }),
  })

  const enabledByAgent = new Map(configs?.map((c) => [c.agent_name, c.enabled]) ?? [])

  return (
    <div className="flex flex-col gap-3">
      {AGENT_ORDER.map((agentName) => {
        // Ausencia de fila = habilitado por defecto (RF-30).
        const enabled = enabledByAgent.get(agentName) ?? true
        const info = AGENT_INFO[agentName]
        return (
          <Card key={agentName} className="flex items-center justify-between">
            <div>
              <h3 className="font-medium text-ink">{info.label}</h3>
              <p className="mt-1 text-sm text-ink-secondary">{info.description}</p>
            </div>
            <label className="relative inline-flex cursor-pointer items-center">
              <input
                type="checkbox"
                aria-label={`${info.label}: ${enabled ? 'habilitado' : 'deshabilitado'}`}
                checked={enabled}
                onChange={(e) => toggle.mutate({ agentName, enabled: e.target.checked })}
                className="peer sr-only"
              />
              <div className="h-6 w-11 rounded-full bg-overlay transition-colors peer-checked:bg-primary" />
              <div className="absolute left-1 size-4 rounded-full bg-white transition-transform peer-checked:translate-x-5" />
            </label>
          </Card>
        )
      })}
    </div>
  )
}
