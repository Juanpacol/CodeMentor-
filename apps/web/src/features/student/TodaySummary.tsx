import { useQuery } from '@tanstack/react-query'

import { Card } from '../../components/ui/Card'
import { Stat } from '../../components/ui/Stat'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

/** Ítem 1 (dashboard estudiante): "mi progreso hoy" — lo primero que ve el
 * estudiante, antes que sus grupos o tareas pendientes. */
export function TodaySummary() {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const { data } = useQuery({
    queryKey: qk.progress.today,
    queryFn: () =>
      unwrap(apiClient.GET('/progress/me/today', { params: { query: { tz: timeZone } } })),
  })

  if (!data) return null

  const nothingToShow =
    data.submissions === 0 &&
    data.current_streak === 0 &&
    data.due_today === 0 &&
    data.due_tomorrow === 0 &&
    data.badges_earned_today.length === 0

  if (nothingToShow) return null

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-semibold text-ink">Hoy</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <Stat label="Ejercicios hoy" value={data.submissions} hint={`${data.correct} correctos`} />
        </Card>
        <Card>
          <Stat label="Racha actual" value={data.current_streak > 0 ? `🔥 ${data.current_streak}` : '—'} />
        </Card>
        <Card>
          <Stat label="Vencen hoy" value={data.due_today} />
        </Card>
        <Card>
          <Stat label="Vencen mañana" value={data.due_tomorrow} />
        </Card>
      </div>
      {data.badges_earned_today.length > 0 && (
        <p className="mt-3 text-sm text-ink-secondary">
          🏅 Ganaste {data.badges_earned_today.length === 1 ? 'una insignia' : `${data.badges_earned_today.length} insignias`} hoy:{' '}
          {data.badges_earned_today.map((b) => b.name).join(', ')}
        </p>
      )}
    </section>
  )
}
