import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'

import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
import { useTilt } from '../../hooks/useTilt'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { staggerContainer, staggerItem } from '../../lib/motion'
import type { components } from '../../lib/api/schema'

type BadgeOut = components['schemas']['BadgeOut']

const BADGE_ICON: Record<string, string> = {
  topic_mastery: '🎯',
  language_mastery: '🏆',
  practice_streak: '🔥',
}

function BadgeCard({ badge }: { badge: BadgeOut }) {
  const tilt = useTilt<HTMLDivElement>()
  return (
    <motion.div
      variants={staggerItem}
      ref={tilt.ref}
      onPointerMove={tilt.onPointerMove}
      onPointerLeave={tilt.onPointerLeave}
      style={{ transformStyle: 'preserve-3d', willChange: 'transform' }}
      className="transition-transform duration-150 ease-out"
    >
      <Card className="text-center">
        <span className="text-3xl" aria-hidden="true">
          {BADGE_ICON[badge.criteria] ?? '⭐'}
        </span>
        <h3 className="mt-2 text-sm font-semibold text-ink">{badge.name}</h3>
        <p className="mt-1 text-xs text-ink-secondary">{badge.description}</p>
      </Card>
    </motion.div>
  )
}

function MasteryBar({ label, accuracy, submissions }: { label: string; accuracy: number | null; submissions: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className="text-ink-secondary">
          {accuracy !== null ? `${Math.round(accuracy * 100)}%` : '—'} ({submissions})
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-overlay">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(accuracy ?? 0) * 100}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="h-full rounded-full bg-primary"
        />
      </div>
    </div>
  )
}

export function ProgressPage() {
  const { data: progress, isLoading } = useQuery({
    queryKey: qk.progress.me,
    queryFn: () => unwrap(apiClient.GET('/progress/me')),
  })

  if (isLoading || !progress) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">Mi progreso</h1>

      <Card className="mb-8 flex items-center gap-4">
        <motion.span
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20 }}
          className="text-4xl font-bold text-primary"
        >
          {progress.points}
        </motion.span>
        <span className="text-sm text-ink-secondary">puntos acumulados</span>
      </Card>

      <h2 className="mb-3 text-lg font-semibold text-ink">Insignias</h2>
      {progress.badges.length === 0 ? (
        <EmptyState emoji="🏅" title="Aún no has ganado insignias — ¡sigue practicando!" />
      ) : (
        <motion.div
          variants={staggerContainer}
          initial="initial"
          animate="animate"
          className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        >
          {progress.badges.map((badge) => (
            <BadgeCard key={`${badge.id}-${badge.topic_id ?? badge.language_id ?? 'global'}`} badge={badge} />
          ))}
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <div>
          <h2 className="mb-3 text-lg font-semibold text-ink">Dominio por tema</h2>
          <div className="flex flex-col gap-3">
            {progress.mastery_by_topic.map((m) => (
              <MasteryBar
                key={m.topic_id}
                label={m.topic_name}
                accuracy={m.accuracy}
                submissions={m.submissions}
              />
            ))}
          </div>
        </div>
        <div>
          <h2 className="mb-3 text-lg font-semibold text-ink">Dominio por lenguaje</h2>
          <div className="flex flex-col gap-3">
            {progress.mastery_by_language.map((m) => (
              <MasteryBar
                key={m.language_id}
                label={m.language_name}
                accuracy={m.accuracy}
                submissions={m.submissions}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
