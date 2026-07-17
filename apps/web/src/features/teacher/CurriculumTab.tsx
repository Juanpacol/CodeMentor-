import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { staggerContainer, staggerItem } from '../../lib/motion'

const STATE_LABEL: Record<string, string> = {
  locked: 'Bloqueado',
  enabled: 'Habilitado',
  evaluated: 'Evaluado',
}

const STATE_TINT: Record<string, 'neutral' | 'mint' | 'sky'> = {
  locked: 'neutral',
  enabled: 'mint',
  evaluated: 'sky',
}

export function CurriculumTab({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  const [schedulingTopicId, setSchedulingTopicId] = useState<string | null>(null)
  const [scheduleDate, setScheduleDate] = useState('')

  const { data: curriculum, isLoading } = useQuery({
    queryKey: qk.curriculum(groupId),
    queryFn: () =>
      unwrap(apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId } } })),
  })

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: qk.curriculum(groupId) })
  }

  const enable = useMutation({
    mutationFn: (topicId: string) =>
      unwrap(
        apiClient.POST('/groups/{group_id}/topics/{topic_id}/enable', {
          params: { path: { group_id: groupId, topic_id: topicId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Tema habilitado', 'success')
      invalidate()
    },
  })

  const disable = useMutation({
    mutationFn: (topicId: string) =>
      unwrap(
        apiClient.POST('/groups/{group_id}/topics/{topic_id}/disable', {
          params: { path: { group_id: groupId, topic_id: topicId } },
        }),
      ),
    onSuccess: () => {
      pushToast('Tema deshabilitado', 'success')
      invalidate()
    },
  })

  const schedule = useMutation({
    mutationFn: ({ topicId, enableAt }: { topicId: string; enableAt: string }) =>
      unwrap(
        apiClient.POST('/groups/{group_id}/topics/{topic_id}/schedule', {
          params: { path: { group_id: groupId, topic_id: topicId } },
          body: { enable_at: new Date(enableAt).toISOString() },
        }),
      ),
    onSuccess: () => {
      pushToast('Habilitación programada', 'success')
      setSchedulingTopicId(null)
      setScheduleDate('')
      invalidate()
    },
  })

  if (isLoading || !curriculum) return null

  return (
    <motion.ol
      variants={staggerContainer}
      initial="initial"
      animate="animate"
      className="relative flex flex-col gap-4 border-l-2 border-hairline pl-6"
    >
      {curriculum.map((item) => (
        <motion.li key={item.topic.id} variants={staggerItem} className="relative">
          <span
            className={`absolute -left-[27px] top-1.5 size-3 rounded-full ${
              item.state === 'locked' ? 'bg-ink-muted' : 'bg-primary'
            }`}
          />
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{item.topic.name}</h3>
            <Badge tint={STATE_TINT[item.state]}>{STATE_LABEL[item.state]}</Badge>
            {item.scheduled_enable_at && (
              <Badge tint="yellow">
                Programado: {new Date(item.scheduled_enable_at).toLocaleDateString('es-CO')}
              </Badge>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            {item.state === 'locked' ? (
              <Button size="sm" variant="secondary" onClick={() => enable.mutate(item.topic.id)}>
                Habilitar
              </Button>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => disable.mutate(item.topic.id)}>
                Deshabilitar
              </Button>
            )}

            {schedulingTopicId === item.topic.id ? (
              <>
                <Input
                  type="datetime-local"
                  value={scheduleDate}
                  onChange={(e) => setScheduleDate(e.target.value)}
                  className="h-9 w-auto"
                />
                <Button
                  size="sm"
                  disabled={!scheduleDate || schedule.isPending}
                  onClick={() => schedule.mutate({ topicId: item.topic.id, enableAt: scheduleDate })}
                >
                  Confirmar
                </Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => setSchedulingTopicId(item.topic.id)}>
                Programar fecha
              </Button>
            )}
          </div>
        </motion.li>
      ))}
    </motion.ol>
  )
}
