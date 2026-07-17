import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { Link, useParams } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
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

export function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()

  const { data: curriculum, isLoading } = useQuery({
    queryKey: qk.curriculum(groupId!),
    queryFn: () => unwrap(apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId! } } })),
    enabled: Boolean(groupId),
  })

  const { data: evaluations } = useQuery({
    queryKey: qk.groupEvaluations(groupId!),
    queryFn: () =>
      unwrap(
        apiClient.GET('/groups/{group_id}/evaluations', { params: { path: { group_id: groupId! } } }),
      ),
    enabled: Boolean(groupId),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Temario</h1>
        <Link
          to={`/app/grupos/${groupId}/practicar`}
          className="rounded-btn bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
        >
          Ir a practicar
        </Link>
      </div>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}

      {!isLoading && curriculum?.length === 0 && (
        <EmptyState emoji="📚" title="Tu docente aún no ha publicado temas para este grupo" />
      )}

      {!isLoading && curriculum && curriculum.length > 0 && (
        <motion.ol
          variants={staggerContainer}
          initial="initial"
          animate="animate"
          className="relative flex flex-col gap-4 border-l-2 border-hairline pl-6"
        >
          {curriculum.map((item) => {
            const locked = item.state === 'locked'
            return (
              <motion.li key={item.topic.id} variants={staggerItem} className="relative">
                <span
                  className={`absolute -left-[27px] top-1.5 size-3 rounded-full ${
                    locked ? 'bg-ink-muted' : 'bg-primary'
                  }`}
                />
                <div className={locked ? 'opacity-50' : ''}>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-ink">{item.topic.name}</h3>
                    <Badge tint={STATE_TINT[item.state]}>{STATE_LABEL[item.state]}</Badge>
                  </div>
                  {item.enabled_at && (
                    <p className="mt-0.5 text-xs text-ink-secondary">
                      Habilitado el {new Date(item.enabled_at).toLocaleDateString('es-CO')}
                    </p>
                  )}
                </div>
              </motion.li>
            )
          })}
        </motion.ol>
      )}

      {evaluations && evaluations.length > 0 && (
        <div className="mt-10">
          <h2 className="mb-3 text-lg font-semibold text-ink">Evaluaciones</h2>
          <div className="flex flex-col gap-2">
            {evaluations.map((evaluation) => (
              <Link key={evaluation.id} to={`/app/evaluaciones/${evaluation.id}`}>
                <Card interactive className="flex items-center justify-between p-4">
                  <span className="font-medium text-ink">{evaluation.title}</span>
                  {evaluation.duration_minutes && (
                    <Badge tint="sky">{evaluation.duration_minutes} min</Badge>
                  )}
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
