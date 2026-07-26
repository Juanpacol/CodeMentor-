import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'

import { BarList, type BarListItem } from '../../components/ui/BarList'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
import { Stat } from '../../components/ui/Stat'
import { useTilt } from '../../hooks/useTilt'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { staggerContainer, staggerItem } from '../../lib/motion'
import type { components } from '../../lib/api/schema'

type BadgeOut = components['schemas']['BadgeOut']
type MasteryOut = { accuracy: number | null; submissions: number }

/** Suma de envíos y precisión ponderada por envíos, calculadas en el
 * cliente a partir del mismo payload que ya trae `mastery_by_topic` — cero
 * endpoints nuevos. `accuracy: null` significa "sin envíos todavía" y no
 * aporta al ponderado. */
function deriveStats(masteries: MasteryOut[]): { totalSubmissions: number; weightedAccuracy: number | null } {
  const totalSubmissions = masteries.reduce((sum, m) => sum + m.submissions, 0)
  const withAccuracy = masteries.filter((m) => m.accuracy !== null)
  const weightedSubmissions = withAccuracy.reduce((sum, m) => sum + m.submissions, 0)
  const weightedAccuracy =
    weightedSubmissions === 0
      ? null
      : withAccuracy.reduce((sum, m) => sum + m.accuracy! * m.submissions, 0) / weightedSubmissions
  return { totalSubmissions, weightedAccuracy }
}

function toBarListItems(
  masteries: { accuracy: number | null; submissions: number; name: string; id: string }[],
): BarListItem[] {
  return [...masteries]
    .sort((a, b) => (b.accuracy ?? -1) - (a.accuracy ?? -1))
    .map((m) => ({
      key: m.id,
      label: m.name,
      value: m.accuracy,
      hint: <span>({m.submissions})</span>,
    }))
}

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

  const { totalSubmissions, weightedAccuracy } = deriveStats(progress.mastery_by_topic)

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">Mi progreso</h1>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <Stat
            label="Puntos acumulados"
            value={
              <motion.span
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 260, damping: 20 }}
                className="inline-block"
              >
                {progress.points}
              </motion.span>
            }
          />
        </Card>
        <Card>
          <Stat label="Ejercicios resueltos" value={totalSubmissions} />
        </Card>
        <Card>
          <Stat
            label="Precisión global"
            value={weightedAccuracy !== null ? `${Math.round(weightedAccuracy * 100)}%` : '—'}
          />
        </Card>
      </div>

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
          <BarList
            items={toBarListItems(
              progress.mastery_by_topic.map((m) => ({
                id: m.topic_id,
                name: m.topic_name,
                accuracy: m.accuracy,
                submissions: m.submissions,
              })),
            )}
          />
        </div>
        <div>
          <h2 className="mb-3 text-lg font-semibold text-ink">Dominio por lenguaje</h2>
          <BarList
            items={toBarListItems(
              progress.mastery_by_language.map((m) => ({
                id: m.language_id,
                name: m.language_name,
                accuracy: m.accuracy,
                submissions: m.submissions,
              })),
            )}
          />
        </div>
      </div>
    </div>
  )
}
